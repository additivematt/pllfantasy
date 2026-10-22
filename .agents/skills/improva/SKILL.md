---
name: improva
description: >-
  Tracks feature backlog, model Baseline 17 benchmarks, and strict A/B backtest evaluation rules.
  Use this skill when reviewing pending improvements, checking official baseline metrics, or planning
  predictive modeling experiments. Do NOT use for routine weekly pipeline execution.
---

> [!IMPORTANT]
> **Skill Naming Convention**: This skill is named **improva**. In chat responses, explanations, and documentation links, ALWAYS refer to it simply as `improva` (or [`improva`](file://...)). NEVER output `SKILL.md` or `improva/SKILL.md`.

# PLL Fantasy Prediction Engine — Backlog & Baselines (improva)

This skill maintains the prioritized improvement backlog, the active production baseline (**Baseline 17**), and the mathematical evaluation rules for proposed changes to the prediction pipeline.

---

## 1. Active Production Benchmark: Baseline 17

**Baseline 17** (established October 2026) incorporates all **Track A Legitimacy, Data Leakage Remediation & Data Integrity Fixes (Items 62–67)** on top of the Baseline 16 Starting Goalie Designation System, Baseline 15 Faceoff Bradley-Terry Exponential Decay, Baseline 14 multi-position recency weighting (`factor=0.3`), and Baseline 13 position-specific XGBoost hyperparameters:
- **Item 62 (Strict Pre-Game Goalie Starter Designation)**: Gated `goalie_starters.json` behind `ALLOW_RETROSPECTIVE_GOALIE_OVERRIDES = False` so historical backtests strictly use the pre-game starter heuristic (`team_last_w` start bonus, year-scoped `gameday_rosters` `rosterStatus`, F2P `projectedPoints` & `salary`, achieving **94.9% pre-game accuracy** across 2025–2026 without post-game box-score overrides).
- **Item 63 (Year-Scoped Gameday Rosters & Pre-Game Injury/Scratch Parity)**: Scoped `gameday_rosters` lookups by `year` across `02_predict_probabilities.py`, `03_apply_roster_filter.py`, and `utils.py` (eliminating 2026 roster cross-contamination in 2025 backtests) and ignored mutable end-of-season API `injuryStatus` on `gameday_rosters_week*.json` in favor of week-specific F2P `injuryStatus` and gameday `rosterStatus`.
- **Item 64 (Monte Carlo Year-Parsing Fix & 2019–2022 Exclusion)**: Normalized `eventId` in `04_simulate_monte_carlo.py` (`load_player_game_history`) and enforced `yr >= 2023`, eliminating 6,724 pre-2023 entries that previously bypassed the regex and received `weeks_ago = 10` ($\exp(-0.5) = 0.607$) recency weight.
- **Item 65 (Historical Team/Opponent Integrity & Matchup Key Normalization)**: Normalized `CHR` $\rightarrow$ `OUT` on `homeTeam`/`awayTeam`/`team`, resolved pre-trade player-year teams for 41 active traded-player rows, stripped 2,110 phantom DNP rows (`ZPP` and cross-team DNP injections), recovered all **36/189 games** previously skipped by `compute_game_pace_features()` and **26/189 games** skipped by Bradley-Terry FO training, normalized `season_matchups_*.json` keys, and applied `filter_played_only()` inside `compute_defender_ratings()`.
- **Item 66 (Missing Salary Imputation & Playoff `Coulda Max` Salary Parity)**: Replaced the dead `pre_2023_mask` in `02_predict_probabilities.py` with `missing_sal_mask` (imputing 2023 and playoff missing training salaries via expanding player salary / `synth_salaries`) and aligned `StatsDatabase.get_week_players()` in `prediction_model_evaluation_harness.py` to use season-to-date average salaries when playoff F2P salaries are missing.
- **Item 67 (Evaluation Harness `mc_ev` Continuous Metric Alignment & Seeded Local Search)**: Persisted `mc_ev`, `mc_std`, and `mc_p90` into `week{W}_{Y}_predictions.csv`, aligned continuous/Spearman metrics in `prediction_model_evaluation_harness.py` to evaluate `mc_ev`, and seeded `np.random.seed(42)` in `utils.run_local_search()`.

### Baseline 17 Portfolio Performance (`MC_EV`, `MC_Win_160`, `MC_Ceil_90`)

| Season | Strategy | Top-1 Total | Top-1 (Avg/Wk) | Top-5 Mean (Avg/Wk) | Top-5 Max (Avg/Wk) | Top-5 Min (Avg/Wk) | Coulda Max (Avg/Wk) | Top-5 Max Ceiling % |
|---|---|---|---|---|---|---|---|---|
| **2025** (13 Wks) | `MC_EV` | **2,206.7 pts** | **169.7 pts/wk** | **166.0 pts/wk** | **187.8 pts/wk** | **144.2 pts/wk** | 359.0 pts/wk | **52.3%** |
| **2025** (13 Wks) | `MC_Win_160` | **2,076.6 pts** | **159.7 pts/wk** | **165.1 pts/wk** | **191.0 pts/wk** | **141.4 pts/wk** | 359.0 pts/wk | **53.2%** |
| **2025** (13 Wks) | `MC_Ceil_90` | **2,197.7 pts** | **169.1 pts/wk** | **168.8 pts/wk** | **194.5 pts/wk** | **144.7 pts/wk** | 359.0 pts/wk | **54.2%** |
| **2026** (W1–13, 12 Wks) | `MC_EV` | **1,951.0 pts** | **162.6 pts/wk** | **166.5 pts/wk** | **195.6 pts/wk** | **137.6 pts/wk** | 370.4 pts/wk | **52.8%** |
| **2026** (W1–13, 12 Wks) | `MC_Win_160` | **1,926.0 pts** | **160.5 pts/wk** | **167.8 pts/wk** | **197.9 pts/wk** | **135.6 pts/wk** | 370.4 pts/wk | **53.4%** |
| **2026** (W1–13, 12 Wks) | `MC_Ceil_90` | **1,954.8 pts** | **162.9 pts/wk** | **150.9 pts/wk** | **178.5 pts/wk** | **123.1 pts/wk** | 370.4 pts/wk | **48.2%** |
| **2026** (Full 15 Wks) | `MC_EV` | **2,325.0 pts** | **155.0 pts/wk** | **161.0 pts/wk** | **189.8 pts/wk** | **132.2 pts/wk** | 352.5 pts/wk | **53.9%** |
| **2026** (Full 15 Wks) | `MC_Win_160` | **2,300.3 pts** | **153.4 pts/wk** | **162.0 pts/wk** | **191.6 pts/wk** | **130.6 pts/wk** | 352.5 pts/wk | **54.4%** |
| **2026** (Full 15 Wks) | `MC_Ceil_90` | **2,340.0 pts** | **156.0 pts/wk** | **149.7 pts/wk** | **177.6 pts/wk** | **120.8 pts/wk** | 352.5 pts/wk | **50.4%** |

### Baseline 17 Official 22-Metric Benchmark (`MC_EV` Top-1 & `mc_ev` Continuous Predictions)

| Metric | 2025 (13 Wks) | 2026 (15 Wks) | Combined (28 Wks) |
|---|---|---|---|
| **1. `MC_EV` Roster Total (Avg/Wk)** | **2,206.7** (169.7/wk) | **2,325.0** (155.0/wk) | **4,531.7** (161.8/wk) |
| **2. Top-5 Mean Roster Score** | **2,158.3** (166.0/wk) | **2,414.5** (161.0/wk) | **4,572.8** (163.3/wk) |
| **3. Top-5 Max Roster Score** | **2,441.8** (187.8/wk) | **2,847.2** (189.8/wk) | **5,289.0** (188.9/wk) |
| **4. Top-5 Min Roster Score** | **1,874.0** (144.2/wk) | **1,983.5** (132.2/wk) | **3,857.5** (137.8/wk) |
| **5. `MC_Win_160` Roster Total** | **2,076.6** (159.7/wk) | **2,300.3** (153.4/wk) | **4,376.9** (156.3/wk) |
| **6. `MC_Ceil_90` Roster Total** | **2,197.7** (169.1/wk) | **2,340.0** (156.0/wk) | **4,537.7** (162.1/wk) |
| **7. Season Total VOR (Avg/Wk)** | **+581.0** (+44.7/wk) | **+1,236.0** (+82.4/wk) | **+1,817.0** (+64.9/wk) |
| **8. `A_VOR` / Slot** | **+13.2** (19/26 > med) | **+16.2** (25/30 > med) | **+14.8** (44/56 > med) |
| **9. `M_VOR` / Slot** | **+2.0** (14/26 > med) | **+14.0** (24/30 > med) | **+8.4** (38/56 > med) |
| **10. `D_VOR` / Slot** | **+7.0** (9/13 > med) | **+7.1** (10/15 > med) | **+7.1** (19/28 > med) |
| **11. `FO_VOR` / Slot** | **+6.6** (10/13 > med) | **+12.6** (13/15 > med) | **+9.8** (23/28 > med) |
| **12. `G_VOR` / Slot** | **+0.7** (7/13 > med) | **+2.2** (7/15 > med) | **+1.5** (14/28 > med) |
| **13. `Slot_Weighted_Spearman`** | **0.296** | **0.241** | **0.267** |
| **14. `Coulda_Weighted_Spearman`** | **0.294** | **0.243** | **0.267** |
| **15. `Spearman_Correlation` (Overall)** | **0.438** | **0.354** | **0.393** |
| **16. Per-Pos Spearman (`A/M/D/FO/G`)** | **0.317 / 0.181 / 0.207 / 0.403 / 0.482** | **0.287 / 0.188 / 0.242 / 0.268 / 0.237** | **0.301 / 0.185 / 0.226 / 0.331 / 0.351** |
| **17. `MAE` / `Slot_Weighted_MAE`** | **11.30 / 12.53** | **11.36 / 12.80** | **11.33 / 12.68** |
| **18. `RMSE` / `R_Squared` ($R^2$)** | **14.73 / +0.226** | **15.04 / +0.126** | **14.90 / +0.173** |
| **19. `Tier_Accuracy`** | **41.4%** | **40.1%** | **40.7%** |
| **20. `Boom_Precision`** | **29.2%** | **28.0%** | **28.6%** |
| **21. `Boom_Recall`** | **37.8%** | **30.1%** | **33.7%** |
| **22. `Boom_Brier_Score`** | **0.206** | **0.198** | **0.202** |

> [!NOTE]
> For the complete audit history, scores, and post-mortems of **Baselines 1 through 16**, see the [Historical Baselines Archive](references/baseline_archive.md).

---

## 2. Mandatory Rules for A/B Testing & Model Evaluation

1. **User Preference (Precision > Recall)**: The user makes manual player swaps. Optimizations must prioritize **Boom Precision** and $F_{0.5}$ score alongside roster EV to eliminate false-positive trap picks.
2. **Never Recalculate Baselines on the Fly**: Read baseline scores directly from archived CSV files in `baselines/rosters_<strategy>_baseline_<N>.csv`.
3. **Mandatory Top-5 Candidate Pool Archiving**: Baseline roster CSVs MUST ALWAYS store all 5 candidate lineups (ranks 1–5, 35 player rows/wk). Never filter out ranks 2–5.
4. **Mandatory 22-Metric 6-Column Mobile Layout**: All backtests must report results across the 4 standard category tables (Candidate Portfolio, VOR Process Quality, Continuous Error & Spearman, Classification & Calibration). See [evaluata reporting spec](../evaluata/references/reporting_spec.md).
5. **No Deterministic Point Proxies**: Always execute the complete 5-stage production pipeline (`02` $\rightarrow$ `03` $\rightarrow$ `04` $\rightarrow$ `05` $\rightarrow$ `06_optimize_lineups.py`).
6. **SSH-Resilient Detached Execution**: Always launch long backtests as independent background processes via `scratch/start_<job>_silent.vbs`.

---

## 3. Prioritized Improvement Backlog (Future Proposals for Testing Against Baseline 17)

### Track A: Legitimacy, Data Leakage Remediation & Data Integrity Fixes (Completed in Baseline 17)

| Status | Item # & Name | Summary of Resolution in Baseline 17 | Details / Spec Link |
|---|---|---|---|
| **✅ Adopted (B17)** | **Item 62**: Strict Pre-Game Goalie Starter Designation | Gated `goalie_starters.json` behind `ALLOW_RETROSPECTIVE_GOALIE_OVERRIDES = False`; 94.9% accurate pre-game heuristic | [Backlog Details](references/backlog_details.md#item-62-strict-pre-game-goalie-starter-designation-adopted-in-baseline-17) |
| **✅ Adopted (B17)** | **Item 63**: Year-Scoped Gameday Rosters & Injury Parity | Scoped `gameday_rosters` by `year` and ignored mutable API `injuryStatus`; lifted 2026 `MC_EV` by +137.4 pts | [Backlog Details](references/backlog_details.md#item-63-year-scoped-gameday-rosters--pre-game-injuryscratch-parity-adopted-in-baseline-17) |
| **✅ Adopted (B17)** | **Item 64**: MC Year-Parsing Fix & 2019–2022 Exclusion | Fixed `^(\d{4})_` regex and excluded 6,724 pre-2023 rows weighted at `weeks_ago=10` | [Backlog Details](references/backlog_details.md#item-64-monte-carlo-year-parsing-fix--20192022-exclusion-adopted-in-baseline-17) |
| **✅ Adopted (B17)** | **Item 65**: Historical Team/Opponent Integrity & Matchup Keys | Fixed `CHR` $\rightarrow$ `OUT`, 41 traded-player rows, 2,110 phantom DNP rows, and recovered 36/189 pace games & 26/189 FO BT games | [Backlog Details](references/backlog_details.md#item-65-historical-teamopponent-integrity-chr-to-out-traded-players--normalized-matchup-keys-adopted-in-baseline-17) |
| **✅ Adopted (B17)** | **Item 66**: Missing Salary Imputation & Playoff `Coulda Max` | Replaced dead `pre_2023_mask` with `missing_sal_mask` and aligned playoff `Coulda Max` salaries | [Backlog Details](references/backlog_details.md#item-66-missing-salary-imputation-in-training-2023-2025-w1214-2026-w14--coulda-max-salary-parity-adopted-in-baseline-17) |
| **✅ Adopted (B17)** | **Item 67**: Evaluation Harness `mc_ev` Alignment & Seeded Search | Evaluated continuous/Spearman metrics on `mc_ev` (MAE $17.6 \rightarrow 11.3$, $R^2$ $-0.53 \rightarrow +0.17$) and seeded `run_local_search` | [Backlog Details](references/backlog_details.md#item-67-evaluation-harness-mc_ev-continuous-metric-alignment--seeded-local-search-adopted-in-baseline-17) |

### Track B: High-Leverage Modeling, Simulation & Optimization Proposals (To Be Tested One-by-One Against Baseline 17)

Ranked by expected value and likelihood of effectiveness when evaluated against **Baseline 17**:

| Priority | Item # & Name | Category | Expected Impact | Details / Spec Link |
|---|---|---|---|---|
| **1** | **Item 68**: Full-History Classifier Training + OOF Walk-Forward Calibration | Tier 2 (Architecture) | +4 to +10 pts/wk | [Backlog Details](references/backlog_details.md#item-68-fix-classifier-training-starvation--full-history-gbdt-fit--oof-walk-forward-calibration) |
| **2** | **Item 70**: EWMA / Current-Season Shrunk EV Anchor, Position-Switch Fix & Direct FO EV | Tier 2/3 (Features & EV) | +4 to +12 pts/wk | [Backlog Details](references/backlog_details.md#item-70-ewma--current-season-shrunk-ev-anchor-position-switch-fix--direct-faceoff-ev) |
| **3** | **Item 69**: Weekly Relative Ground-Truth Tier Labels in Training (`groupby(year, week, pos)`) | Tier 2 (Target Alignment) | +2 to +6 pts/wk | [Backlog Details](references/backlog_details.md#item-69-weekly-relative-ground-truth-tier-labels-in-training-replace-assign_tiers_expanding) |
| **4** | **Item 39 / 71**: Multi-Quantile Regressor (`p25, p50, p90`) & Skewed Bootstrap CDF Mapping | Tier 3 (Simulation) | +5 to +12 pts/wk | [Backlog Details](references/backlog_details.md#item-71-multi-quantile-distributional-regression-p25-p50-p90--quantile-preserving-mc-bootstrap-upgraded-item-39) |
| **5** | **Item 72**: 2-Opt Pair-Swap Local Search & Correlated Top-5 Pool Generation | Tier 3 (Optimizer) | +2 to +6 pts/wk | [Backlog Details](references/backlog_details.md#item-72-2-opt-pair-swap-local-search--correlated-top-5-candidate-pool-generation) |
| **6** | **Item 32**: Matchup Rating Temporal Decay | Tier 2 (Features) | +3 to +8 pts/wk | [Backlog Details](references/backlog_details.md#item-32-matchup-rating-temporal-decay) |
| **7** | **Item 54**: Per-Position Recency Weight Tuning | Tier 2 (Tuning) | +1 to +4 pts/wk | [Backlog Details](references/backlog_details.md#item-54-per-position-recency-weight-tuning) |
| **8** | **Item 43**: Scoring Environment Multiplier | Tier 3 (Simulation) | +3 to +10 pts/wk | [Backlog Details](references/backlog_details.md#item-43-scoring-environment-multiplier) |
| **9** | **Item 41**: Ensemble Meta-Selector (Strategy Picker) | Tier 3 (Optimizer) | +3 to +8 pts/wk | [Backlog Details](references/backlog_details.md#item-41-ensemble-meta-selector-strategy-picker) |
| **10** | **Item 12**: Dynamic Monte Carlo Correlation Matrix | Tier 3 (Simulator) | +2 to +5 pts/wk | [Backlog Details](references/backlog_details.md#item-12-dynamic-monte-carlo-correlation-matrix) |
| **11** | **Item 44 / 40**: Ownership Archive & Penalty | Tier 3 (Optimizer) | 0 to +3 pts/wk | [Backlog Details](references/backlog_details.md#item-44-historical-ownership-archive--chalk-analysis-prerequisite-for-item-40) |
| **12** | **Item 42**: Player-Level Pairwise Correlations | Tier 3 (Simulation) | +1 to +4 pts/wk | [Backlog Details](references/backlog_details.md#item-42-player-level-mc-correlations) |
| **13** | **Items 16–19**: Pipeline Performance & Safety | Tier 4 (Infra) | Speed & Reliability | [Backlog Details](references/backlog_details.md#tier-4-pipeline-performance--safety) |
| **14** | **Items 20–24**: UI/UX & Live Game-Day Tools | Tier 5 (UX) | Operational Safety | [Backlog Details](references/backlog_details.md#tier-5-uiux--live-game-day-tools) |
| **15** | **Retest Queue (Items 10, 26, 30, 55–58)** | Retest | Various | [Backlog Details](references/backlog_details.md#retest-queue-candidates-for-22-metric-re-evaluation) |

> [!NOTE]
> For detailed reports on all completed trials (Items 9, 11, 27, 33, 36–38, 48–50, 52, 59, 62–67), advanced August 2026 modeling trials (LTR, Option E, Decoupled EV), and tested/rejected experiments (Items 45–47, 51, 53, 60, 61), consult the [Completed & Tested Experiment Archive](references/experiment_archive.md).

---

## Verification Directive

When modifying improvement models or running backtests:
1. Verify baseline archive integrity: `python -c "from utils import get_latest_baseline_num; print(f'Active baseline: {get_latest_baseline_num()}')"` (must output `17`).
2. Run evaluation harness: `python prediction_model_evaluation_harness.py --rosters baselines/rosters_mc_ev_baseline_17.csv --predictions predicta/predictions --year 2026` and verify exit code 0.
