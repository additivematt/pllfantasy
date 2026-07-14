"""
General Backtest Runner for Sweep Toggles
=========================================
Runs predictions, filters, simulations, and optimizations using production scripts,
appends actual points, evaluates them, and compares the results against Baseline 5.

Usage:
    python scratch/run_backtest_for_sweep.py --label no_ewma
"""

import os
import sys
import subprocess
import argparse

SEASONS = {
    2025: [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14],
    2026: [1, 2, 3, 4, 5, 6, 8]
}

def run_step(cmd, cwd, step_name):
    print(f"  -> {step_name}: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [FAILED] {step_name} (exit code {result.returncode})")
        print(f"    stderr: {result.stderr[-500:] if result.stderr else '(empty)'}")
        sys.exit(result.returncode)
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", type=str, required=True)
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    pred_dir = os.path.join(root_dir, "predicta", "predictions")

    # 1. Clear old roster files in root directory
    strategies = ["mc_ev", "mc_ceil_90", "mc_win_160", "mc_win_180"]
    for s in strategies:
        csv_path = os.path.join(root_dir, f"rosters_{s}.csv")
        if os.path.exists(csv_path):
            os.remove(csv_path)

    # 2. Wipe predictions folder to prevent stale predictions/simulations reuse
    if os.path.exists(pred_dir):
        for f in os.listdir(pred_dir):
            if f.endswith(".csv") or f.endswith(".json"):
                fpath = os.path.join(pred_dir, f)
                try:
                    os.remove(fpath)
                except Exception as e:
                    print(f"  Failed to delete {fpath}: {e}")

    # 3. Run the full pipeline for each year/week
    for year, weeks in SEASONS.items():
        for week in weeks:
            run_step(
                [sys.executable, "02_predict_probabilities.py", "--year", str(year), "--week", str(week)],
                root_dir, f"Predict {year} W{week}"
            )
            run_step(
                [sys.executable, "03_apply_roster_filter.py", "--year", str(year), "--week", str(week), "--no-opt"],
                root_dir, f"Filter {year} W{week}"
            )
            run_step(
                [sys.executable, "04_simulate_monte_carlo.py", "--year", str(year), "--week", str(week), "--sims", "10000"],
                root_dir, f"Simulate {year} W{week}"
            )
            run_step(
                [sys.executable, "05_bake_mc_ev.py", str(year), str(week)],
                root_dir, f"Bake {year} W{week}"
            )
            run_step(
                [sys.executable, "06_optimize_lineups.py", "--year", str(year), "--week", str(week)],
                root_dir, f"Optimize {year} W{week}"
            )

    # 4. Append actual points to rosters in root folder
    run_step([sys.executable, "scratch/append_actual_points.py"], root_dir, "Append actual points")

    # 5. Evaluate the generated rosters using the harness
    for year, weeks in SEASONS.items():
        weeks_str = ",".join(map(str, weeks))
        lbl = f"sweep_{args.label}_{year}"
        print(f"\nEvaluating {year} for label: {lbl}...")
        
        run_step([
            sys.executable, "prediction_model_evaluation_harness.py",
            "--rosters", os.path.join(root_dir, "rosters_mc_ev.csv"),
            "--predictions", pred_dir,
            "--year", str(year),
            "--weeks", weeks_str,
            "--label", lbl
        ], root_dir, f"Harness {year}")

        # Compare vs Baseline 5
        comp_cmd = [
            sys.executable, "prediction_model_evaluation_harness.py",
            "--compare", f"baseline5_mc_ev_{year},{lbl}"
        ]
        res = run_step(comp_cmd, root_dir, f"Compare {year} vs Baseline 5")
        print(res.stdout)

if __name__ == "__main__":
    main()
