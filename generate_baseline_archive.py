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
from utils import get_eval_weeks, get_latest_baseline_num

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASELINES_DIR = os.path.join(SCRIPT_DIR, "baselines")

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
    default_base = get_latest_baseline_num()
    parser = argparse.ArgumentParser(description="Official Baseline Archive Generator")
    parser.add_argument("--baseline-num", type=int, default=default_base, help=f"Baseline number (default: {default_base})")
    parser.add_argument("--year", type=int, default=None, help="Specific year to process/append (e.g. 2026)")
    parser.add_argument("--week", type=int, default=None, help="Specific week to process/append (e.g. 13)")
    parser.add_argument("--env-vars", type=str, default="", help="Optional JSON string or key=val pairs of env vars")
    args = parser.parse_args()

    num = args.baseline_num
    env = os.environ.copy()

    is_incremental = (args.year is not None) and (args.week is not None)

    if is_incremental:
        print("\n==========================================================================")
        print(f" INCREMENTALLY APPENDING {args.year} WEEK {args.week} TO BASELINE {num}")
        print("==========================================================================")
        weeks_to_process = [(args.year, [args.week])]
    else:
        print("\n==========================================================================")
        print(f" GENERATING OFFICIAL BASELINE {num} ARCHIVES USING PRODUCTION OPTIMIZER")
        print("==========================================================================")
        # Clear root roster CSVs only during full baseline regeneration
        for strat_key in ["mc_ev", "mc_win_160", "mc_ceil_90"]:
            root_path = os.path.join(SCRIPT_DIR, f"rosters_{strat_key}.csv")
            if os.path.exists(root_path):
                os.remove(root_path)
        weeks_to_process = [(2025, get_eval_weeks(2025)), (2026, get_eval_weeks(2026))]

    for yr, weeks in weeks_to_process:
        for w in weeks:
            print(f" -> Processing {yr} Week {w} Baseline {num} Production Pipeline...")
            run_cmd([sys.executable, "02_predict_probabilities.py", "--year", str(yr), "--week", str(w), "--boom-weight", "2.0"], env=env)
            run_cmd([sys.executable, "03_apply_roster_filter.py", "--year", str(yr), "--week", str(w), "--no-opt"], env=env)
            run_cmd([sys.executable, "04_simulate_monte_carlo.py", "--year", str(yr), "--week", str(w), "--sims", "10000"], env=env)
            run_cmd([sys.executable, "05_bake_mc_ev.py", str(yr), str(w)], env=env)
            run_cmd([sys.executable, "06_optimize_lineups.py", "--year", str(yr), "--week", str(w)], env=env)

    # Sync root rosters to baseline archive CSVs
    os.makedirs(BASELINES_DIR, exist_ok=True)
    for strat_key in ["mc_ev", "mc_win_160", "mc_ceil_90"]:
        root_path = os.path.join(SCRIPT_DIR, f"rosters_{strat_key}.csv")
        target_csv = os.path.join(BASELINES_DIR, f"rosters_{strat_key}_baseline_{num}.csv")
        
        if is_incremental and os.path.exists(target_csv) and os.path.exists(root_path):
            df_base = pd.read_csv(target_csv)
            df_root = pd.read_csv(root_path)
            # Filter new week rows from root
            df_new_wk = df_root[(df_root["year"] == args.year) & (df_root["week"] == args.week)]
            # Remove week if already exists in baseline archive
            df_base = df_base[~((df_base["year"] == args.year) & (df_base["week"] == args.week))]
            df_updated = pd.concat([df_base, df_new_wk], ignore_index=True)
            df_updated.to_csv(target_csv, index=False)
            print(f"  -> Appended {args.year} Week {args.week} Top-5 rosters to {target_csv}")
        elif os.path.exists(root_path):
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
            for yr in sorted(df["year"].unique()):
                df_yr = df[df["year"] == yr]
                if "lineup_rank" in df_yr.columns:
                    df_yr = df_yr[df_yr["lineup_rank"] == 1]
                n_w = len(df_yr["week"].unique())
                tot_pts = df_yr.groupby("week")["actualPoints"].sum().sum()
                avg_wk = tot_pts / n_w if n_w > 0 else 0
                print(f"  {yr} Season ({n_w} weeks evaluated): Total = {tot_pts:.1f} pts | Avg/Wk = {avg_wk:.1f} pts/wk")

if __name__ == "__main__":
    main()
