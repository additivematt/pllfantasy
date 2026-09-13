---
name: improva
description: >-
  Tracks feature backlog, model Baseline 15 benchmarks, and strict A/B backtest evaluation rules.
  Use this skill when reviewing pending improvements, checking official baseline metrics, or planning
  predictive modeling experiments. Do NOT use for routine weekly pipeline execution.
---

> [!IMPORTANT]
> **Skill Naming Convention**: This skill is named **improva**. In chat responses, explanations, and documentation links, ALWAYS refer to it simply as `improva` (or [`improva`](file://...)). NEVER output `SKILL.md` or `improva/SKILL.md`.

# PLL Fantasy Prediction Engine — Backlog & Baselines (improva)

This skill maintains the prioritized improvement backlog, the active production baseline (Baseline 15), and the mathematical evaluation rules for proposed changes to the prediction pipeline.

---

## 1. Active Production Benchmark: Baseline 16

Baseline 16 (established September 2026) establishes the **Starting Goalie Designation System** (authoritative overrides via `goalie_starters.json` + multi-signal heuristic fallback, zeroed-out simulation draws, and optimizer pool exclusion for non-starters) alongside Baseline 15 Faceoff Bradley-Terry Exponential Decay, Baseline 14 multi-position recency weighting (`factor=0.3`), and Baseline 13 position-specific XGBoost hyperparameters.

### Baseline 16 Portfolio Performance (MC_EV, MC_Win_160, MC_Ceil_90)

| Season | Strategy | Top-1 (Avg/Wk) | Top-5 Mean (Avg/Wk) | Top-5 Max (Avg/Wk) | Top-5 Min (Avg/Wk) | Coulda Max (Avg/Wk) | Top-5 Max Ceiling % |
|---|---|---|---|---|---|---|---|
| **2025** | `MC_EV` | **173.2 pts/wk** | **172.9 pts/wk** | **196.3 pts/wk** | **150.6 pts/wk** | 359.9 pts/wk | **54.5%** |
| **2025** | `MC_Win_160` | **170.6 pts/wk** | **172.0 pts/wk** | **196.3 pts/wk** | **149.6 pts/wk** | 359.9 pts/wk | **54.5%** |
| **2025** | `MC_Ceil_90` | **178.5 pts/wk** | **177.8 pts/wk** | **203.6 pts/wk** | **154.2 pts/wk** | 359.9 pts/wk | **56.6%** |
| **2026** (W1-13) | `MC_EV` | **164.6 pts/wk** | **165.4 pts/wk** | **191.3 pts/wk** | **144.7 pts/wk** | 370.4 pts/wk | **51.7%** |
| **2026** (W1-13) | `MC_Win_160` | **167.9 pts/wk** | **166.4 pts/wk** | **192.6 pts/wk** | **145.3 pts/wk** | 370.4 pts/wk | **52.0%** |
| **2026** (W1-13) | `MC_Ceil_90` | **166.5 pts/wk** | **154.9 pts/wk** | **191.0 pts/wk** | **131.8 pts/wk** | 370.4 pts/wk | **51.6%** |
| **2026** (Full 14 Wks) | `MC_EV` | **156.3 pts/wk** | **156.5 pts/wk** | **180.8 pts/wk** | **136.1 pts/wk** | 361.4 pts/wk | **50.0%** |

### Baseline 16 Process-Quality Metrics (MC_EV Top-1)

| Season | Avg VOR/Slot | VOR/Week | Slots Above Median | Spearman ρ (Overall) | A | M | D | FO | G |
|---|---|---|---|---|---|---|---|---|---|
| **2025** | **+6.9** | **+48.2** | **67.0%** (61/91) | **0.314** | **0.265** | **0.066** | **0.156** | **0.383** | **+1.3** (+3.7 gain) |
| **2026** (W1-13) | **+13.4** | **+94.1** | **78.6%** (66/84) | **0.323** | **0.204** | **0.125** | **0.250** | **0.263** | **+5.0** (8/12 above median) |
| **2026** (Full 14 Wks) | **+11.9** | **+83.1** | **74.5%** (73/98) | **0.323** | **0.204** | **0.125** | **0.250** | **0.263** | **+6.9** (10/14 above median) |

> [!NOTE]
> For the complete audit history, scores, and post-mortems of **Baselines 1 through 15**, see the [Historical Baselines Archive](references/baseline_archive.md).

---

## 2. Mandatory Rules for A/B Testing & Model Evaluation

1. **User Preference (Precision > Recall)**: The user makes manual player swaps. Optimizations must prioritize **Boom Precision** and $F_{0.5}$ score alongside roster EV to eliminate false-positive trap picks.
2. **Never Recalculate Baselines on the Fly**: Read baseline scores directly from archived CSV files in `baselines/rosters_<strategy>_baseline_<N>.csv`.
3. **Mandatory Top-5 Candidate Pool Archiving**: Baseline roster CSVs MUST ALWAYS store all 5 candidate lineups (ranks 1–5, 35 player rows/wk). Never filter out ranks 2–5.
4. **Mandatory 22-Metric 6-Column Mobile Layout**: All backtests must report results across the 4 standard category tables (Candidate Portfolio, VOR Process Quality, Continuous Error & Spearman, Classification & Calibration). See [evaluata reporting spec](../evaluata/references/reporting_spec.md).
5. **No Deterministic Point Proxies**: Always execute the complete 5-stage production pipeline (`02` $\rightarrow$ `03` $\rightarrow$ `04` $\rightarrow$ `05` $\rightarrow$ `06_optimize_lineups.py`).
6. **SSH-Resilient Detached Execution**: Always launch long backtests as independent background processes via `scratch/start_<job>_silent.vbs`.

---

## 3. Prioritized Improvement Backlog

Ranked by expected value and likelihood of effectiveness when evaluated against **Baseline 15**:

| # | Item # & Name | Category | Expected Impact | Details / Spec Link |
|---|---|---|---|---|
| **1** | **Item 54**: Per-Position Recency Weight Tuning | Tier 2 (Tuning) | +1 to +4 pts/wk | [Backlog Details](references/backlog_details.md#item-54-per-position-recency-weight-tuning) |
| **2** | **Item 39**: Skewed Bootstrap (Quantile CDF Mapping) | Tier 3 (Simulation) | +5 to +15 pts/wk | [Backlog Details](references/backlog_details.md#item-39-skewed-bootstrap--quantile-preserving-mc-transformation) |
| **3** | **Item 43**: Scoring Environment Multiplier | Tier 3 (Simulation) | +3 to +10 pts/wk | [Backlog Details](references/backlog_details.md#item-43-scoring-environment-multiplier) |
| **4** | **Item 32**: Matchup Rating Temporal Decay | Tier 2 (Features) | +3 to +8 pts/wk | [Backlog Details](references/backlog_details.md#item-32-matchup-rating-temporal-decay) |
| **5** | **Item 41**: Ensemble Meta-Selector (Strategy Picker) | Tier 3 (Optimizer) | +3 to +8 pts/wk | [Backlog Details](references/backlog_details.md#item-41-ensemble-meta-selector-strategy-picker) |
| **6** | **Item 12**: Dynamic Monte Carlo Correlation Matrix | Tier 3 (Simulator) | +2 to +5 pts/wk | [Backlog Details](references/backlog_details.md#item-12-dynamic-monte-carlo-correlation-matrix) |
| **7** | **Item 44 / 40**: Ownership Archive & Penalty | Tier 3 (Optimizer) | 0 to +3 pts/wk | [Backlog Details](references/backlog_details.md#item-44-historical-ownership-archive--chalk-analysis-prerequisite-for-item-40) |
| **8** | **Item 42**: Player-Level Pairwise Correlations | Tier 3 (Simulation) | +1 to +4 pts/wk | [Backlog Details](references/backlog_details.md#item-42-player-level-mc-correlations) |
| **9** | **Items 16–19**: Pipeline Performance & Safety | Tier 4 (Infra) | Speed & Reliability | [Backlog Details](references/backlog_details.md#tier-4-pipeline-performance--safety) |
| **10** | **Items 20–24**: UI/UX & Live Game-Day Tools | Tier 5 (UX) | Operational Safety | [Backlog Details](references/backlog_details.md#tier-5-uiux--live-game-day-tools) |
| **11** | **Retest Queue (Items 10, 26, 30, 55–58)** | Retest | Various | [Backlog Details](references/backlog_details.md#retest-queue-candidates-for-22-metric-re-evaluation) |

> [!NOTE]
> For detailed reports on all completed trials (Items 9, 11, 27, 33, 36–38, 48–50, 52, 59), advanced August 2026 modeling trials (LTR, Option E, Decoupled EV), and tested/rejected experiments (Items 45–47, 51, 53, 60, 61), consult the [Completed & Tested Experiment Archive](references/experiment_archive.md).

---

## Verification Directive

When modifying improvement models or running backtests:
1. Verify baseline archive integrity: `python -c "from utils import get_latest_baseline_num; print(f'Active baseline: {get_latest_baseline_num()}')"` (must output `16`).
2. Run evaluation harness: `python prediction_model_evaluation_harness.py` and verify exit code 0.
