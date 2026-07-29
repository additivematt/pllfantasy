import http.server
import socketserver
import json
import os

PORT = 8000
# The directory where server.py lives (matchup_tagger)
TAGGER_DIR = os.path.dirname(os.path.abspath(__file__))
# The parent directory (scripts)
SCRIPTS_DIR = os.path.dirname(TAGGER_DIR)

import sys
if SCRIPTS_DIR not in sys.path:
    sys.path.append(SCRIPTS_DIR)
import extract_trial_data
import importlib
opt_lineups = importlib.import_module("06_optimize_lineups")
load_historical_data = opt_lineups.load_historical_data
calculate_tier_averages = opt_lineups.calculate_tier_averages

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Default directory is TAGGER_DIR so http://localhost:8000/ serves the tagger
        super().__init__(*args, directory=TAGGER_DIR, **kwargs)

    def do_GET(self):
        clean_path = self.path.split('?')[0]

        # 0a. Serve dynamic predictions endpoints (within pllpredicta scope or fallback)
        if clean_path in ['/predictions/available', '/pllpredicta/predictions/available', '/predicta/predictions/available']:
            # Check for statically compiled available file first
            static_path = os.path.join(SCRIPTS_DIR, 'predicta', 'predictions', 'available')
            if os.path.exists(static_path):
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                with open(static_path, 'rb') as f:
                    self.wfile.write(f.read())
                return

            import glob
            import re
            files = glob.glob(os.path.join(SCRIPTS_DIR, "week*_predictions.csv"))
            files += glob.glob(os.path.join(SCRIPTS_DIR, "predicta", "predictions", "week*_predictions.csv"))
            available = []
            seen = set()
            for filepath in files:
                filename = os.path.basename(filepath)
                match = re.match(r"week(\d+)_(\d+)_predictions\.csv", filename)
                if match:
                    week = int(match.group(1))
                    year = int(match.group(2))
                    period = (year, week)
                    if period not in seen:
                        seen.add(period)
                        available.append({"year": year, "week": week})
            
            # Sort chronologically (year desc, week desc)
            available.sort(key=lambda x: (x['year'], x['week']), reverse=True)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(available).encode('utf-8'))
            return

        if clean_path.startswith('/predictions/') or clean_path.startswith('/pllpredicta/predictions/') or clean_path.startswith('/predicta/predictions/'):
            # Format: /predictions/2026/2 or /pllpredicta/predictions/2026/2 or /predicta/predictions/2026/2
            parts = [p for p in clean_path.split('/') if p]
            if parts and parts[0] in ['pllpredicta', 'predicta']:
                parts = parts[1:]
            if len(parts) >= 3:
                year, week = parts[1], parts[2]
                
                # Check for statically compiled predictions first
                static_path = os.path.join(SCRIPTS_DIR, 'predicta', 'predictions', year, week)
                if os.path.exists(static_path):
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    with open(static_path, 'rb') as f:
                        self.wfile.write(f.read())
                    return

                filepath = os.path.join(SCRIPTS_DIR, f"week{week}_{year}_predictions.csv")
                reg_filepath = os.path.join(SCRIPTS_DIR, f"week{week}_{year}_predictions_regression.csv")
                sim_filepath = os.path.join(SCRIPTS_DIR, f"week{week}_{year}_simulations.csv")
                if os.path.exists(filepath):
                    import pandas as pd
                    import re as _re
                    df = pd.read_csv(filepath)
                    if os.path.exists(reg_filepath):
                        df_reg = pd.read_csv(reg_filepath)
                        df = df.merge(
                            df_reg[['firstName', 'lastName', 'game_id', 'PredictedPoints']],
                            on=['firstName', 'lastName', 'game_id'],
                            how='left',
                            suffixes=('_x', '_reg')
                        ).fillna(0.0)
                        # Use regression PredictedPoints as the canonical PredictedPoints
                        if 'PredictedPoints_reg' in df.columns:
                            df['PredictedPoints'] = df['PredictedPoints_reg']
                    else:
                        df['PredictedPoints'] = df.get('PredictedPoints', 0.0)
                    # Compute MC EV and Std Dev from simulation file if available
                    if os.path.exists(sim_filepath):
                        df_sims = pd.read_csv(sim_filepath)
                        mc_stats_map = {}
                        for col in df_sims.columns:
                            m = _re.match(r'^(.+?)_(\d{4}-ev-\d+)$', col)
                            if m:
                                name_part, game_id_s = m.group(1), m.group(2)
                                parts = name_part.split('_')
                                first_s = parts[0]
                                last_s = '_'.join(parts[1:]) if len(parts) > 1 else ''
                                mc_stats_map[(first_s, last_s, game_id_s)] = {
                                    'ev':  round(float(df_sims[col].mean()), 2),
                                    'std': round(float(df_sims[col].std()), 2),
                                    'p90': round(float(df_sims[col].quantile(0.9)), 2),
                                }
                        def _find_mc_stats(row):
                            key = (row['firstName'], row['lastName'], row['game_id'])
                            if key in mc_stats_map:
                                return mc_stats_map[key]
                            f_c = _re.sub(r'[^a-zA-Z]', '', row['firstName'])
                            l_c = _re.sub(r'[^a-zA-Z]', '', row['lastName'])
                            for (f2, l2, g2), stats in mc_stats_map.items():
                                if g2 == row['game_id'] and _re.sub(r'[^a-zA-Z]', '', f2) == f_c and _re.sub(r'[^a-zA-Z]', '', l2) == l_c:
                                    return stats
                            return None
                        df['mc_ev']  = df.apply(lambda r: (_find_mc_stats(r) or {}).get('ev'),  axis=1)
                        df['mc_std'] = df.apply(lambda r: (_find_mc_stats(r) or {}).get('std'), axis=1)
                        df['mc_p90'] = df.apply(lambda r: (_find_mc_stats(r) or {}).get('p90'), axis=1)

                    # Add actual points from f2p season JSON or combined player stats if available
                    actuals_lookup = {}
                    season_file = os.path.join(SCRIPTS_DIR, f"f2p_{year}_season.json")
                    if os.path.exists(season_file):
                        with open(season_file, "r") as f_f2p:
                            f2p_data = json.load(f_f2p)
                        week_data = [p for p in f2p_data if p.get("week") == int(week)]
                        has_actuals = any(p.get("f2p", {}).get("totalPoints", 0.0) > 0.0 or p.get("totalPoints", 0.0) > 0.0 for p in week_data)
                        if has_actuals:
                            for p in week_data:
                                fname = p.get("firstName")
                                lname = p.get("lastName")
                                g_id = p.get("eventId", "UNK").replace("_game_", "-ev-")
                                pts = float(p.get("totalPoints", 0.0))
                                actuals_lookup[(fname, lname, g_id)] = pts
                    else:
                        stats_file = os.path.join(SCRIPTS_DIR, f"combined_player_stats_{year}.json")
                        if os.path.exists(stats_file):
                            with open(stats_file, "r", encoding="utf-8") as f_stats:
                                stats_data = json.load(f_stats)
                            for p in stats_data:
                                if p.get("week") == int(week):
                                    fname = p.get("identity", {}).get("firstName")
                                    lname = p.get("identity", {}).get("lastName")
                                    g_id = p.get("event", {}).get("eventId", "UNK").replace("_game_", "-ev-")
                                    f2p = p.get("f2p", {})
                                    pts = f2p.get("totalPoints")
                                    if pts is not None:
                                        actuals_lookup[(fname, lname, g_id)] = float(pts)
                    
                    def _find_actual_points(row):
                        key = (row['firstName'], row['lastName'], row['game_id'])
                        if key in actuals_lookup:
                            return actuals_lookup[key]
                        f_c = _re.sub(r'[^a-zA-Z]', '', row['firstName'])
                        l_c = _re.sub(r'[^a-zA-Z]', '', row['lastName'])
                        for (f2, l2, g2), pts in actuals_lookup.items():
                            if g2 == row['game_id'] and _re.sub(r'[^a-zA-Z]', '', f2) == f_c and _re.sub(r'[^a-zA-Z]', '', l2) == l_c:
                                return pts
                        return None
                    
                    df['actualPoints'] = df.apply(_find_actual_points, axis=1)

                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(df.to_json(orient='records').encode('utf-8'))
                    return
                else:
                    self.send_error(404, "Prediction file not found")
                    return
            else:
                self.send_error(400, "Invalid predictions path format")
                return

        # 0c. Serve dynamic advisory endpoints for optimized lineups
        if clean_path.startswith('/advisory/') or clean_path.startswith('/pllpredicta/advisory/') or clean_path.startswith('/predicta/advisory/'):
            # Format: /advisory/2026/2 or /pllpredicta/advisory/2026/2 or /predicta/advisory/2026/2
            parts = [p for p in clean_path.split('/') if p]
            if parts and parts[0] in ['pllpredicta', 'predicta']:
                parts = parts[1:]
            if len(parts) >= 3:
                year_str, week_str = parts[1], parts[2]
                
                # Check for statically compiled advisory first
                static_path = os.path.join(SCRIPTS_DIR, 'predicta', 'advisory', year_str, week_str)
                if os.path.exists(static_path):
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    with open(static_path, 'rb') as f:
                        self.wfile.write(f.read())
                    return

                year, week = int(year_str), int(week_str)
                class_file = os.path.join(SCRIPTS_DIR, f"week{week}_{year}_predictions.csv")
                reg_file = os.path.join(SCRIPTS_DIR, f"week{week}_{year}_predictions_regression.csv")
                if os.path.exists(class_file) and os.path.exists(reg_file):
                    import pandas as pd
                    df_class = pd.read_csv(class_file)
                    df_reg = pd.read_csv(reg_file)
                    
                    df_hist = load_historical_data(year, week, SCRIPTS_DIR)
                    tier_avgs = calculate_tier_averages(df_hist)
                    
                    def get_ev(row):
                        pos = row['positionGroup']
                        p_boom = row['BoomProbability'] / 100.0
                        p_nonboom = 1.0 - p_boom
                        avgs = tier_avgs.get(pos, {"Boom": 25.0, "NonBoom": 8.0})
                        return p_boom * avgs["Boom"] + p_nonboom * avgs["NonBoom"]
                    df_class['EV'] = df_class.apply(get_ev, axis=1)
                    
                    merged_cols = ['firstName', 'lastName', 'team', 'opponent', 'game_id', 'positionGroup', 'subPosition', 'salary', 'BoomProbability', 'EV']
                    df_merged = df_class[merged_cols].merge(
                        df_reg[['firstName', 'lastName', 'game_id', 'PredictedPoints']],
                        on=['firstName', 'lastName', 'game_id'],
                        how='inner'
                    )
                    
                    pool_ev = df_merged.sort_values('EV', ascending=False).drop_duplicates(subset=['firstName', 'lastName'], keep='first').to_dict('records')
                    pool_reg = df_merged.sort_values('PredictedPoints', ascending=False).drop_duplicates(subset=['firstName', 'lastName'], keep='first').to_dict('records')
                    pool_boom = df_merged.sort_values('BoomProbability', ascending=False).drop_duplicates(subset=['firstName', 'lastName'], keep='first').to_dict('records')
                    
                    import optimize_weekly
                    team_cash = optimize_weekly.optimize_unstacked(pool_ev, 200, 'EV')
                    team_ceil = optimize_weekly.optimize_unstacked(pool_reg, 200, 'PredictedPoints')
                    team_sboom = optimize_weekly.optimize_stacked(pool_boom, 200, 'BoomProbability', beta=1.0)
                    team_sreg = optimize_weekly.optimize_stacked(pool_reg, 200, 'PredictedPoints', beta=1.0)
                    
                    actuals_lookup = {}
                    season_file = os.path.join(SCRIPTS_DIR, f"f2p_{year}_season.json")
                    if os.path.exists(season_file):
                        with open(season_file, "r") as f_f2p:
                            f2p_data = json.load(f_f2p)
                        week_data = [p for p in f2p_data if p.get("week") == week]
                        has_actuals = any(p.get("f2p", {}).get("totalPoints", 0.0) > 0.0 or p.get("totalPoints", 0.0) > 0.0 for p in week_data)
                        if has_actuals:
                            for p in week_data:
                                fname = p.get("firstName")
                                lname = p.get("lastName")
                                g_id = p.get("eventId", "UNK").replace("_game_", "-ev-")
                                pts = float(p.get("totalPoints", 0.0))
                                actuals_lookup[(fname, lname, g_id)] = pts
                    
                    def strip_player(p):
                        fname = p["firstName"]
                        lname = p["lastName"]
                        g_id = p["game_id"]
                        pts = actuals_lookup.get((fname, lname, g_id))
                        res = {
                            "firstName": fname,
                            "lastName": lname,
                            "team": p["team"],
                            "opponent": p["opponent"],
                            "game_id": g_id,
                            "position": p["positionGroup"],
                            "salary": int(p["salary"]),
                            "EV": round(float(p["EV"]), 1),
                            "ceiling": round(float(p["PredictedPoints"]), 1),
                            "boom": round(float(p["BoomProbability"]), 1)
                        }
                        if pts is not None:
                            res["actualPoints"] = round(pts, 1)
                        return res
                    
                    response_data = {
                        "Cash": [strip_player(p) for p in team_cash] if team_cash else [],
                        "Ceiling": [strip_player(p) for p in team_ceil] if team_ceil else [],
                        "StackedBoom": [strip_player(p) for p in team_sboom] if team_sboom else [],
                        "StackedReg": [strip_player(p) for p in team_sreg] if team_sreg else [],
                        "Coulda": []
                    }

                    # Retroactive Coulda lineup (Only if actual stats exist for this week)
                    try:
                        import coulda_optimizer
                        season_file = os.path.join(SCRIPTS_DIR, f"f2p_{year}_season.json")
                        if os.path.exists(season_file):
                            with open(season_file, "r") as f_f2p:
                                f2p_data = json.load(f_f2p)
                            # Check if actual stats are populated
                            week_data = [p for p in f2p_data if p.get("week") == week]
                            has_actuals = any(p.get("f2p", {}).get("totalPoints", 0.0) > 0.0 or p.get("totalPoints", 0.0) > 0.0 for p in week_data)
                            
                            if has_actuals:
                                matchups_file = os.path.join(SCRIPTS_DIR, f"season_matchups_{year}.json")
                                matchups = {}
                                if os.path.exists(matchups_file):
                                    with open(matchups_file, "r") as f_m:
                                        matchups = json.load(f_m)
                                
                                processed_pool = coulda_optimizer.process_players(week_data, matchups)
                                # Filter out backup goalies who didn't play (Method 3)
                                active_roster_names = set(zip(df_class['firstName'], df_class['lastName']))
                                cleaned_coulda_pool = []
                                for p in processed_pool:
                                    first = p['firstName']
                                    last = p['lastName']
                                    pos = p['position']
                                    pts = p['totalPoints']
                                    
                                    if (first, last) not in active_roster_names:
                                        continue
                                    if pos == "G" and pts == 0:
                                        continue
                                    cleaned_coulda_pool.append(p)
                                
                                team_coulda, _ = coulda_optimizer.run_optimizer(cleaned_coulda_pool, 200)
                                if team_coulda:
                                    def strip_coulda_player(p):
                                        fname = p["firstName"]
                                        lname = p["lastName"]
                                        lookup = df_merged[(df_merged["firstName"] == fname) & (df_merged["lastName"] == lname)]
                                        
                                        team_abbr = p.get("currentTeam", {}).get("teamId", "UNK")
                                        opp_abbr = p.get("_opponent", "UNK")
                                        game_id = p.get("eventId", "UNK").replace("_game_", "-ev-")
                                        salary = int(p.get("salary", 10))
                                        
                                        ev_val = float(lookup.iloc[0]["EV"]) if not lookup.empty else 0.0
                                        ceil_val = float(lookup.iloc[0]["PredictedPoints"]) if not lookup.empty else 0.0
                                        boom_val = float(lookup.iloc[0]["BoomProbability"]) if not lookup.empty else 0.0
                                        
                                        return {
                                            "firstName": fname,
                                            "lastName": lname,
                                            "team": team_abbr,
                                            "opponent": opp_abbr,
                                            "game_id": game_id,
                                            "position": p["position"],
                                            "salary": salary,
                                            "EV": round(ev_val, 1),
                                            "ceiling": round(ceil_val, 1),
                                            "boom": round(boom_val, 1),
                                            "actualPoints": round(float(p["totalPoints"]), 1)
                                        }
                                    response_data["Coulda"] = [strip_coulda_player(p) for p in team_coulda]
                    except Exception as e_coulda:
                        print(f"Warning: Could not run Coulda optimizer for {year} Week {week}: {e_coulda}")
                    
                    # Consensus Core: players appearing in all 4 forward-looking MC rosters.
                    # Coulda is excluded — it is a retrospective lineup, not a forward-looking one.
                    mc_roster_keys = ['MC_EV', 'MC_Win_160', 'MC_Win_180', 'MC_Ceil_90']
                    player_counts = {}
                    for key in mc_roster_keys:
                        for p in response_data.get(key, []):
                            p_name = f"{p['firstName']} {p['lastName']}"
                            player_counts[p_name] = player_counts.get(p_name, 0) + 1
                    response_data["Core"] = [k for k, v in player_counts.items() if v >= 4]
                    
                    cash_names = set(f"{p['firstName']} {p['lastName']}" for p in response_data["Cash"])
                    sleepers = []
                    for p in response_data["StackedReg"]:
                        p_name = f"{p['firstName']} {p['lastName']}"
                        if p['salary'] <= 10 and p_name not in cash_names:
                            sleepers.append(p_name)
                    response_data["Sleepers"] = sleepers
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(response_data).encode('utf-8'))
                    return
                else:
                    self.send_error(404, "Predictions data not found for advisory")
                    return
            else:
                self.send_error(400, "Invalid advisory path format")
                return

        # 0b. Serve player stats file within pllinterrogata or interrogata scope
        if clean_path in ['/pllinterrogata/all_players_stats.json', '/interrogata/all_players_stats.json']:
            filepath = os.path.join(SCRIPTS_DIR, 'interrogata', 'all_players_stats.json')
            if not os.path.exists(filepath):
                filepath = os.path.join(SCRIPTS_DIR, 'all_players_stats.json')
            return self.serve_file(filepath)

        # 1. Serve Predicta UI files
        if clean_path.startswith('/pllpredicta/') or clean_path.startswith('/predicta/'):
            sub_path = clean_path.replace('/pllpredicta/', '').replace('/predicta/', '')
            # Try new folder name 'predicta' first, then fallback to 'predicta_ui'
            filepath = os.path.join(SCRIPTS_DIR, 'predicta', sub_path.lstrip('/'))
            if not os.path.exists(filepath) and not filepath.endswith('index.html'):
                filepath = os.path.join(SCRIPTS_DIR, 'predicta_ui', sub_path.lstrip('/'))
            return self.serve_file(filepath)

        # 2. Serve Player Interrogator files
        if clean_path.startswith('/pllinterrogata/') or clean_path.startswith('/interrogata/'):
            sub_path = clean_path.replace('/pllinterrogata/', '').replace('/interrogata/', '')
            # Try new folder name 'interrogata' first, then fallback to 'player_interrogator'
            filepath = os.path.join(SCRIPTS_DIR, 'interrogata', sub_path.lstrip('/'))
            if not os.path.exists(filepath) and not filepath.endswith('index.html'):
                filepath = os.path.join(SCRIPTS_DIR, 'player_interrogator', sub_path.lstrip('/'))
            return self.serve_file(filepath)


        # 3. Serve Matcha (Matchup Tagger) files
        if clean_path.startswith('/pllmatcha/'):
            # Map /pllmatcha/ to /matchup_tagger/
            sub_path = clean_path.replace('/pllmatcha/', '/matchup_tagger/')
            filepath = os.path.join(SCRIPTS_DIR, sub_path.lstrip('/'))
            return self.serve_file(filepath)

        # 4. Serve the trial data files (root fallback)
        if clean_path in ['/jeff_teat_stats.json', '/atlas_players_stats.json', '/all_players_stats.json']:
            filepath = os.path.join(SCRIPTS_DIR, clean_path.lstrip('/'))
            return self.serve_file(filepath)

        # 5. Handle Data Routes
        if clean_path.startswith('/data/'):
            year = [p for p in clean_path.split('/') if p][-1]
            filepath = os.path.join(SCRIPTS_DIR, f'combined_player_stats_{year}.json')
            print(f"GET Data: {filepath}")
            return self.serve_json(filepath)

        if clean_path.startswith('/matchups/'):
            year = [p for p in clean_path.split('/') if p][-1]
            filepath = os.path.join(SCRIPTS_DIR, f'season_matchups_{year}.json')
            print(f"GET Matchups: {filepath}")
            return self.serve_json(filepath)

        if clean_path.startswith('/active-rosters/'):
            week = [p for p in clean_path.split('/') if p][-1]
            import urllib.parse
            week = urllib.parse.unquote(week).replace('Week ', '').strip()
            filepath = os.path.join(SCRIPTS_DIR, f'gameday_rosters_week{week}.json')
            print(f"GET Active Rosters: {filepath}")
            if os.path.exists(filepath):
                return self.serve_json(filepath)
            else:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{}')
                return

        # 4. Default behavior (serves from TAGGER_DIR)
        return super().do_GET()

    def serve_file(self, filepath):
        # If it's a directory, look for index.html inside it
        if os.path.isdir(filepath):
            filepath = os.path.join(filepath, 'index.html')

        if os.path.exists(filepath):
            self.send_response(200)
            if filepath.endswith('.html'): self.send_header('Content-type', 'text/html')
            elif filepath.endswith('.js'): self.send_header('Content-type', 'application/javascript')
            elif filepath.endswith('.css'): self.send_header('Content-type', 'text/css')
            elif filepath.endswith('.json'): self.send_header('Content-type', 'application/json')
            elif filepath.endswith('.png'): self.send_header('Content-type', 'image/png')
            elif filepath.endswith('.jpg') or filepath.endswith('.jpeg'): self.send_header('Content-type', 'image/jpeg')
            self.end_headers()
            with open(filepath, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, f"File not found: {filepath}")

    def serve_json(self, filepath):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.wfile.write(b'{}')

    def do_POST(self):
        if self.path == '/save':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                year = data.get('year', '2026')
                game_id = data.get('game_id', 'unknown')
                # Save to SCRIPTS_DIR where matchups are stored
                output_file = os.path.join(SCRIPTS_DIR, f"season_matchups_{year}.json")
                print(f"SAVING Matchups: {output_file}")
                
                season_data = {}
                if os.path.exists(output_file):
                    with open(output_file, 'r', encoding='utf-8') as f:
                        try:
                            season_data = json.load(f)
                        except json.JSONDecodeError:
                            season_data = {}
                            
                season_data[game_id] = data
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(season_data, f, indent=4)
                
                # Automatically refresh the Interrogator data
                print("Refreshing Player Interrogator data...")
                try:
                    importlib.reload(extract_trial_data)
                    extract_trial_data.extract_data()
                except Exception as e:
                    print(f"Error refreshing data: {e}")
                    
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "success"}')
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
            return
        
        self.send_response(404)
        self.end_headers()

if __name__ == '__main__':
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Server started: http://localhost:{PORT}")
        print("Press Ctrl+C to stop.")
        httpd.serve_forever()
