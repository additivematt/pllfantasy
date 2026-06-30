"""
bake_mc_ev.py
Reads week{N}_{YEAR}_simulations.csv files, computes per-player MC Expected Value
(mean of simulated outcomes) and MC Std Dev (standard deviation = risk/volatility),
and bakes `mc_ev` and `mc_std` into the static predictions JSON files at
predicta/predictions/{YEAR}/{WEEK}.

Usage:
    python bake_mc_ev.py              # Process all available weeks
    python bake_mc_ev.py 2026 4       # Process a specific year/week
"""

import os
import re
import sys
import json
import glob
import pandas as pd

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PREDICTA_DIR = os.path.join(SCRIPTS_DIR, "predicta", "predictions")


def get_available_weeks():
    """Scan for simulation CSVs to find available year/week pairs."""
    pattern = os.path.join(PREDICTA_DIR, "week*_simulations.csv")
    files = glob.glob(pattern)
    weeks = []
    for filepath in files:
        filename = os.path.basename(filepath)
        match = re.match(r"week(\d+)_(\d+)_simulations\.csv", filename)
        if match:
            week = int(match.group(1))
            year = int(match.group(2))
            weeks.append((year, week))
    return sorted(weeks)


def parse_sim_columns(df):
    """
    Parse simulation CSV columns into a dict:
      {(firstName, lastName, game_id): {"ev": float, "std": float}}
    """
    stats_map = {}
    for col in df.columns:
        match = re.match(r"^(.+?)_(\d{4}-ev-\d+)$", col)
        if not match:
            parts = col.rsplit("_", 1)
            if len(parts) == 2 and re.match(r"\d{4}-ev-\d+", parts[1]):
                name_part = parts[0]
                game_id = parts[1]
            else:
                print(f"    [WARN] Cannot parse column: {col}")
                continue
        else:
            name_part = match.group(1)
            game_id = match.group(2)

        name_parts = name_part.split("_")
        firstName = name_parts[0]
        lastName = "_".join(name_parts[1:]) if len(name_parts) > 1 else ""

        col_data = df[col]
        stats_map[(firstName, lastName, game_id)] = {
            "ev":  round(float(col_data.mean()), 2),
            "std": round(float(col_data.std()), 2),
            "p90": round(float(col_data.quantile(0.9)), 2),
        }

    return stats_map


def find_player_stats(first, last, game_id, stats_map):
    """Look up a player's stats by exact key, then fuzzy (strip non-alpha)."""
    key = (first, last, game_id)
    if key in stats_map:
        return stats_map[key]

    f_c = re.sub(r"[^a-zA-Z]", "", first)
    l_c = re.sub(r"[^a-zA-Z]", "", last)
    for (f2, l2, g2), stats in stats_map.items():
        if g2 == game_id and re.sub(r"[^a-zA-Z]", "", f2) == f_c and re.sub(r"[^a-zA-Z]", "", l2) == l_c:
            return stats
    return None


def bake_week(year, week):
    """Compute MC EV + Std and update the static predictions JSON for a given year/week."""
    json_path = os.path.join(PREDICTA_DIR, str(year), str(week))
    if not os.path.exists(json_path):
        print(f"  [SKIP] No static predictions JSON: {json_path}")
        return False

    sim_path = os.path.join(PREDICTA_DIR, f"week{week}_{year}_simulations.csv")
    if not os.path.exists(sim_path):
        print(f"  [SKIP] No simulation file: {sim_path}")
        return False

    print(f"  Loading simulations: {sim_path} ...", end="", flush=True)
    df = pd.read_csv(sim_path)
    print(f" {len(df)} trials, {len(df.columns)} players")

    stats_map = parse_sim_columns(df)

    with open(json_path, "r", encoding="utf-8") as f:
        players = json.load(f)

    updated = 0
    not_found = 0
    for p in players:
        first = p.get("firstName", "")
        last = p.get("lastName", "")
        game_id = p.get("game_id", "")

        stats = find_player_stats(first, last, game_id, stats_map)
        if stats:
            p["mc_ev"]  = stats["ev"]
            p["mc_std"] = stats["std"]
            p["mc_p90"] = stats["p90"]
            updated += 1
        else:
            not_found += 1
            print(f"    [MISS] {first} {last} ({game_id})")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(players, f)

    print(f"  [{year} W{week}] Updated {updated} players, {not_found} not matched.")
    return True


def main():
    if len(sys.argv) == 3:
        year, week = int(sys.argv[1]), int(sys.argv[2])
        pairs = [(year, week)]
    else:
        pairs = get_available_weeks()
        print(f"Found {len(pairs)} simulation files to process.")

    for year, week in pairs:
        print(f"\nProcessing {year} Week {week}...")
        bake_week(year, week)

    print("\nDone.")


if __name__ == "__main__":
    main()
