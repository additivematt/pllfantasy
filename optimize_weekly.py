import os
import subprocess
import json
import argparse
import pandas as pd
import numpy as np
import pulp
import re

# ── Positional Mappings ────────────────────────────────────────────────────────
def get_standard_pos(pos):
    pos = str(pos).upper().strip()
    if pos in ['A', 'ATTACK']: return 'A'
    if pos in ['M', 'MIDFIELD', 'MID']: return 'M'
    if pos in ['D', 'DEFENSE', 'DEF', 'SSDM', 'LSM']: return 'D'
    if pos in ['FO', 'FACEOFF']: return 'FO'
    if pos in ['G', 'GOALIE']: return 'G'
    return pos

def get_granular_pos(p):
    pos = p.get('subPosition') or p.get('positionGroup') or p.get('position')
    pos = str(pos).upper().strip()
    if pos in ["A", "ATTACK"]: return "Attack"
    if pos in ["M", "MIDFIELD", "MID"]: return "Midfield"
    if pos == "SSDM": return "SSDM"
    if pos == "LSM": return "LSM"
    if pos in ["D", "DEFENSE", "DEFENSEMEN", "DEF"]: return "Defensemen"
    if pos in ["FO", "FACEOFF"]: return "Faceoff"
    if pos in ["G", "GOALIE"]: return "Goalie"
    return "Unknown"

# ── EV Average Calculations (Prevent Data Leakage) ───────────────────────────
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

def load_historical_data(year, week, script_dir):
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

# ── Monte Carlo Optimization Helper Functions ────────────────────────────────
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
    parser = argparse.ArgumentParser(description="Weekly Advisory & Roster Optimization Dashboard")
    parser.add_argument('--year', type=int, required=True, help="Season Year (e.g. 2026)")
    parser.add_argument('--week', type=int, required=True, help="Week number to predict")
    parser.add_argument('--budget', type=int, default=200, help="F2P coins budget limit")
    parser.add_argument('--force-regen', action='store_true', help="Regenerate predictions fresh")
    args = parser.parse_args()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    class_file = os.path.join(script_dir, f"week{args.week}_{args.year}_predictions.csv")
    reg_file = os.path.join(script_dir, f"week{args.week}_{args.year}_predictions_regression.csv")
    sims_file = os.path.join(script_dir, f"week{args.week}_{args.year}_simulations.csv")
    
    # Generate predictions if they don't exist or if forced
    if args.force_regen or not os.path.exists(class_file) or not os.path.exists(reg_file):
        print("Predictions files not found or refresh requested. Generating fresh predictions...")
        subprocess.run(["python", "predict_fantasy_points.py", "--year", str(args.year), "--week", str(args.week)], cwd=script_dir, check=True)
        subprocess.run(["python", "predict_fantasy_points_regression.py", "--year", str(args.year), "--week", str(args.week)], cwd=script_dir, check=True)
        
    # Generate simulations if they don't exist or if forced
    if args.force_regen or not os.path.exists(sims_file):
        print("Simulations file not found or refresh requested. Generating fresh simulations...")
        subprocess.run(["python", "simulate_fantasy_points.py", "--year", str(args.year), "--week", str(args.week), "--sims", "10000"], cwd=script_dir, check=True)

    # Load datasets
    df_class = pd.read_csv(class_file)
    df_reg = pd.read_csv(reg_file)
    df_sims = pd.read_csv(sims_file)
    
    # Merge classification and regression datasets into a single unified workspace
    merged_cols = ['firstName', 'lastName', 'team', 'opponent', 'game_id', 'positionGroup', 'subPosition', 'salary', 'BoomProbability']
    df_merged = df_class[merged_cols].merge(
        df_reg[['firstName', 'lastName', 'game_id', 'PredictedPoints']],
        on=['firstName', 'lastName', 'game_id'],
        how='inner'
    )
    
    # Add simulated EV and p90 to the prediction DataFrame and align with simulation headers
    sim_evs = []
    sim_p90s = []
    valid_rows = []
    for idx, r in df_merged.iterrows():
        col_name = f"{r['firstName']}_{r['lastName']}_{r['game_id']}"
        if col_name in df_sims.columns:
            sim_evs.append(df_sims[col_name].mean())
            sim_p90s.append(df_sims[col_name].quantile(0.9))
            valid_rows.append(True)
        else:
            sim_evs.append(0.0)
            sim_p90s.append(0.0)
            valid_rows.append(False)
            
    df_merged["sim_ev"] = sim_evs
    df_merged["mc_ev"] = sim_evs
    df_merged["mc_p90"] = sim_p90s
    df_merged = df_merged[valid_rows]
    
    # Deduplicate: keep the best projected game per player based on sim_ev descending
    df_merged = df_merged.sort_values("sim_ev", ascending=False).drop_duplicates(subset=["firstName", "lastName"], keep="first")
    
    # Create player pool
    player_pool = []
    for idx, r in df_merged.iterrows():
        col_name = f"{r['firstName']}_{r['lastName']}_{r['game_id']}"
        sim_idx = df_sims.columns.get_loc(col_name)
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
            "mc_ev": round(float(r["mc_ev"]), 1),
            "mc_p90": round(float(r["mc_p90"]), 1)
        })
        
    if not player_pool:
        print("Error: Player pool is empty after matching simulations.")
        return
        
    # Run Optimizers
    print("Finding baseline EV optimal lineup...")
    ev_baseline = run_mc_ev_optimizer(player_pool, args.budget)
    if not ev_baseline:
        print("Error: Could not find a valid baseline EV lineup.")
        return
        
    sim_matrix = df_sims.values
    
    print("Running local search for MC EV...")
    team_mc_ev = run_local_search(player_pool, sim_matrix, 'MC_EV', ev_baseline, args.budget)
    print("Running local search for MC Win 160...")
    team_mc_win_160 = run_local_search(player_pool, sim_matrix, 'MC_Win_Prob', ev_baseline, args.budget, target_win_score=160.0)
    print("Running local search for MC Win 180...")
    team_mc_win_180 = run_local_search(player_pool, sim_matrix, 'MC_Win_Prob', ev_baseline, args.budget, target_win_score=180.0)
    print("Running local search for MC Ceil 90...")
    team_mc_ceil_90 = run_local_search(player_pool, sim_matrix, 'MC_Ceiling_90', ev_baseline, args.budget)
    
    # Cross-Reference Selections
    rosters = {
        "MC EV": team_mc_ev,
        "MC Win 160": team_mc_win_160,
        "MC Win 180": team_mc_win_180,
        "MC Ceil 90": team_mc_ceil_90
    }
    
    player_appearances = {}
    for r_name, roster in rosters.items():
        if roster:
            for p in roster:
                p_name = f"{p['firstName']} {p['lastName']} ({p['positionGroup']})"
                player_appearances[p_name] = player_appearances.get(p_name, []) + [r_name]
                
    # Consensus Core (players in >= 3 rosters)
    consensus_core = [k for k, v in player_appearances.items() if len(v) >= 3]
    
    # Sleepers (in MC Ceil 90, cost <= 10, not in MC EV)
    mc_ev_names = set(f"{p['firstName']} {p['lastName']}" for p in team_mc_ev) if team_mc_ev else set()
    sleepers = []
    if team_mc_ceil_90:
        for p in team_mc_ceil_90:
            p_name = f"{p['firstName']} {p['lastName']}"
            if p['salary'] <= 10 and p_name not in mc_ev_names:
                sleepers.append(f"{p_name} ({get_granular_pos(p)}) - Cost: {p['salary']} coins | MC p90: {p['mc_p90']:.1f} pts")
                
    slate_size = len(set(p['game_id'] for p in player_pool))
    cheap_value_count = sum(1 for p in player_pool if p['salary'] <= 12 and p['mc_ev'] >= 10)
    
    if slate_size < 4 or cheap_value_count < 40:
        recommended_strategy = "MC EV"
        recommended_reason = f"Tight pricing / short slate ({slate_size} games, {cheap_value_count} cheap value players). Optimizing for floor is best."
    else:
        recommended_strategy = "MC Win 160"
        recommended_reason = f"Stars & Scrubs slate ({slate_size} games, {cheap_value_count} cheap value players). Optimizing for variance with {recommended_strategy} is best."

    # ── Render Advisory Report ──────────────────────────────────────────────────
    advisory_path = os.path.join(script_dir, f"week{args.week}_{args.year}_advisory.md")
    
    with open(advisory_path, "w", encoding="utf-8") as f:
        f.write(f"# PLL Fantasy Weekly Advisory Report - {args.year} Week {args.week}\n\n")
        f.write(f"This report provides cross-referenced optimization results from different roster strategies for the upcoming fantasy slate.\n\n")
        
        f.write("## RECOMMENDED STRATEGY FOR THE WEEK\n")
        f.write(f"**Recommendation**: {recommended_strategy}\n\n")
        f.write(f"*{recommended_reason}*\n\n")

        # Define helper for printing a roster table
        def write_roster(r_name, roster):
            f.write(f"### {r_name}\n")
            if not roster:
                f.write("*Failed to solve optimal roster.*\n\n")
                return
                
            pos_order = {"Attack": 0, "Midfield": 1, "Defense": 2, "Faceoff": 3, "Goalie": 4}
            sorted_roster = sorted(roster, key=lambda x: pos_order.get(x['positionGroup'], 9))
            tot_cost = sum(p['salary'] for p in sorted_roster)
            tot_ev = sum(p['mc_ev'] for p in sorted_roster)
            tot_ceil = sum(p['mc_p90'] for p in sorted_roster)
            
            f.write("| Slot | Player | Team | Opponent | Game ID | Cost | MC EV | MC p90 |\n")
            f.write("| :--- | :--- | :---: | :---: | :--- | :---: | :---: | :---: |\n")
            for p in sorted_roster:
                f.write(f"| {p['positionGroup']} | {p['firstName']} {p['lastName']} | {p['team']} | {p['opponent']} | `{p['game_id']}` | {p['salary']} | {p['mc_ev']:.1f} | {p['mc_p90']:.1f} |\n")
            f.write(f"| **TOTAL** | | | | | **{tot_cost}** | **{tot_ev:.1f}** | **{tot_ceil:.1f}** |\n\n")
            
            # Detect stacks in this lineup
            teams = [p['team'] for p in sorted_roster]
            stacks = {t: teams.count(t) for t in set(teams) if teams.count(t) >= 2}
            if stacks:
                f.write(f"**Identified Stacks**: {', '.join(f'{k} ({v}-players)' for k, v in stacks.items())}\n\n")
            f.write("---\n\n")

        # Write Recommended Roster
        write_roster(f"{recommended_strategy} (Recommended)", rosters[recommended_strategy])

        f.write("## 🎯 Consensus Core Plays\n")
        f.write("These players are selected by 3 or more optimized lineups, representing high-probability foundations for your teams:\n")
        if consensus_core:
            for c in consensus_core:
                apps = ", ".join(player_appearances[c])
                f.write(f"- **{c}** (Featured in: *{apps}*)\n")
        else:
            f.write("- *No consensus core players found. Value spread is highly diversified this week.*\n")
        f.write("\n")
        
        f.write("## 🚀 High-Ceiling Sleeper Picks\n")
        f.write("Cheap, high-ceiling options identified by the Monte Carlo ceiling models (cost <= 10 coins, not in MC EV lineups):\n")
        if sleepers:
            for s in sleepers:
                f.write(f"- {s}\n")
        else:
            f.write("- *No budget sleepers identified. Stick to core pricing.*\n")
        f.write("\n")
        
        f.write("## 📋 Lineup Strategy Breakdown\n\n")
        for r_name, roster in rosters.items():
            if r_name == recommended_strategy:
                continue
            write_roster(r_name, roster)
            
    print(f"\nSaved weekly advisory report to {advisory_path}")
    print("Cross-referencing complete!")
    print(f"Consensus Core Players: {len(consensus_core)}")
    print(f"Budget Sleeper Options: {len(sleepers)}")

if __name__ == "__main__":
    main()
