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

## 1. Active Production Benchmark: Baseline 15

Baseline 15 (established August 2026) incorporates **Item 52** (Faceoff Bradley-Terry Exponential Decay, Specialist Share Scaling, Starter Prioritization, Tighter Bayesian Priors, 10 pt Assist Alignment) alongside Baseline 14 multi-position recency weighting (`factor=0.3`) and Baseline 13 position-specific XGBoost hyperparameters.

### Baseline 15 Portfolio Performance (MC_EV, MC_Win_160, MC_Ceil_90)

| Season | Strategy | Top-1 (Avg/Wk) | Top-5 Mean (Avg/Wk) | Top-5 Max (Avg/Wk) | Top-5 Min (Avg/Wk) | Coulda Max (Avg/Wk) | Top-5 Max Ceiling % |
|---|---|---|---|---|---|---|---|
| **2025** | `MC_EV` | **175.6 pts/wk** | **174.7 pts/wk** | **191.7 pts/wk** | **143.3 pts/wk** | 359.9 pts/wk | **53.3%** |
| **2025** | `MC_Win_160` | **171.8 pts/wk** | **163.1 pts/wk** | **191.7 pts/wk** | **143.1 pts/wk** | 359.9 pts/wk | **53.3%** |
| **2025** | `MC_Ceil_90` | **173.6 pts/wk** | **177.8 pts/wk** | **204.5 pts/wk** | **146.8 pts/wk** | 359.9 pts/wk | **56.8%** |
| **2026** | `MC_EV` | **175.6 pts/wk** | **169.6 pts/wk** | **183.7 pts/wk** | **135.2 pts/wk** | 370.4 pts/wk | **49.6%** |
| **2026** | `MC_Win_160` | **168.1 pts/wk** | **161.2 pts/wk** | **185.5 pts/wk** | **135.2 pts/wk** | 370.4 pts/wk | **50.1%** |
| **2026** | `MC_Ceil_90` | **174.3 pts/wk** | **155.7 pts/wk** | **185.6 pts/wk** | **130.2 pts/wk** | 370.4 pts/wk | **50.1%** |

### Baseline 15 Process-Quality Metrics (MC_EV Top-1)

| Season | Avg VOR/Slot | VOR/Week | Slots Above Median | Spearman ρ (Overall) | A | M | D | FO | G |
|---|---|---|---|---|---|---|---|---|---|
| **2025** | **+13.6** | **+94.9** | **72.5%** (66/91) | **0.386** | **0.430** | 0.413 | 0.439 | **0.475** | 0.298 |
| **2026** | **+20.5** | **+143.8** | **94.0%** (79/84) | **0.386** | **0.544** | **0.481** | **0.612** | **0.400** | **0.527** |

> [!NOTE]
> For the complete audit history, scores, and post-mortems of **Baselines 1 through 14**, see the [Historical Baselines Archive](references/baseline_archive.md).

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
1. Verify baseline archive integrity: `python -c "from utils import get_latest_baseline_num; print(f'Active baseline: {get_latest_baseline_num()}')"` (must output `15`).
2. Run evaluation harness: `python prediction_model_evaluation_harness.py` and verify exit code 0.
