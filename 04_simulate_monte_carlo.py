import json
import os
import argparse
import pandas as pd
import numpy as np
import scipy.stats as stats
import re
from utils import assign_position_group, assign_sub_position, calc_fantasy
import config
from config import LAMBDA_RECENCY, MC_POOL_BLENDING_ENABLED, MC_POOL_BLENDING_K, PACE_ADJUSTED_RATES_ENABLED

# ── Team Mapping ─────────────────────────────────────────────────────────────
TEAM_NAME_TO_ID = {
    "California Redwoods": "RED",
    "Denver Outlaws": "OUT",
    "Philadelphia Waterdogs": "WAT",
    "Boston Cannons": "CAN",
    "Maryland Whipsnakes": "WHP",
    "New York Atlas": "ATL",
    "Utah Archers": "ARC",
    "Carolina Chaos": "CHA",
}

# ── Historical Position-Pair Correlation Matrix (2023-2026 data) ────────────────
CORRELATIONS = {
    # Same-Team (teammates)
    ("same", "Attack", "Attack"): 0.124,
    ("same", "Defense", "Goalie"): -0.283,
    ("same", "Goalie", "SSDM"): -0.392,
    ("same", "Goalie", "LSM"): -0.254,
    ("same", "Faceoff", "Goalie"): -0.290,
    ("same", "Attack", "SSDM"): -0.227,
    
    # Cross-Team (matchups in same game)
    ("opp", "Faceoff", "Faceoff"): -0.435,
    ("opp", "Attack", "Goalie"): -0.182,
    ("opp", "Goalie", "Goalie"): -0.150,
    ("opp", "Attack", "SSDM"): -0.249,
    ("opp", "Goalie", "SSDM"): -0.389,
    ("opp", "Goalie", "LSM"): -0.283,
    ("opp", "Faceoff", "Midfield"): 0.094,
    ("opp", "Goalie", "Midfield"): -0.226,
    ("opp", "Defense", "Goalie"): -0.229,
}


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
            
            is_dnp = p.get("isDNP", False)
            if is_dnp:
                continue
                
            ident = p.get("identity", {})
            stats = p.get("stats", {})
            f2p = p.get("f2p", {})
            fp = f2p.get("totalPoints") if f2p.get("totalPoints") is not None else calc_fantasy(stats)
            
            pos_group = assign_position_group(ident.get("position"))
            if pos_group == "Goalie":
                saves = stats.get("saves", 0)
                ga = stats.get("goalsAgainst", 0)
                if saves == 0 and ga == 0 and fp == 0:
                    # Backup goalie didn't play
                    continue
            
            rows.append({
                "positionGroup": pos_group,
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

def clean_name(n):
    return (n or "").replace("'", "").replace("-", "").replace(".", "").replace(" ", "").lower()

def load_player_game_history(all_stats_path, target_year, target_week):
    """Loads all historical game-level actual fantasy points for each player up to target_week/target_year.
    Also computes dynamic leak-free position-pair correlations from this history."""
    with open(all_stats_path, encoding="utf-8") as f:
        data = json.load(f)
    
    player_games = {} # (clean_first, clean_last) -> list of points
    position_games = {} # posGroup -> list of points
    
    # Gather game player info for dynamic correlation calculation
    game_players = {}
    
    def get_corr_pos_local(pos_str):
        pos_str = str(pos_str).upper().strip()
        if pos_str in ["A", "ATTACK"]: return "Attack"
        if pos_str in ["M", "MIDFIELD", "MID"]: return "Midfield"
        if pos_str == "SSDM": return "SSDM"
        if pos_str == "LSM": return "LSM"
        if pos_str in ["D", "DEFENSE", "DEFENSEMEN", "DEF"]: return "Defense"
        if pos_str in ["FO", "FACEOFF"]: return "Faceoff"
        if pos_str in ["G", "GOALIE"]: return "Goalie"
        return "Unknown"
    
    for slug, p_data in data.items():
        for entry in p_data.get("stats", []):
            ident = entry.get("identity", {})
            stats_dict = entry.get("stats", {})
            f2p = entry.get("f2p", {})
            evt = entry.get("event", {})
            e_id = evt.get("eventId", "")
            
            # Extract year from eventId
            yr_match = re.search(r'^(\d{4})_', e_id)
            yr = int(yr_match.group(1)) if yr_match else None
            w = entry.get("week")
            
            # Data leakage prevention
            if yr is not None and (yr > target_year or (yr == target_year and w is not None and w >= target_week)):
                continue
                
            is_dnp = entry.get("isDNP", False)
            if is_dnp:
                continue
                
            pts = f2p.get("totalPoints") if f2p.get("totalPoints") is not None else calc_fantasy(stats_dict)
            pos = assign_position_group(ident.get("position"))
            
            # Goalie backup check
            if pos == "Goalie":
                saves = stats_dict.get("saves", 0)
                ga = stats_dict.get("goalsAgainst", 0)
                if saves == 0 and ga == 0 and pts == 0:
                    continue
            
            first_c = clean_name(ident.get("firstName"))
            last_c = clean_name(ident.get("lastName"))
            key = (first_c, last_c)
            
            player_games.setdefault(key, []).append((pts, yr, w))
            position_games.setdefault(pos, []).append((pts, yr, w))
            
            # Record for dynamic correlations
            c_pos = get_corr_pos_local(ident.get("position"))
            team = ident.get("team")
            if c_pos != "Unknown" and team and e_id:
                game_players.setdefault(e_id, []).append({
                    "team": team,
                    "corr_pos": c_pos,
                    "points": pts
                })
                
    # Now compute correlations dynamically from the gathered game_players
    pair_values = {}
    for e_id, players in game_players.items():
        num_p = len(players)
        for i in range(num_p):
            for j in range(i+1, num_p):
                p1 = players[i]
                p2 = players[j]
                
                is_same = p1["team"] == p2["team"]
                rel_type = "same" if is_same else "opp"
                
                key = (rel_type,) + tuple(sorted([p1["corr_pos"], p2["corr_pos"]]))
                pair_values.setdefault(key, ([], []))
                
                pair_values[key][0].append(p1["points"])
                pair_values[key][1].append(p2["points"])
                # For symmetric position groups on the same team, append reverse to ensure symmetry
                if is_same and p1["corr_pos"] == p2["corr_pos"]:
                    pair_values[key][0].append(p2["points"])
                    pair_values[key][1].append(p1["points"])
                    
    dynamic_correlations = {}
    for key, (x, y) in pair_values.items():
        if len(x) >= 15:
            r, _ = stats.pearsonr(x, y)
            if not np.isnan(r):
                dynamic_correlations[key] = float(np.clip(r, -0.99, 0.99))
                
    return player_games, position_games, dynamic_correlations

def make_pos_semidefinite(matrix):
    """Finds the nearest positive semi-definite matrix by clipping negative eigenvalues."""
    eigenvalues, eigenvectors = np.linalg.eigh(matrix)
    # Clip negative eigenvalues to a small positive value
    eigenvalues = np.maximum(eigenvalues, 1e-6)
    # Reconstruct the matrix
    psd_matrix = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
    # Re-normalize diagonal to 1.0 (correlation matrix property)
    d = np.diag(psd_matrix)
    stddev = np.sqrt(d)
    psd_matrix = psd_matrix / np.outer(stddev, stddev)
    return psd_matrix

def main():
    parser = argparse.ArgumentParser(description="Monte Carlo Fantasy Points Simulator")
    parser.add_argument("--year", type=int, default=2025, help="Target year")
    parser.add_argument("--week", type=int, default=1, help="Target week")
    parser.add_argument("--sims", type=int, default=10000, help="Number of simulation runs")
    parser.add_argument("--correlated", action="store_true", default=True, help="Use correlation copula")
    parser.add_argument("--no-correlation", action="store_false", dest="correlated", help="Disable correlation copula")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for numpy reproducibility")
    args = parser.parse_args()
    
    np.random.seed(args.seed)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    predictions_dir = os.path.join(script_dir, "predicta", "predictions")
    
    # 1. Load predictions to get target players and predicted Boom probabilities
    preds_file = os.path.join(predictions_dir, f"week{args.week}_{args.year}_predictions.csv")
    if not os.path.exists(preds_file):
        # Fallback to legacy path
        preds_file = os.path.join(script_dir, f"week{args.week}_{args.year}_predictions.csv")
    
    if not os.path.exists(preds_file):
        print(f"Error: Predictions file not found for {args.year} Week {args.week}. Please run predictions first.")
        return

    # Sanity check for stale predictions
    raw_preds_file = os.path.join(predictions_dir, f"week{args.week}_{args.year}_predictions_raw.csv")
    if os.path.exists(raw_preds_file) and os.path.exists(preds_file):
        if os.path.getmtime(raw_preds_file) > os.path.getmtime(preds_file):
            print("\n" + "!"*80)
            print(f"WARNING: The raw predictions file '{raw_preds_file}' is newer than the filtered predictions file '{preds_file}'.")
            print("This suggests that '03_apply_roster_filter.py' has not been run after the last prediction run.")
            print("You may be using stale predictions! Please run '03_apply_roster_filter.py' first.")
            print("!"*80 + "\n")
        
    df_preds = pd.read_csv(preds_file)
    print(f"Loaded {len(df_preds)} player-game prediction rows.")
    
    # 2. Calculate EV dynamically for each row
    df_hist = load_historical_data(args.year, args.week, script_dir)
    tier_avgs = calculate_tier_averages(df_hist)
    
    # Calculate EV dynamically for each row
    use_pred_pts_ev = getattr(config, "USE_PREDICTED_POINTS_FOR_EV", False) or (os.environ.get("USE_PREDICTED_POINTS_FOR_EV", "False") == "True")
    use_player_anchored_ev = getattr(config, "USE_PLAYER_ANCHORED_EV", True) and (os.environ.get("USE_PLAYER_ANCHORED_EV", "True") == "True")

    if use_player_anchored_ev and "BoomProbability" in df_preds.columns:
        window_choice = os.environ.get("EV_WINDOW_GAMES", "all").strip().lower()
        def calc_player_anchored_ev(r):
            if window_choice == "all":
                base_fp = r.get("fp_season_avg") if pd.notna(r.get("fp_season_avg")) and float(r.get("fp_season_avg", 0)) > 2.0 else tier_avgs.get(r["positionGroup"], {}).get("NonBoom", 8.0)
            else:
                col_name = f"fp_last{window_choice}_avg"
                raw_fp = r.get(col_name) if col_name in r else r.get("fp_season_avg")
                n_games = float(r.get("n_games_played", 0) or 0)
                
                sal = float(r.get("salary", 10) or 10)
                pos = r.get("positionGroup", "Attack")
                nonboom_default = tier_avgs.get(pos, {}).get("NonBoom", 8.0)
                prior_fp = (sal / 1.3333) if (sal > 0 and sal != 10) else nonboom_default
                prior_fp = max(5.0, min(22.0, prior_fp))
                
                K = float(os.environ.get("EV_SHRINKAGE_K", "5.0"))
                if n_games == 0 or pd.isna(raw_fp) or float(raw_fp or 0) <= 0.0:
                    base_fp = prior_fp
                else:
                    weight = n_games / (n_games + K)
                    base_fp = weight * float(raw_fp) + (1.0 - weight) * prior_fp
            
            boom_p = float(r.get("BoomProbability", 25.0)) / 100.0
            matchup_mult = 0.5 + boom_p
            return float(base_fp) * matchup_mult
        df_preds["EV"] = df_preds.apply(calc_player_anchored_ev, axis=1)
    elif use_pred_pts_ev and "PredictedPoints" in df_preds.columns:
        df_preds["EV"] = df_preds["PredictedPoints"]
    elif "BoomProbability" in df_preds.columns:
        df_preds["EV"] = df_preds.apply(lambda r: (r["BoomProbability"] / 100.0) * tier_avgs.get(r["positionGroup"], {}).get("Boom", 25.0) + (1.0 - r["BoomProbability"] / 100.0) * tier_avgs.get(r["positionGroup"], {}).get("NonBoom", 8.0), axis=1)
    elif "PredictedPoints" in df_preds.columns:
        df_preds["EV"] = df_preds["PredictedPoints"]
    else:
        df_preds["EV"] = 10.0
        
    # 3. Load historical player and position game pools
    all_stats_path = os.path.join(script_dir, "all_players_stats.json")
    if not os.path.exists(all_stats_path):
        print(f"Error: {all_stats_path} not found.")
        return
        
    print("Loading player game histories...")
    player_histories, position_histories, dynamic_correlations = load_player_game_history(all_stats_path, args.year, args.week)
    
    # 4. Prepare multipliers and sorted historical pools for each row in df_preds
    pools = []
    cdfs = []
    multipliers = []
    
    # Pre-compute position-wide normalized pools and recency weights to avoid redundant calculations
    pos_pool_info = {}
    if MC_POOL_BLENDING_ENABLED:
        for pos in ["Attack", "Midfield", "Defense", "Faceoff", "Goalie"]:
            pos_hist = position_histories.get(pos, [(8.0, args.year, args.week)])
            sorted_pos_hist = sorted(pos_hist, key=lambda x: x[0])
            
            pos_pool = [x[0] for x in sorted_pos_hist]
            pos_weights = []
            for pt, yr, w in sorted_pos_hist:
                if yr is None or w is None:
                    weeks_ago = 10
                else:
                    weeks_ago = (args.year * 22 + args.week) - (yr * 22 + w)
                    weeks_ago = max(0, weeks_ago)
                weight = np.exp(-LAMBDA_RECENCY * weeks_ago)
                pos_weights.append(weight)
            
            pos_weights_arr = np.array(pos_weights)
            pos_weights_sum = np.sum(pos_weights_arr)
            if pos_weights_sum > 0:
                pos_weights_normalized = pos_weights_arr / pos_weights_sum
            else:
                pos_weights_normalized = np.ones(len(pos_pool)) / len(pos_pool)
                
            pos_pool_info[pos] = {
                "pool": np.array(pos_pool),
                "weights": pos_weights_normalized
            }
            
    for idx, r in df_preds.iterrows():
        first_c = clean_name(r["firstName"])
        last_c = clean_name(r["lastName"])
        pos = r["positionGroup"]
        
        hist = player_histories.get((first_c, last_c), [])
        
        if MC_POOL_BLENDING_ENABLED:
            n_games = len(hist)
            alpha = min(1.0, n_games / MC_POOL_BLENDING_K)
            
            if alpha == 0:
                # 100% position pool
                p_info = pos_pool_info.get(pos, {"pool": np.array([8.0]), "weights": np.array([1.0])})
                pool = p_info["pool"]
                weights = p_info["weights"]
            elif alpha == 1.0:
                # 100% player pool
                sorted_hist = sorted(hist, key=lambda x: x[0])
                pool = np.array([x[0] for x in sorted_hist])
                player_weights = []
                for pt, yr, w in sorted_hist:
                    if yr is None or w is None:
                        weeks_ago = 10
                    else:
                        weeks_ago = (args.year * 22 + args.week) - (yr * 22 + w)
                        weeks_ago = max(0, weeks_ago)
                    weight = np.exp(-LAMBDA_RECENCY * weeks_ago)
                    player_weights.append(weight)
                
                weights = np.array(player_weights)
                weights_sum = np.sum(weights)
                if weights_sum > 0:
                    weights = weights / weights_sum
                else:
                    weights = np.ones(len(pool)) / len(pool)
            else:
                # Blend player pool and position pool
                # 1. Sort player history and compute normalized recency weights
                sorted_hist = sorted(hist, key=lambda x: x[0])
                player_pool = np.array([x[0] for x in sorted_hist])
                player_weights = []
                for pt, yr, w in sorted_hist:
                    if yr is None or w is None:
                        weeks_ago = 10
                    else:
                        weeks_ago = (args.year * 22 + args.week) - (yr * 22 + w)
                        weeks_ago = max(0, weeks_ago)
                    weight = np.exp(-LAMBDA_RECENCY * weeks_ago)
                    player_weights.append(weight)
                
                player_weights = np.array(player_weights)
                player_weights_sum = np.sum(player_weights)
                if player_weights_sum > 0:
                    player_weights = player_weights / player_weights_sum
                else:
                    player_weights = np.ones(len(player_pool)) / len(player_pool)
                    
                # 2. Get precomputed position pool
                p_info = pos_pool_info.get(pos, {"pool": np.array([8.0]), "weights": np.array([1.0])})
                pos_pool = p_info["pool"]
                pos_weights = p_info["weights"]
                
                # 3. Scale normalized weights by alpha / (1 - alpha)
                combined = []
                for pt, w in zip(player_pool, player_weights):
                    combined.append((pt, alpha * w))
                for pt, w in zip(pos_pool, pos_weights):
                    combined.append((pt, (1.0 - alpha) * w))
                    
                # Sort combined list by points ascending to preserve CDF lookup structure
                combined = sorted(combined, key=lambda x: x[0])
                
                pool = np.array([x[0] for x in combined])
                weights = np.array([x[1] for x in combined])
            
            # Compute CDF and hist_avg directly from blended/pre-normalized pool
            hist_avg = np.average(pool, weights=weights)
            cdf = np.cumsum(weights)
        else:
            # Legacy behavior: Determine base pool and historical average
            if len(hist) >= 5:
                raw_hist = hist
            else:
                # Fallback to position group
                raw_hist = position_histories.get(pos, [(8.0, args.year, args.week)])
                
            # Sort history by points ascending to support CDF
            raw_hist = sorted(raw_hist, key=lambda x: x[0])
            
            pool = []
            weights = []
            for pt, yr, w in raw_hist:
                if yr is None or w is None:
                    weeks_ago = 10
                else:
                    # 14 regular weeks + 8 offseason weeks = 22 weeks per year
                    weeks_ago = (args.year * 22 + args.week) - (yr * 22 + w)
                    weeks_ago = max(0, weeks_ago)
                    
                weight = np.exp(-LAMBDA_RECENCY * weeks_ago)
                pool.append(pt)
                weights.append(weight)
                
            weights_array = np.array(weights)
            weight_sum = np.sum(weights_array)
            
            if weight_sum > 0:
                hist_avg = np.average(pool, weights=weights_array)
                cdf = np.cumsum(weights_array / weight_sum)
            else:
                hist_avg = np.mean(pool)
                cdf = np.linspace(1.0/len(pool), 1.0, len(pool))
                
        if hist_avg <= 0.1:
            hist_avg = 0.1
            
        # Matchup scaling multiplier
        mult = r["EV"] / hist_avg
        
        if PACE_ADJUSTED_RATES_ENABLED and "game_pace" in r:
            mult = mult * r["game_pace"]
            
        # Clip multiplier to prevent extreme scaling
        mult = np.clip(mult, 0.2, 2.5)
        
        pools.append(np.array(pool))
        cdfs.append(cdf)
        multipliers.append(mult)
        
    num_players = len(df_preds)
    
    # 5. Generate simulations
    print(f"Running simulation ({args.sims} runs, correlated={args.correlated})...")
    
    if args.correlated and num_players > 1:
        # Build correlation matrix C
        C = np.eye(num_players)
        
        # Standardize position names for correlation dictionary
        def get_corr_pos(p):
            sub_pos = p.get("subPosition") or p.get("positionGroup") or p.get("position")
            sub_pos = str(sub_pos).upper().strip()
            if sub_pos in ["A", "ATTACK"]: return "Attack"
            if sub_pos in ["M", "MIDFIELD", "MID"]: return "Midfield"
            if sub_pos == "SSDM": return "SSDM"
            if sub_pos == "LSM": return "LSM"
            if sub_pos in ["D", "DEFENSE", "DEFENSEMEN", "DEF"]: return "Defense"
            if sub_pos in ["FO", "FACEOFF"]: return "Faceoff"
            if sub_pos in ["G", "GOALIE"]: return "Goalie"
            return "Unknown"
            
        for i in range(num_players):
            for j in range(i+1, num_players):
                p1 = df_preds.iloc[i]
                p2 = df_preds.iloc[j]
                
                is_same = p1["team"] == p2["team"]
                rel_type = "same" if is_same else "opp"
                
                # Check if they are in the same game
                is_opponent = False
                if not is_same:
                    is_opponent = p1["game_id"] == p2["game_id"]
                    
                if is_same or is_opponent:
                    pos1 = get_corr_pos(p1)
                    pos2 = get_corr_pos(p2)
                    sorted_pos = tuple(sorted([pos1, pos2]))
                    lookup_key = (rel_type,) + sorted_pos
                    corr = dynamic_correlations.get(lookup_key, CORRELATIONS.get(lookup_key, 0.0))
                    if corr != 0.0:
                        C[i, j] = corr
                        C[j, i] = corr
                        
        # Ensure positive semi-definite
        C = make_pos_semidefinite(C)
        
        # Sample from Multivariate Normal
        Z = np.random.multivariate_normal(np.zeros(num_players), C, size=args.sims)
        # Convert to uniform variables
        U = stats.norm.cdf(Z) # shape (args.sims, num_players)
    else:
        # Independent uniform draws
        U = np.random.uniform(0.0, 1.0, size=(args.sims, num_players))
        
    # Apply inverse transform sampling to get player simulated points
    sim_results = np.zeros((args.sims, num_players))
    
    for i in range(num_players):
        pool = pools[i]
        cdf = cdfs[i]
        mult = multipliers[i]
        M = len(pool)
        
        # Map uniform values to indices using weighted CDF
        indices = np.searchsorted(cdf, U[:, i])
        indices = np.clip(indices, 0, M - 1)
        
        # Gather historical scores and scale by multiplier
        raw_scores = pool[indices]
        sim_results[:, i] = np.maximum(0.0, raw_scores * mult)
        
    # 6. Save simulations
    # Output is a CSV file where columns are player keys (firstName_lastName_gameId) and rows are runs
    columns = []
    for idx, r in df_preds.iterrows():
        # Clean naming format
        col_name = f"{r['firstName']}_{r['lastName']}_{r['game_id']}"
        columns.append(col_name)
        
    df_sims = pd.DataFrame(sim_results, columns=columns)
    
    # Save simulations CSV
    output_dir = os.path.join(script_dir, "predicta", "predictions")
    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, f"week{args.week}_{args.year}_simulations.csv")
    df_sims.to_csv(out_file, index=False)
    print(f"Successfully saved {args.sims} simulations to {out_file}")
    
    # 7. Pre-compute and save simulation stats (Item 11)
    stats_summary = {}
    for i, col_name in enumerate(columns):
        col_data = sim_results[:, i]
        stats_summary[col_name] = {
            "mc_ev":  round(float(np.mean(col_data)), 2),
            "mc_std": round(float(np.std(col_data)), 2),
            "mc_p10": round(float(np.percentile(col_data, 10)), 2),
            "mc_p25": round(float(np.percentile(col_data, 25)), 2),
            "mc_p75": round(float(np.percentile(col_data, 75)), 2),
            "mc_p90": round(float(np.percentile(col_data, 90)), 2)
        }
        
    stats_file = os.path.join(output_dir, f"week{args.week}_{args.year}_simulation_stats.json")
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats_summary, f, indent=4)
    print(f"Successfully saved pre-computed simulation stats to {stats_file}")
    
if __name__ == "__main__":
    main()
