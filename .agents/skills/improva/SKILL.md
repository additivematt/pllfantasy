---
name: improva
description: >-
  Tracks feature backlog, model Baseline 18 benchmarks, and strict A/B backtest evaluation rules.
  Use this skill when reviewing pending improvements, checking official baseline metrics, or planning
  predictive modeling experiments. Do NOT use for routine weekly pipeline execution.
---

> [!IMPORTANT]
> **Skill Naming Convention**: This skill is named **improva**. In chat responses, explanations, and documentation links, ALWAYS refer to it simply as `improva` (or [`improva`](file://...)). NEVER output `SKILL.md` or `improva/SKILL.md`.

# PLL Fantasy Prediction Engine — Backlog & Baselines (improva)

This skill maintains the prioritized improvement backlog, the active production baseline (**Baseline 18**), and the mathematical evaluation rules for proposed changes to the prediction pipeline.

---

## 1. Active Production Benchmark: Baseline 18

**Baseline 18** (established October 2026) incorporates **Item 68 (Full-History Classifier Training + OOF Walk-Forward Calibration Ensemble)** on top of the Baseline 17 Track A Legitimacy, Data Leakage Remediation & Data Integrity Fixes (Items 62–67), Baseline 16 Starting Goalie Designation System, Baseline 15 Faceoff Bradley-Terry Exponential Decay, Baseline 14 multi-position recency weighting (`factor=0.3`), and Baseline 13 position-specific XGBoost hyperparameters:
- **Item 68 (Full-History Classifier Training + OOF Walk-Forward Calibration)**: Expanded Stage-1 `XGBRegressor` OOF generation to `TimeSeriesSplit(n_splits=4)` with strict in-fold `StandardScaler` fitting (retaining 80% of `df_pg`), fit `StandardScaler`, `XGBClassifier`, and fold-matched `IsotonicRegression` strictly inside each walk-forward fold (`TimeSeriesSplit(n_splits=3)`) of `clf_train`, and added a 4th **Full-History `XGBClassifier`** trained on **100% of `clf_train`** (so all current-season games train the decision trees), calibrated via pooled walk-forward OOF `IsotonicRegression` (`0.90 * iso_pool + 0.10 * raw_te`) and blended with expanding recency weights `[0.15, 0.20, 0.25, 0.40]` (`ITEM68_FULL_HISTORY_CLF_ENABLED = True`).
- **Items 62–67 (Baseline 17 Foundation)**: Strict Pre-Game Goalie Starter Designation (`ALLOW_RETROSPECTIVE_GOALIE_OVERRIDES = False`, 94.9% pre-game accuracy), Year-Scoped Gameday Rosters & Injury/Scratch Parity, Monte Carlo Year-Parsing Fix & 2019–2022 Exclusion, Historical Team/Opponent Integrity (`CHR` $\rightarrow$ `OUT`, traded players, phantom DNP stripping), Missing Salary Imputation & Playoff `Coulda Max` Salary Parity, and Evaluation Harness `mc_ev` Continuous Metric Alignment & Seeded Local Search.

### Baseline 18 Portfolio Performance (`MC_EV`, `MC_Win_160`, `MC_Ceil_90`)

| Season | Strategy | Top-1 Total | Top-1 (Avg/Wk) | Top-5 Mean (Avg/Wk) | Top-5 Max (Avg/Wk) | Top-5 Min (Avg/Wk) | Coulda Max (Avg/Wk) | Top-5 Max Ceiling % |
|---|---|---|---|---|---|---|---|---|
| **2025** (13 Wks) | `MC_EV` | **2,205.0 pts** | **169.6 pts/wk** | **173.2 pts/wk** | **192.6 pts/wk** | **157.5 pts/wk** | 359.0 pts/wk | **53.7%** |
| **2025** (13 Wks) | `MC_Win_160` | **2,177.2 pts** | **167.5 pts/wk** | **171.2 pts/wk** | **195.8 pts/wk** | **148.5 pts/wk** | 359.0 pts/wk | **54.5%** |
| **2025** (13 Wks) | `MC_Ceil_90` | **2,257.5 pts** | **173.7 pts/wk** | **173.6 pts/wk** | **197.0 pts/wk** | **150.2 pts/wk** | 359.0 pts/wk | **54.9%** |
| **2026** (W1–13, 12 Wks) | `MC_EV` | **2,063.8 pts** | **172.0 pts/wk** | **166.9 pts/wk** | **192.6 pts/wk** | **140.5 pts/wk** | 370.4 pts/wk | **52.0%** |
| **2026** (W1–13, 12 Wks) | `MC_Win_160` | **2,163.8 pts** | **180.3 pts/wk** | **170.3 pts/wk** | **198.2 pts/wk** | **140.5 pts/wk** | 370.4 pts/wk | **53.5%** |
| **2026** (W1–13, 12 Wks) | `MC_Ceil_90` | **2,013.8 pts** | **167.8 pts/wk** | **160.1 pts/wk** | **190.4 pts/wk** | **131.6 pts/wk** | 370.4 pts/wk | **51.4%** |
| **2026** (Full 15 Wks) | `MC_EV` | **2,559.0 pts** | **170.6 pts/wk** | **162.7 pts/wk** | **188.2 pts/wk** | **134.9 pts/wk** | 352.5 pts/wk | **53.4%** |
| **2026** (Full 15 Wks) | `MC_Win_160` | **2,669.3 pts** | **178.0 pts/wk** | **166.1 pts/wk** | **194.2 pts/wk** | **135.7 pts/wk** | 352.5 pts/wk | **55.1%** |
| **2026** (Full 15 Wks) | `MC_Ceil_90` | **2,391.2 pts** | **159.4 pts/wk** | **157.5 pts/wk** | **187.4 pts/wk** | **128.9 pts/wk** | 352.5 pts/wk | **53.2%** |

### Baseline 18 Official 22-Metric Benchmark (`MC_EV` Top-1 & `mc_ev` Continuous Predictions)

| Metric | 2025 (13 Wks) | 2026 (15 Wks) | Combined (28 Wks) |
|---|---|---|---|
| **1. `MC_EV` Roster Total (Avg/Wk)** | **2,205.0** (169.6/wk) | **2,559.0** (170.6/wk) | **4,764.0** (170.1/wk) |
| **2. Top-5 Mean Roster Score** | **2,251.5** (173.2/wk) | **2,440.9** (162.7/wk) | **4,692.4** (167.6/wk) |
| **3. Top-5 Max Roster Score** | **2,503.5** (192.6/wk) | **2,823.0** (188.2/wk) | **5,326.5** (190.2/wk) |
| **4. Top-5 Min Roster Score** | **2,047.5** (157.5/wk) | **2,023.0** (134.9/wk) | **4,070.5** (145.4/wk) |
| **5. `MC_Win_160` Roster Total** | **2,177.2** (167.5/wk) | **2,669.3** (178.0/wk) | **4,846.5** (173.1/wk) |
| **6. `MC_Ceil_90` Roster Total** | **2,257.5** (173.7/wk) | **2,391.2** (159.4/wk) | **4,648.7** (166.0/wk) |
| **7. Season Total VOR (Avg/Wk)** | **+579.3** (+44.6/wk) | **+1,470.0** (+98.0/wk) | **+2,049.3** (+73.2/wk) |
| **8. `A_VOR` / Slot** | **+13.9** (20/26 > med) | **+17.2** (28/30 > med) | **+15.6** (48/56 > med) |
| **9. `M_VOR` / Slot** | **+1.5** (13/26 > med) | **+18.4** (26/30 > med) | **+10.5** (39/56 > med) |
| **10. `D_VOR` / Slot** | **+7.5** (10/13 > med) | **+11.9** (11/15 > med) | **+9.8** (21/28 > med) |
| **11. `FO_VOR` / Slot** | **+5.9** (9/13 > med) | **+12.6** (13/15 > med) | **+9.5** (22/28 > med) |
| **12. `G_VOR` / Slot** | **+0.5** (7/13 > med) | **+2.5** (7/15 > med) | **+1.6** (14/28 > med) |
| **13. `Slot_Weighted_Spearman`** | **0.305** | **0.256** | **0.279** |
| **14. `Coulda_Weighted_Spearman`** | **0.304** | **0.255** | **0.278** |
| **15. `Spearman_Correlation` (Overall)** | **0.440** | **0.363** | **0.399** |
| **16. Per-Pos Spearman (`A/M/D/FO/G`)** | **0.312 / 0.193 / 0.208 / 0.403 / 0.546** | **0.292 / 0.230 / 0.247 / 0.268 / 0.239** | **0.301 / 0.213 / 0.229 / 0.331 / 0.382** |
| **17. `MAE` / `Slot_Weighted_MAE`** | **11.27 / 12.50** | **11.32 / 12.74** | **11.30 / 12.63** |
| **18. `RMSE` / `R_Squared` ($R^2$)** | **14.70 / +0.230** | **14.97 / +0.135** | **14.84 / +0.179** |
| **19. `Tier_Accuracy`** | **43.1%** | **40.5%** | **41.7%** |
| **20. `Boom_Precision`** | **32.7%** | **30.1%** | **31.3%** |
| **21. `Boom_Recall`** | **42.1%** | **33.4%** | **37.4%** |
| **22. `Boom_Brier_Score`** | **0.204** | **0.196** | **0.200** |

> [!NOTE]
> For the complete audit history, scores, and post-mortems of **Baselines 1 through 17**, see the [Historical Baselines Archive](references/baseline_archive.md).

---

## 2. Mandatory Rules for A/B Testing & Model Evaluation

1. **User Preference (Precision > Recall)**: The user makes manual player swaps. Optimizations must prioritize **Boom Precision** and $F_{0.5}$ score alongside roster EV to eliminate false-positive trap picks.
2. **Never Recalculate Baselines on the Fly**: Read baseline scores directly from archived CSV files in `baselines/rosters_<strategy>_baseline_<N>.csv`.
3. **Mandatory Top-5 Candidate Pool Archiving**: Baseline roster CSVs MUST ALWAYS store all 5 candidate lineups (ranks 1–5, 35 player rows/wk). Never filter out ranks 2–5.
4. **Mandatory 22-Metric 6-Column Mobile Layout**: All backtests must report results across the 4 standard category tables (Candidate Portfolio, VOR Process Quality, Continuous Error & Spearman, Classification & Calibration). See [evaluata reporting spec](../evaluata/references/reporting_spec.md).
5. **No Deterministic Point Proxies**: Always execute the complete 5-stage production pipeline (`02` $\rightarrow$ `03` $\rightarrow$ `04` $\rightarrow$ `05` $\rightarrow$ `06_optimize_lineups.py`).
6. **SSH-Resilient Detached Execution**: Always launch long backtests as independent background processes via `scratch/start_<job>_silent.vbs`.

---

## 3. Prioritized Improvement Backlog (Future Proposals for Testing Against Baseline 18)

### Track A: Legitimacy, Data Leakage Remediation & Data Integrity Fixes (Completed in Baseline 17 & 18)

| Status | Item # & Name | Summary of Resolution | Details / Spec Link |
|---|---|---|---|
| **✅ Adopted (B18)** | **Item 68**: Full-History Classifier Training + OOF Walk-Forward Calibration | 4-horizon expanding GBDT + 100% full-history GBDT ensemble with strict in-fold `StandardScaler` & OOF isotonic calibration (+232.3 pts `MC_EV`, +469.6 pts `MC_Win_160`) | [Backlog Details](references/backlog_details.md#item-68-fix-classifier-training-starvation--full-history-gbdt-fit--oof-walk-forward-calibration-adopted-in-baseline-18) |
| **✅ Adopted (B17)** | **Item 62**: Strict Pre-Game Goalie Starter Designation | Gated `goalie_starters.json` behind `ALLOW_RETROSPECTIVE_GOALIE_OVERRIDES = False`; 94.9% accurate pre-game heuristic | [Backlog Details](references/backlog_details.md#item-62-strict-pre-game-goalie-starter-designation-adopted-in-baseline-17) |
| **✅ Adopted (B17)** | **Item 63**: Year-Scoped Gameday Rosters & Injury Parity | Scoped `gameday_rosters` by `year` and ignored mutable API `injuryStatus`; lifted 2026 `MC_EV` by +137.4 pts | [Backlog Details](references/backlog_details.md#item-63-year-scoped-gameday-rosters--pre-game-injuryscratch-parity-adopted-in-baseline-17) |
| **✅ Adopted (B17)** | **Item 64**: MC Year-Parsing Fix & 2019–2022 Exclusion | Fixed `^(\d{4})_` regex and excluded 6,724 pre-2023 rows weighted at `weeks_ago=10` | [Backlog Details](references/backlog_details.md#item-64-monte-carlo-year-parsing-fix--20192022-exclusion-adopted-in-baseline-17) |
| **✅ Adopted (B17)** | **Item 65**: Historical Team/Opponent Integrity & Matchup Keys | Fixed `CHR` $\rightarrow$ `OUT`, 41 traded-player rows, 2,110 phantom DNP rows, and recovered 36/189 pace games & 26/189 FO BT games | [Backlog Details](references/backlog_details.md#item-65-historical-teamopponent-integrity-chr-to-out-traded-players--normalized-matchup-keys-adopted-in-baseline-17) |
| **✅ Adopted (B17)** | **Item 66**: Missing Salary Imputation & Playoff `Coulda Max` | Replaced dead `pre_2023_mask` with `missing_sal_mask` and aligned playoff `Coulda Max` salaries | [Backlog Details](references/backlog_details.md#item-66-missing-salary-imputation-in-training-2023-2025-w1214-2026-w14--coulda-max-salary-parity-adopted-in-baseline-17) |
| **✅ Adopted (B17)** | **Item 67**: Evaluation Harness `mc_ev` Alignment & Seeded Search | Evaluated continuous/Spearman metrics on `mc_ev` (MAE $17.6 \rightarrow 11.3$, $R^2$ $-0.53 \rightarrow +0.17$) and seeded `run_local_search` | [Backlog Details](references/backlog_details.md#item-67-evaluation-harness-mc_ev-continuous-metric-alignment--seeded-local-search-adopted-in-baseline-17) |

### Track B: High-Leverage Modeling, Simulation & Optimization Proposals (To Be Tested One-by-One Against Baseline 18)

Ranked by expected value and likelihood of effectiveness when evaluated against **Baseline 18**:

| Priority | Item # & Name | Category | Expected Impact | Details / Spec Link |
|---|---|---|---|---|
| **1** | **Item 70**: EWMA / Current-Season Shrunk EV Anchor, Position-Switch Fix & Direct FO EV | Tier 2/3 (Features & EV) | +4 to +12 pts/wk | [Backlog Details](references/backlog_details.md#item-70-ewma--current-season-shrunk-ev-anchor-position-switch-fix--direct-faceoff-ev) |
| **2** | **Item 69**: Weekly Relative Ground-Truth Tier Labels in Training (`groupby(year, week, pos)`) | Tier 2 (Target Alignment) | +2 to +6 pts/wk | [Backlog Details](references/backlog_details.md#item-69-weekly-relative-ground-truth-tier-labels-in-training-replace-assign_tiers_expanding) |
| **3** | **Item 39 / 71**: Multi-Quantile Regressor (`p25, p50, p90`) & Skewed Bootstrap CDF Mapping | Tier 3 (Simulation) | +5 to +12 pts/wk | [Backlog Details](references/backlog_details.md#item-71-multi-quantile-distributional-regression-p25-p50-p90--quantile-preserving-mc-bootstrap-upgraded-item-39) |
| **4** | **Item 72**: 2-Opt Pair-Swap Local Search & Correlated Top-5 Pool Generation | Tier 3 (Optimizer) | +2 to +6 pts/wk | [Backlog Details](references/backlog_details.md#item-72-2-opt-pair-swap-local-search--correlated-top-5-candidate-pool-generation) |
| **5** | **Item 32**: Matchup Rating Temporal Decay | Tier 2 (Features) | +3 to +8 pts/wk | [Backlog Details](references/backlog_details.md#item-32-matchup-rating-temporal-decay) |
| **6** | **Item 54**: Per-Position Recency Weight Tuning | Tier 2 (Tuning) | +1 to +4 pts/wk | [Backlog Details](references/backlog_details.md#item-54-per-position-recency-weight-tuning) |
| **7** | **Item 43**: Scoring Environment Multiplier | Tier 3 (Simulation) | +3 to +10 pts/wk | [Backlog Details](references/backlog_details.md#item-43-scoring-environment-multiplier) |
| **8** | **Item 41**: Ensemble Meta-Selector (Strategy Picker) | Tier 3 (Optimizer) | +3 to +8 pts/wk | [Backlog Details](references/backlog_details.md#item-41-ensemble-meta-selector-strategy-picker) |
| **9** | **Item 12**: Dynamic Monte Carlo Correlation Matrix | Tier 3 (Simulator) | +2 to +5 pts/wk | [Backlog Details](references/backlog_details.md#item-12-dynamic-monte-carlo-correlation-matrix) |
| **10** | **Item 44 / 40**: Ownership Archive & Penalty | Tier 3 (Optimizer) | 0 to +3 pts/wk | [Backlog Details](references/backlog_details.md#item-44-historical-ownership-archive--chalk-analysis-prerequisite-for-item-40) |
| **11** | **Item 42**: Player-Level Pairwise Correlations | Tier 3 (Simulation) | +1 to +4 pts/wk | [Backlog Details](references/backlog_details.md#item-42-player-level-mc-correlations) |
| **12** | **Items 16–19**: Pipeline Performance & Safety | Tier 4 (Infra) | Speed & Reliability | [Backlog Details](references/backlog_details.md#tier-4-pipeline-performance--safety) |
| **13** | **Items 20–24**: UI/UX & Live Game-Day Tools | Tier 5 (UX) | Operational Safety | [Backlog Details](references/backlog_details.md#tier-5-uiux--live-game-day-tools) |
| **14** | **Retest Queue (Items 10, 26, 30, 55–58)** | Retest | Various | [Backlog Details](references/backlog_details.md#retest-queue-candidates-for-22-metric-re-evaluation) |

> [!NOTE]
> For detailed reports on all completed trials (Items 9, 11, 27, 33, 36–38, 48–50, 52, 59, 62–68), advanced August 2026 modeling trials (LTR, Option E, Decoupled EV), and tested/rejected experiments (Items 45–47, 51, 53, 60, 61), consult the [Completed & Tested Experiment Archive](references/experiment_archive.md).

---

## Verification Directive

When modifying improvement models or running backtests:
1. Verify baseline archive integrity: `python -c "from utils import get_latest_baseline_num; print(f'Active baseline: {get_latest_baseline_num()}')"` (must output `18`).
2. Run evaluation harness: `python prediction_model_evaluation_harness.py --rosters baselines/rosters_mc_ev_baseline_18.csv --predictions predicta/predictions --year 2026` and verify exit code 0.
