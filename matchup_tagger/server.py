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
from optimize_weekly import load_historical_data, calculate_tier_averages

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Default directory is TAGGER_DIR so http://localhost:8000/ serves the tagger
        super().__init__(*args, directory=TAGGER_DIR, **kwargs)

    def do_GET(self):
        clean_path = self.path.split('?')[0]

        # 0a. Serve dynamic predictions endpoints (within pllpredicta scope or fallback)
        if clean_path in ['/predictions/available', '/pllpredicta/predictions/available']:
            import glob
            import re
            pattern = os.path.join(SCRIPTS_DIR, "week*_predictions.csv")
            files = glob.glob(pattern)
            available = []
            for filepath in files:
                filename = os.path.basename(filepath)
                match = re.match(r"week(\d+)_(\d+)_predictions\.csv", filename)
                if match:
                    week = int(match.group(1))
                    year = int(match.group(2))
                    available.append({"year": year, "week": week})
            
            # Sort chronologically (year desc, week desc)
            available.sort(key=lambda x: (x['year'], x['week']), reverse=True)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(available).encode('utf-8'))
            return

        if clean_path.startswith('/predictions/') or clean_path.startswith('/pllpredicta/predictions/'):
            # Format: /predictions/2026/2 or /pllpredicta/predictions/2026/2
            parts = [p for p in clean_path.split('/') if p]
            if parts and parts[0] == 'pllpredicta':
                parts = parts[1:]
            if len(parts) >= 3:
                year, week = parts[1], parts[2]
                filepath = os.path.join(SCRIPTS_DIR, f"week{week}_{year}_predictions.csv")
                reg_filepath = os.path.join(SCRIPTS_DIR, f"week{week}_{year}_predictions_regression.csv")
                if os.path.exists(filepath):
                    import pandas as pd
                    df = pd.read_csv(filepath)
                    if os.path.exists(reg_filepath):
                        df_reg = pd.read_csv(reg_filepath)
                        df = df.merge(
                            df_reg[['firstName', 'lastName', 'game_id', 'PredictedPoints']],
                            on=['firstName', 'lastName', 'game_id'],
                            how='left'
                        ).fillna(0.0)
                    else:
                        df['PredictedPoints'] = 0.0
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
        if clean_path.startswith('/advisory/') or clean_path.startswith('/pllpredicta/advisory/'):
            # Format: /advisory/2026/2 or /pllpredicta/advisory/2026/2
            parts = [p for p in clean_path.split('/') if p]
            if parts and parts[0] == 'pllpredicta':
                parts = parts[1:]
            if len(parts) >= 3:
                year, week = int(parts[1]), int(parts[2])
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
                    team_sboom = optimize_weekly.optimize_stacked(pool_boom, 200, 'BoomProbability', beta=0.15)
                    team_sreg = optimize_weekly.optimize_stacked(pool_reg, 200, 'PredictedPoints', beta=0.15)
                    
                    def strip_player(p):
                        return {
                            "firstName": p["firstName"],
                            "lastName": p["lastName"],
                            "team": p["team"],
                            "opponent": p["opponent"],
                            "game_id": p["game_id"],
                            "position": p["positionGroup"],
                            "salary": int(p["salary"]),
                            "EV": round(float(p["EV"]), 1),
                            "ceiling": round(float(p["PredictedPoints"]), 1),
                            "boom": round(float(p["BoomProbability"]), 1)
                        }
                    
                    response_data = {
                        "Cash": [strip_player(p) for p in team_cash] if team_cash else [],
                        "Ceiling": [strip_player(p) for p in team_ceil] if team_ceil else [],
                        "StackedBoom": [strip_player(p) for p in team_sboom] if team_sboom else [],
                        "StackedReg": [strip_player(p) for p in team_sreg] if team_sreg else []
                    }
                    
                    player_counts = {}
                    for key, roster in response_data.items():
                        if isinstance(roster, list):
                            for p in roster:
                                p_name = f"{p['firstName']} {p['lastName']}"
                                player_counts[p_name] = player_counts.get(p_name, 0) + 1
                    response_data["Core"] = [k for k, v in player_counts.items() if v >= 3]
                    
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

        # 0b. Serve player stats file within pllinterrogata scope
        if clean_path == '/pllinterrogata/all_players_stats.json':
            filepath = os.path.join(SCRIPTS_DIR, 'all_players_stats.json')
            return self.serve_file(filepath)

        # 1. Serve Predicta UI files
        if clean_path.startswith('/pllpredicta/'):
            sub_path = clean_path.replace('/pllpredicta/', '')
            # Try new folder name 'predicta' first, then fallback to 'predicta_ui'
            filepath = os.path.join(SCRIPTS_DIR, 'predicta', sub_path.lstrip('/'))
            if not os.path.exists(filepath) and not filepath.endswith('index.html'):
                filepath = os.path.join(SCRIPTS_DIR, 'predicta_ui', sub_path.lstrip('/'))
            return self.serve_file(filepath)

        # 2. Serve Player Interrogator files
        if clean_path.startswith('/pllinterrogata/'):
            sub_path = clean_path.replace('/pllinterrogata/', '')
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
