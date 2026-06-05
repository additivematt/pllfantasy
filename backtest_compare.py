import os
import subprocess
import json
import pandas as pd
import numpy as np
import argparse

WEEKS_2025 = [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14]

def assign_position_group(pos):
    pos = str(pos).upper()
    if pos in ["A", "ATTACK"]: return "Attack"
    if pos in ["M", "MIDFIELD"]: return "Midfield"
    if pos in ["SSDM", "LSM", "D", "DEFENSE", "DEFENSEMEN"]: return "Defense"
    if pos in ["FO", "FACEOFF"]: return "Faceoff"
    if pos in ["G", "GOALIE"]: return "Goalie"
    return "Unknown"

def calc_fantasy(s):
    pts = (s.get("onePointGoals", 0) * 10 + s.get("twoPointGoals", 0) * 15 + s.get("assists", 0) * 7 + s.get("faceoffsWon", 0) * 0.8 + (s.get("faceoffs", 0) - s.get("faceoffsWon", 0)) * -0.5 + s.get("groundBalls", 0) + s.get("saves", 0) * 3 + s.get("causedTurnovers", 0) * 10)
    if s.get("onePointGoals", 0) + s.get("twoPointGoals", 0) >= 3: pts += 5
    if s.get("assists", 0) >= 3: pts += 5
    if s.get("causedTurnovers", 0) >= 3: pts += 5
    if s.get("saves", 0) >= 15: pts += 5
    return pts

def precompute_best_pairs(pool, max_budget, metric):
    result = {}
    all_pairs = []
    for i in range(len(pool)):
        for j in range(i+1, len(pool)):
            if pool[i]['firstName'] == pool[j]['firstName'] and pool[i]['lastName'] == pool[j]['lastName']:
                continue
            cost = pool[i]["salary"] + pool[j]["salary"]
            if cost <= max_budget:
                score = pool[i][metric] + pool[j][metric]
                all_pairs.append((score, cost, pool[i], pool[j]))
    
    all_pairs.sort(key=lambda x: -x[0])
    
    for b in range(max_budget + 1):
        for pair in all_pairs:
            if pair[1] <= b:
                result[b] = pair
                break
        else:
            result[b] = None
    return result

def run_optimizer(players, budget, metric):
    attackmen  = sorted([p for p in players if p["positionGroup"] == "Attack"],  key=lambda p: -p[metric])
    midfielders= sorted([p for p in players if p["positionGroup"] == "Midfield"],  key=lambda p: -p[metric])
    defenders  = sorted([p for p in players if p["positionGroup"] in ("Defense", "Defensemen", "SSDM", "LSM")], key=lambda p: -p[metric])
    faceoffs   = sorted([p for p in players if p["positionGroup"] == "Faceoff"], key=lambda p: -p[metric])
    goalies    = sorted([p for p in players if p["positionGroup"] == "Goalie"],  key=lambda p: -p[metric])

    atk_best = precompute_best_pairs(attackmen, budget, metric)
    mid_best = precompute_best_pairs(midfielders, budget, metric)
    
    best_score = -1
    best_team = None
    
    for fo in faceoffs:
        for g in goalies:
            for d in defenders:
                fixed_cost = fo["salary"] + g["salary"] + d["salary"]
                if fixed_cost > budget:
                    continue
                
                names = {(fo['firstName'], fo['lastName']), (g['firstName'], g['lastName']), (d['firstName'], d['lastName'])}
                if len(names) < 3: continue

                fixed_score = fo[metric] + g[metric] + d[metric]
                remaining = budget - fixed_cost
                
                current_best_combined = -1
                current_best_a = None
                current_best_m = None
                
                for a_budget in range(remaining + 1):
                    m_budget = remaining - a_budget
                    a_pair = atk_best.get(a_budget)
                    m_pair = mid_best.get(m_budget)
                    
                    if a_pair and m_pair:
                        n_a1 = (a_pair[2]['firstName'], a_pair[2]['lastName'])
                        n_a2 = (a_pair[3]['firstName'], a_pair[3]['lastName'])
                        n_m1 = (m_pair[2]['firstName'], m_pair[2]['lastName'])
                        n_m2 = (m_pair[3]['firstName'], m_pair[3]['lastName'])
                        
                        all_names = {n_a1, n_a2, n_m1, n_m2}.union(names)
                        if len(all_names) < 7:
                            continue
                            
                        combined = a_pair[0] + m_pair[0]
                        if combined > current_best_combined:
                            current_best_combined = combined
                            current_best_a = a_pair
                            current_best_m = m_pair
                
                if current_best_a and current_best_m:
                    total_score = fixed_score + current_best_combined
                    if total_score > best_score:
                        best_score = total_score
                        best_team = [current_best_a[2], current_best_a[3], current_best_m[2], current_best_m[3], d, fo, g]

    return best_team

def load_historical_data(year, week, script_dir):
    """Loads all stats prior to the target year/week to calculate historical tier averages (avoiding leakage)."""
    rows = []
    for yr in range(2023, year + 1):
        path = os.path.join(script_dir, f"combined_player_stats_{yr}.json")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for p in data:
            if yr == year and p.get("week", 1) >= week:
                continue
            ident = p.get("identity", {})
            stats = p.get("stats", {})
            f2p = p.get("f2p", {})
            fp = f2p.get("totalPoints") if f2p.get("totalPoints") is not None else calc_fantasy(stats)
            rows.append({
                "positionGroup": assign_position_group(ident.get("position")),
                "TotalFantasyPoints": fp,
                "week": p.get("week"),
                "year": yr
            })
    return pd.DataFrame(rows)

def calculate_tier_averages(df_hist):
    averages = {}
    if df_hist.empty:
        for pos in ["Attack", "Midfield", "Defense", "Faceoff", "Goalie"]:
            averages[pos] = {"Boom": 25.0, "NonBoom": 8.0}
        return averages

    df_hist = df_hist.copy()
    df_hist["IsBoom"] = False
    
    grouped = df_hist.groupby(["year", "week", "positionGroup"])
    for name, group in grouped:
        q75 = group["TotalFantasyPoints"].quantile(0.75)
        df_hist.loc[group.index, "IsBoom"] = group["TotalFantasyPoints"] > q75
        
    for pos in ["Attack", "Midfield", "Defense", "Faceoff", "Goalie"]:
        pos_data = df_hist[df_hist["positionGroup"] == pos]
        if pos_data.empty:
            averages[pos] = {"Boom": 25.0, "NonBoom": 8.0}
            continue
            
        boom_avg = pos_data[pos_data["IsBoom"]]["TotalFantasyPoints"].mean()
        nonboom_avg = pos_data[~pos_data["IsBoom"]]["TotalFantasyPoints"].mean()
        
        averages[pos] = {
            "Boom": boom_avg if pd.notna(boom_avg) else 25.0,
            "NonBoom": nonboom_avg if pd.notna(nonboom_avg) else 8.0
        }
    return averages

def evaluate_lineup(team, actuals_map):
    """Calculates actual total points and cost for a lineup."""
    if not team: return 0.0, 0
    total_pts = 0.0
    total_cost = 0
    for p in team:
        key = (p['firstName'], p['lastName'], p['game_id'].replace('-ev-', '_game_'))
        total_pts += actuals_map.get(key, 0.0)
        total_cost += p['salary']
    return total_pts, total_cost

def main():
    parser = argparse.ArgumentParser(description="Evaluate & Compare Optimization Approaches")
    parser.add_argument('--year', type=int, default=2025)
    parser.add_argument('--week', type=int, default=None)
    parser.add_argument('--no-dnps', action='store_true', help="Filter out players who did not actually play")
    args = parser.parse_args()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    comb_file = os.path.join(script_dir, f"combined_player_stats_{args.year}.json")
    
    if not os.path.exists(comb_file):
        print(f"Error: {comb_file} not found.")
        return
        
    with open(comb_file, "r") as f:
        all_year_data = json.load(f)
        
    if args.week is not None:
        weeks = [args.week]
    else:
        weeks = WEEKS_2025 if args.year == 2025 else []
        if not weeks:
            # Auto detect weeks for other years
            weeks = sorted(list(set(p.get("week") for p in all_year_data if p.get("week"))))
        
    results = []
    
    print(f"=== STARTING BACKTEST COMPARISON FOR SEASON {args.year} ===")
    print("This will run classification & regression models week-by-week.")
    
    for w in weeks:
        print(f"\nProcessing Week {w}...")
        
        # 1. Generate classification predictions
        cmd_class = ["python", "predict_fantasy_points.py", "--year", str(args.year), "--week", str(w)]
        subprocess.run(cmd_class, cwd=script_dir, check=True)
        
        # 2. Generate regression predictions
        cmd_reg = ["python", "predict_fantasy_points_regression.py", "--year", str(args.year), "--week", str(w)]
        subprocess.run(cmd_reg, cwd=script_dir, check=True)
        
        # 3. Filter predictions (maps to the final prediction CSV paths)
        cmd_filter = ["python", "apply_roster_filter.py", "--year", str(args.year), "--week", str(w)]
        subprocess.run(cmd_filter, cwd=script_dir, check=True)
        
        # Load prediction files
        class_file = os.path.join(script_dir, f"week{w}_{args.year}_predictions.csv")
        reg_file = os.path.join(script_dir, f"week{w}_{args.year}_predictions_regression.csv")
        
        if not os.path.exists(class_file) or not os.path.exists(reg_file):
            print(f"Skipping week {w}: prediction files missing.")
            continue
            
        df_class = pd.read_csv(class_file)
        df_reg = pd.read_csv(reg_file)
        
        # Build actual points map & coulda pool
        week_data = [p for p in all_year_data if p.get("week") == w]
        actuals_map = {}
        coulda_pool = []
        
        # Patch salaries for weeks >= 12 in 2025 to match predictions
        sal_map = {}
        for p in week_data:
            fname = p.get('identity', {}).get('firstName')
            lname = p.get('identity', {}).get('lastName')
            game_id = p.get('event', {}).get('eventId', '')
            sal = p.get('f2p', {}).get('salary')
            if args.year == 2025 and (w >= 12 or sal is None):
                # Fallback salary map to align actuals with test dataset salaries
                # Let's read the salary from the prediction csv
                pred_row = df_class[(df_class['firstName'] == fname) & (df_class['lastName'] == lname) & (df_class['game_id'] == game_id.replace('_game_', '-ev-'))]
                sal = int(pred_row.iloc[0]['salary']) if not pred_row.empty else 10
            sal_map[(fname, lname, game_id)] = sal
        
        for p in week_data:
            ident = p.get("identity", {})
            evt = p.get("event", {})
            f2p = p.get("f2p", {})
            first = ident.get("firstName")
            last = ident.get("lastName")
            event_id = evt.get("eventId")
            
            # Skip DNPs
            if not p.get("stats") and f2p.get("totalPoints", 0) == 0:
                continue
                
            pts = f2p.get("totalPoints") if f2p.get("totalPoints") is not None else calc_fantasy(p.get("stats", {}))
            key = (first, last, event_id)
            actuals_map[key] = pts
            
            # Roster parameters
            salary = sal_map.get(key, f2p.get("salary", 10))
            
            coulda_pool.append({
                "firstName": first,
                "lastName": last,
                "positionGroup": assign_position_group(ident.get("position")),
                "game_id": event_id.replace("_game_", "-ev-"),
                "salary": salary,
                "actualPoints": pts
            })
            
        if not actuals_map:
            print(f"Skipping week {w}: no actual game data found (week may not have occurred yet).")
            continue
            
        # Filter out DNPs if requested
        if args.no_dnps:
            df_class = df_class[df_class.apply(lambda r: (r['firstName'], r['lastName'], r['game_id'].replace('-ev-', '_game_')) in actuals_map, axis=1)]
            df_reg = df_reg[df_reg.apply(lambda r: (r['firstName'], r['lastName'], r['game_id'].replace('-ev-', '_game_')) in actuals_map, axis=1)]
            
        # 3. Calculate expected values (EV) on classification predictions
        df_hist = load_historical_data(args.year, w, script_dir)
        tier_avgs = calculate_tier_averages(df_hist)
        
        def get_ev(row):
            pos = row['positionGroup']
            p_boom = row['BoomProbability'] / 100.0
            p_nonboom = 1.0 - p_boom
            avgs = tier_avgs.get(pos, {"Boom": 25.0, "NonBoom": 8.0})
            return p_boom * avgs["Boom"] + p_nonboom * avgs["NonBoom"]
            
        df_class['EV'] = df_class.apply(get_ev, axis=1)
        
        # 4. Drop duplicates to select the best performance per player
        df_class_sorted_boom = df_class.sort_values('BoomProbability', ascending=False).drop_duplicates(subset=['firstName', 'lastName'], keep='first')
        df_class_sorted_ev = df_class.sort_values('EV', ascending=False).drop_duplicates(subset=['firstName', 'lastName'], keep='first')
        df_reg_sorted = df_reg.sort_values('PredictedPoints', ascending=False).drop_duplicates(subset=['firstName', 'lastName'], keep='first')
        
        # Drop duplicates for Coulda pool (actual points)
        df_coulda_df = pd.DataFrame(coulda_pool)
        if not df_coulda_df.empty:
            df_coulda_df = df_coulda_df.sort_values('actualPoints', ascending=False).drop_duplicates(subset=['firstName', 'lastName'], keep='first')
            df_coulda_pool = df_coulda_df.to_dict('records')
        else:
            df_coulda_pool = []
            
        # 5. Run Optimizations
        from roster_optimizer_stack import optimize_stack
        team_boom = run_optimizer(df_class_sorted_boom.to_dict('records'), 200, 'BoomProbability')
        team_ev = run_optimizer(df_class_sorted_ev.to_dict('records'), 200, 'EV')
        team_reg = run_optimizer(df_reg_sorted.to_dict('records'), 200, 'PredictedPoints')
        
        # Run teammate stack optimizers (beta = 0.15)
        team_boom_stack = optimize_stack(df_class_sorted_boom.to_dict('records'), 200, 'BoomProbability', 0.15)
        team_reg_stack = optimize_stack(df_reg_sorted.to_dict('records'), 200, 'PredictedPoints', 0.15)
        
        team_coulda = run_optimizer(df_coulda_pool, 200, 'actualPoints') if df_coulda_pool else None
        
        # 6. Evaluate actual points scored
        pts_boom, cost_boom = evaluate_lineup(team_boom, actuals_map)
        pts_ev, cost_ev = evaluate_lineup(team_ev, actuals_map)
        pts_reg, cost_reg = evaluate_lineup(team_reg, actuals_map)
        pts_boom_stack, cost_boom_stack = evaluate_lineup(team_boom_stack, actuals_map)
        pts_reg_stack, cost_reg_stack = evaluate_lineup(team_reg_stack, actuals_map)
        pts_coulda, cost_coulda = evaluate_lineup(team_coulda, actuals_map)
        
        print(f"  Week {w} Results:")
        print(f"    - Classification (Boom %): {pts_boom:.1f} pts (Cost: {cost_boom})")
        print(f"    - EV Weighted:             {pts_ev:.1f} pts (Cost: {cost_ev})")
        print(f"    - Regression:              {pts_reg:.1f} pts (Cost: {cost_reg})")
        print(f"    - Stacked Boom %:          {pts_boom_stack:.1f} pts (Cost: {cost_boom_stack})")
        print(f"    - Stacked Regression:      {pts_reg_stack:.1f} pts (Cost: {cost_reg_stack})")
        print(f"    - Retroactive Coulda:      {pts_coulda:.1f} pts (Cost: {cost_coulda})")
        
        results.append({
            "Week": w,
            "Classification_Pts": pts_boom,
            "EV_Pts": pts_ev,
            "Regression_Pts": pts_reg,
            "Stacked_Boom_Pts": pts_boom_stack,
            "Stacked_Reg_Pts": pts_reg_stack,
            "Coulda_Pts": pts_coulda
        })
        
    # Generate final comparison report
    if not results:
        print("No backtest results generated.")
        return
        
    df_res = pd.DataFrame(results)
    
    total_class = df_res["Classification_Pts"].sum()
    total_ev = df_res["EV_Pts"].sum()
    total_reg = df_res["Regression_Pts"].sum()
    total_sclass = df_res["Stacked_Boom_Pts"].sum()
    total_sreg = df_res["Stacked_Reg_Pts"].sum()
    total_coulda = df_res["Coulda_Pts"].sum()
    
    avg_class = df_res["Classification_Pts"].mean()
    avg_ev = df_res["EV_Pts"].mean()
    avg_reg = df_res["Regression_Pts"].mean()
    avg_sclass = df_res["Stacked_Boom_Pts"].mean()
    avg_sreg = df_res["Stacked_Reg_Pts"].mean()
    avg_coulda = df_res["Coulda_Pts"].mean()
    
    # Scale width for columns to fit new entries
    width = 120
    print("\n" + "="*width)
    print(f"                                   2025 SEASON OPTIMIZER STRATEGY COMPARISON")
    print("="*width)
    print(f"{'Week':<6} | {'Class (Boom %)':<16} | {'EV Weighted':<14} | {'Regression':<12} | {'Stacked Boom':<14} | {'Stacked Reg':<12} | {'Coulda Optimal':<15}")
    print("-" * width)
    for idx, row in df_res.iterrows():
        print(f"Week {int(row['Week']):<2} | {row['Classification_Pts']:<16.1f} | {row['EV_Pts']:<14.1f} | {row['Regression_Pts']:<12.1f} | {row['Stacked_Boom_Pts']:<14.1f} | {row['Stacked_Reg_Pts']:<12.1f} | {row['Coulda_Pts']:<15.1f}")
    print("-" * width)
    print(f"{'TOTAL':<6} | {total_class:<16.1f} | {total_ev:<14.1f} | {total_reg:<12.1f} | {total_sclass:<14.1f} | {total_sreg:<12.1f} | {total_coulda:<15.1f}")
    print(f"{'AVG':<6} | {avg_class:<16.1f} | {avg_ev:<14.1f} | {avg_reg:<12.1f} | {avg_sclass:<14.1f} | {avg_sreg:<12.1f} | {avg_coulda:<15.1f}")
    print(f"{'% MAX':<6} | {100*total_class/total_coulda:<15.1f}% | {100*total_ev/total_coulda:<13.1f}% | {100*total_reg/total_coulda:<11.1f}% | {100*total_sclass/total_coulda:<13.1f}% | {100*total_sreg/total_coulda:<11.1f}% | {100.0:<15.1f}%")
    print("="*width)

if __name__ == "__main__":
    main()
