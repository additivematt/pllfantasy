import os
import shutil
import glob
import re
import json
import sys

# Ensure UTF-8 console output on Windows to prevent UnicodeEncodeError with emojis
if sys.version_info >= (3, 7):
    sys.stdout.reconfigure(encoding='utf-8')


SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
if SCRIPTS_DIR not in sys.path:
    sys.path.append(SCRIPTS_DIR)
INTERROGATOR_DIR = os.path.join(SCRIPTS_DIR, "interrogata") if os.path.exists(os.path.join(SCRIPTS_DIR, "interrogata")) else os.path.join(SCRIPTS_DIR, "player_interrogator")
PREDICTA_DIR = os.path.join(SCRIPTS_DIR, "predicta") if os.path.exists(os.path.join(SCRIPTS_DIR, "predicta")) else os.path.join(SCRIPTS_DIR, "predicta_ui")

import pandas as pd
import numpy as np
import pulp

def get_standard_pos(pos):
    pos = str(pos).upper().strip()
    if pos in ['A', 'ATTACK']: return 'A'
    if pos in ['M', 'MIDFIELD', 'MID']: return 'M'
    if pos in ['D', 'DEFENSE', 'DEF', 'SSDM', 'LSM']: return 'D'
    if pos in ['FO', 'FACEOFF']: return 'FO'
    if pos in ['G', 'GOALIE']: return 'G'
    return pos

def run_mc_ev_optimizer(players, budget=200):
    prob = pulp.LpProblem("MC_EV_Optimizer", pulp.LpMaximize)
    player_vars = {}
    for i, p in enumerate(players):
        player_vars[i] = pulp.LpVariable(f"x_{i}", cat='Binary')
    prob += pulp.lpSum([p['sim_ev'] * player_vars[i] for i, p in enumerate(players)]), "Total_EV"
    prob += pulp.lpSum([p['salary'] * player_vars[i] for i, p in enumerate(players)]) <= budget, "Budget"
    pos_requirements = {'A': 2, 'M': 2, 'D': 1, 'FO': 1, 'G': 1}
    for r_pos, count in pos_requirements.items():
        prob += pulp.lpSum([
            player_vars[i] for i, p in enumerate(players)
            if get_standard_pos(p['positionGroup']) == r_pos
        ]) == count, f"Count_{r_pos}"
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[prob.status] == 'Optimal':
        selected_indices = [i for i, var in player_vars.items() if pulp.value(var) == 1]
        return [players[i] for i in selected_indices]
    return None

def evaluate_lineup_mc(lineup, sim_matrix, objective, target_win_score):
    indices = [p['sim_idx'] for p in lineup]
    lineup_sim_scores = sim_matrix[:, indices].sum(axis=1)
    if objective == 'MC_EV':
        return np.mean(lineup_sim_scores)
    elif objective == 'MC_Ceiling_90':
        return np.percentile(lineup_sim_scores, 90)
    elif objective == 'MC_Win_Prob':
        return np.mean(lineup_sim_scores > target_win_score)
    return 0.0

def generate_random_valid_lineup(players, budget=200):
    attackmen = [p for p in players if get_standard_pos(p['positionGroup']) == 'A']
    midfielders = [p for p in players if get_standard_pos(p['positionGroup']) == 'M']
    defenders = [p for p in players if get_standard_pos(p['positionGroup']) == 'D']
    faceoffs = [p for p in players if get_standard_pos(p['positionGroup']) == 'FO']
    goalies = [p for p in players if get_standard_pos(p['positionGroup']) == 'G']
    
    for _ in range(100):
        selected = []
        if len(attackmen) < 2: continue
        selected.extend(np.random.choice(attackmen, size=2, replace=False))
        if len(midfielders) < 2: continue
        selected.extend(np.random.choice(midfielders, size=2, replace=False))
        if len(defenders) < 1: continue
        selected.append(np.random.choice(defenders))
        if len(faceoffs) < 1: continue
        selected.append(np.random.choice(faceoffs))
        if len(goalies) < 1: continue
        selected.append(np.random.choice(goalies))
        
        total_cost = sum(p['salary'] for p in selected)
        if total_cost <= budget:
            return selected
    return None

def run_local_search(players, sim_matrix, objective, initial_lineup, budget=200, target_win_score=165.0, restarts=10):
    best_lineup = list(initial_lineup)
    best_val = evaluate_lineup_mc(best_lineup, sim_matrix, objective, target_win_score)
    
    for r in range(restarts):
        if r == 0:
            current_lineup = list(initial_lineup)
        else:
            current_lineup = generate_random_valid_lineup(players, budget)
            if current_lineup is None:
                continue
                
        current_val = evaluate_lineup_mc(current_lineup, sim_matrix, objective, target_win_score)
        
        improved = True
        while improved:
            improved = False
            
            pool_by_pos = {}
            for p in players:
                p_pos = get_standard_pos(p['positionGroup'])
                pool_by_pos.setdefault(p_pos, []).append(p)
                
            for i in range(len(current_lineup)):
                curr_player = current_lineup[i]
                pos_group = get_standard_pos(curr_player['positionGroup'])
                
                best_swap_player = None
                best_swap_val = current_val
                
                for candidate in pool_by_pos.get(pos_group, []):
                    if candidate['sim_idx'] == curr_player['sim_idx']:
                        continue
                    if any(p['firstName'] == candidate['firstName'] and p['lastName'] == candidate['lastName'] for p in current_lineup):
                        continue
                        
                    test_lineup = list(current_lineup)
                    test_lineup[i] = candidate
                    
                    cost = sum(p['salary'] for p in test_lineup)
                    if cost > budget:
                        continue
                        
                    val = evaluate_lineup_mc(test_lineup, sim_matrix, objective, target_win_score)
                    if val > best_swap_val:
                        best_swap_val = val
                        best_swap_player = candidate
                        
                if best_swap_player is not None:
                    current_lineup[i] = best_swap_player
                    current_val = best_swap_val
                    improved = True
                    
        if current_val > best_val:
            best_val = current_val
            best_lineup = current_lineup
            
    return best_lineup



def main():
    print("=== PREPARING STATIC DATA FOR GITHUB PAGES ===")
    
    # 1. Copy all_players_stats.json to player_interrogator folder
    src_stats = os.path.join(SCRIPTS_DIR, "all_players_stats.json")
    dest_stats = os.path.join(INTERROGATOR_DIR, "all_players_stats.json")
    
    if os.path.exists(src_stats):
        print(f"Copying player stats to {dest_stats}...")
        shutil.copy2(src_stats, dest_stats)
        print("✅ Player stats copied successfully!")
    else:
        print("❌ Error: all_players_stats.json not found in scripts directory!")
        return

    # 2. Setup predictions static directory
    predictions_root = os.path.join(PREDICTA_DIR, "predictions")
    shutil.rmtree(predictions_root, ignore_errors=True)
    os.makedirs(predictions_root, exist_ok=True)
    print(f"Created predictions root: {predictions_root}")

    # 3. Setup advisory static directory
    advisory_root = os.path.join(PREDICTA_DIR, "advisory")
    shutil.rmtree(advisory_root, ignore_errors=True)
    os.makedirs(advisory_root, exist_ok=True)
    print(f"Created advisory root: {advisory_root}")

    # 4. Scan and compile CSV predictions
    csv_pattern = os.path.join(SCRIPTS_DIR, "week*_predictions.csv")
    csv_files = glob.glob(csv_pattern)
    available_periods = []

    print(f"Found {len(csv_files)} prediction CSV files.")

    for filepath in csv_files:
        filename = os.path.basename(filepath)
        match = re.match(r"week(\d+)_(\d+)_predictions\.csv", filename)
        if match:
            week = int(match.group(1))
            year = int(match.group(2))
            available_periods.append({"year": year, "week": week})

            reg_filepath = os.path.join(SCRIPTS_DIR, f"week{week}_{year}_predictions_regression.csv")

            # Initialize Monte Carlo statistics map and helper function for predictions and advisory
            mc_stats_map = {}
            def get_mc_stats(row):
                first = row.get("firstName", "")
                last = row.get("lastName", "")
                game_id = row.get("game_id", "")
                key = (first, last, game_id)
                if key in mc_stats_map:
                    return mc_stats_map[key]
                
                f_c = re.sub(r"[^a-zA-Z]", "", first)
                l_c = re.sub(r"[^a-zA-Z]", "", last)
                for (f2, l2, g2), stats in mc_stats_map.items():
                    if g2 == game_id and re.sub(r"[^a-zA-Z]", "", f2) == f_c and re.sub(r"[^a-zA-Z]", "", l2) == l_c:
                        return stats
                return {}

            # Load actual points map for predictions and advisory
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
            else:
                # Fallback: load actuals from combined_player_stats_{year}.json
                stats_file = os.path.join(SCRIPTS_DIR, f"combined_player_stats_{year}.json")
                if os.path.exists(stats_file):
                    with open(stats_file, "r", encoding="utf-8") as f_stats:
                        stats_data = json.load(f_stats)
                    for p in stats_data:
                        if p.get("week") == week:
                            fname = p.get("identity", {}).get("firstName")
                            lname = p.get("identity", {}).get("lastName")
                            g_id = p.get("event", {}).get("eventId", "UNK").replace("_game_", "-ev-")
                            f2p = p.get("f2p", {})
                            pts = f2p.get("totalPoints")
                            if pts is not None:
                                actuals_lookup[(fname, lname, g_id)] = float(pts)
            
            # Convert CSV to JSON (Merging regression PredictedPoints if available)
            try:
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

                sims_filepath = os.path.join(SCRIPTS_DIR, f"week{week}_{year}_simulations.csv")
                if os.path.exists(sims_filepath):
                    df_sims = pd.read_csv(sims_filepath)
                    for col in df_sims.columns:
                        m = re.match(r'^(.+?)_(\d{4}-ev-\d+)$', col)
                        if not m:
                            parts = col.rsplit("_", 1)
                            if len(parts) == 2 and re.match(r"\d{4}-ev-\d+", parts[1]):
                                name_part = parts[0]
                                game_id_s = parts[1]
                            else:
                                continue
                        else:
                            name_part = m.group(1)
                            game_id_s = m.group(2)
                        
                        name_parts = name_part.split("_")
                        first_s = name_parts[0]
                        last_s = "_".join(name_parts[1:]) if len(name_parts) > 1 else ""
                        
                        col_data = df_sims[col]
                        mc_stats_map[(first_s, last_s, game_id_s)] = {
                            "mc_ev":  round(float(col_data.mean()), 2),
                            "mc_std": round(float(col_data.std()), 2),
                            "mc_p90": round(float(col_data.quantile(0.9)), 2),
                        }
                    
                    df["mc_ev"]  = df.apply(lambda r: get_mc_stats(r).get("mc_ev"), axis=1)
                    df["mc_std"] = df.apply(lambda r: get_mc_stats(r).get("mc_std"), axis=1)
                    df["mc_p90"] = df.apply(lambda r: get_mc_stats(r).get("mc_p90"), axis=1)

                # Add actual points to df
                def get_actual_pts(row):
                    first = row.get("firstName", "")
                    last = row.get("lastName", "")
                    game_id = row.get("game_id", "")
                    key = (first, last, game_id)
                    if key in actuals_lookup:
                        return actuals_lookup[key]
                    
                    f_c = re.sub(r"[^a-zA-Z]", "", first)
                    l_c = re.sub(r"[^a-zA-Z]", "", last)
                    for (f2, l2, g2), pts in actuals_lookup.items():
                        if g2 == game_id and re.sub(r"[^a-zA-Z]", "", f2) == f_c and re.sub(r"[^a-zA-Z]", "", l2) == l_c:
                            return pts
                    return None
                
                df["actualPoints"] = df.apply(get_actual_pts, axis=1)

                records_json = df.to_json(orient='records')
                records = json.loads(records_json)
            except Exception as e:
                print(f"Falling back to basic CSV reader for {filename} due to: {e}")
                import csv
                records = []
                # Fallback implementation without merge
                with open(filepath, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        cleaned_row = {}
                        for k, v in row.items():
                            try:
                                if '.' in v:
                                    cleaned_row[k] = float(v)
                                else:
                                    cleaned_row[k] = int(v)
                            except ValueError:
                                cleaned_row[k] = v
                        cleaned_row['PredictedPoints'] = 0.0
                        
                        # Add actual points fallback
                        first = cleaned_row.get("firstName", "")
                        last = cleaned_row.get("lastName", "")
                        game_id = cleaned_row.get("game_id", "")
                        pts = actuals_lookup.get((first, last, game_id))
                        if pts is None:
                            f_c = re.sub(r"[^a-zA-Z]", "", first)
                            l_c = re.sub(r"[^a-zA-Z]", "", last)
                            for (f2, l2, g2), p_pts in actuals_lookup.items():
                                if g2 == game_id and re.sub(r"[^a-zA-Z]", "", f2) == f_c and re.sub(r"[^a-zA-Z]", "", l2) == l_c:
                                    pts = p_pts
                                    break
                        if pts is not None:
                            cleaned_row["actualPoints"] = round(pts, 1)

                        records.append(cleaned_row)

            # Create year directory inside predictions
            year_dir = os.path.join(predictions_root, str(year))
            os.makedirs(year_dir, exist_ok=True)

            # Write week file (extensionless to match clean /predictions/YYYY/W URL)
            week_file = os.path.join(year_dir, str(week))
            with open(week_file, 'w', encoding='utf-8') as f:
                json.dump(records, f, indent=4)
            print(f"  Processed predictions: {year} Week {week} -> {week_file}")

            # Generate static advisory payload
            if os.path.exists(reg_filepath):
                try:
                    df_class = pd.read_csv(filepath)
                    df_reg = pd.read_csv(reg_filepath)
                    
                    import optimize_weekly
                    df_hist = optimize_weekly.load_historical_data(year, week, SCRIPTS_DIR)
                    tier_avgs = optimize_weekly.calculate_tier_averages(df_hist)
                    
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
                    df_merged["mc_ev"]  = df_merged.apply(lambda r: get_mc_stats(r).get("mc_ev"), axis=1)
                    df_merged["mc_p90"] = df_merged.apply(lambda r: get_mc_stats(r).get("mc_p90"), axis=1)
                    
                    # Load simulations CSV
                    sims_file = os.path.join(SCRIPTS_DIR, f"week{week}_{year}_simulations.csv")
                    if not os.path.exists(sims_file):
                        print(f"  ⚠️ Simulation file {sims_file} not found. Skipping MC optimization.")
                        continue
                        
                    df_sims = pd.read_csv(sims_file)
                    sim_matrix = df_sims.values
                    
                    # Load historical combined player stats to identify active players (non-DNPs) for the current week.
                    stats_file = os.path.join(SCRIPTS_DIR, f"combined_player_stats_{year}.json")
                    active_players = set()
                    has_active_players = False
                    if os.path.exists(stats_file):
                        with open(stats_file, "r", encoding="utf-8") as f_stats:
                            stats_data = json.load(f_stats)
                        for p in stats_data:
                            if p.get("week") == week:
                                is_dnp = p.get("isDNP", False)
                                pos = p.get("identity", {}).get("position")
                                first = p.get("identity", {}).get("firstName")
                                last = p.get("identity", {}).get("lastName")
                                p_stats = p.get("stats", {})
                                p_f2p = p.get("f2p", {})
                                pts = p_f2p.get("totalPoints") if p_f2p.get("totalPoints") is not None else 0.0
                                
                                # Goalie DNP check: saves == 0 and ga == 0 and pts == 0 (only if games have been played/actuals are recorded)
                                if (pos == "G" or pos == "Goalie") and len(actuals_lookup) > 0:
                                    saves = p_stats.get("saves", 0)
                                    ga = p_stats.get("goalsAgainst", 0)
                                    if saves == 0 and ga == 0 and pts == 0:
                                        is_dnp = True
                                
                                if not is_dnp:
                                    active_players.add((first, last))
                        if active_players:
                            has_active_players = True
                            print(f"  Loaded {len(active_players)} active players from combined stats for {year} W{week}")
                    
                    # Filter df_merged using active_players (DNP filtering)
                    if has_active_players:
                        df_merged = df_merged[df_merged.apply(lambda r: (r['firstName'], r['lastName']) in active_players, axis=1)]
                        
                    # Add simulated EV to the prediction DataFrame and align with simulation headers
                    sim_evs = []
                    valid_rows = []
                    for idx, r in df_merged.iterrows():
                        col_name = f"{r['firstName']}_{r['lastName']}_{r['game_id']}"
                        if col_name in df_sims.columns:
                            sim_evs.append(df_sims[col_name].mean())
                            valid_rows.append(True)
                        else:
                            sim_evs.append(0.0)
                            valid_rows.append(False)
                    df_merged["sim_ev"] = sim_evs
                    df_merged = df_merged[valid_rows]
                    
                    # Deduplicate: keep the best projected game per player
                    df_merged = df_merged.sort_values("sim_ev", ascending=False).drop_duplicates(subset=["firstName", "lastName"], keep="first")
                    
                    # Create player pool
                    player_pool = []
                    for idx, r in df_merged.iterrows():
                        col_name = f"{r['firstName']}_{r['lastName']}_{r['game_id']}"
                        sim_idx = df_sims.columns.get_loc(col_name)
                        
                        ev_val = float(r["mc_ev"]) if (pd.notna(r["mc_ev"]) and r["mc_ev"] is not None) else float(r["EV"])
                        ceil_val = float(r["mc_p90"]) if (pd.notna(r["mc_p90"]) and r["mc_p90"] is not None) else float(r["PredictedPoints"])
                        
                        player_pool.append({
                            "firstName": r["firstName"],
                            "lastName": r["lastName"],
                            "team": r["team"],
                            "opponent": r["opponent"],
                            "game_id": r["game_id"],
                            "positionGroup": r["positionGroup"],
                            "salary": int(r["salary"]),
                            "sim_ev": r["sim_ev"],
                            "sim_idx": sim_idx,
                            "EV": round(float(r["EV"]), 1),
                            "ceiling": round(float(r["PredictedPoints"]), 1),
                            "boom": round(float(r["BoomProbability"]), 1),
                            "mc_ev": round(ev_val, 1),
                            "mc_p90": round(ceil_val, 1)
                        })
                        
                    # 1. Run MC EV Baseline
                    ev_baseline = run_mc_ev_optimizer(player_pool, budget=200)
                    if not ev_baseline:
                        print("  ⚠️ Could not find a valid baseline EV lineup.")
                        continue
                        
                    # 2. Run MC EV Optimization via Local Search
                    team_mc_ev = run_local_search(player_pool, sim_matrix, 'MC_EV', ev_baseline, budget=200)
                    
                    # 3. Run MC Win 160 Optimization
                    team_mc_win_160 = run_local_search(player_pool, sim_matrix, 'MC_Win_Prob', ev_baseline, budget=200, target_win_score=160.0)
                    
                    # 4. Run MC Win 180 Optimization
                    team_mc_win_180 = run_local_search(player_pool, sim_matrix, 'MC_Win_Prob', ev_baseline, budget=200, target_win_score=180.0)
                    
                    # 5. Run MC Ceil 90 Optimization
                    team_mc_ceil_90 = run_local_search(player_pool, sim_matrix, 'MC_Ceiling_90', ev_baseline, budget=200)
                    
                    # actuals_lookup is already loaded at the start of the week loop
                    pass
                                        
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
                            "mc_ev": p["mc_ev"],
                            "mc_p90": p["mc_p90"]
                        }
                        if pts is not None:
                            res["actualPoints"] = round(pts, 1)
                        return res
                        
                    adv_response = {
                        "MC_EV": [strip_player(p) for p in team_mc_ev] if team_mc_ev else [],
                        "MC_Win_160": [strip_player(p) for p in team_mc_win_160] if team_mc_win_160 else [],
                        "MC_Win_180": [strip_player(p) for p in team_mc_win_180] if team_mc_win_180 else [],
                        "MC_Ceil_90": [strip_player(p) for p in team_mc_ceil_90] if team_mc_ceil_90 else [],
                        "Coulda": []
                    }
                    
                    # Retroactive Coulda lineup (Only if actual stats exist for this week)
                    try:
                        import coulda_optimizer
                        has_actuals = len(actuals_lookup) > 0
                        if has_actuals:
                            if os.path.exists(season_file):
                                with open(season_file, "r") as f_f2p:
                                    f2p_data = json.load(f_f2p)
                                week_data = [p for p in f2p_data if p.get("week") == week]
                            else:
                                week_data = []
                                if os.path.exists(stats_file):
                                    with open(stats_file, "r", encoding="utf-8") as f_stats:
                                        stats_data = json.load(f_stats)
                                    for p in stats_data:
                                        if p.get("week") == week:
                                            ident = p.get("identity", {})
                                            evt = p.get("event", {})
                                            f2p = p.get("f2p", {})
                                            
                                            sal_val = f2p.get("salary")
                                            try:
                                                sal = int(float(sal_val)) if sal_val is not None else 10
                                            except:
                                                sal = 10
                                                
                                            pts_val = f2p.get("totalPoints")
                                            try:
                                                pts = float(pts_val) if pts_val is not None else 0.0
                                            except:
                                                pts = 0.0
                                                
                                            week_data.append({
                                                "officialId": ident.get("officialId"),
                                                "firstName": ident.get("firstName"),
                                                "lastName": ident.get("lastName"),
                                                "position": ident.get("position"),
                                                "currentTeam": {"teamId": ident.get("team")},
                                                "eventId": evt.get("eventId"),
                                                "gameNumber": evt.get("gameNumber"),
                                                "salary": sal,
                                                "totalPoints": pts
                                            })
                                            
                            matchups = {}
                            matchups_file = os.path.join(SCRIPTS_DIR, f"season_matchups_{year}.json")
                            if os.path.exists(matchups_file):
                                with open(matchups_file, "r") as f_m:
                                    matchups = json.load(f_m)
                                    
                            # Supplement with any missing matchups from combined stats
                            if os.path.exists(stats_file):
                                with open(stats_file, "r", encoding="utf-8") as f_stats:
                                    stats_data = json.load(f_stats)
                                for p in stats_data:
                                    evt = p.get("event", {})
                                    e_id = evt.get("eventId")
                                    if e_id and e_id not in matchups:
                                        matchups[e_id] = {
                                            "team_a": evt.get("homeTeam"),
                                            "team_b": evt.get("awayTeam")
                                        }
                                            
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
                                    
                                    ev_val = float(lookup.iloc[0]["mc_ev"]) if (not lookup.empty and pd.notna(lookup.iloc[0]["mc_ev"])) else (float(lookup.iloc[0]["EV"]) if not lookup.empty else 0.0)
                                    ceil_val = float(lookup.iloc[0]["mc_p90"]) if (not lookup.empty and pd.notna(lookup.iloc[0]["mc_p90"])) else (float(lookup.iloc[0]["PredictedPoints"]) if not lookup.empty else 0.0)
                                    
                                    return {
                                        "firstName": fname,
                                        "lastName": lname,
                                        "team": team_abbr,
                                        "opponent": opp_abbr,
                                        "game_id": game_id,
                                        "position": p["position"],
                                        "salary": salary,
                                        "mc_ev": round(ev_val, 1),
                                        "mc_p90": round(ceil_val, 1),
                                        "actualPoints": round(float(p["totalPoints"]), 1)
                                    }
                                adv_response["Coulda"] = [strip_coulda_player(p) for p in team_coulda]
                    except Exception as e_coulda:
                        import traceback
                        traceback.print_exc()
                        print(f"  Warning: Could not run Coulda optimizer for {year} Week {week}: {e_coulda}")
                        
                    # Consensus Core: players appearing in all 4 forward-looking MC rosters.
                    # Coulda is excluded — it is a retrospective lineup, not a forward-looking one.
                    mc_roster_keys = ['MC_EV', 'MC_Win_160', 'MC_Win_180', 'MC_Ceil_90']
                    player_counts = {}
                    for key in mc_roster_keys:
                        for p in adv_response.get(key, []):
                            p_name = f"{p['firstName']} {p['lastName']}"
                            player_counts[p_name] = player_counts.get(p_name, 0) + 1
                    adv_response["Core"] = [k for k, v in player_counts.items() if v >= 4]
                    
                    ev_names = set(f"{p['firstName']} {p['lastName']}" for p in adv_response["MC_EV"])
                    sleepers = []
                    for p in adv_response["MC_Ceil_90"]:
                        p_name = f"{p['firstName']} {p['lastName']}"
                        if p['salary'] <= 10 and p_name not in ev_names:
                            sleepers.append(p_name)
                    adv_response["Sleepers"] = sleepers
                    
                    adv_year_dir = os.path.join(advisory_root, str(year))
                    os.makedirs(adv_year_dir, exist_ok=True)
                    
                    adv_week_file = os.path.join(adv_year_dir, str(week))
                    with open(adv_week_file, 'w', encoding='utf-8') as f_adv:
                        json.dump(adv_response, f_adv, indent=4)
                    print(f"  Processed advisory: {year} Week {week} -> {adv_week_file}")
                except Exception as e_adv:
                    import traceback
                    traceback.print_exc()
                    print(f"  ❌ Error generating static advisory for {year} Week {week}: {e_adv}")

    # Sort available periods chronologically (newest first)
    available_periods.sort(key=lambda x: (x['year'], x['week']), reverse=True)

    # Write available file (extensionless to match clean /predictions/available URL)
    available_file = os.path.join(predictions_root, "available")
    with open(available_file, 'w', encoding='utf-8') as f:
        json.dump(available_periods, f, indent=4)
    print(f"✅ Generated predictions index: {available_file}")
    
    print("\n🎉 STATIC DATA PREPARATION COMPLETE!")
    print("You can now upload the 'interrogata' and 'predicta' folders to your GitHub repository!")


if __name__ == '__main__':
    main()
