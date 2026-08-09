"""
Official Baseline Archive Generator
------------------------------------
Executes the full production pipeline (02 -> 03 -> 04 -> 05 -> 06_optimize_lineups.py) across all evaluated weeks
in 2025 and 2026 to generate official baseline roster archives:
- baselines/rosters_mc_ev_baseline_{num}.csv
- baselines/rosters_mc_win_160_baseline_{num}.csv
- baselines/rosters_mc_ceil_90_baseline_{num}.csv

Usage:
  python generate_baseline_archive.py --baseline-num 11
"""

import os
import sys
import argparse
import subprocess
import shutil
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASELINES_DIR = os.path.join(SCRIPT_DIR, "baselines")

EVAL_WEEKS_2025 = [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14]
EVAL_WEEKS_2026 = [1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12]

def run_cmd(cmd, env=None, check=True):
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    res = subprocess.run(cmd, cwd=SCRIPT_DIR, env=full_env, capture_output=True, text=True)
    if res.returncode != 0 and check:
        print(f"FAILED command: {' '.join(cmd)}")
        print(res.stderr[-500:])
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return res

def main():
    parser = argparse.ArgumentParser(description="Official Baseline Archive Generator")
    parser.add_argument("--baseline-num", type=int, default=11, help="Baseline number (e.g. 11)")
    parser.add_argument("--env-vars", type=str, default="", help="Optional JSON string or key=val pairs of env vars")
    args = parser.parse_args()

    num = args.baseline_num
    print("\n==========================================================================")
    print(f" GENERATING OFFICIAL BASELINE {num} ARCHIVES USING PRODUCTION OPTIMIZER")
    print("==========================================================================")

    env = os.environ.copy()

    # Clear root roster CSVs before starting run
    for strat_key in ["mc_ev", "mc_win_160", "mc_ceil_90"]:
        root_path = os.path.join(SCRIPT_DIR, f"rosters_{strat_key}.csv")
        if os.path.exists(root_path):
            os.remove(root_path)

    for yr, weeks in [(2025, EVAL_WEEKS_2025), (2026, EVAL_WEEKS_2026)]:
        for w in weeks:
            print(f" -> Processing {yr} Week {w} Baseline {num} Production Pipeline...")
            run_cmd([sys.executable, "02_predict_probabilities.py", "--year", str(yr), "--week", str(w), "--boom-weight", "2.0"], env=env)
            run_cmd([sys.executable, "03_apply_roster_filter.py", "--year", str(yr), "--week", str(w), "--no-opt"], env=env)
            run_cmd([sys.executable, "04_simulate_monte_carlo.py", "--year", str(yr), "--week", str(w), "--sims", "10000"], env=env)
            run_cmd([sys.executable, "05_bake_mc_ev.py", str(yr), str(w)], env=env)
            run_cmd([sys.executable, "06_optimize_lineups.py", "--year", str(yr), "--week", str(w)], env=env)

    # Copy accumulated rosters to baselines/
    os.makedirs(BASELINES_DIR, exist_ok=True)
    for strat_key in ["mc_ev", "mc_win_160", "mc_ceil_90"]:
        root_path = os.path.join(SCRIPT_DIR, f"rosters_{strat_key}.csv")
        if os.path.exists(root_path):
            target_csv = os.path.join(BASELINES_DIR, f"rosters_{strat_key}_baseline_{num}.csv")
            shutil.copy2(root_path, target_csv)
            print(f"  -> Saved official Baseline {num} archive to {target_csv}")

    # Append actualPoints
    print("\nAppending actual points to baseline archives...")
    run_cmd([sys.executable, "scratch/append_actual_points.py"])

    # Print summary evaluation
    print("\n" + "="*80)
    print(f" BASELINE {num} OFFICIAL EVALUATION SUMMARY (PRODUCTION OPTIMIZER)")
    print("="*80)

    for strat_key in ["mc_ev", "mc_win_160", "mc_ceil_90"]:
        print(f"\n--- Strategy: {strat_key.upper()} ---")
        csv_path = os.path.join(BASELINES_DIR, f"rosters_{strat_key}_baseline_{num}.csv")
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            for yr, n_w in [(2025, len(EVAL_WEEKS_2025)), (2026, len(EVAL_WEEKS_2026))]:
                df_yr = df[df["year"] == yr]
                if "lineup_rank" in df_yr.columns:
                    df_yr = df_yr[df_yr["lineup_rank"] == 1]
                tot_pts = df_yr.groupby("week")["actualPoints"].sum().sum()
                avg_wk = tot_pts / n_w
                print(f"  {yr} Season ({n_w} weeks): Total = {tot_pts:.1f} pts | Avg/Wk = {avg_wk:.1f} pts/wk")

if __name__ == "__main__":
    main()
