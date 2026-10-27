---
name: improva
description: >-
  Tracks feature backlog, model Baseline 19 benchmarks, and strict A/B backtest evaluation rules.
  Use this skill when reviewing pending improvements, checking official baseline metrics, or planning
  predictive modeling experiments. Do NOT use for routine weekly pipeline execution.
---

> [!IMPORTANT]
> **Skill Naming Convention**: This skill is named **improva**. In chat responses, explanations, and documentation links, ALWAYS refer to it simply as `improva` (or [`improva`](file://...)). NEVER output `SKILL.md` or `improva/SKILL.md`.

# PLL Fantasy Prediction Engine — Backlog & Baselines (improva)

This skill maintains the prioritized improvement backlog, the active production baseline (**Baseline 19**), and the mathematical evaluation rules for proposed changes to the prediction pipeline.

---

## 1. Active Production Benchmark: Baseline 19

**Baseline 19** (established October 2026) incorporates **Item 70 (Position-Switch Rescue, Small-Sample Shrunk EV Anchor + 15-Game Recency Blend, & Direct Faceoff EV Blend)** on top of Baseline 18 (Item 68 Full-History Classifier Training + OOF Walk-Forward Calibration), Baseline 17 Track A Legitimacy & Data Integrity Fixes (Items 62–67), Baseline 16 Starting Goalie Designation System, Baseline 15 Faceoff Bradley-Terry Exponential Decay, Baseline 14 multi-position recency weighting (`factor=0.3`), and Baseline 13 position-specific XGBoost hyperparameters:
- **Item 70 (Position-Switch Rescue, Small-Sample Shrunk EV Anchor & Direct Faceoff EV Blend)**:
  1. **70a (Position-Switch Rescue)**: Rescues cross-position career mean, 15-game mean, and game count from `player_histories[(first, last)]` whenever a veteran player has `n_games_played == 0` at a newly assigned `positionGroup` (`33` player-weeks across 2025–2026 including Bernhardt, Garnsey, King, Carroll, Kurtz, Eicher, Currier).
  2. **70b (Small-Sample Bayesian Salary-Prior Shrinkage + 15-Game Recency Blend)**: Shrinks `base_fp` for small-sample non-Faceoff players (`n_g < 4`) toward `clip(salary / 1.3333, 6.0, 22.0)` with Bayesian weight `w_g = n_g / (n_g + 2.0)`, and blends `85% fp_season_avg + 15% fp_last15_avg` for established `Attack`, `Midfield`, and `Defense` players (`n_g >= 4`).
  3. **70c (Direct Faceoff EV Blend)**: Blends `70%` player-anchored EV with `30%` direct Bradley-Terry + specialist-share `PredictedPoints` (`ITEM70_FO_DIRECT_WEIGHT = 0.30`).
- **Item 68 (Baseline 18 Foundation)**: `TimeSeriesSplit(n_splits=4)` in-fold scaled OOF `PredictedPoints` + 4-horizon expanding & 100% full-history `XGBClassifier` ensemble calibrated via walk-forward OOF `IsotonicRegression` (`[0.15, 0.20, 0.25, 0.40]`).
- **Items 62–67 (Baseline 17 Foundation)**: Strict Pre-Game Goalie Starter Designation (`ALLOW_RETROSPECTIVE_GOALIE_OVERRIDES = False`, 94.9% pre-game accuracy), Year-Scoped Gameday Rosters & Injury/Scratch Parity, Monte Carlo Year-Parsing Fix & 2019–2022 Exclusion, Historical Team/Opponent Integrity (`CHR` $\rightarrow$ `OUT`, traded players, phantom DNP stripping), Missing Salary Imputation & Playoff `Coulda Max` Salary Parity, and Evaluation Harness `mc_ev` Continuous Metric Alignment & Seeded Local Search.

### Baseline 19 Portfolio Performance (`MC_EV`, `MC_Win_160`, `MC_Ceil_90`)

| Season | Strategy | Top-1 Total | Top-1 (Avg/Wk) | Top-5 Mean (Avg/Wk) | Top-5 Max (Avg/Wk) | Top-5 Min (Avg/Wk) | Coulda Max (Avg/Wk) | Top-5 Max Ceiling % |
|---|---|---|---|---|---|---|---|---|
| **2025** (13 Wks) | `MC_EV` | **2,335.0 pts** | **179.6 pts/wk** | **171.7 pts/wk** | **196.6 pts/wk** | **148.8 pts/wk** | 359.0 pts/wk | **54.8%** |
| **2025** (13 Wks) | `MC_Win_160` | **2,313.0 pts** | **177.9 pts/wk** | **172.1 pts/wk** | **196.1 pts/wk** | **150.1 pts/wk** | 359.0 pts/wk | **54.6%** |
| **2025** (13 Wks) | `MC_Ceil_90` | **2,412.9 pts** | **185.6 pts/wk** | **182.3 pts/wk** | **213.8 pts/wk** | **151.3 pts/wk** | 359.0 pts/wk | **59.6%** |
| **2026** (W1–13, 12 Wks) | `MC_EV` | **2,229.5 pts** | **185.8 pts/wk** | **177.4 pts/wk** | **205.8 pts/wk** | **138.9 pts/wk** | 370.4 pts/wk | **55.6%** |
| **2026** (W1–13, 12 Wks) | `MC_Win_160` | **2,157.3 pts** | **179.8 pts/wk** | **176.2 pts/wk** | **205.6 pts/wk** | **136.4 pts/wk** | 370.4 pts/wk | **55.5%** |
| **2026** (W1–13, 12 Wks) | `MC_Ceil_90` | **2,091.0 pts** | **174.3 pts/wk** | **156.9 pts/wk** | **199.3 pts/wk** | **123.3 pts/wk** | 370.4 pts/wk | **53.8%** |
| **2026** (Full 15 Wks) | `MC_EV` | **2,647.5 pts** | **176.5 pts/wk** | **170.1 pts/wk** | **196.6 pts/wk** | **136.9 pts/wk** | 352.5 pts/wk | **55.8%** |
| **2026** (Full 15 Wks) | `MC_Win_160` | **2,575.3 pts** | **171.7 pts/wk** | **169.1 pts/wk** | **196.5 pts/wk** | **134.9 pts/wk** | 352.5 pts/wk | **55.7%** |
| **2026** (Full 15 Wks) | `MC_Ceil_90` | **2,509.0 pts** | **167.3 pts/wk** | **153.2 pts/wk** | **192.1 pts/wk** | **123.3 pts/wk** | 352.5 pts/wk | **54.5%** |

### Baseline 19 Official 22-Metric Benchmark (`MC_EV` Top-1 & `mc_ev` Continuous Predictions)

| Metric | 2025 (13 Wks) | 2026 (15 Wks) | Combined (28 Wks) |
|---|---|---|---|
| **1. `MC_EV` Roster Total (Avg/Wk)** | **2,335.0** (179.6/wk) | **2,647.5** (176.5/wk) | **4,982.5** (177.9/wk) |
| **2. Top-5 Mean Roster Score** | **2,232.7** (171.7/wk) | **2,551.0** (170.1/wk) | **4,783.7** (170.8/wk) |
| **3. Top-5 Max Roster Score** | **2,555.5** (196.6/wk) | **2,949.0** (196.6/wk) | **5,504.5** (196.6/wk) |
| **4. Top-5 Min Roster Score** | **1,935.0** (148.8/wk) | **2,053.5** (136.9/wk) | **3,988.5** (142.4/wk) |
| **5. `MC_Win_160` Roster Total** | **2,313.0** (177.9/wk) | **2,575.3** (171.7/wk) | **4,888.3** (174.6/wk) |
| **6. `MC_Ceil_90` Roster Total** | **2,412.9** (185.6/wk) | **2,509.0** (167.3/wk) | **4,921.9** (175.8/wk) |
| **7. Season Total VOR (Avg/Wk)** | **+709.3** (+54.6/wk) | **+1,558.6** (+103.9/wk) | **+2,267.8** (+81.0/wk) |
| **8. `A_VOR` / Slot** | **+15.6** (19/26 > med) | **+19.2** (22/30 > med) | **+17.5** (41/56 > med) |
| **9. `M_VOR` / Slot** | **+5.5** (16/26 > med) | **+19.3** (25/30 > med) | **+12.9** (41/56 > med) |
| **10. `D_VOR` / Slot** | **+3.5** (8/13 > med) | **+7.5** (11/15 > med) | **+5.6** (19/28 > med) |
| **11. `FO_VOR` / Slot** | **+7.9** (11/13 > med) | **+12.6** (14/15 > med) | **+10.4** (25/28 > med) |
| **12. `G_VOR` / Slot** | **+1.1** (7/13 > med) | **+7.0** (7/15 > med) | **+4.3** (14/28 > med) |
| **13. `Slot_Weighted_Spearman`** | **0.311** | **0.265** | **0.286** |
| **14. `Coulda_Weighted_Spearman`** | **0.308** | **0.267** | **0.286** |
| **15. `Spearman_Correlation` (Overall)** | **0.444** | **0.374** | **0.406** |
| **16. Per-Pos Spearman (`A/M/D/FO/G`)** | **0.321 / 0.220 / 0.210 / 0.419 / 0.477** | **0.282 / 0.242 / 0.258 / 0.242 / 0.294** | **0.301 / 0.232 / 0.236 / 0.322 / 0.370** |
| **17. `MAE` / `Slot_Weighted_MAE`** | **11.15 / 12.36** | **11.24 / 12.67** | **11.19 / 12.53** |
| **18. `RMSE` / `R_Squared` ($R^2$)** | **14.57 / +0.244** | **14.81 / +0.152** | **14.70 / +0.195** |
| **19. `Tier_Accuracy`** | **42.5%** | **41.1%** | **41.7%** |
| **20. `Boom_Precision`** | **32.1%** | **30.6%** | **31.3%** |
| **21. `Boom_Recall`** | **39.6%** | **35.6%** | **37.4%** |
| **22. `Boom_Brier_Score`** | **0.201** | **0.199** | **0.200** |

> [!NOTE]
> For the complete audit history, scores, and post-mortems of **Baselines 1 through 18**, see the [Historical Baselines Archive](references/baseline_archive.md).

---

## 2. Mandatory Rules for A/B Testing & Model Evaluation

1. **User Preference (Precision > Recall)**: The user makes manual player swaps. Optimizations must prioritize **Boom Precision** and $F_{0.5}$ score alongside roster EV to eliminate false-positive trap picks.
2. **Never Recalculate Baselines on the Fly**: Read baseline scores directly from archived CSV files in `baselines/rosters_<strategy>_baseline_<N>.csv`.
3. **Mandatory Top-5 Candidate Pool Archiving**: Baseline roster CSVs MUST ALWAYS store all 5 candidate lineups (ranks 1–5, 35 player rows/wk). Never filter out ranks 2–5.
4. **Mandatory 22-Metric 6-Column Mobile Layout**: All backtests must report results across the 4 standard category tables (Candidate Portfolio, VOR Process Quality, Continuous Error & Spearman, Classification & Calibration). See [evaluata reporting spec](../evaluata/references/reporting_spec.md).
5. **No Deterministic Point Proxies**: Always execute the complete 5-stage production pipeline (`02` $\rightarrow$ `03` $\rightarrow$ `04` $\rightarrow$ `05` $\rightarrow$ `06_optimize_lineups.py`).
6. **SSH-Resilient Detached Execution**: Always launch long backtests as independent background processes via `scratch/start_<job>_silent.vbs`.

---

## 3. Prioritized Improvement Backlog (Future Proposals for Testing Against Baseline 19)

### Track A: Legitimacy, Data Leakage Remediation & Data Integrity Fixes (Completed in Baselines 17–19)

| Status | Item # & Name | Summary of Resolution | Details / Spec Link |
|---|---|---|---|
| **✅ Adopted (B19)** | **Item 70**: Position-Switch Rescue, Shrunk EV Anchor & Direct FO EV | Cross-position history rescue (`n_g==0`), small-sample Bayesian salary-prior shrinkage (`n_g<4`), 15-game recency blend (`15%`), & 30% direct FO EV (+218.5 pts `MC_EV`, +273.2 pts `MC_Ceil_90`) | [Backlog Details](references/backlog_details.md#item-70-ewma--current-season-shrunk-ev-anchor-position-switch-fix--direct-faceoff-ev-adopted-in-baseline-19) |
| **✅ Adopted (B18)** | **Item 68**: Full-History Classifier Training + OOF Walk-Forward Calibration | 4-horizon expanding GBDT + 100% full-history GBDT ensemble with strict in-fold `StandardScaler` & OOF isotonic calibration (+232.3 pts `MC_EV`, +469.6 pts `MC_Win_160`) | [Backlog Details](references/backlog_details.md#item-68-fix-classifier-training-starvation--full-history-gbdt-fit--oof-walk-forward-calibration-adopted-in-baseline-18) |
| **✅ Adopted (B17)** | **Item 62**: Strict Pre-Game Goalie Starter Designation | Gated `goalie_starters.json` behind `ALLOW_RETROSPECTIVE_GOALIE_OVERRIDES = False`; 94.9% accurate pre-game heuristic | [Backlog Details](references/backlog_details.md#item-62-strict-pre-game-goalie-starter-designation-adopted-in-baseline-17) |
| **✅ Adopted (B17)** | **Item 63**: Year-Scoped Gameday Rosters & Injury Parity | Scoped `gameday_rosters` by `year` and ignored mutable API `injuryStatus`; lifted 2026 `MC_EV` by +137.4 pts | [Backlog Details](references/backlog_details.md#item-63-year-scoped-gameday-rosters--pre-game-injuryscratch-parity-adopted-in-baseline-17) |
| **✅ Adopted (B17)** | **Item 64**: MC Year-Parsing Fix & 2019–2022 Exclusion | Fixed `^(\d{4})_` regex and excluded 6,724 pre-2023 rows weighted at `weeks_ago=10` | [Backlog Details](references/backlog_details.md#item-64-monte-carlo-year-parsing-fix--20192022-exclusion-adopted-in-baseline-17) |
| **✅ Adopted (B17)** | **Item 65**: Historical Team/Opponent Integrity & Matchup Keys | Fixed `CHR` $\rightarrow$ `OUT`, 41 traded-player rows, 2,110 phantom DNP rows, and recovered 36/189 pace games & 26/189 FO BT games | [Backlog Details](references/backlog_details.md#item-65-historical-teamopponent-integrity-chr-to-out-traded-players--normalized-matchup-keys-adopted-in-baseline-17) |
| **✅ Adopted (B17)** | **Item 66**: Missing Salary Imputation & Playoff `Coulda Max` | Replaced dead `pre_2023_mask` with `missing_sal_mask` and aligned playoff `Coulda Max` salaries | [Backlog Details](references/backlog_details.md#item-66-missing-salary-imputation-in-training-2023-2025-w1214-2026-w14--coulda-max-salary-parity-adopted-in-baseline-17) |
| **✅ Adopted (B17)** | **Item 67**: Evaluation Harness `mc_ev` Alignment & Seeded Search | Evaluated continuous/Spearman metrics on `mc_ev` (MAE $17.6 \rightarrow 11.3$, $R^2$ $-0.53 \rightarrow +0.17$) and seeded `run_local_search` | [Backlog Details](references/backlog_details.md#item-67-evaluation-harness-mc_ev-continuous-metric-alignment--seeded-local-search-adopted-in-baseline-17) |

### Track B: High-Leverage Modeling, Simulation & Optimization Proposals (To Be Tested One-by-One Against Baseline 19)

Ranked by expected value and likelihood of effectiveness when evaluated against **Baseline 19**:

| Priority | Item # & Name | Category | Expected Impact | Details / Spec Link |
|---|---|---|---|---|
| **1** | **Item 69**: Weekly Relative Ground-Truth Tier Labels in Training (`groupby(year, week, pos)`) | Tier 2 (Target Alignment) | +2 to +6 pts/wk | [Backlog Details](references/backlog_details.md#item-69-weekly-relative-ground-truth-tier-labels-in-training-replace-assign_tiers_expanding) |
| **2** | **Item 39 / 71**: Multi-Quantile Regressor (`p25, p50, p90`) & Skewed Bootstrap CDF Mapping | Tier 3 (Simulation) | +5 to +12 pts/wk | [Backlog Details](references/backlog_details.md#item-71-multi-quantile-distributional-regression-p25-p50-p90--quantile-preserving-mc-bootstrap-upgraded-item-39) |
| **3** | **Item 72**: 2-Opt Pair-Swap Local Search & Correlated Top-5 Pool Generation | Tier 3 (Optimizer) | +2 to +6 pts/wk | [Backlog Details](references/backlog_details.md#item-72-2-opt-pair-swap-local-search--correlated-top-5-candidate-pool-generation) |
| **4** | **Item 32**: Matchup Rating Temporal Decay | Tier 2 (Features) | +3 to +8 pts/wk | [Backlog Details](references/backlog_details.md#item-32-matchup-rating-temporal-decay) |
| **5** | **Item 54**: Per-Position Recency Weight Tuning | Tier 2 (Tuning) | +1 to +4 pts/wk | [Backlog Details](references/backlog_details.md#item-54-per-position-recency-weight-tuning) |
| **6** | **Item 43**: Scoring Environment Multiplier | Tier 3 (Simulation) | +3 to +10 pts/wk | [Backlog Details](references/backlog_details.md#item-43-scoring-environment-multiplier) |
| **7** | **Item 41**: Ensemble Meta-Selector (Strategy Picker) | Tier 3 (Optimizer) | +3 to +8 pts/wk | [Backlog Details](references/backlog_details.md#item-41-ensemble-meta-selector-strategy-picker) |
| **8** | **Item 12**: Dynamic Monte Carlo Correlation Matrix | Tier 3 (Simulator) | +2 to +5 pts/wk | [Backlog Details](references/backlog_details.md#item-12-dynamic-monte-carlo-correlation-matrix) |
| **9** | **Item 44 / 40**: Ownership Archive & Penalty | Tier 3 (Optimizer) | 0 to +3 pts/wk | [Backlog Details](references/backlog_details.md#item-44-historical-ownership-archive--chalk-analysis-prerequisite-for-item-40) |
| **10** | **Item 42**: Player-Level Pairwise Correlations | Tier 3 (Simulation) | +1 to +4 pts/wk | [Backlog Details](references/backlog_details.md#item-42-player-level-mc-correlations) |
| **11** | **Items 16–19**: Pipeline Performance & Safety | Tier 4 (Infra) | Speed & Reliability | [Backlog Details](references/backlog_details.md#tier-4-pipeline-performance--safety) |
| **12** | **Items 20–24**: UI/UX & Live Game-Day Tools | Tier 5 (UX) | Operational Safety | [Backlog Details](references/backlog_details.md#tier-5-uiux--live-game-day-tools) |
| **13** | **Retest Queue (Items 10, 26, 30, 55–58)** | Retest | Various | [Backlog Details](references/backlog_details.md#retest-queue-candidates-for-22-metric-re-evaluation) |

> [!NOTE]
> For detailed reports on all completed trials (Items 9, 11, 27, 33, 36–38, 48–50, 52, 59, 62–68, 70), advanced August 2026 modeling trials (LTR, Option E, Decoupled EV), and tested/rejected experiments (Items 45–47, 51, 53, 60, 61), consult the [Completed & Tested Experiment Archive](references/experiment_archive.md).

---

## Verification Directive

When modifying improvement models or running backtests:
1. Verify baseline archive integrity: `python -c "from utils import get_latest_baseline_num; print(f'Active baseline: {get_latest_baseline_num()}')"` (must output `19`).
2. Run evaluation harness: `python prediction_model_evaluation_harness.py --rosters baselines/rosters_mc_ev_baseline_19.csv --predictions predicta/predictions --year 2026` and verify exit code 0.
