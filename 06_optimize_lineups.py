import os
import subprocess
import json
import argparse
import pandas as pd
import numpy as np
import pulp
import re
from utils import (
    assign_position_group,
    calc_fantasy,
    get_standard_pos,
    run_mc_ev_optimizer,
    generate_random_valid_lineup,
    evaluate_lineup_mc,
    run_local_search
)
from config import DEFAULT_WIN_SCORE_THRESHOLD, LOCAL_SEARCH_RESTARTS, DEFAULT_BUDGET

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


def main():
    parser = argparse.ArgumentParser(description="Weekly Advisory & Roster Optimization Dashboard")
    parser.add_argument('--year', type=int, required=True, help="Season Year (e.g. 2026)")
    parser.add_argument('--week', type=int, required=True, help="Week number to predict")
    parser.add_argument('--budget', type=int, default=DEFAULT_BUDGET, help="F2P coins budget limit")
    parser.add_argument('--force-regen', action='store_true', help="Regenerate predictions fresh")
    args = parser.parse_args()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    predictions_dir = os.path.join(script_dir, "predicta", "predictions")
    class_file = os.path.join(predictions_dir, f"week{args.week}_{args.year}_predictions.csv")
    sims_file = os.path.join(predictions_dir, f"week{args.week}_{args.year}_simulations.csv")
    
    # Generate predictions if they don't exist or if forced
    if args.force_regen or not os.path.exists(class_file):
        print("Predictions file not found or refresh requested. Generating fresh predictions...")
        subprocess.run(["python", "02_predict_probabilities.py", "--year", str(args.year), "--week", str(args.week)], cwd=script_dir, check=True)
        
    # Generate simulations if they don't exist or if forced
    if args.force_regen or not os.path.exists(sims_file):
        print("Simulations file not found or refresh requested. Generating fresh simulations...")
        subprocess.run(["python", "04_simulate_monte_carlo.py", "--year", str(args.year), "--week", str(args.week), "--sims", "10000"], cwd=script_dir, check=True)

    # Load datasets
    df_class = pd.read_csv(class_file)
    df_sims = pd.read_csv(sims_file)
    
    df_merged = df_class.copy()
    
    # Map simulated EV and simulated standard deviation / ceiling from Monte Carlo simulations
    sim_evs = []
    sim_p90s = []
    sim_idxs = []
    
    for idx, r in df_merged.iterrows():
        col_name = f"{r['firstName']}_{r['lastName']}_{r['game_id']}"
        if col_name in df_sims.columns:
            sim_evs.append(df_sims[col_name].mean())
            sim_p90s.append(np.percentile(df_sims[col_name].values, 90))
            sim_idxs.append(df_sims.columns.get_loc(col_name))
        else:
            sim_evs.append(0.0)
            sim_p90s.append(0.0)
            sim_idxs.append(-1)
            
    df_merged["sim_ev"] = sim_evs
    df_merged["sim_p90"] = sim_p90s
    df_merged["sim_idx"] = sim_idxs
    df_merged = df_merged[df_merged["sim_idx"] != -1].copy()
    
    # Sort and drop duplicates, retaining the best projected game for players with doubleheaders
    df_merged = df_merged.sort_values("sim_ev", ascending=False).drop_duplicates(subset=["firstName", "lastName"], keep="first")
    
    # Prepare player pool dicts
    player_pool = []
    for idx, r in df_merged.iterrows():
        player_pool.append({
            "firstName": r["firstName"],
            "lastName": r["lastName"],
            "team": r["team"],
            "opponent": r["opponent"],
            "positionGroup": r["positionGroup"],
            "salary": int(r["salary"]),
            "sim_ev": r["sim_ev"],
            "mc_ev": r["sim_ev"],
            "mc_p90": r["sim_p90"],
            "sim_idx": r["sim_idx"],
            "game_id": r["game_id"]
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
    team_mc_ev = run_local_search(player_pool, sim_matrix, 'MC_EV', ev_baseline, args.budget, restarts=LOCAL_SEARCH_RESTARTS)
    print("Running local search for MC Win 160...")
    team_mc_win_160 = run_local_search(player_pool, sim_matrix, 'MC_Win_Prob', ev_baseline, args.budget, target_win_score=160.0, restarts=LOCAL_SEARCH_RESTARTS)

    print("Running local search for MC Ceil 90...")
    team_mc_ceil_90 = run_local_search(player_pool, sim_matrix, 'MC_Ceiling_90', ev_baseline, args.budget, restarts=LOCAL_SEARCH_RESTARTS)
    
    # ── Consensus and Differential Options (Incorporating User Feedback) ─────────
    def clean_name(n):
        return (n or "").replace("'", "").replace("-", "").replace(".", "").replace(" ", "").lower()

    consensus_file = os.path.join(script_dir, "predicta", "advisory", f"week{args.week}_{args.year}_consensus_ownership.json")
    global_ownership = {}
    rival_rosters = {}
    team_mc_consensus = None
    team_mc_differential = None

    if os.path.exists(consensus_file):
        print(f"Loading consensus ownership data from {consensus_file}...")
        try:
            with open(consensus_file, "r", encoding="utf-8") as f:
                c_data = json.load(f)
            for item in c_data.get("global_top_25", []):
                global_ownership[item["clean_name"]] = item["rate"]
            rival_rosters = c_data.get("local_league_rosters", {})
        except Exception as e:
            print(f"Error loading consensus ownership: {e}")

        # 1. Consensus-Aligned Optimization
        from config import F2P_CONSENSUS_WEIGHT
        print(f"Running consensus-adjusted EV optimization (weight = {F2P_CONSENSUS_WEIGHT})...")
        player_pool_consensus = []
        for p in player_pool:
            p_clean = clean_name(p["firstName"] + p["lastName"])
            rate = global_ownership.get(p_clean, 0.0)
            p_copy = p.copy()
            p_copy["sim_ev"] = p["sim_ev"] * (1.0 + rate * F2P_CONSENSUS_WEIGHT)
            player_pool_consensus.append(p_copy)
            
        consensus_baseline = run_mc_ev_optimizer(player_pool_consensus, args.budget)
        if consensus_baseline:
            team_mc_consensus = run_local_search(player_pool_consensus, sim_matrix, 'MC_EV', consensus_baseline, args.budget, restarts=LOCAL_SEARCH_RESTARTS)

        # 2. Differential Compromise Optimization vs Top 3 Rivals
        if rival_rosters:
            print(f"Running differential optimization vs top local rivals...")
            rival_player_cols = {}
            for r_name, r_info in rival_rosters.items():
                rival_player_cols[r_name] = []
                for p_name in r_info.get("players", []):
                    p_clean = clean_name(p_name)
                    matched = False
                    for p in player_pool:
                        p_pool_clean = clean_name(p["firstName"] + p["lastName"])
                        if p_pool_clean == p_clean:
                            col_name = f"{p['firstName']}_{p['lastName']}_{p['game_id']}"
                            if col_name in df_sims.columns:
                                rival_player_cols[r_name].append(col_name)
                                matched = True
                                break
                    if not matched:
                        # Try loose matching (e.g. lastName check)
                        for p in player_pool:
                            if clean_name(p["lastName"]) == clean_name(p_name.split()[-1]):
                                col_name = f"{p['firstName']}_{p['lastName']}_{p['game_id']}"
                                if col_name in df_sims.columns:
                                    rival_player_cols[r_name].append(col_name)
                                    matched = True
                                    break
            
            rival_score_vectors = []
            for r_name, cols in rival_player_cols.items():
                if cols:
                    r_scores = df_sims[cols].sum(axis=1).values
                    rival_score_vectors.append(r_scores)
                else:
                    rival_score_vectors.append(np.zeros(10000))
            
            if rival_score_vectors:
                target_win_score = np.array(rival_score_vectors) # Shape (K, 10000)
                # Optimize to maximize average win probability vs all K rivals
                team_mc_differential = run_local_search(player_pool, sim_matrix, 'MC_Win_Prob', ev_baseline, args.budget, target_win_score=target_win_score, restarts=LOCAL_SEARCH_RESTARTS)

    # Cross-Reference Selections
    rosters = {
        "MC EV": team_mc_ev,
        "MC Win 160": team_mc_win_160,
        "MC Ceil 90": team_mc_ceil_90
    }
    if team_mc_consensus:
        rosters["MC Consensus"] = team_mc_consensus
    if team_mc_differential:
        rosters["MC Differential"] = team_mc_differential

    
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
    
    if slate_size < 4:
        recommended_strategy = "MC EV"
        recommended_reason = f"Short slate ({slate_size} games). Variance is compressed, so optimizing for highest expected floor with {recommended_strategy} is best."
    else:
        recommended_strategy = "MC Win 160"
        recommended_reason = f"Full slate ({slate_size} games). High player pool variance means optimizing for ceiling with {recommended_strategy} is best."

    # Append optimal selections to strategy roster CSVs
    for r_name, roster in rosters.items():
        if roster:
            suffix = r_name.lower().replace(" ", "_")
            csv_path = os.path.join(script_dir, f"rosters_{suffix}.csv")
            
            rows = []
            for p in roster:
                std_pos = get_standard_pos(p.get('positionGroup') or p.get('position'))
                rows.append({
                    "year": int(args.year),
                    "week": int(args.week),
                    "firstName": p["firstName"],
                    "lastName": p["lastName"],
                    "position": std_pos,
                    "salary": int(p["salary"]),
                    "eventId": p.get("game_id") or p.get("eventId")
                })
            df_new = pd.DataFrame(rows)
            if os.path.exists(csv_path):
                df_old = pd.read_csv(csv_path)
                df_old = df_old[~((df_old["year"] == int(args.year)) & (df_old["week"] == int(args.week)))]
                df_combined = pd.concat([df_old, df_new], ignore_index=True)
            else:
                df_combined = df_new
            df_combined.to_csv(csv_path, index=False)
            print(f"Appended optimal {r_name} selections to {csv_path}")

    print("Cross-referencing complete!")
    print(f"Consensus Core Players: {len(consensus_core)}")
    print(f"Budget Sleeper Options: {len(sleepers)}")

if __name__ == "__main__":
    main()
