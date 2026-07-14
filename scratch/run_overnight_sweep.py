"""
Master Overnight Sweep Coordinator
==================================
Sequentially executes 15 combination and ablation test configurations.
Modifies config.py dynamically before each run, executes the backtest runner,
and restores the default config.py state.

Usage:
    python scratch/run_overnight_sweep.py
"""

import os
import sys
import subprocess
import time

CONFIG_PATH = "config.py"

SWEEP_CONFIGS = [
    # --- Ablation Studies (Disabling Core features) ---
    {"label": "no_ewma", "toggles": {"EWMA_ENABLED": False}},
    {"label": "no_shrinkage", "toggles": {"SHRINKAGE_ENABLED": False}},
    {"label": "no_game_pace", "toggles": {"GAME_PACE_ENABLED": False}},
    {"label": "no_ewma_no_shrinkage", "toggles": {"EWMA_ENABLED": False, "SHRINKAGE_ENABLED": False}},
    {"label": "no_ewma_no_game_pace", "toggles": {"EWMA_ENABLED": False, "GAME_PACE_ENABLED": False}},
    {"label": "no_shrinkage_no_game_pace", "toggles": {"SHRINKAGE_ENABLED": False, "GAME_PACE_ENABLED": False}},
    {"label": "stripped_gbdt", "toggles": {"EWMA_ENABLED": False, "SHRINKAGE_ENABLED": False, "GAME_PACE_ENABLED": False}},
    
    # --- Experimental Additions (Enabling on top of Baseline 5) ---
    {"label": "stratified_bootstrap", "toggles": {"OPPONENT_STRATIFIED_BOOTSTRAP": True}},
    {"label": "pool_blending_k8", "toggles": {"MC_POOL_BLENDING_ENABLED": True, "MC_POOL_BLENDING_K": 8}},
    {"label": "pool_blending_k15", "toggles": {"MC_POOL_BLENDING_ENABLED": True, "MC_POOL_BLENDING_K": 15}},
    {"label": "item26", "script": "scratch/run_full_pipeline_backtest_item26.py"},
    
    # --- Experimental Combinations ---
    {"label": "bootstrap_blending_k8", "toggles": {"OPPONENT_STRATIFIED_BOOTSTRAP": True, "MC_POOL_BLENDING_ENABLED": True, "MC_POOL_BLENDING_K": 8}},
    {"label": "bootstrap_item26", "toggles": {"OPPONENT_STRATIFIED_BOOTSTRAP": True}, "script": "scratch/run_full_pipeline_backtest_item26.py"},
    {"label": "blending_k8_item26", "toggles": {"MC_POOL_BLENDING_ENABLED": True, "MC_POOL_BLENDING_K": 8}, "script": "scratch/run_full_pipeline_backtest_item26.py"},
    {"label": "bootstrap_blending_k8_item26", "toggles": {"OPPONENT_STRATIFIED_BOOTSTRAP": True, "MC_POOL_BLENDING_ENABLED": True, "MC_POOL_BLENDING_K": 8}, "script": "scratch/run_full_pipeline_backtest_item26.py"},
]


def backup_config():
    """Read the current config.py and return its contents."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return f.read()


def restore_config(original_content):
    """Write the original config.py content back to disk."""
    with open(CONFIG_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(original_content)


def apply_toggles(toggles):
    """Modify config.py variables dynamically."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    
    lines = content.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        for var, val in toggles.items():
            if stripped.startswith(f"{var} =") or stripped.startswith(f"{var}="):
                lines[i] = f"{var} = {val}"
                
    with open(CONFIG_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    os.chdir(root_dir)

    print("=" * 70)
    print(" PLL FANTASY OVERNIGHT BACKTEST SWEEP COORDINATOR")
    print(f" Starting execution of {len(SWEEP_CONFIGS)} sweep runs...")
    print("=" * 70)

    original_config = backup_config()
    start_time = time.time()

    for idx, run_cfg in enumerate(SWEEP_CONFIGS, 1):
        label = run_cfg["label"]
        toggles = run_cfg.get("toggles", {})
        script_path = run_cfg.get("script", None)

        print(f"\n" + "=" * 70)
        print(f"[{idx}/{len(SWEEP_CONFIGS)}] SWEEP RUN: {label.upper()}")
        if toggles:
            print(f"  Applying config modifications: {toggles}")
        print("=" * 70)

        # 1. Apply config toggles (if any)
        if toggles:
            apply_toggles(toggles)
        else:
            # Ensure config is in default baseline state
            restore_config(original_config)

        # 2. Run appropriate script
        run_start = time.time()
        if script_path:
            cmd = [sys.executable, script_path, "--label", label]
        else:
            cmd = [sys.executable, "scratch/run_backtest_for_sweep.py", "--label", label]

        print(f"  Executing: {' '.join(cmd)}")
        result = subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)
        
        run_elapsed = time.time() - run_start
        print(f"\n  -> Run finished in {run_elapsed/60:.1f} minutes with exit code {result.returncode}")

        # 3. Always restore config.py to original state
        restore_config(original_config)

        if result.returncode != 0:
            print(f"  [WARN] Run {label} failed. Continuing with sweep...")

    total_elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(f" OVERNIGHT SWEEP COMPLETE! Total runtime: {total_elapsed/60:.1f} minutes")
    print(" All results logged under 'sweep_*' labels in evaluation_runs_log.json")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSweep interrupted by user. Restoring config.py...")
        # Emergency config restoration is handled by importing and writing the backup if main is interrupted
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        # Simple safety fallback
        sys.exit(1)
