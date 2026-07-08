---
name: improva
description: Central tracking for feature improvements, model baseline audits (Baseline 2), and A/B backtest evaluation rules.
---

# PLL Fantasy Prediction Engine — Improvement Ideas

> **Date**: June 2026  
> **Scope**: A deep-dive review of all documentation (`.md` files) and source code to identify accuracy, architecture, and reliability improvement opportunities.

---

## Centralized Improvement Policy
All improvement ideas, including feature proposals, architectural refactors, simulation enhancements, and UI upgrades, MUST be recorded in this document. Individual feature docs should link here and must not maintain separate/independent lists of improvements.

---

## Target Success Criteria & Evaluation Baseline
To ensure that changes are mathematically sound and do not degrade model performance:
- **Baseline Metric**: The table below defines the official baseline backtest metrics established on **3 July 2026** (Baseline 2, Leak-Free + EWMA) by running predictions and simulations freshly and evaluating them with the harness.

### Baseline 2 (Leak-Free + EWMA) Evaluation Results (3 July 2026)

Established under the optimal configuration (Game Pace Scaling enabled, Correlation Copula enabled, 0.05 Recency decay, Bayesian Shrinkage enabled, and 4-game half-life EWMA enabled) using fresh predictions and 10,000 Monte Carlo trials on the corrected doubleheader database, with ALL data leakage sources completely eliminated.

| Season | Strategy | Total Score | Coulda Max | Ceiling % |
|---|---|---|---|---|
| 2025 | MC_EV | 2305.3 | 4679.1 | 49.3% |
| 2025 | MC_Ceil_90 | 1999.5 | 4679.1 | 42.7% |
| 2025 | MC_Win_160 | 2317.3 | 4679.1 | 49.5% |
| 2025 | MC_Win_180 | 2127.8 | 4679.1 | 45.5% |
| 2026 | MC_EV | 835.4 | 2194.1 | 38.1% |
| 2026 | MC_Ceil_90 | 615.0 | 2194.1 | 28.0% |
| 2026 | MC_Win_160 | 838.6 | 2194.1 | 38.2% |
| 2026 | MC_Win_180 | 775.8 | 2194.1 | 35.4% |

- **Target Threshold**: A proposed feature or logic change will be accepted if it demonstrates a statistically significant improvement over these baselines (paired t-test p-value < 0.05) without increasing runtimes by more than 20%, or if it fixes a critical code health issue without degrading performance.
- **RNG Reproducibility**: All backtests must run under a fixed random seed to ensure comparison consistency.

> [!IMPORTANT]
> **Instructions for AI Agents / Backtesting Rules:**
> 1. **Do NOT Re-Backtest the Baseline**: When A/B testing a new feature, do not waste compute resources re-running backtests for baseline configurations. All baseline scores are frozen and archived directly in `baselines/rosters_<strategy>_baseline_2.csv` (which includes the `actualPoints` column). Use those existing scores for comparison.
> 2. **Do NOT Create New Baselines**: Do not establish a new baseline (e.g. Baseline 3) or overwrite Baseline 2 data unless the user explicitly instructs you to do so.

---

## Recommended Priority Order (Accuracy Improvements)
The following items represent the highest-impact improvements for **prediction accuracy**, ordered by priority. Item 27 (data leakage elimination) is the **mandatory prerequisite** — all other improvements must be tested on a leak-free pipeline.

1. **Item 9: Market Consensus (Salary as a Feature)**
   * *Aims to Fix*: Anchors regression projections using normalized player salary as a consensus market signal.
   * *Testability*: Toggleable via `config.SALARY_AS_FEATURE`.
   * *Status*: Proposed.

---

## Baseline Version History & Performance Tracking

To track historical performance changes and maintain auditability across key milestones, we document each baseline iteration below. All active roster files are stored in the `baselines/` directory.

> [!NOTE]
> **Baseline Roster Generation Policy:**
> Every time a new baseline is established and rosters are saved to `baselines/`, we must include the actual player scores in the `.csv` files as an `actualPoints` column. This is achieved by running `scratch/append_actual_points.py`, which cross-references selected player names and `eventId`s against the post-game database in `combined_player_stats_YYYY.json` to calculate and write the correct fantasy points. This preserves the out-of-sample scores directly inside the roster artifacts without requiring subsequent lookups or re-evaluations.

> [!WARNING]
> **Historic Baselines Compromised:**
> All previous baselines (formerly Baselines 1 through 8) have been removed from this document. They were fundamentally compromised by a combination of pipeline bugs (stale file retention), database corrections (doubleheaders), and several sources of data leakage (including future-leaking matchup ratings, non-chronological cross-validation, and full-season tier thresholds). The baseline below represents the first truly clean, leak-free reference point (established 1 July 2026). All future A/B testing must compare against this standard.

### Baseline 1 (Leak-Free — 1 July 2026)
- **Changes / Description**: The first completely clean baseline after resolving all 6 data leakage sources (Item 27a-27f). All future-leaking components have been replaced with chronologically expanding windows or strict target-year guards. Game pace scaling, correlation copula, and recency decay remain enabled as per the optimal configuration. (Note: Bayesian shrinkage was also enabled in this baseline, but EWMA was not.)
- **Performance Summary**:

  | Season | Strategy | Total Score | Coulda Max | Ceiling % |
  |---|---|---|---|---|
  | 2025 | MC_EV | 2168.1 | 4679.1 | 46.3% |
  | 2026 | MC_EV | 902.1 | 2194.1 | 41.1% |

### Baseline 2 (Leak-Free + EWMA — 3 July 2026)
- **Changes / Description**: Built on top of Baseline 1 by enabling exponentially-weighted moving average rolling features (`fp_ewma_4` with half-life of 4 games). Bayesian shrinkage remains enabled.
- **Roster Files**: All Baseline 2 rosters are archived in the `baselines/` directory as `rosters_<strategy>_baseline_2.csv` (e.g. `rosters_mc_ev_baseline_2.csv`).
- **Performance Summary**:

  | Season | Strategy | Total Score | Coulda Max | Ceiling % |
  |---|---|---|---|---|
  | 2025 | MC_EV | 2305.3 | 4679.1 | 49.3% |
  | 2025 | MC_Ceil_90 | 1999.5 | 4679.1 | 42.7% |
  | 2025 | MC_Win_160 | 2317.3 | 4679.1 | 49.5% |
  | 2025 | MC_Win_180 | 2127.8 | 4679.1 | 45.5% |
  | 2026 | MC_EV | 835.4 | 2194.1 | 38.1% |
  | 2026 | MC_Ceil_90 | 615.0 | 2194.1 | 28.0% |
  | 2026 | MC_Win_160 | 838.6 | 2194.1 | 38.2% |
  | 2026 | MC_Win_180 | 775.8 | 2194.1 | 35.4% |

- **Interpretation**: Baseline 2 is the new reference standard for all subsequent A/B tests. EWMA provides a net benefit of +137.2 points (+10.55 points/week) in 2025 but has a mild net drag of -66.7 points (-11.12 points/week) in 2026, leading to a combined net improvement of +70.5 points (+3.92 points/week) across 19 weeks.

> [!WARNING]
> **Question Mark Over MC Ceil 90 Strategy:**
> Backtest analysis demonstrates that the `MC_Ceil_90` strategy consistently underperforms compared to `MC_EV` and `MC_Win_160`. Across 19 weeks in Baseline 2, it was the top-performing strategy in only 3 weeks (2025 Weeks 2, 3, and 9) and was beaten by the other strategies in the remaining 16 weeks. Consider deprecating or replacing `MC_Ceil_90` in future optimization iterations.

---

## Core Priorities (Thematic Grouping)

### Tier 2: Model & Feature Improvements (Accuracy)

#### Item 9: Market Consensus (Salary as a Feature)
- **Problem**: F2P coin salaries are only used as optimization constraints and are ignored during model training.
- **Why it matters**: Salary encodes platform consensus and external signals (injury news, role changes, practice rumors) that the model lacks.
- **Suggested Fix**: Feed normalized salary (or salary percentile within position group) as an input feature to the stacked regressor model. This anchors our primary feature (`PredictedPoints`) to a baseline market consensus value, improving predictions before classification.
- **Success Criteria**: The model successfully learns to adjust its predictions using salary as a market consensus indicator.

#### Item 10: Player Usage and Field Time Proxy
- **Problem**: The model uses rolling fantasy averages but does not explicitly model playing time or usage rate.
- **Why it matters**: Backup midfielders have lower ceilings than starters. Normalizing by usage helps the model adapt to role changes (promotions/demotions) much faster.
- **Suggested Fix**: Extract player touch count and total stat accumulation as usage proxies. Feed touch delta (current expected touches vs. season average) into the feature engine. Additionally, weight opponent roster health features (e.g., `opp_ssdm_health`, `opp_def_health`) by active players' average points/usage rather than simple counts, to better reflect true unit degradation.
- **Success Criteria**: Improved adaptation speed and model accuracy for players with recent role changes.

#### Item 32: Matchup Rating Temporal Decay
- **Problem**: Defender and opponent ratings use career averages, weighting ancient games the same as recent matchups.
- **Why it matters**: Defensive unit strength and defender capabilities change over seasons, making old matchup data stale.
- **Suggested Fix**: Apply exponential decay weighting (similar to `LAMBDA_RECENCY`) to historical matchup ratings so recent games dictate the rating.
- **Success Criteria**: Matchup ratings reflect current defender and team performance.

#### Item 33: Position-Specific XGBoost Hyperparameter Tuning
- **Problem**: All five position groups use identical model configurations and tree depths regardless of sample size.
- **Why it matters**: Attack has ~48 rows/season while Goalie has ~16. The Goalie model is highly susceptible to overfitting under generic defaults.
- **Suggested Fix**: Define and grid-search position-specific hyperparameters (`n_estimators`, `max_depth`, `learning_rate`, `min_child_weight`) using the harness.
- **Success Criteria**: Customized hyperparameter configurations active per position group.

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
- **Opponent-Stratified Bootstrap** (Rolled Back / Disabled)
- **Item 26: Stacked Regressor PredictedPoints to MC EV** (Tested & Rejected / Closed)
- **Item 30: Dual Regressors or Multi-Quantile Forecasts** (Tested & Rejected / Closed)
- **Item 28: Bayesian Shrinkage on Matchup Rating Features** (Tested & Kept / Closed)
- **Item 34: Challenger Roster Scraping & Consensus Advice** (Done)
- **Item 35: Local League Roster Scraping & Differential Optimization** (Done)
- **Item 29: EWMA Rolling Features** (Tested & Kept / Closed)
- **Item 13: Bayesian Shrinkage for Low-Sample Players** (Tested & Kept / Closed)
  - *Details*: Matchup ratings shrinkage `SHRINKAGE_K = 5` is verified as highly critical for model stability. Testing it disabled resulted in severe 2026 performance degradation (-222.9 pts). Keep enabled at `SHRINKAGE_K = 5`.
- **Item 31: Smooth MC Historical Pool Blending** (Tested & Rejected / Closed)
  - *Details*: Tested pool blending across various blending levels ($K \in [5, 8, 10, 12, 15]$). While blending with $K=15$ provides a major performance boost specifically for the `MC_Ceil_90` strategy (+287.3 pts combined), it causes a net drag on the primary `MC_EV` and `MC_Win_160` strategies due to variance regularization. Because we want to prioritize EV-based cash game stability and the `MC_Ceil_90` strategy is poorly performing overall, we have rejected the feature and disabled it in production (`MC_POOL_BLENDING_ENABLED = False`).

#### Item 11: Extract Distributional Statistics from MC Simulations & Consolidated Tooltip ✅ DONE
- **Problem**: Downstream scripts loaded the massive 23MB simulations CSV just to extract mean and quantile values, creating severe CPU/disk bottlenecks. The web UI lacked visual outcomes representation.
- **Fix**: Refactored the Monte Carlo simulator (`04_simulate_monte_carlo.py`) to pre-calculate player-level stats (`mc_ev`, `mc_std`, `mc_p10`, `mc_p25`, `mc_p75`, `mc_p90`) and output them to a compact JSON file. Modified downstream optimizer (`06_optimize_lineups.py`) and compiler (`07_prepare_static_data.py`) to use this fast JSON file.
- **UI Integration**: Upgraded the Predicta custom hover tooltip to a two-column stats grid and integrated a horizontal outcome range bar displaying the floor-to-ceiling range ($p_{10}$ to $p_{90}$) and the relative EV dot.
- **Status**: ✅ Completed & Verified.
