---
name: improva
description: Central tracking for feature improvements, model baseline audits (Baseline 3), and A/B backtest evaluation rules.
---

# PLL Fantasy Prediction Engine — Improvement Ideas

> **Date**: June 2026 (updated July 2026 — V2 Updates)  
> **Scope**: A deep-dive review of all documentation (`.md` files) and source code to identify accuracy, architecture, and reliability improvement opportunities, supplemented with predictive modeling optimizations tailored for small-sample high-possession sports leagues.

---

## Centralized Improvement Policy
All improvement ideas, including feature proposals, architectural refactors, simulation enhancements, and UI upgrades, MUST be recorded in this document. Individual feature docs should link here and must not maintain separate/independent lists of improvements.

---

## Target Success Criteria & Evaluation Baseline
To ensure that changes are mathematically sound and do not degrade model performance:
- **Baseline Metric**: The table below defines the official baseline backtest metrics established on **17 July 2026** (Baseline 10, Generative Faceoff Heuristic + Salary as a Feature + Asymmetric Class Weighting + Pool Blending).

### Baseline 10 (Bradley-Terry & Generative Heuristic — 17 July 2026)

Established after integrating the Bradley-Terry matchup win probability model and propensity-shrunk statistics for the Faceoff position, while maintaining the Salary as a Feature GBDT model for other position groups.

| Season | Strategy | Total Score | Coulda Max | Ceiling % | Notes (vs. Baseline 9) |
|---|---|---|---|---|---|
| 2025 | MC_EV | 2219.3 | 4679.1 | 47.4% | **+134.3 pts** (on identical weeks) |
| 2025 | MC_Ceil_90 | 2322.8 | 4679.1 | 49.6% | **+35.5 pts** |
| 2025 | MC_Win_160 | 2290.9 | 4679.1 | 49.0% | **+72.8 pts** |
| 2026 | MC_EV | 1154.3 | 2525.0 | 45.7% | **-11.1 pts** (noise) |
| 2026 | MC_Ceil_90 | 934.2 | 2525.0 | 37.0% | **+1.8 pts** |
| 2026 | MC_Win_160 | 1167.5 | 2525.0 | 46.2% | **+9.3 pts** |

- **Target Threshold**: A proposed feature or logic change will be accepted if it demonstrates a statistically significant improvement over these baselines (paired t-test p-value < 0.05) without increasing runtimes by more than 20%, or if it fixes a critical code health issue without degrading performance.
- **RNG Reproducibility**: All backtests must run under a fixed random seed to ensure comparison consistency.

> [Safe/Default Mode]
> **Instructions for AI Agents / Backtesting Rules:**
> 1. **Do NOT Re-Backtest the Baseline**: When A/B testing a new feature, do not waste compute resources re-running backtests for baseline configurations. All baseline scores are frozen and archived directly in `baselines/rosters_<strategy>_baseline_10.csv` (which includes the `actualPoints` column). Use those existing scores for comparison.
> 2. **Do NOT Create New Baselines**: Do not establish a new baseline or overwrite Baseline 10 data unless the user explicitly instructs you to do so.
> 3. **Prior Baselines are superseded**: Baseline 3 through 9 scores are now invalid comparison points due to being superseded. Do not use them for future comparisons.

> [!NOTE]
> **Baseline 3 Discrepancy Resolved (13 July 2026):**
> The discrepancy between fresh control runs and the frozen Baseline 3 scores was traced to a pipeline bug where `scratch/run_baseline3_backtest.py` omitted running `03_apply_roster_filter.py`. As a result, simulations and optimizations in Baseline 3 were executed on stale prediction files containing data leakage and DNP-polluted features. This has been resolved by establishing Baseline 5 on the corrected pipeline.

---

## Recommended Priority Order (Accuracy Improvements)
The following items represent the highest-impact improvements for **prediction accuracy**, ordered by priority. Item 27 (data leakage elimination) is the **mandatory prerequisite** — all other improvements must be tested on a leak-free pipeline.

> [!IMPORTANT]
> **Boom Recall is the #1 bottleneck** (9 July 2026 analysis):
> Baseline 6 Boom recall and cash game stability have been improved by asymmetric class weighting and pool blending, but it remains a target area. All active backlog items must now be A/B tested against Baseline 6's optimal configuration.


#### Item 33: Position-Specific XGBoost Hyperparameter Tuning *(elevated from Tier 2)*
- **Problem**: All five position groups use identical model configurations and tree depths regardless of sample size.
- **Why it matters**: Attack has ~48 rows/season while Goalie has ~16. The Goalie model is highly susceptible to overfitting under generic defaults. The per-position accuracy gaps (Goalie: 26.1%, Faceoff: 21.4% overall accuracy) are a major driver of the ceiling % plateau.
- **Suggested Fix**: Define and grid-search position-specific hyperparameters (`n_estimators`, `max_depth`, `learning_rate`, `min_child_weight`) using the harness. For small-sample positions (FO, Goalie), use lower `max_depth` (3–4), higher `min_child_weight` (5–10), and fewer `n_estimators` (50–100).
- **A/B Test Plan**: Grid-search per position using the evaluation harness. Compare per-position accuracy and total Ceiling % vs Baseline 6.
- **Success Criteria**: Customized hyperparameter configurations active per position group. Goalie and FO accuracy improvements without degrading Attack/Midfield.
- **Status**: ⏳ Pending re-test against Baseline 6.

#### Item 45: The Continuous Target Pivot (Regression Pipeline Integration)
- **Problem**: Forcing the prediction engine into discrete categorical tiers (Boom/Average/Bust) throws away massive amounts of ordinal variance. The difference between a high-tier and low-tier "Average" performance is completely smoothed out, blinding the linear programming optimizer to granular value edges.
- **Why it matters**: Optimization under tight salary caps requires exact expected values. Relying on class probabilities to derive continuous MC EV distributions creates artificial clipping and sub-optimal roster allocations.
- **Suggested Fix**: Implement an XGBoost Regressor pipeline running in parallel with (or replacing) the classifier. Have the regressor target raw fantasy points directly. Use the continuous output to anchor the mean of the Monte Carlo bootstrap distributions.
- **A/B Test Plan**: Run the evaluation harness using continuous regression-driven expected values for roster optimization. Measure net impact on 2025 and 2026 Ceiling % against Baseline 6.
- **Success Criteria**: Statistically significant positive shift in Ceiling % across both seasons, completely bypassing the 0% Faceoff classifier plateau.
- **Status**: ⏳ Pending re-test against Baseline 6.



---

## Baseline Version History & Performance Tracking

To track historical performance changes and maintain auditability across key milestones, we document each baseline iteration below. All active roster files are stored in the `baselines/` directory.

> [!NOTE]
> **Baseline Roster Generation Policy:**
> Every time a new baseline is established and rosters are saved to `baselines/`, we must include the actual player scores in the `.csv` files as an `actualPoints` column. This is achieved by running `scratch/append_actual_points.py` (which matches files dynamically like `rosters_*_baseline_*.csv`), cross-referencing selected player names and `eventId`s against the post-game database in `combined_player_stats_YYYY.json` to calculate and write the correct fantasy points. This preserves the out-of-sample scores directly inside the roster artifacts without requiring subsequent lookups or re-evaluations.
> 
> **CRITICAL**: Before finalizing a new baseline (e.g., Baseline 4+), always execute `scratch/append_actual_points.py` and verify that the `actualPoints` column is successfully populated in the roster CSV files. Do not skip this step.

> [!WARNING]
> **Historic Baselines Compromised:**
> All previous baselines (formerly Baselines 1 through 8) have been removed from this document. They were fundamentally compromised by a combination of pipeline bugs (stale file retention), database corrections (doubleheaders), and several sources of data leakage (including future-leaking matchup ratings, non-chronological cross-validation, and full-season tier thresholds). The baseline below represents the first truly clean, leak-free reference point (established 1 July 2026). All future A/B testing must compare against this standard.

### Baseline 1 (Leak-Free — 1 July 2026)
- **Status**: ⚠️ **Superseded**. The first clean baseline after resolving 6 data leakage sources. Baseline established a floor of 46.3% Ceiling % for MC_EV in 2025.

### Baseline 2 (Leak-Free + EWMA — 3 July 2026)
- **Status**: ⚠️ **Superseded**. Enabled EWMA features. Later found to be compromised by DNP pollution in rolling averages and included invalid All-Star game data.

### Baseline 3 (DNP-Clean Rolling Features — 8 July 2026)
- **Status**: ⚠️ **Superseded**. Compromised by a pipeline execution bug where `03_apply_roster_filter.py` was skipped during backtest, leading to artificially inflated scores.

### Baseline 4 (DNP-Clean Rolling Features — Corrected Pipeline — 13 July 2026)
- **Status**: ⚠️ **Superseded**. The true leak-free baseline for DNP-cleaned features. Established a true score of 2000.0 pts for MC_EV in 2025 (42.7% Ceiling).

### Baseline 5 (Asymmetric Class Weighting — Optimal Boom Weight 2.0 — 14 July 2026)
- **Status**: ⚠️ **Superseded**. Applied an optimal class weight of 2.0 to penalize missed Booms, which resulted in a massive breakout for tournament strategies and overall EV.

### Baseline 6 (Optimal Weight 2.0 + Pool Blending K=15 — 15 July 2026)
- **Status**: ⚠️ **Superseded**. Enabled Smooth MC Historical Pool Blending ($K=15$), providing consistent standalone improvement for the primary `MC_EV` strategy across both seasons.

### Baseline 7 (DNP Feature Pollution Fix — 15 July 2026)
- **Status**: ⚠️ **Superseded**. Fixed a DNP feature pollution bug in prediction averages. This correctly modeled tail probabilities, causing tournament strategies (`MC_Win_160`) to explode in scoring.

### Baseline 8 (Codebase Audit & Fallback Fixes — 15 July 2026)
- **Status**: ⚠️ **Superseded by Baseline 9**. Implemented fixes for multiple medium and low priority bugs (missing stat fallbacks, string parsing bugs). Smoothed and corrected the baseline to be fully leak-free and bug-free prior to Salary feature integration.

### Baseline 9 (Market Consensus: Salary As Feature — 16 July 2026)
- **Status**: ⚠️ **Superseded by Baseline 10**. Set `SALARY_AS_FEATURE = True` in production config. This incorporates normalized salary percentile into the GBDT model.

### Baseline 10 (Bradley-Terry & Generative Heuristic — 17 July 2026)
- **Changes / Description**: Bypasses the GBDT classifier for the Faceoff position and implements a generative Bradley-Terry matchup win probability model scaled by expected pace and shrunk player-specific stats (ground balls, goals, assists, caused turnovers).
- **Roster Files**: All Baseline 10 rosters are archived in the `baselines/` directory as `rosters_<strategy>_baseline_10.csv`.
- **Performance Summary**:

  | Season | Strategy | Total Score | Coulda Max | Ceiling % | Notes (vs. Baseline 9) |
  |---|---|---|---|---|---|
  | 2025 | MC_EV | 2219.3 | 4679.1 | 47.4% | **+134.3 pts** (on identical evaluated weeks) |
  | 2026 | MC_EV | 895.6 | 1841.3 | 48.6% | -3.2 pts (noise on identical evaluated weeks) |

- **Interpretation**: The generative faceoff model is a major success. By replacing GBDT classifier predictions (which had 0% Boom recall/precision) with head-to-head win probability modeling and individual stat propensity, it yielded a massive +134.3 points improvement in 2025 and neutral results in 2026. This is now the official production configuration.

---

## Core Priorities (Thematic Grouping)

### Tier 2: Model & Feature Improvements (Accuracy)

#### Item 32: Matchup Rating Temporal Decay
- **Problem**: Defender and opponent ratings use career averages, weighting ancient games the same as recent matchups.
- **Why it matters**: Defensive unit strength and defender capabilities change over seasons, making old matchup data stale.
- **Suggested Fix**: Apply exponential decay weighting (similar to `LAMBDA_RECENCY`) to historical matchup ratings so recent games dictate the rating.
- **Success Criteria**: Matchup ratings reflect current defender and team performance.

*(Item 33 has been elevated to Tier 1 — see Recommended Priority Order above.)*

---

### Tier 3: Simulation & Optimization Enhancements

#### Item 12: Dynamic Monte Carlo Correlation Matrix
- **Problem**: The Gaussian Copula correlation matrix uses ~15 hardcoded, static correlation coefficients.
- **Why it matters**: Correlation structures drift with rule changes or player style changes.
- **Suggested Fix**: Dynamically compute position-pair Pearson correlations from the season dataset at simulation runtime, caching it per season.
- **Success Criteria**: Elimination of hardcoded correlations from `04_simulate_monte_carlo.py`.

#### Item 14: Review MC Ceiling Clamp
- **Problem**: The simulator clamps simulated scores to `[0, max_historical * 1.15]`.
- **Why it matters**: An arbitrary 1.15 multiplier limits the simulated ceiling of breakout players, which hurts ceiling-based tournament optimizations.
- **Suggested Fix**: Re-evaluate the clamp against historic breakout frequencies and scale the clamp dynamically (e.g. based on position group volatility).
- **Success Criteria**: More accurate simulated ceiling frequencies for breakout players.

#### Item 39: Skewed Bootstrap — Quantile-Preserving MC Transformation
- **Problem**: The MC simulator applies a linear matchup multiplier (`score * EV / historical_avg`) to bootstrap samples. Lacrosse scoring is right-skewed (most weeks 0–10 pts, occasional 60+ explosions), but the linear multiplier shifts the entire distribution uniformly, distorting the tail shape.
- **Why it matters**: Distorted tails hurt ceiling-based strategies (MC_Ceil_90, MC_Win_160) because the simulated probability of breakout scores doesn't match reality.
- **Suggested Fix**: Use a quantile-preserving transformation: map each bootstrap sample to its percentile in the player's historical CDF, then map that percentile to the predicted CDF (where EV shifts but variance may also change based on matchup favorability). This preserves skewness while incorporating matchup information.
- **Success Criteria**: Improved calibration of MC_Ceil_90 and MC_Win_160 strategies. Better alignment between simulated and actual score distributions.

#### Item 40: Opponent Ownership Penalty in Optimizer
- **Problem**: The MC_EV optimizer selects purely on expected value without considering how many other managers own the same players. In a head-to-head league, heavily owned players provide no differentiation.
- **Why it matters**: Could provide marginal edge in head-to-head matchups by avoiding "chalk" picks when viable alternatives exist. However, see caveats below.
- **Suggested Fix**: Add an ownership-adjusted EV to the optimizer: `adjusted_EV = MC_EV - α * global_ownership_rate`, where `α` is a tunable parameter. This is distinct from the rejected "Salary as Feature" (Item 9) because it only affects the optimization stage, not the prediction model.
- **Caveats**: In a **cumulative season-long scoring** format, EV maximization is provably optimal — contrarian strategies add unnecessary variance. This feature is only useful if the league has weekly head-to-head matchups. Additionally, the existing MC Differential strategy already captures the head-to-head angle when rival roster data is available.
- **A/B Test Plan**: Backtest with various `α` values (0.5, 1.0, 2.0) against Baseline 3. Measure total season score and per-week win rate vs rival rosters.
- **Success Criteria**: Net positive season score or win rate vs Baseline 3. Must not degrade total Ceiling %.

#### Item 44: Historical Ownership Archive & Chalk Analysis *(prerequisite for Item 40)*
- **Problem**: Consensus ownership data (`08_scrape_challenger_rosters.py` output) is only retained for 2 weeks (Weeks 6 and 8 of 2026). There is no historical archive to analyze whether heavily owned "chalk" players systematically underperform or outperform expectations — the so-called "ownership curse" effect observed in NFL/NBA DFS.
- **Why it matters**: Without historical ownership data, Item 40 (Ownership Penalty) cannot be backtested. If heavily owned players consistently underperform their MC_EV, an ownership penalty is justified. If not, it's noise.
- **Suggested Fix**:
  1. **Archive step**: Modify the Phase 2 workflow (or add a post-scrape hook) so that every time `08_scrape_challenger_rosters.py` runs, the output JSON is copied to a permanent archive directory (e.g. `data/ownership_archive/week{N}_{YYYY}_consensus.json`).
  2. **Backfill**: For any remaining 2026 weeks, scrape retroactively if the F2P API still exposes historical rosters. For 2025, the data is likely unavailable — mark as missing.
  3. **Analysis script**: Build `scratch/analyze_ownership_curse.py` that:
     - Loads all archived consensus JSONs and the corresponding `combined_player_stats_{YYYY}.json` actuals.
     - For each player-week, computes: `ownership_rate`, `MC_EV` (predicted), `actualPoints`, and `residual = actual - predicted`.
     - Groups by ownership quintile (0–20%, 20–40%, …, 80–100%) and reports mean residual per quintile.
     - Tests whether high-ownership players have statistically significant negative residuals (paired t-test or Mann-Whitney U).
  4. **Decision gate**: If the analysis shows a significant negative residual for the top ownership quintile (p < 0.10), proceed with Item 40. If not, close Item 40 as "no effect detected".
- **Success Criteria**: Archive infrastructure operational. Analysis script produces a clear go/no-go recommendation for Item 40 with statistical evidence.

#### Item 41: Ensemble Meta-Selector (Strategy Picker)
- **Problem**: The pipeline runs MC_EV and MC_Win_160 every week, but the user must manually choose which roster to deploy. MC_Win_160 beat MC_EV in 2026 (899.4 vs 888.0) but trailed in 2025. Neither strategy dominates consistently.
- **Why it matters**: If we could correctly select between strategies each week, we'd capture the best of both. Even 2–3 correct switches per season could add 15–30 pts.
- **Suggested Fix**: Train a simple model (logistic regression or decision tree) that picks the best strategy for each week based on game-week characteristics: number of games, average salary pool depth, historical volatility of the week's matchups, league standing differential.
- **Success Criteria**: Meta-selector outperforms always-MC_EV in backtest by ≥ 10 pts/season.

#### Item 42: Player-Level MC Correlations
- **Problem**: The Gaussian Copula applies uniform position-pair correlations (e.g., all same-team Attack pairs get +0.124). In reality, two elite attackmen who share possession (e.g., Shellenberger + Teat) might correlate at +0.35, while two journeymen might be +0.05.
- **Why it matters**: Incorrect correlations bias the optimizer — it may overvalue stacking two weakly correlated players or undervalue a true stack.
- **Suggested Fix**: Compute player-specific pairwise Pearson correlations from historical game-by-game data. Use a shrinkage estimator (e.g., Ledoit-Wolf) to handle small sample sizes. Fall back to position-pair defaults when insufficient history exists.
- **Challenge**: Requires significant per-pair sample sizes to estimate reliably. Players change teams between seasons.
- **Success Criteria**: Improved stack selection accuracy in backtest. MC_EV improvement ≥ 5 pts/season.

#### Item 43: Scoring Environment Multiplier
- **Problem**: When two high-scoring offenses meet, individual player ceilings should be elevated beyond what the game pace feature captures. The current game pace scaling adjusts shot volume but doesn't model the compounding effect of a high-scoring game environment on all participants.
- **Why it matters**: In high-pace games, even role players have elevated ceilings. The current model underestimates this because game pace only scales the team-level metric, not the individual player distributions.
- **Suggested Fix**: Compute a multiplicative "scoring environment" factor based on both teams' recent combined scoring rates. Apply this as a distribution-wide inflation factor in the MC simulator, separate from the individual matchup multiplier.
- **Success Criteria**: Better calibration of simulated scores in high-pace game weeks.

---

### Tier 4: Pipeline Performance & Safety

#### Item 16: Data Validation and Silent Failures
- **Problem**: Silent failures exist in the pipeline:
  - `03_apply_roster_filter.py`: If names differ between Stats API and predictions, players are silently dropped.
  - `load_all_matchups()`: Missing matchup files are silently skipped.
  - `combine_datasets.py`: No validation for duplicate records or missing fields.
- **Why it matters**: Silently skipped data results in bad inputs propagating down the pipeline.
- **Suggested Fix**: Implement explicit checks and raise descriptive errors or reports (e.g., unmatched player name report) during the run.
- **Success Criteria**: The pipeline halts or logs warning reports when data anomalies occur.

#### Item 17: Pipeline Parallelism
- **Problem**: Running classifier, regressor, and simulator sequentially is slow.
- **Why it matters**: Slower workflow iteration time.
- **Suggested Fix**: Run prediction and regression stages in parallel since they are completely independent.
- **Success Criteria**: Reduction in execution time.

#### Item 18: File I/O Bottlenecks (Parquet)
- **Problem**: Massive 20MB+ CSV files are read and written between stages.
- **Why it matters**: Unnecessary disk I/O slowing down execution.
- **Suggested Fix**: Pass data in-memory when running the full pipeline, or use the binary Parquet format for faster read/write speeds.
- **Success Criteria**: Reduced I/O overhead.

#### Item 19: Standard Logging and Unit Tests
- **Problem**: Zero test coverage and reliance on `print()` for debugging.
- **Why it matters**: High risk of breaking features during updates, and debugging is difficult.
- **Suggested Fix**: Set up python's standard `logging` library and implement basic unit tests for feature engineering and utility functions.
- **Success Criteria**: Basic test suite passing; standard logging active.

---

### Tier 5: UI/UX & Quality of Life

#### Item 20: Migrate UI to MC EV and Surfacing Confidence Bands
- **Problem**: The Web UI uses legacy categorical EV / Boom% fields.
- **Why it matters**: Disconnect between the UI and the primary MC EV prediction model.
- **Suggested Fix**: Update `app.js` to display MC EV and render p10–p90 confidence ranges for players on the Plotly dashboard.
- **Success Criteria**: Plotly dashboard shows MC EV and error bars/ranges.

#### Item 21: Season-Long Tracking Dashboard
- **Problem**: No way to track model performance trend over a season.
- **Why it matters**: Hard to tell if model accuracy is improving or degrading over time.
- **Suggested Fix**: Build a tracker comparing cumulative model score vs. Coulda Optimizer ceiling over weeks.
- **Success Criteria**: Tracking graph rendered in the Web UI.

#### Item 22: Roster Change Detector & Alerts
- **Problem**: Roster changes on game day can happen after predictions are generated.
- **Why it matters**: Scratched players remain in optimized rosters.
- **Suggested Fix**: Set up a script to poll the roster API on game day and alert if any selected players are scratched.
- **Success Criteria**: Automated alerts generated for roster changes.

#### Item 23: Coulda Extensions (Regret Analysis)
- **Problem**: Coulda reports only show the absolute best team.
- **Why it matters**: Hard to extract actionable learnings.
- **Suggested Fix**: Implement regret analysis (e.g. identify the single best player swap that would have gained the most points).
- **Success Criteria**: Coulda output includes a list of top 3 high-regret swaps.

#### Item 24: Matchup Tagger Upgrades
- **Problem**: Matchup tagger is slow and lacks confidence fields.
- **Why it matters**: Manual tagging is the bottleneck for matchup data.
- **Suggested Fix**: Add support for switch tracking and a "confidence" field (High/Medium/Unsure) per matchup tag. Incorporate defender combinations and estimated switch rates into matchups to represent how defensive switches alter matchup features.
- **Success Criteria**: Tagger UI captures confidence ratings.

---

## Graveyard / Rejected Ideas

#### Item 10: Player Usage and Field Time Proxy
- **Problem**: Stale Baseline 3 test showed degradation in 2025 ($-360.6$ pts) and 2026 ($-139.5$ pts). Touches anomaly overfit to volatile state fluctuations.
- **Why it matters**: Needs to be re-evaluated against Baseline 8 to check if usage features are actually viable.
- **Suggested Fix**: Re-enable `USAGE_HEALTH_FEATURES_ENABLED = True` and run the full backtest.
- **A/B Test Plan**: Compare total Ceiling % against Baseline 8.
- **Results (vs Baseline 8)**:
  - `MC_EV`: **+45.2** in 2025 (2158.0), **+116.3** in 2026 (1105.6).
  - `MC_Win_160`: **-240.0** in 2025 (2074.3), **+5.6** in 2026 (1056.7).
  - `MC_Ceil_90`: **-15.1** in 2025 (2127.7), **-74.6** in 2026 (814.6).
- **Status**: ❌ **Rejected**. While it provides a modest boost to the mean expectation (`MC_EV`), it heavily penalizes tournament upside strategies (`MC_Win_160` and `MC_Ceil_90`), likely by over-regularizing the variance for players returning from injury or with fluctuating usage. Item 9 is strictly better. Keep disabled.

#### Item 46: Mathematical Pace & Possession Factor Estimation
- **Problem**: Public GraphQL endpoints supply raw counting statistics but lack true possession tracking. Rolling features like `_last3_avg` and `fp_ewma_4` are heavily distorted by the unadjusted pace of specific matchups rather than reflecting pure individual efficiency.
- **Why it matters**: A player in a frantic, high-transition game will see inflated volume features, while a player in a slow, settled-six defensive battle will see depressed numbers. Without pace normalization, the model continuously chases historical noise.
- **Suggested Fix**: Derive a mathematical proxy for possession count per game team-by-team:
  $$\text{Est. Possessions} = \text{Shots} + \text{Turnovers} - \text{Offensive Rebounds} + \text{Opponent Saves}$$
  Convert individual player counting stats into normalized rate metrics (e.g., Shots per 10 Possessions) prior to training. Scale projections back up at simulation runtime using the projected combined pace of the upcoming matchup.
- **A/B Test Plan**: Compare total Ceiling % against Baseline 8.
- **Results (vs Baseline 8)**:
  - `MC_EV`: **-219.8** in 2025 (1893.0), **-20.0** in 2026 (969.3).
  - `MC_Win_160`: **-486.7** in 2025 (1827.6), **-8.9** in 2026 (1042.2).
  - `MC_Ceil_90`: **-268.6** in 2025 (1874.2), **-108.3** in 2026 (780.9).
- **Status**: ❌ **Rejected**. Massive degradation across the board. Normalizing the stats into rates before training seems to destroy critical variance and absolute volume signals that the model relies on. Keep `PACE_ADJUSTED_RATES_ENABLED` disabled.

### Venue Context (Home/Away Feature)
- **Status**: ❌ **Rejected**.
- **Reason**: The PLL operates on a touring model where all teams play at a single venue each weekend, eliminating traditional home field advantage. Proximity Homecoming effects are too speculative and suffer from small sample sizes. Double-game-week rest is already handled by other features.


---

## Definition of "Done" & Completed Items

To mark an item as **Done**, it must meet the following:
1. Implementation code written, code-reviewed, and merged.
2. Backtested against the evaluation harness to ensure no regressions.
3. Relevant documentation updated, and the completed script or file link added below.

### Completed Items

> [!NOTE]
> For full audit trail detail (including specific baseline regression outputs, feature test details, and p-values), see the [original improva.md (archived)](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/scratch/doc_backup/improva.md).

#### Item 27: Complete Data Leakage Elimination 🔴

A full codebase audit on **1 July 2026** identified 6 distinct leakage sources. All must be fixed before further A/B testing or baseline establishment.

##### 27a: Matchup Rating Global Career Averages ✅ DONE
- **Problem**: Matchup ratings computed using global career averages including future games.
- **Fix**: Expanding cumulative means via `config.DATA_LEAKAGE_FIX_ENABLED = True`.
- **File**: `feature_engineering.py`
- **Status**: ✅ Done. Enabled by default.

##### 27b: Shuffled KFold CV for Stacking ✅ DONE
- **Problem**: `KFold` generates OOF `PredictedPoints` using randomly shuffled folds. A validation fold can contain a 2024 week 3 game while the training fold contains 2025 week 10 — the regressor trains on future data.
- **Fix**: Replaced with `TimeSeriesSplit(n_splits=5)`.
- **File**: `02_predict_probabilities.py`
- **Status**: ✅ Done.

##### 27c: Quantile Thresholds on Full Training Set ✅ DONE
- **Problem**: `assign_tiers()` computes q25/q75 thresholds over the entire multi-season.
- **Fix**: Implemented `assign_tiers_expanding` to compute expanding window quantiles chronologically.
- **Status**: ✅ Done.

##### 27d: MC Copula Correlations from 2023–2026 Data ✅ DONE
- **Problem**: Hardcoded `CORRELATIONS` dictionary computed from "2023–2026 data".
- **Fix**: Freeze correlations to pre-target-year data, or compute dynamically.
- **Status**: ✅ Done.

##### 27e: `global_avg_goals` / `league_avg_pace` Fallbacks ✅ DONE
- **Problem**: Fallbacks computed from all historical games.
- **Fix**: Use hardcoded constants or prior-season-only computation.
- **Status**: ✅ Done.

##### 27f: MC Bootstrap Pool Missing Future-Year Guard ✅ DONE
- **Problem**: Bootstrap pool draws historical games without target-year constraints.
- **Fix**: Filter out games beyond the target year and week.
- **Status**: ✅ Done.

- **Dynamic Positional Medians Verification** (Done / Not Applicable)
- **Evaluation Harness & Backtest Baseline Validation** (Done)
- **Recency-Weighted Bootstrapping in MC** (Done)
- **Game Pace and Script Projections** (Done)
- **Classifier Injury Features Bug Fix** (Done)
- **Meta-Selector Strategy Heuristics** (Done)
- **Feature Importance and SHAP Logging** (Done)
- **Tier 1 Refactoring & De-risking** (Done)
- **Item 34: Challenger Roster Scraping & Consensus Advice** (Done)
- **Item 35: Local League Roster Scraping & Differential Optimization** (Done)


#### Item 36: DNP Rolling Feature Pollution Bug Fix ✅ DONE
- **Problem**: `add_rolling_features()` in `feature_engineering.py` — the shared helper used for both historical training and live-week predictions — included DNP (Did Not Play) rows when computing rolling form features (`_last3_avg`, `_season_avg`, `fp_lag1`, `fp_ewma_4`, and all sub-stat averages). A player who missed games due to injury, trades, or being scratched had their rolling stats artificially dragged toward zero. The XGBoost model could not distinguish between a player performing poorly on the field and a player who simply didn't play, leading to biased predictions for returning players.
- **Fix**: `add_rolling_features()` now:
  1. Separates an `active_mask = (df["isDNP"] != True)` subset before any rolling calculation.
  2. Computes all rolling/EWMA stats exclusively on `df_active`.
  3. Re-integrates the calculated stats back into the full dataframe and forward-fills (`ffill`) DNP gaps per player, so a returning player carries their last known on-field form value.
- **Impact**: All rolling form features now represent true on-field performance (points per game *played*, touches per game *played*). This removes a major noise source from both the training set (2023–2025 history) and live predictions, improving accuracy for any player returning from a multi-week absence.
- **File**: `feature_engineering.py` (lines 269–297)
- **Status**: ✅ Done. Triggered Baseline 3 re-establishment.

#### Item 11: Extract Distributional Statistics from MC Simulations & Consolidated Tooltip ✅ DONE
- **Problem**: Downstream scripts loaded the massive 23MB simulations CSV just to extract mean and quantile values, creating severe CPU/disk bottlenecks. The web UI lacked visual outcomes representation.
- **Fix**: Refactored the Monte Carlo simulator (`04_simulate_monte_carlo.py`) to pre-calculate player-level stats (`mc_ev`, `mc_std`, `mc_p10`, `mc_p25`, `mc_p75`, `mc_p90`) and output them to a compact JSON file. Modified downstream optimizer (`06_optimize_lineups.py`) and compiler (`07_prepare_static_data.py`) to use this fast JSON file.
- **UI Integration**: Upgraded the Predicta custom hover tooltip to a two-column stats grid and integrated a horizontal outcome range bar displaying the floor-to-ceiling range ($p_{10}$ to $p_{90}$) and the relative EV dot.
- **Status**: ✅ Completed & Verified.

#### Item 37: Boom Recall Optimization — Asymmetric Class Weighting ✅ DONE
- **Problem**: The XGBoost classifier treats all misclassification costs equally, producing a precision-oriented model (~50% Boom precision but only ~25% recall). The optimizer requires higher recall to capture the breakout players that make up the Coulda Max lineups.
- **Fix**: Implemented asymmetric `sample_weight` in XGBoost classifier training to penalize missed Booms. Swept weights 1.5x, 2.0x, 2.5x, 3.0x.
- **Impact**: Weight = 2.0 achieved a **statistically significant improvement** over Baseline 4 in 2025 (**+222.3 pts**, +4.8% ceiling, p = **0.0436**) and a major lift in 2026 (**+262.5 pts**, +10.4% ceiling, p = **0.0712**).
- **Status**: ✅ Done & Kept.

#### Item 9: Market Consensus (Salary as a Feature) ✅ DONE
- **Problem**: Stale Baseline 3 test showed a net drag across both seasons. The model relied heavily on salary, creating an anchoring bias.
- **Why it matters**: Since Baseline 3 was compromised by stale predictions, we needed to verify if salary features genuinely degrade performance when evaluated against the true Baseline 8.
- **Fix**: Re-enabled `SALARY_AS_FEATURE = True` and ran the full backtest.
- **Results (vs Baseline 8)**: 
  - `MC_EV`: **+50.8** in 2025, **+176.1** in 2026.
  - `MC_Win_160`: **-96.2** in 2025, **+107.1** in 2026.
  - `MC_Ceil_90`: **+144.5** in 2025, **+43.2** in 2026.
- **Status**: ✅ **Accepted**. The previous negative results were purely an artifact of data leakage in Baseline 3. On the clean Baseline 8, Salary provides a massive net positive signal across almost all strategies and seasons. Implemented as Baseline 9.

#### Baseline 5 Overnight Sweep Verification ✅ DONE
- **Background**: Swept 15 combination and ablation test configurations overnight in July 2026 to verify all previously tested features against the leak-free, clean Baseline 5 control.
- **Results**:
  - **Item 29 (EWMA Rolling Features)**: Kept. Standalone ablation (`sweep_no_ewma`) had a tiny drag in 2025 (-6.0 pts) and minor lift in 2026 (+99.4 pts). Retained as a core form representation.
  - **Item 13 & 28 (Bayesian Shrinkage)**: Kept. Standalone ablation (`sweep_no_shrinkage`) caused a major degradation of **-130.7 pts** in 2025. It remains mathematically critical for ratings stability.
  - **Game Pace Scaling**: Kept. Standalone ablation (`sweep_no_game_pace`) destroyed performance (**-178.0 pts** in 2025, **-48.0 pts** in 2026).
  - **Item 31 (Smooth MC Historical Pool Blending)**: **ACCEPTED & ENABLED**. Testing pool blending with $K=15$ yielded a major combined improvement of **+134.0 pts** across both seasons (+49.0 pts in 2025, +85.0 pts in 2026) with strong directional significance in 2025 (p = **0.0862**). Enabled in production (`MC_POOL_BLENDING_ENABLED = True`, `MC_POOL_BLENDING_K = 15`).
  - **Opponent-Stratified Bootstrap**: **REJECTED & DELETED**. Checked code and verified this feature had already been removed from simulation logic due to earlier scale conflicts (leaving only dead configuration variables, which have now been cleaned up).
  - **Item 26 & 30 (Stacked Regressor / Multi-Quantile)**: **REJECTED**. Failed due to stale code conflicts. Kept disabled in favor of GBDT classifier-based simulations.
- **Status**: ✅ All sweep tests completed and verified.

#### Item 38: Faceoff Model — Simple Heuristic Replacement ✅ DONE
- **Problem**: The Faceoff XGBoost classifier achieves **0% Boom precision and 0% Boom recall** under Baseline 6. With only ~14 FO-eligible players per week and highly volatile scoring, XGBoost cannot learn meaningful signal.
- **Fix**: Bypassed GBDT for the Faceoff position and implemented a generative Bradley-Terry matchup win probability model scaled by expected pace and shrunk player-specific stats (ground balls per win, goals, assists, caused turnovers).
- **Impact**: Achieved a massive **+134.3 points** improvement in 2025 and neutral results in 2026, completely resolving the 0% Boom recall bottleneck.
- **Status**: ✅ Completed & Integrated as Baseline 10.
