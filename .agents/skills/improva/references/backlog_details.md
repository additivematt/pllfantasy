# PLL Fantasy Prediction Engine — Backlog Item Specifications & Test Plans

> **Context**: Technical problem statements, suggested fixes, and test plans for active backlog items, archived from `improva`. For the prioritized summary, see [improva](../SKILL.md).

---

## Tier 2: Model & Feature Improvements (Accuracy)

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
