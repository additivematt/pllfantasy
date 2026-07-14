"""
Master Full-Pipeline Backtest Runner

Orchestrates the full predict → simulate → optimize pipeline for backtesting,
then evaluates results via the evaluation harness with statistical comparison.

Feature toggles are read from config.py by default, but can be overridden via
CLI arguments (e.g., --pace-scale / --no-pace-scale, --correlation / --no-correlation).

Usage:
    python scratch/run_full_pipeline_backtest.py
    python scratch/run_full_pipeline_backtest.py --pace-scale --label my_pace_test
    python scratch/run_full_pipeline_backtest.py --no-pace-scale --no-correlation --label stripped_test
"""

import os
import sys
import subprocess
import argparse
import time

# Add parent dir so we can import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GAME_PACE_ENABLED, CORRELATION_COPULA_ENABLED


def run_step(cmd, cwd, step_name):
    """Run a pipeline step with error handling and timing."""
    print(f"  -> {step_name}: {' '.join(cmd)}")
    start = time.time()
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    elapsed = time.time() - start

    if result.returncode != 0:
        print(f"  [FAILED] in {elapsed:.1f}s (exit code {result.returncode})")
        print(f"    stderr: {result.stderr[-500:] if result.stderr else '(empty)'}")
        raise RuntimeError(f"Pipeline step '{step_name}' failed with exit code {result.returncode}")
    
    print(f"  [OK] {step_name} completed in {elapsed:.1f}s")
    return result


def main():
    parser = argparse.ArgumentParser(description="Run full pipeline backtest with feature toggles")
    
    # Feature toggles (default to config.py values)
    pace_group = parser.add_mutually_exclusive_group()
    pace_group.add_argument("--pace-scale", action="store_true", default=None,
                           help="Enable game pace scaling (overrides config)")
    pace_group.add_argument("--no-pace-scale", action="store_true", default=None,
                           help="Disable game pace scaling (overrides config)")
    
    corr_group = parser.add_mutually_exclusive_group()
    corr_group.add_argument("--correlation", action="store_true", default=None,
                           help="Enable correlation copula (overrides config)")
    corr_group.add_argument("--no-correlation", action="store_true", default=None,
                           help="Disable correlation copula (overrides config)")
    
    parser.add_argument("--label", type=str, default=None,
                        help="Evaluation label suffix (auto-generated if not provided)")
    parser.add_argument("--sims", type=int, default=10000,
                        help="Number of Monte Carlo simulation trials")
    parser.add_argument("--compare-2025", type=str, default="baseline5_mc_ev_2025",
                       help="Baseline label to compare 2025 against")
    parser.add_argument("--compare-2026", type=str, default="baseline5_mc_ev_2026",
                       help="Baseline label to compare 2026 against")
    parser.add_argument("--alpha", type=float, default=0.9,
                        help="XGBRegressor quantile regression target alpha")
    parser.add_argument("--no-debias", action="store_true",
                        help="Disable GBDT predictions de-biasing in MC simulator")
    args = parser.parse_args()
    
    # Resolve feature toggles: CLI > config.py
    use_pace = GAME_PACE_ENABLED
    if args.pace_scale:
        use_pace = True
    elif args.no_pace_scale:
        use_pace = False
    
    use_corr = CORRELATION_COPULA_ENABLED
    if args.correlation:
        use_corr = True
    elif args.no_correlation:
        use_corr = False
    
    # Auto-generate label from toggle state if not provided
    if args.label is None:
        parts = []
        parts.append("pace" if use_pace else "nopace")
        parts.append("corr" if use_corr else "nocorr")
        label_suffix = "_".join(parts)
    else:
        label_suffix = args.label
    
    # Build CLI flags to forward to pipeline scripts
    pred_extra_args = []
    if use_pace:
        pred_extra_args.append("--pace-scale")
    else:
        pred_extra_args.append("--no-pace-scale")
    pred_extra_args.extend(["--alpha", str(args.alpha)])
    
    sim_extra_args = []
    if not use_corr:
        sim_extra_args.append("--no-correlation")
    sim_extra_args.extend(["--alpha", str(args.alpha)])
    if args.no_debias:
        sim_extra_args.append("--no-debias")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    
    # Print config summary
    print("=" * 60)
    print("PLL Fantasy Full Pipeline Backtest")
    print("=" * 60)
    print(f"  Game Pace Scaling:    {'ENABLED' if use_pace else 'DISABLED'}")
    print(f"  Correlation Copula:   {'ENABLED' if use_corr else 'DISABLED'}")
    print(f"  MC Simulations:       {args.sims:,}")
    print(f"  Evaluation Label:     {label_suffix}")
    print("=" * 60)
    
    # 1. Clear old roster files in root directory
    strategies = ["mc_ev", "mc_ceil_90", "mc_win_160", "mc_win_180"]
    for s in strategies:
        csv_path = os.path.join(root_dir, f"rosters_{s}.csv")
        if os.path.exists(csv_path):
            print(f"Removing old roster file: {csv_path}")
            os.remove(csv_path)
            
    # Define tasks: 2025 weeks 1-14 (excluding 6) + 2026 weeks 1-6, 8
    tasks = []
    for w in [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14]:
        tasks.append((2025, w))
    for w in [1, 2, 3, 4, 5, 6, 8]:
        tasks.append((2026, w))
        
    # 2. Run full pipeline for all weeks
    total_start = time.time()
    for i, (year, week) in enumerate(tasks, 1):
        print(f"\n{'=' * 60}")
        print(f"[{i}/{len(tasks)}] Pipeline: {year} Week {week}")
        print(f"{'=' * 60}")
        
        # A. Predict probabilities
        pred_cmd = [sys.executable, "scratch/02_predict_probabilities_item26.py",
                   "--year", str(year), "--week", str(week)] + pred_extra_args
        run_step(pred_cmd, root_dir, "Predict Probabilities")
        
        # A2. Apply Roster Filter
        filter_cmd = [sys.executable, "03_apply_roster_filter.py",
                      "--year", str(year), "--week", str(week), "--no-opt"]
        run_step(filter_cmd, root_dir, "Apply Roster Filter")
        
        # B. Monte Carlo simulation
        sim_cmd = [sys.executable, "scratch/04_simulate_monte_carlo_item26.py",
                   "--year", str(year), "--week", str(week),
                   "--sims", str(args.sims)] + sim_extra_args
        run_step(sim_cmd, root_dir, "Monte Carlo Simulation")
        
        # C. Roster Optimization
        opt_cmd = [sys.executable, "06_optimize_lineups.py",
                   "--year", str(year), "--week", str(week)]
        run_step(opt_cmd, root_dir, "Optimize Lineups")
        
    total_elapsed = time.time() - total_start
    print(f"\n{'=' * 60}")
    print(f"Pipeline runs completed in {total_elapsed/60:.1f} minutes. Starting evaluations...")
    print(f"{'=' * 60}")
    
    # 3. Evaluate 2025
    label_2025 = f"mc_ev_2025_{label_suffix}"
    harness_2025_cmd = [
        sys.executable,
        "prediction_model_evaluation_harness.py",
        "--rosters", "rosters_mc_ev.csv",
        "--year", "2025",
        "--weeks", "1,2,3,4,5,7,8,9,10,11,12,13,14",
        "--label", label_2025
    ]
    run_step(harness_2025_cmd, root_dir, "Evaluate 2025")
    
    # Compare 2025 with baseline
    compare_2025_cmd = [
        sys.executable,
        "prediction_model_evaluation_harness.py",
        "--compare", f"{args.compare_2025},{label_2025}"
    ]
    run_step(compare_2025_cmd, root_dir, "Compare 2025 vs Baseline")
    
    # 4. Evaluate 2026
    label_2026 = f"mc_ev_2026_{label_suffix}"
    harness_2026_cmd = [
        sys.executable,
        "prediction_model_evaluation_harness.py",
        "--rosters", "rosters_mc_ev.csv",
        "--year", "2026",
        "--weeks", "1,2,3,4,5,6,8",
        "--label", label_2026
    ]
    run_step(harness_2026_cmd, root_dir, "Evaluate 2026")
    
    # Compare 2026 with baseline
    compare_2026_cmd = [
        sys.executable,
        "prediction_model_evaluation_harness.py",
        "--compare", f"{args.compare_2026},{label_2026}"
    ]
    run_step(compare_2026_cmd, root_dir, "Compare 2026 vs Baseline")
    
    print(f"\n{'=' * 60}")
    print(f"ALL DONE - Total runtime: {(time.time() - total_start)/60:.1f} minutes")
    print(f"Labels: {label_2025}, {label_2026}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
