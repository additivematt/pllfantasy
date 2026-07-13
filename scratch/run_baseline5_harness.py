"""
Baseline 5 Evaluation Harness Runner
======================================
Runs the evaluation harness for all 3 baseline 5 strategies across 2025 and 2026,
logging results under 'baseline5_*' labels in evaluation_runs_log.json.

Usage:
    python scratch/run_baseline5_harness.py
"""

import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STRATEGIES = [
    ("rosters_mc_ev_baseline_5.csv",      "mc_ev"),
    ("rosters_mc_win_160_baseline_5.csv", "mc_win_160"),
    ("rosters_mc_ceil_90_baseline_5.csv", "mc_ceil_90"),
]

YEARS = [2025, 2026]


def run(cmd, desc):
    print(f"\n  >> {desc}")
    print(f"     {' '.join(cmd)}")
    subprocess.run(cmd, cwd=SCRIPT_DIR)


def main():
    print("=" * 70)
    print(" BASELINE 5 EVALUATION HARNESS RUNNER")
    print("=" * 70)

    baselines_dir = os.path.join(SCRIPT_DIR, "baselines")
    pred_dir = os.path.join(SCRIPT_DIR, "predicta", "predictions")

    for roster_file, strategy_key in STRATEGIES:
        roster_path = os.path.join(baselines_dir, roster_file)
        if not os.path.exists(roster_path):
            print(f"\n[SKIP] Roster file not found: {roster_file}")
            continue

        for year in YEARS:
            label = f"baseline5_{strategy_key}_{year}"
            print(f"\n{'='*70}")
            print(f"  Strategy: {strategy_key} | Year: {year} | Label: {label}")
            print(f"{'='*70}")

            # Define valid weeks to evaluate
            weeks_str = "1,2,3,4,5,7,8,9,10,11,12,13,14" if year == 2025 else "1,2,3,4,5,6,8"

            run(
                [
                    sys.executable,
                    "prediction_model_evaluation_harness.py",
                    "--rosters", roster_path,
                    "--predictions", pred_dir,
                    "--year", str(year),
                    "--weeks", weeks_str,
                    "--label", label,
                ],
                f"Harness: {strategy_key} {year}"
            )

    print("\n" + "=" * 70)
    print(" ALL HARNESS RUNS COMPLETE")
    print(" Results logged to evaluation_runs_log.json")
    print("=" * 70)


if __name__ == "__main__":
    main()
