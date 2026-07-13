"""
Baseline 5 Full Backtest Runner
================================
Runs the complete prediction -> filter -> simulation -> optimize pipeline for all historical
weeks in 2025 (1-14) and 2026 (1-8) to produce Baseline 5 rosters (which include asymmetric
class weighting for Boom recall). Outputs rosters_mc_*_baseline_5.csv files in the baselines/ directory.

Usage:
    python scratch/run_baseline5_backtest.py
"""

import subprocess
import sys
import os
import shutil

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # scripts/

SEASONS = {
    2025: [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14],  # 13 weeks (Week 6 is All-Star)
    2026: [1, 2, 3, 4, 5, 6, 8],                        # 7 weeks (Week 7 is All-Star)
}

ROSTER_FILES = [
    "rosters_mc_ev.csv",
    "rosters_mc_win_160.csv",
    "rosters_mc_ceil_90.csv",
    "rosters_mc_win_180.csv",
    "rosters_mc_consensus.csv",
    "rosters_mc_differential.csv",
]


def run(cmd, desc):
    print(f"\n  >> {desc}")
    print(f"     {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=SCRIPT_DIR, capture_output=False)
    if result.returncode != 0:
        print(f"  [WARN] Command exited with code {result.returncode}. Continuing...")
    return result.returncode == 0


def main():
    print("=" * 70)
    print(" BASELINE 5 FULL BACKTEST RUNNER")
    print(" Asymmetric Class Weighting (Boom Weight = 2.0)")
    print("=" * 70)

    # Step 1: Clear root-level roster CSV files so we start from blank slate
    print("\n[1/3] Clearing stale root-level roster files...")
    for fname in ROSTER_FILES:
        fpath = os.path.join(SCRIPT_DIR, fname)
        if os.path.exists(fpath):
            os.remove(fpath)
            print(f"  Deleted: {fname}")
        else:
            print(f"  (Not found, skipping): {fname}")

    # Also clean the predictions folder to ensure no stale predictions/simulations are reused
    predictions_folder = os.path.join(SCRIPT_DIR, "predicta", "predictions")
    if os.path.exists(predictions_folder):
        print(f"\nCleaning predictions folder: {predictions_folder} ...")
        for f in os.listdir(predictions_folder):
            if f.endswith(".csv") or f.endswith(".json"):
                fpath = os.path.join(predictions_folder, f)
                try:
                    if os.path.isfile(fpath):
                        os.remove(fpath)
                except Exception as e:
                    print(f"  Failed to delete {fpath}: {e}")

    # Step 2: Run the full pipeline for each year/week
    print("\n[2/3] Running full pipeline for all seasons/weeks...")
    total_weeks = sum(len(wks) for wks in SEASONS.values())
    done = 0

    for year, weeks in SEASONS.items():
        print(f"\n{'='*70}")
        print(f"  SEASON {year}")
        print(f"{'='*70}")
        for week in weeks:
            done += 1
            print(f"\n--- [{done}/{total_weeks}] Year {year}, Week {week} ---")

            # 1. Predictions (uses default boom-weight 2.0!)
            run(
                [sys.executable, "02_predict_probabilities.py", "--year", str(year), "--week", str(week)],
                f"Generating predictions ({year} W{week})"
            )

            # 1.5. Roster Filter
            run(
                [sys.executable, "03_apply_roster_filter.py", "--year", str(year), "--week", str(week), "--no-opt"],
                f"Applying roster filter ({year} W{week})"
            )

            # 2. Monte Carlo simulations (10,000 trials)
            run(
                [sys.executable, "04_simulate_monte_carlo.py", "--year", str(year), "--week", str(week), "--sims", "10000"],
                f"Running Monte Carlo simulations ({year} W{week})"
            )

            # 3. Bake simulation stats (mc_ev, mc_p90, etc.)
            run(
                [sys.executable, "05_bake_mc_ev.py", str(year), str(week)],
                f"Baking MC EV stats ({year} W{week})"
            )

            # 4. Optimize lineups (appends to rosters_mc_*.csv)
            run(
                [sys.executable, "06_optimize_lineups.py", "--year", str(year), "--week", str(week)],
                f"Optimizing lineups ({year} W{week})"
            )

    # Step 3: Copy root roster files to baselines/ as baseline_5 artifacts
    print("\n[3/3] Archiving rosters to baselines/ as baseline_5 files...")
    baselines_dir = os.path.join(SCRIPT_DIR, "baselines")
    os.makedirs(baselines_dir, exist_ok=True)

    strategy_map = {
        "rosters_mc_ev.csv":          "rosters_mc_ev_baseline_5.csv",
        "rosters_mc_win_160.csv":     "rosters_mc_win_160_baseline_5.csv",
        "rosters_mc_ceil_90.csv":     "rosters_mc_ceil_90_baseline_5.csv",
        "rosters_mc_win_180.csv":     "rosters_mc_win_180_baseline_5.csv",
    }

    for src_name, dst_name in strategy_map.items():
        src = os.path.join(SCRIPT_DIR, src_name)
        dst = os.path.join(baselines_dir, dst_name)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"  Archived: {src_name} -> baselines/{dst_name}")
        else:
            print(f"  [WARN] Source not found (no data?): {src_name}")

    print("\n" + "=" * 70)
    print(" BACKTEST COMPLETE")
    print(" Baseline 5 roster files are in baselines/")
    print(" Next step: Run the evaluation harness on these baseline_5 rosters")
    print("=" * 70)


if __name__ == "__main__":
    main()
