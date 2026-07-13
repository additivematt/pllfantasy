"""
Boom Weight Sweep Wrapper
==========================
Runs the Item 37 full-pipeline backtest across multiple Boom class weights: 1.5, 2.0, 2.5, and 3.0.

Usage:
    python scratch/sweep_boom_weights.py
    python scratch/sweep_boom_weights.py --backtest-year 2026
"""

import subprocess
import sys
import os

WEIGHTS = [1.5, 2.0, 2.5, 3.0]


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)

    print("=" * 60)
    print(" STARTING BOOM WEIGHTS SWEEP")
    print(f" Weights to test: {WEIGHTS}")
    print("=" * 60)

    for w in WEIGHTS:
        print(f"\n" + "=" * 65)
        print(f" RUNNING BACKTEST FOR BOOM WEIGHT = {w}")
        print("=" * 65)

        cmd = [
            sys.executable,
            "scratch/run_full_pipeline_backtest_item37.py",
            "--boom-weight", str(w)
        ]
        
        # Forward any arguments (like --backtest-year 2026)
        if len(sys.argv) > 1:
            cmd.extend(sys.argv[1:])
            
        print(f"Executing: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=root_dir)
        
        if result.returncode != 0:
            print(f"\n[ERROR] Sweep failed for boom weight = {w} (exit code {result.returncode})")
            sys.exit(result.returncode)

    print("\n" + "=" * 60)
    print(" SWEEP COMPLETED SUCCESSFULLY")
    print(" Check evaluation_runs_log.json for results comparison.")
    print("=" * 60)


if __name__ == "__main__":
    main()
