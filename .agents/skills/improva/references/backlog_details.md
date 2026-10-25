# PLL Fantasy Prediction Engine — Backlog Item Specifications & Test Plans

> **Context**: Technical problem statements, suggested fixes, and test plans for active backlog items, archived from `improva`. For the prioritized summary, see [improva](../SKILL.md).

---

## Tier 1: Legitimacy, Data Leakage Remediation & Data Integrity Fixes (Adopted in Baseline 17 — October 2026)

> **Status**: All 6 items in Tier 1 (**Items 62–67**) have been implemented and verified in **Baseline 17** (+91.9 pts 2-year `MC_EV` gain, +134.2 pts 2-year `Top-5 Mean` gain, +137.4 pts 2026 `MC_EV` gain, +223.9 pts 2026 `Top-5 Mean` gain, while eliminating 100% retrospective `goalie_starters.json` leakage).

### Item 62: Strict Pre-Game Goalie Starter Designation (Adopted in Baseline 17)
- **Problem**: `utils.get_designated_goalie_starters(year, week)` checked `goalie_starters.json` as Priority #1 before running the automated multi-signal heuristic. Because `goalie_starters.json` was populated for all weeks of 2025 and 2026 using post-game box-score actual starters, the automated heuristic was bypassed 100% of the time during historical backtests.
- **Implemented Fix (Baseline 17)**:
  1. Added `ALLOW_RETROSPECTIVE_GOALIE_OVERRIDES = False` in `config.py` (default `False` for historical backtests).
  2. Strengthened the leak-free heuristic in `utils.get_designated_goalie_starters()` using strictly pre-game signals (`< week`): year-scoped 19-man gameday active roster presence (`-500` pts if scratched or absent; `+30` pts if `rosterStatus == 'starter'`), started in team's most recent game (`+45` pts) or within 2 weeks (`+10` pts), F2P `projectedPoints * 2.0 + salary * 1.0`, and `-500` pts for F2P `injuryStatus in ("IR", "O")`.
- **Verified Result**: Achieved **98.8% (81/82) in 2025** and **91.4% (85/93) in 2026 (94.9% combined)** agreement with actual starters without consulting `goalie_starters.json`.

### Item 63: Year-Scoped Gameday Rosters & Pre-Game Injury/Scratch Parity (Adopted in Baseline 17)
- **Problem**:
  1. `02_predict_probabilities.py` (line 455) and `03_apply_roster_filter.py` (line 17) referenced `gameday_rosters_week{week}.json` without `{year}`.
  2. `gameday_rosters_week*.json` files fetched via the PLL REST API later in the 2026 season contained end-of-season mutated `player.injuryStatus` (`"IR"`/`"O"`), causing `03_apply_roster_filter.py` and `02_predict_probabilities.py` to falsely drop players who were active in early weeks (e.g., Matt DeLuca, Dylan Hess, Cole Kastner, Jon Robbins in 2026 W1).
  3. F2P `injuryStatus in ("IR", "O")` filtering in `02_predict_probabilities.py` was commented out when gameday rosters were unavailable.
- **Implemented Fix (Baseline 17)**:
  1. Scoped local roster files to `gameday_rosters_{year}_week{week}.json` (falling back to `gameday_rosters_week{week}.json` only when `year == 2026` and verifying event slug year).
  2. Ignored mutable API `injuryStatus` on `gameday_rosters_week*.json`, using `rosterStatus in ("active", "starter")` plus week-specific F2P `injuryStatus` from `f2p_{year}_season.json`.

### Item 64: Monte Carlo Year-Parsing Fix & 2019–2022 Exclusion (Adopted in Baseline 17)
- **Problem**: `load_player_game_history()` in `04_simulate_monte_carlo.py` parsed `year` via `re.search(r'^(\d{4})_', e_id)`. In `all_players_stats.json`, **6,967 entries** (all 6,724 entries from 2019–2022 and all 243 entries from the 2024 Playoffs) evaluated to `yr = None`, bypassing the leakage filter and receiving `weeks_ago = 10` ($\exp(-0.05 \times 10) = 0.607$) recency weight.
- **Implemented Fix (Baseline 17)**: Normalized `e_id` via `normalize_event_id(e_id)`, extracted year via `re.search(r'(?:^|-|_)(20\d{2})(?:-|_|$)', e_id)`, and enforced `if yr is None or yr < 2023: continue`.

### Item 65: Historical Team/Opponent Integrity (`CHR` $\rightarrow$ `OUT`, Traded Players, & Normalized Matchup Keys) (Adopted in Baseline 17)
- **Problem**:
  1. `event.homeTeam` and `event.awayTeam` remained `"CHR"` in 2023 while `identity.team` was `"OUT"`, assigning `opponent = "CHR"` on 81 Outlaws rows.
  2. 41 active traded-player rows and 2,110 phantom DNP rows (`ZPP` and cross-team DNP injections) caused **36 out of 189 games (19%)** to have $>2$ unique teams and be skipped by `compute_game_pace_features()`, and **26 out of 189 games** to be dropped from Bradley-Terry Faceoff training.
  3. `load_all_matchups()` did not normalize `season_matchups_*.json` keys, and `compute_defender_ratings()` computed `p_avgs` without `filter_played_only(df_all)`.
- **Implemented Fix (Baseline 17)**: Normalized `"CHR"` $\rightarrow$ `"OUT"`, resolved pre-trade player-year teams, stripped phantom DNP rows where `team not in (home, away)`, recovered 100% of pace and Bradley-Terry games, normalized matchup keys, and applied `filter_played_only(df_all)` inside `compute_defender_ratings()`.

### Item 66: Missing Salary Imputation in Training (`2023`, `2025 W12–14`, `2026 W14`) & `Coulda Max` Salary Parity (Adopted in Baseline 17)
- **Problem**:
  1. `pre_2023_mask = df_all["year"] < 2023` in `02_predict_probabilities.py` was dead code after `df_all["year"] >= 2023`, leaving all 2023 rows at `salary = 10.0`.
  2. `StatsDatabase.get_week_players()` in `prediction_model_evaluation_harness.py` defaulted `salary = None` to `10` coins in 2025 W12–14 and 2026 W14.
- **Implemented Fix (Baseline 17)**: Replaced `pre_2023_mask` with `missing_sal_mask = df_all["salary"].isna() | (df_all["salary"] <= 0)` using expanding player historical salary / `synth_salaries`, and applied STD salary fallback in `StatsDatabase.get_week_players()`.

### Item 67: Evaluation Harness `mc_ev` Continuous Metric Alignment & Seeded Local Search (Adopted in Baseline 17)
- **Problem**: `prediction_model_evaluation_harness.py` computed `MAE`, `RMSE`, `Pearson`, and `Spearman` on Stage-1 `p90` `PredictedPoints` instead of `mc_ev`, and `utils.run_local_search()` was unseeded.
- **Implemented Fix (Baseline 17)**: Persisted `mc_ev`, `mc_std`, and `mc_p90` into `week{W}_{Y}_predictions.csv`, evaluated continuous/rank metrics on `mc_ev` (reducing evaluated MAE from `~17.6` to `11.33` and lifting $R^2$ from `-0.53` to `+0.173`), and seeded `np.random.seed(42)` in `utils.run_local_search()`.

---

## Tier 2: Model & Feature Improvements (Accuracy)

### Item 68: Fix Classifier Training Starvation — Full-History GBDT Fit + OOF Walk-Forward Calibration (Adopted in Baseline 18)
- **Problem**: In `02_predict_probabilities.py` (lines 986–1048), `TimeSeriesSplit(n_splits=3)` for OOF `PredictedPoints` dropped the oldest 25% of `df_pg`, and passing the remaining 75% (`clf_train`) into `CalibratedClassifierCV(cv=TimeSeriesSplit(n_splits=3))` trained 3 internal `XGBClassifier` models on only 18.75%, 37.5%, and 56.25% of history. **No classifier tree ever trained on the most recent 18.75% of games (practically the entire current season!)**, and 2/3 of the ensemble was blind to the most recent 37.5%–56.25% of games. Additionally, `sc_clf = StandardScaler()` was fit globally on `clf_train` before `TimeSeriesSplit`.
- **Implemented Fix (Baseline 18)**:
  1. Expanded Stage-1 `XGBRegressor` OOF generation to `TimeSeriesSplit(n_splits=4)` with strict in-fold `StandardScaler` fitting, increasing `clf_train` coverage from 75% to 80% of `df_pg`.
  2. Fit `StandardScaler`, `XGBClassifier`, and fold-matched `IsotonicRegression` strictly inside each walk-forward fold (`TimeSeriesSplit(n_splits=3)`) of `clf_train`.
  3. Added a 4th **Full-History `XGBClassifier`** trained on **100% of `clf_train`** (so all current-season games train the decision trees), calibrated via pooled walk-forward OOF `IsotonicRegression` (`0.90 * iso_pool + 0.10 * raw_te`), and blended the 4 expanding horizons with recency weights `[0.15, 0.20, 0.25, 0.40]` (`ITEM68_FULL_HISTORY_CLF_ENABLED = True` in `config.py`).
- **Verified Result**: Delivered **+232.3 pts (+8.3 pts/wk)** in 2-year `MC_EV` Top-1 (`4,531.7` $\rightarrow$ `4,764.0`), **+469.6 pts (+16.8 pts/wk)** in `MC_Win_160` (`4,376.9` $\rightarrow$ `4,846.5`), **+111.0 pts (+4.0 pts/wk)** in `MC_Ceil_90` (`4,537.7` $\rightarrow$ `4,648.7`), **+119.6 pts** in `Top-5 Mean`, **+213.0 pts (+7.6 pts/wk)** in `Top-5 Min` floor, **+2.7%** in `Boom_Precision` (`28.6%` $\rightarrow$ `31.3%`), **+3.8%** in `Boom_Recall` (`33.7%` $\rightarrow$ `37.4%`), and lifted `Slot_Weighted_Spearman` (`0.2666` $\rightarrow$ `0.2787`).

### Item 69: Weekly Relative Ground-Truth Tier Labels in Training (Replace `assign_tiers_expanding`)
- **Problem**: `df_train["PerformanceTier"]` uses `assign_tiers_expanding` (global multi-year expanding quantiles with intra-game `.shift(1)` drift), whereas evaluation (`evaluata`) and MC simulation (`04_simulate_monte_carlo.py`) define `Boom` as `> q75` within each `(year, week, positionGroup)`. Because `df_train` only contains completed past weeks (`week < target_week`), computing weekly positional quantiles on `df_train` has zero lookahead leakage.
- **Suggested Fix**: Compute `df_train["PerformanceTier"]` via `df_train.groupby(["year", "week", "positionGroup"])["TotalFantasyPoints"].transform(assign_weekly_tiers)` (with fallback to expanding quantiles only if a cell has $< 4$ active players).
- **Success Criteria**: Improved `Tier_Accuracy`, `Boom_Precision`, `Boom_Brier_Score`, and `MC_EV` portfolio scores.

### Item 70: EWMA / Current-Season Shrunk EV Anchor, Position-Switch Fix & Direct Faceoff EV
- **Problem**:
  1. `02_predict_probabilities.py` (line 246) groups `p_avgs` by `["firstName", "lastName", "positionGroup"]`, wiping out prior history on `df_test` for **47 players** who switched positions across 2023–2026 (`Brandau`, `Kurtz`, `Currier`, `Bernhardt`, `King`, etc.), whereas `df_train` groups by `["firstName", "lastName"]`.
  2. `fp_season_avg` is an unweighted 2023–2026 career average, causing `USE_PLAYER_ANCHORED_EV` in `04_simulate_monte_carlo.py` to anchor 2026 EV to 4-year unweighted averages.
  3. For Faceoff, `04_simulate_monte_carlo.py` overwrites the Bradley-Terry + share-scaled `PredictedPoints` with `fp_season_avg * (0.5 + BoomProb/100)`, and `02_predict_probabilities.py` omits `-3.0 * turnovers` from the FO EV formula.
- **Suggested Fix**:
  1. Group `p_avgs` by `["firstName", "lastName"]`.
  2. Anchor MC `EV` to a Bayesian shrinkage blend of `fp_ewma_4` (or current-season STD average) and career `fp_season_avg` ($K \in \{3, 5\}$).
  3. Include `-3.0 * to_rate_shrunk` in Faceoff `ev` (`02_predict_probabilities.py`) and use `PredictedPoints` directly as `EV` for `positionGroup == "Faceoff"` in `04_simulate_monte_carlo.py`.
- **Success Criteria**: Lift in A/M/FO Spearman $\rho$ and +4 to +12 pts/wk in `MC_EV` / `MC_Win_160`.

### Item 71: Multi-Quantile Distributional Regression (`p25, p50, p90`) + Quantile-Preserving MC Bootstrap (Upgraded Item 39)
- **Problem**: Single-quantile regression (`alpha = 0.90`) only predicts ceiling, and `04_simulate_monte_carlo.py` applies a linear multiplier (`raw_scores * mult`) to historical bootstrap samples, distorting right-skewed tail distributions.
- **Suggested Fix**: Fit 3 quantile regressors ($\alpha \in \{0.25, 0.50, 0.90\}$) in `02_predict_probabilities.py` (enforcing monotonicity $\hat{q}_{25} \le \hat{q}_{50} \le \hat{q}_{90}$) and apply a piecewise-linear quantile-preserving transformation in `04_simulate_monte_carlo.py`.

### Item 72: 2-Opt Pair-Swap Local Search & Correlated Top-5 Candidate Pool Generation
- **Problem**:
  1. `utils.run_local_search` (now seeded in Baseline 17) only explores 1-player swaps (`1-opt`), getting stuck in budget-locked local optima when lineup cost is 198–200 coins.
  2. In `06_optimize_lineups.py` (lines 471–493), Ranks 2–5 for `MC_Win_160` and `MC_Ceil_90` are generated by an uncorrelated MILP on `mc_ev` / `mc_p90` instead of optimizing over `sim_matrix`.
- **Suggested Fix**: Add a 2-opt pair-swap pass in `utils.run_local_search` (simultaneously upgrading slot $i$ and downgrading slot $j$ within the 200-coin cap), and generate Ranks 2–5 via correlated local search with an overlap cut ($\le 5$ shared players with prior ranks).

### Item 32: Matchup Rating Temporal Decay
- **Problem**: Defender and opponent ratings use career averages, weighting ancient games identically to recent matchups.
- **Why it matters**: Defensive unit strength and defender capabilities change over seasons.
- **Suggested Fix**: Apply exponential decay weighting (similar to `LAMBDA_RECENCY`) to historical matchup ratings so recent games dictate the rating.
- **Success Criteria**: Matchup ratings reflect current defender and team form without degrading cross-season MAE.

### Item 54: Per-Position Recency Weight Tuning
- **Problem**: The recency sample weight factor is applied uniformly at 0.3 across all four GBDT position groups (Attack, Midfield, Defense, Goalie). Config variable `ATTACK_RECENCY_WEIGHT` exists in `config.py` but is unused in `02_predict_probabilities.py`.
- **Why it matters**: Positions have different optimal recency emphasis. Goalie is highly matchup-dependent week-to-week; Midfield is heterogeneous and may overfit to recent role changes.
- **Prior Empirical Findings**: Uniform factor=0.3 produced Defense (+4.3% '25, +5.2% '26 Spearman), Goalie (+9.2% '26 Spearman), Attack (+32.2% '25, -4.5% '26 Spearman), and Midfield (-2.0% '25, +5.7% '26 Spearman).
- **Proposed Fix**: Wire up per-position recency weight variables in `02_predict_probabilities.py` and sweep a grid of factors (0.1, 0.2, 0.3, 0.4, 0.5) per position.
- **Success Criteria**: Per-position Spearman ρ improvement vs uniform 0.3 in at least 2 of 4 positions without degrading the others.

---

## Tier 3: Simulation & Optimization Enhancements

### Item 12: Dynamic Monte Carlo Correlation Matrix
- **Problem**: The Gaussian Copula correlation matrix uses ~15 hardcoded, static correlation coefficients.
- **Why it matters**: Correlation structures drift with rule changes and personnel changes.
- **Suggested Fix**: Dynamically compute position-pair Pearson correlations from the season dataset at simulation runtime (caching per season).
- **Success Criteria**: Elimination of hardcoded correlations from `04_simulate_monte_carlo.py`.

### Item 14: Review MC Ceiling Clamp
- **Problem**: The simulator clamps simulated scores to `[0, max_historical * 1.15]`.
- **Status Note**: In current production, `CEILING_CLAMP_MULTIPLIER = None` (clamp is disabled). Revisit if extreme tail outliers distort tournament simulations.

### Item 39: Skewed Bootstrap — Quantile-Preserving MC Transformation
- **Problem**: The MC simulator applies a linear matchup multiplier (`score * EV / historical_avg`) to bootstrap samples. Lacrosse scoring is right-skewed; a linear multiplier shifts the entire distribution uniformly, distorting tail shape.
- **Why it matters**: Distorted tails hurt ceiling-based strategies (`MC_Ceil_90`, `MC_Win_160`).
- **Suggested Fix**: Quantile-preserving transformation: map each bootstrap sample to its percentile in the player's historical CDF, then map that percentile to the predicted CDF.
- **Success Criteria**: Better alignment between simulated and actual tail distributions; improved tournament strategy calibration.

### Item 40: Opponent Ownership Penalty in Optimizer
- **Problem**: The `MC_EV` optimizer selects purely on expected value without considering rival ownership rates.
- **Caveat**: In cumulative season-long scoring, EV maximization is provably optimal. This is only useful for head-to-head weekly formats.
- **Suggested Fix**: `adjusted_EV = MC_EV - α * global_ownership_rate`. Requires historical ownership data (Item 44).

### Item 44: Historical Ownership Archive & Chalk Analysis (Prerequisite for Item 40)
- **Problem**: Consensus ownership data (`08_scrape_challenger_rosters.py`) is only retained for limited weeks. No historical archive exists to evaluate whether "chalk" underperforms expectations.
- **Suggested Fix**:
  1. Modify Phase 2 workflow to archive ownership JSONs permanently to `data/ownership_archive/`.
  2. Build `scratch/analyze_ownership_curse.py` computing residuals (`actual - predicted`) by ownership quintile.
  3. Proceed with Item 40 only if the top quintile exhibits significant negative residuals ($p < 0.10$).

### Item 41: Ensemble Meta-Selector (Strategy Picker)
- **Problem**: Pipeline runs `MC_EV` and `MC_Win_160`, but user manually selects which to deploy. `MC_Win_160` beat `MC_EV` in 2026 but trailed in 2025.
- **Suggested Fix**: Train a meta-model picking the best strategy per week based on number of games, salary pool depth, and slate volatility.
- **Success Criteria**: Outperforms static `MC_EV` by $\ge 10\text{ pts/season}$.

### Item 42: Player-Level MC Correlations
- **Problem**: Gaussian Copula applies uniform position-pair correlations. Elite pairs (e.g. Shellenberger + Teat) correlate higher than journeymen.
- **Suggested Fix**: Compute player-specific pairwise Pearson correlations using Ledoit-Wolf shrinkage. Fall back to position defaults when samples are small.

### Item 43: Scoring Environment Multiplier
- **Problem**: When two high-scoring offenses meet, individual ceilings elevate beyond what team game pace captures.
- **Suggested Fix**: Multiplicative scoring environment factor based on combined recent scoring rates applied as a distribution-wide inflation factor in MC simulation.

---

## Tier 4: Pipeline Performance & Safety

### Item 16: Data Validation and Silent Failures
- **Problem**: Silent failures exist: `03_apply_roster_filter.py` silently drops unmatched names; missing matchups are silently skipped.
- **Suggested Fix**: Descriptive warning reports and strict validation assertions during execution.

### Item 17: Pipeline Parallelism
- **Problem**: Sequential execution of classifier, regressor, and simulator is slow.
- **Suggested Fix**: Run independent stages in parallel sub-processes.

### Item 18: File I/O Bottlenecks (Parquet)
- **Problem**: 20MB+ CSV files read/written between stages.
- **Suggested Fix**: Binary Parquet format or in-memory execution.

### Item 19: Standard Logging and Unit Tests
- **Problem**: Reliance on `print()` and lack of automated unit tests.
- **Suggested Fix**: Standard `logging` module and `pytest` suite for feature engineering.

---

## Tier 5: UI/UX & Live Game-Day Tools

### Item 20: Migrate UI to MC EV and Surface Confidence Bands
- **Problem**: UI uses legacy categorical EV / Boom% fields.
- **Suggested Fix**: Display `mc_ev` and $p_{10}$–$p_{90}$ outcome range bars natively on the Plotly dashboard.

### Item 21: Season-Long Tracking Dashboard
- **Suggested Fix**: Track cumulative model score vs Coulda Optimizer ceiling across weeks.

### Item 22: Roster Change Detector & Alerts
- **Suggested Fix**: Game-day polling script to alert if selected players are scratched.

### Item 23: Coulda Extensions (Regret Analysis)
- **Suggested Fix**: Output top 3 single-player swaps that would have gained the most points in Coulda post-game analysis.

### Item 24: Matchup Tagger Upgrades
- **Suggested Fix**: Add switch tracking, tag confidence field (High/Medium/Unsure), and defender combination ratings.

---

## Retest Queue (Candidates for 22-Metric Re-evaluation)

### Item 55: Defense Assists & Shots
- Add `assists_season_avg/last3_avg` and `shots_season_avg/last3_avg` to Defense (`FEATURE_DEF_STATS_ENABLED = True`).

### Item 56: Goalie Ground Balls & Caused Turnovers
- Add `groundBalls_season_avg/last3_avg` and `causedTurnovers_season_avg/last3_avg` to Goalie (`FEATURE_GOALIE_GB_CT_ENABLED = True`).

### Item 57: Squad & Defensive Unit Churn
- Add `team_roster_churn` and `opp_def_churn` (`FEATURE_SQUAD_CHURN_ENABLED = True`).

### Item 58: Retiring 1v1 Defensive Pairings for Non-FO Positions
- Remove `pairing_rating` from Attack, Midfield, Defense, and Goalie, keeping it exclusively for Faceoff (`FEATURE_RETIRE_1V1_PAIRINGS_ENABLED = True`).

### Item 10: Player Usage and Field Time Proxy
- Re-evaluate touch anomaly and usage proxy features (`USAGE_HEALTH_FEATURES_ENABLED = True`) against Baseline 15 using VOR and per-position Spearman ρ.

### Items 26 & 30: Stacked Regressor / Multi-Quantile
- Rebuild cleanly against Baseline 15 hyperparameters and evaluate across full 22-metric suite.
