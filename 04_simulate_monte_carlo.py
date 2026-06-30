import json
import os
import argparse
import pandas as pd
import numpy as np
import scipy.stats as stats
import re
from utils import assign_position_group, assign_sub_position, calc_fantasy
from config import LAMBDA_RECENCY

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
    """Loads all historical game-level actual fantasy points for each player up to target_week/target_year."""
    with open(all_stats_path, encoding="utf-8") as f:
        data = json.load(f)
    
    player_games = {} # (clean_first, clean_last) -> list of points
    position_games = {} # posGroup -> list of points
    
    for slug, p_data in data.items():
        for entry in p_data.get("stats", []):
            ident = entry.get("identity", {})
            stats = entry.get("stats", {})
            f2p = entry.get("f2p", {})
            evt = entry.get("event", {})
            e_id = evt.get("eventId", "")
            
            # Extract year from eventId
            yr_match = re.search(r'^(\d{4})_', e_id)
            yr = int(yr_match.group(1)) if yr_match else None
            w = entry.get("week")
            
            # Data leakage prevention
            if yr == target_year and w is not None and w >= target_week:
                continue
                
            is_dnp = entry.get("isDNP", False)
            if is_dnp:
                continue
                
            pts = f2p.get("totalPoints") if f2p.get("totalPoints") is not None else calc_fantasy(stats)
            pos = assign_position_group(ident.get("position"))
            
            # Goalie backup check
            if pos == "Goalie":
                saves = stats.get("saves", 0)
                ga = stats.get("goalsAgainst", 0)
                if saves == 0 and ga == 0 and pts == 0:
                    continue
            
            first_c = clean_name(ident.get("firstName"))
            last_c = clean_name(ident.get("lastName"))
            key = (first_c, last_c)
            
            player_games.setdefault(key, []).append((pts, yr, w))
            position_games.setdefault(pos, []).append((pts, yr, w))
            
    return player_games, position_games

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
        
    df_preds = pd.read_csv(preds_file)
    print(f"Loaded {len(df_preds)} player-game prediction rows.")
    
    # 2. Calculate EV dynamically for each row
    df_hist = load_historical_data(args.year, args.week, script_dir)
    tier_avgs = calculate_tier_averages(df_hist)
    
    # Calculate EV from BoomProbability (with default fallback)
    if "BoomProbability" in df_preds.columns:
        df_preds["EV"] = df_preds.apply(lambda r: (r["BoomProbability"] / 100.0) * tier_avgs.get(r["positionGroup"], {}).get("Boom", 25.0) + (1.0 - r["BoomProbability"] / 100.0) * tier_avgs.get(r["positionGroup"], {}).get("NonBoom", 8.0), axis=1)
    else:
        df_preds["EV"] = 10.0
        
    # 3. Load historical player and position game pools
    all_stats_path = os.path.join(script_dir, "all_players_stats.json")
    if not os.path.exists(all_stats_path):
        print(f"Error: {all_stats_path} not found.")
        return
        
    print("Loading player game histories...")
    player_histories, position_histories = load_player_game_history(all_stats_path, args.year, args.week)
    
    # 4. Prepare multipliers and sorted historical pools for each row in df_preds
    pools = []
    cdfs = []
    multipliers = []
    
    for idx, r in df_preds.iterrows():
        first_c = clean_name(r["firstName"])
        last_c = clean_name(r["lastName"])
        pos = r["positionGroup"]
        
        hist = player_histories.get((first_c, last_c), [])
        
        # Determine base pool and historical average
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
                    corr = CORRELATIONS.get(lookup_key, 0.0)
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
    
if __name__ == "__main__":
    main()
