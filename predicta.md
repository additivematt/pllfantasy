# Agent Context: PLL Fantasy Prediction Engine

> [!NOTE]
> **Design System**: All Predicta UI development must follow the [styla.md](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/styla.md) guide (Electric Purple aesthetic).
> **Hosted Address (Local)**: [http://localhost:8000/predicta/](http://localhost:8000/predicta/)
> **Hosted Address (Public)**: [https://additivematt.github.io/pllfantasy/predicta/](https://additivematt.github.io/pllfantasy/predicta/) (GitHub Pages secure origin)

## Purpose

This document provides a **new agent with full context** to continue development of the PLL fantasy points prediction engine. Load this file at the start of any session related to predicting player performance or improving the forecasting model.

---

## Where This Fits in the Project

```
1. DATA FETCHING  (see fetcha.md)
       ↓
2. PREDICTION     ← this module
       ↓
3. VISUALIZATION  (see /predicta/)
       ↓
4. LINEUP OPTIMIZATION  (see coulda.md)
```

| Stage | Key Scripts / Paths | Output |
|---|---|---|
| **Data Fetching** | `fetch_f2p_costs.py` | `combined_player_stats_YYYY.json` |
| **Prediction** | `predict_fantasy_points.py` | `weekN_YYYY_predictions.csv` |
| **Visualization** | `/predicta/index.html` | Interactive Web Dashboard |
| **Optimization** | `roster_optimizer.py` | Optimal lineup |

---

## Model Design & Optimization

Predicta supports multiple prediction models and roster optimization strategies. Through extensive historical backtesting, we have transitioned our primary selection method from standard Expected Value (EV) / Boom % models to a **Monte Carlo Expected Value (MC EV)** simulation framework.

---

### 1. Prediction Models

#### A. Classification Model (`predict_fantasy_points.py` - Legacy / Deprecated)
- **Core Purpose**: Classifies each player's potential performance into three relative tiers and outputs the probability of hitting each tier. Used historically to calculate standard Expected Value.
- **Algorithm**: XGBoost Classifier (`XGBClassifier`)
- **Target Variable**: Performance tier label (`Bust`, `Average`, `Boom`) derived from actual fantasy points scored in a game, calculated dynamically relative to the player's position group:
  
  | Tier | Definition |
  |---|---|
  | **Boom** | Top 25% of scorers for that position in that week |
  | **Average** | Middle 50% |
  | **Bust** | Bottom 25% |

- **Position Groups for Tier Assignment**: The model uses a **merged `positionGroup`** for tier labelling and model training, and a granular **`subPosition`** for opposition ratings and visualisation:
  
  | `positionGroup` (training / tiers) | `subPosition` (opposition ratings / UI) |
  |---|---|
  | Attack | Attack |
  | Midfield | Midfield |
  | **Defense** | **SSDM** (covers SSDM & LSM) |
  | **Defense** | **Defensemen** |
  | Faceoff | Faceoff |
  | Goalie | Goalie |

  > [!IMPORTANT]
  > SSDM, LSM, and Defensemen all occupy **a single F2P roster slot**. Merging them into one `Defense` group ensures boom = top 25% across **all** eligible D-slot players, not independently within each sub-type. Opposition ratings (`team_def_rating`) retain `subPosition` granularity so the model can still distinguish how a team defends SSDMs vs traditional Defensemen.

- **Features Used**: Rest advantage (days since last game), team/opponent face-off advantages, 4-Tier symmetrical matchup ratings (pairing rating, opponent rating, player vs team rating, team defense vs sub-position rating), and lagged season/last-3 rolling averages for fantasy points and sub-statistics.
- **File Link**: [predict_fantasy_points.py](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/predict_fantasy_points.py)

#### B. Quantile Regression Model (`predict_fantasy_points_regression.py`)
- **Core Purpose**: Predicts raw fantasy point ceilings directly, rather than predicting point averages or categorical tiers.
- **Algorithm**: XGBoost Regressor (`XGBRegressor`) with a custom pinball loss objective.
- **Objective Function**: Since standard regression models suffer from a "regression to the mean" compression effect (which is not useful for picking high-scoring outliers needed to win fantasy weeks), this model uses 90th percentile quantile regression (`alpha = 0.9` pinball loss). Due to environment limits (XGBoost 1.6.2 lacking native `reg:quantileerror` on Windows), this is implemented via a custom objective function with a constant Hessian of `1.0`:
  $$\text{Loss}(y, \hat{y}) = \max(\alpha(y - \hat{y}), (\alpha - 1)(y - \hat{y}))$$
- **Target Variable**: Actual total fantasy points.
- **Features Used**: Identical to the classification features (rolling stats, matchup pairing ratings, and defensive allowance ratios).
- **File Link**: [predict_fantasy_points_regression.py](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/predict_fantasy_points_regression.py)

#### C. Monte Carlo Simulation Model (`simulate_fantasy_points.py` - Primary)
- **Core Purpose**: Simulates 10,000 distinct trials of player-game fantasy outcomes by generating empirical probability distributions per player, scaling them by matchup difficulty, and applying teammate/opponent correlations.
- **Methodology**:
  1. **Historical Bootstrap**: Retrieves the player's historical game-by-game fantasy scoring records prior to the prediction week.
  2. **Matchup Scaling**: Adjusts each historical game sample by the target week's matchup difficulty multiplier (allowance ratio) to account for defensive opposition strength.
  3. **Correlation Structure (Gaussian Copula)**: To model teammate positive correlation (e.g., Attack/Midfield points rise together during high-scoring games) and opponent negative correlation (e.g., Face-off battles are zero-sum, and Attack goals lower opponent Goalie save points), the simulator implements a Gaussian Copula using Pearson correlation coefficients calculated from 2023–2026 data.
- **File Link**: [simulate_fantasy_points.py](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/simulate_fantasy_points.py)

---

### 2. Roster Optimization Strategies

All optimizers target the core F2P roster requirements (select exactly 7 players within a 200-coin salary budget: 2 Attack, 2 Midfield, 1 Defense [merged SSDM/LSM/Defensemen], 1 Face-off, and 1 Goalie) and automatically pre-filter double-game weeks to retain only the best projected matchup per player (while mapping alternatives for manual swaps).

#### A. Monte Carlo Expected Value (MC EV) Optimizer (`roster_optimizer_mc.py` - Primary Selection)
- **Approach**: Maximizes the average simulated lineup score across 10,000 Monte Carlo trials:
  $$\text{MC EV} = \frac{1}{M} \sum_{m=1}^{M} \sum_{i \in \text{Lineup}} \text{SimulatedPoints}_{i, m}$$
  where $M = 10,000$ simulation trials.
- **Optimization Goal**: Maximizes expected points within the 200-coin budget. By simulating outcomes from each player's empirical distribution, this naturally captures individual variance and true salary efficiency.
- **Best Use Case**: Primary selection algorithm for season-long formats, head-to-head cash matches, and double-ups.
- **File Link**: [roster_optimizer_mc.py](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/roster_optimizer_mc.py)

#### B. Quantile Regression Optimizer (`roster_optimizer_regression.py`)
- **Approach**: Selects players by maximizing the sum of their predicted 90th percentile ceiling points directly.
- **Optimization Goal**: Maximizes total ceiling points within the 200-coin budget.
- **Best Use Case**: Identifying high-value sleeper selections with enormous ceilings.
- **File Link**: [roster_optimizer_regression.py](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/roster_optimizer_regression.py)

#### C. Teammate & Opponent Correlation Stacking Optimizer (`roster_optimizer_stack.py` - Tournament)
- **Approach**: Employs integer linear programming (ILP) using the `PuLP` library to optimize rosters while factoring in teammate positive correlations and matchup/opponent negative correlations.
- **Correlation Bonuses & Penalties**: Uses historical Pearson correlation coefficients ($\text{Corr}_{ij}$) calculated from 2023–2026 game data to adjust the objective score. Linearization is applied via binary quadratic constraints ($z_{ij} = x_i \cdot x_j$):
  $$\text{Bonus/Penalty} = \beta \times \text{Corr}_{ij} \times \min(P_i, P_j)$$
  where $\beta$ is a scaling multiplier (default `1.0`) and $P$ is the player's predicted performance metric (Boom probability or point ceiling).
  *   **Positive Stacks ($\text{Corr}_{ij} > 0$)**: Encourages pairing correlated players (e.g. Same-Team Attack - Attack = `+0.124`).
  *   **Negative Penalties ($\text{Corr}_{ij} < 0$)**: Penalizes co-rostering mutually-exclusive players in the same lineup:
      *   *Same-Team Goalie - Defense/SSDM/LSM*: range `-0.25` to `-0.39` (defensemen stats and goalie save counts are negatively correlated).
      *   *Cross-Team Faceoff - Faceoff*: `-0.435` (zero-sum possession battles).
      *   *Cross-Team Attack - Goalie*: `-0.182` (attack goals hurt the opposing goalie's score).
- **Configured Variants**:
  *   **Stacked Boom % (Tourney)**: Uses calibrated predictions from the Classification Model to maximize joint Boom probability.
  *   **Stacked Regression (Tourney)**: Uses predictions from the Quantile Regression Model to maximize joint points ceiling.
- **Best Use Case**: GPP tournament formats. Stacking captures same-team offensive explosions while negative correlation penalties actively prevent co-rostering players who limit each other's ceiling.
- **File Link**: [roster_optimizer_stack.py](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/roster_optimizer_stack.py)

#### D. Expected Value (EV) Optimizer (`roster_optimizer_ev.py` / `roster_optimizer.py` - Legacy / Deprecated)
- **Approach**: Calculates each player's Expected Value (EV) using classification probabilities combined with historical tier-level averages:
  $$\text{EV} = P(\text{Boom}) \times \text{Avg}(\text{Boom Points}) + (1.0 - P(\text{Boom})) \times \text{Avg}(\text{Non-Boom Points})$$
- **Status**: **Deprecated** due to the compression of individual player variance caused by position-wide average multipliers.
- **File Links**: [roster_optimizer_ev.py](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/roster_optimizer_ev.py) / [roster_optimizer.py](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/roster_optimizer.py)

---

### 📈 Backtest Results & Rationale

We performed extensive historical backtests across the 2024, 2025, and early 2026 seasons to compare standard selection methods (Classification Boom %, standard EV Weighted) against regression models and Monte Carlo simulations.

#### A. 2025 Seasonal Backtest Results (Weeks 1–14)
*   **Total Max Possible points (Coulda Optimizer)**: 4,666.6 pts
*   **MC EV** won the season-long backtest with **2,177.4 pts** (46.7% of max), outperforming standard EV Weighted by **161.1 pts** (+8% performance boost).

| Week | Class (Boom%) | EV Weighted | Regression | Stacked Boom | Stacked Reg | MC EV | MC Ceil 90 | MC Win 110 | Coulda Opt |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Week 1** | 142.4 | 142.4 | 191.6 | 142.4 | 189.6 | 152.9 | 103.1 | **209.3** | 349.6 |
| **Week 2** | 114.9 | 114.9 | 99.4 | 114.9 | **186.4** | 162.9 | 105.4 | 139.9 | 385.0 |
| **Week 3** | 150.9 | 150.9 | 184.2 | 151.9 | **194.9** | 150.9 | 174.9 | 164.2 | 371.0 |
| **Week 4** | 263.0 | 263.0 | 71.7 | 234.0 | 96.7 | 263.0 | 150.7 | 251.7 | 433.7 |
| **Week 5** | 181.4 | 181.4 | 181.6 | 182.4 | **188.6** | 181.4 | 175.4 | 163.9 | 385.7 |
| **Week 7** | 63.8 | 63.8 | 82.6 | **149.8** | 74.6 | 63.8 | 95.8 | 120.8 | 365.1 |
| **Week 8** | 176.1 | 176.1 | 124.6 | **205.1** | 107.6 | 193.2 | 114.2 | 148.2 | 379.9 |
| **Week 9** | 83.1 | 83.1 | 116.1 | 122.1 | 125.1 | **144.1** | 101.0 | 98.0 | 339.9 |
| **Week 10** | 184.7 | 184.7 | 140.1 | 184.7 | 151.9 | **220.7** | 157.1 | 146.7 | 362.0 |
| **Week 11** | 201.3 | 201.3 | 150.4 | 201.3 | **211.8** | 191.8 | 165.3 | 147.8 | 413.3 |
| **Week 12** | 181.0 | 181.0 | 126.7 | 182.0 | 133.7 | 179.0 | 157.8 | **235.0** | 336.5 |
| **Week 13** | 119.0 | 119.0 | **142.0** | 119.0 | 111.0 | 119.0 | 119.0 | 117.0 | 307.8 |
| **Week 14** | 154.7 | 154.7 | 140.7 | **182.6** | 122.6 | 154.7 | 154.7 | 155.7 | 237.1 |
| **TOTAL** | **2016.3** | **2016.3** | **1751.7** | **2172.2** | **1894.5** | **2177.4** | **1774.4** | **2098.2** | **4666.6** |
| **% MAX** | **43.2%** | **43.2%** | **37.5%** | **46.5%** | **40.6%** | **46.7%** | **38.0%** | **45.0%** | **100.0%** |

#### B. 2024 Seasonal Backtest Results (Weeks 1–14)
*   **Total Max Possible points (Coulda Optimizer)**: 4,560.4 pts
*   **MC EV** scored **1858.9 pts** (40.8% of max), outscoring standard EV Weighted (**1834.3 pts**). The season was won by Stacked Regression (**2157.4 pts**), and **MC Win 110** was the top-performing MC model at **1973.2 pts** (43.3% of max).

| Week | Class (Boom%) | EV Weighted | Regression | Stacked Boom | Stacked Reg | MC EV | MC Ceil 90 | MC Win 110 | Coulda Opt |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Week 1** | 116.5 | 116.5 | 157.5 | 179.5 | **240.5** | 116.5 | 148.0 | 131.0 | 438.4 |
| **Week 2** | 111.7 | 111.7 | 142.5 | 125.7 | 181.5 | 132.7 | 131.2 | **199.7** | 385.5 |
| **Week 3** | 191.4 | 191.4 | 142.4 | **235.6** | 203.2 | 176.6 | 124.6 | 193.8 | 447.9 |
| **Week 4** | 125.9 | 106.4 | 155.4 | 168.5 | **188.4** | 147.5 | 145.5 | 81.7 | 342.8 |
| **Week 5** | 285.9 | 285.9 | 154.4 | 251.9 | 137.4 | **285.9** | 173.2 | 213.4 | 370.0 |
| **Week 7** | 117.1 | 117.1 | 141.1 | 100.1 | **162.6** | 117.1 | 77.6 | 85.9 | 362.1 |
| **Week 8** | 164.2 | 164.2 | 225.3 | 164.2 | 205.3 | 109.2 | 124.2 | **235.2** | 357.3 |
| **Week 9** | 153.8 | 153.8 | 121.8 | **156.8** | 124.8 | 144.8 | 153.8 | 113.8 | 333.6 |
| **Week 10** | 50.7 | 50.7 | 106.8 | 41.6 | 128.3 | 99.7 | 99.7 | **165.1** | 351.1 |
| **Week 11** | 100.1 | 100.1 | **130.1** | 107.1 | 116.1 | 100.1 | 98.1 | 123.1 | 369.1 |
| **Week 12** | 140.6 | 140.6 | 122.9 | 140.6 | **157.9** | 144.6 | 132.9 | 112.6 | 269.6 |
| **Week 13** | 134.3 | 134.3 | 114.3 | 140.3 | **149.8** | 135.6 | 101.6 | 131.3 | 300.8 |
| **Week 14** | 161.6 | 161.6 | 159.1 | 120.6 | 161.6 | 148.6 | 148.6 | **186.6** | 232.2 |
| **TOTAL** | **1853.8** | **1834.3** | **1873.6** | **1932.5** | **2157.4** | **1858.9** | **1659.0** | **1973.2** | **4560.4** |
| **% MAX** | **40.6%** | **40.2%** | **41.1%** | **42.4%** | **47.3%** | **40.8%** | **36.4%** | **43.3%** | **100.0%** |

#### C. 2026 Seasonal Backtest Results (Weeks 1–4)
*   **Total Max Possible points (Coulda Optimizer)**: 1,437.3 pts
*   **MC EV** scored **637.7 pts** (44.4% of max), outperforming standard EV Weighted (**568.7 pts**) by **69.0 pts** (+12% gain).

| Week | Class (Boom%) | EV Weighted | Regression | Stacked Boom | Stacked Reg | MC EV | MC Ceil 90 | MC Win 110 | Coulda Opt |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Week 1** | 145.5 | 145.5 | 185.6 | 186.5 | 197.6 | 158.5 | **257.5** | 117.6 | 369.7 |
| **Week 2** | 139.9 | 139.9 | **176.9** | 139.9 | 167.9 | 139.9 | 119.4 | 119.9 | 357.9 |
| **Week 3** | 133.8 | 133.8 | 133.8 | 189.8 | 100.8 | 189.8 | 91.8 | **211.8** | 319.8 |
| **Week 4** | 149.5 | 149.5 | 176.6 | **210.5** | 147.5 | 149.5 | 120.5 | 114.6 | 389.9 |
| **TOTAL** | **568.7** | **568.7** | **672.9** | **726.7** | **613.8** | **637.7** | **589.2** | **563.9** | **1437.3** |
| **% MAX** | **39.6%** | **39.6%** | **46.8%** | **50.6%** | **42.7%** | **44.4%** | **41.0%** | **39.2%** | **100.0%** |

---

### Rationale for Retiring Boom % & Standard EV

Based on these backtest findings, standard `Boom %` (Classification) and `EV Weighted` have been retired from our core roster selection pipeline:

1. **Compression of Individual Variance in Standard EV**:
   Standard EV utilizes position-wide averages to multiply the model's classification probabilities:
   $$\text{EV} = P(\text{Boom}) \times \text{Avg}(\text{Boom Points}) + (1.0 - P(\text{Boom})) \times \text{Avg}(\text{Non-Boom Points})$$
   Because $\text{Avg}(\text{Boom Points})$ is a flat constant for all players in a position group (e.g. all Attackmen who boom are assumed to score an average of 25 points), this approach compresses player-specific ceilings. An elite Attackman with a massive historical distribution is evaluated using the exact same multiplier as a budget Attackman, leading to severely compressed and inaccurate EV estimates.

2. **arbitrary Thresholding of Boom %**:
   `Boom %` represents a player's probability of scoring in the top 25% of their position group in a week. Optimizing for the sum of `Boom %` treating all "Booms" identically introduces severe thresholding bias. A player who scores 35 points (a massive boom) and a player who scores 18 points (a marginal boom) are weighted identically. Standard Boom % completely ignores the shape and scale of a player's high-scoring outliers.

3. **Superiority of Monte Carlo Expected Value (MC EV)**:
   MC EV simulates the full empirical distribution of each player. Rather than using arbitrary tier boundaries or flat position-wide constants, MC EV bootstraps directly from each player's historical game-by-game scores and scales them by matchup. The expected value is the true mathematical mean of 10,000 simulations:
   - MC EV naturally accounts for individual players with unique ceilings (e.g. high-variance players vs high-floor players).
   - It captures teammates/opponent correlations dynamically via the Copula matrix.
   - It consistently outperformed standard EV Weighted across all seasons (+8% in 2025, +12% in early 2026).

---

### Key Design Decisions

- **Allowance Ratio**: The core matchup metric. Calculated as `Actual Points / Expected Points`. A ratio < 1.0 indicates a strong performance by the opponent/team who holds the player below their average.
- **Symmetric Evaluation**: When Player A is matched with Player B, the model calculates:
  1. How B's presence affects A's scoring (B as the opponent).
  2. How A's presence affects B's scoring (A as the opponent).
  This allows the model to capture how elite players limit the points of those covering or playing against them (e.g. elite Attackmen lowering an opponent's fantasy output by having very low turnover rates).
- **Feature Coexistence and Defaulting**: Rather than selecting only one matchup tier, the model receives **all four matchup features simultaneously** as independent columns. If no historical data exists for a highly specific feature (e.g. two players have never faced each other, or a player has never played against a franchise), that specific feature defaults to `1.0` (a completely neutral baseline). This allows the XGBoost model to naturally and mathematically weight the most granular and active features available.
- **F2P Salary Fallback Rules**: To ensure predictions always contain valid salaries (even when manual inputs are missing, zero, or placeholder flat `10`s, such as in 2026 Week 4 or 2025 Weeks 12–14), the engine applies the following sequential fallback logic:
  1. **Season-to-Date (STD) Salary Average**: Calculates the average of the player's actual salaries in the current season preceding the prediction week.
  2. **Historical Salary Average**: If no current-season salary history exists, scans previous years (2025, 2024) to find the player's average salary.
  3. **Season-to-Date (STD) Points Average**: If no salary data exists, falls back to the rounded average of their actual fantasy points scored in the current season.
  4. **Overall Points Average**: Uses their overall average fantasy points scored from previous seasons.
  5. **Default Baseline**: Fallback to a neutral baseline of `10` coins.

---

## ⚠️ Critical Rule: Roster Filtering & Fallback

Official gameday rosters are fetched dynamically from the official stats API for the target week:
- **API Endpoint**: `https://api.stats.premierlacrosseleague.com/api/v4/events/gameday-rosters?year=YYYY&week=W`
- **Source Web Page**: [https://premierlacrosseleague.com/gameday-rosters](https://premierlacrosseleague.com/gameday-rosters)
- **Early-Week Fallback**: Because official rosters are only published ~24 hours before game time, running the predictions pipeline early in the week would normally filter out all players (leaving an empty dataset). To prevent this, the filter script (`apply_roster_filter.py`) implements a fallback: if the REST API returns no roster data, the filter step is bypassed with a warning, keeping the unfiltered predictions intact so that lineup optimization can run using historical rosters.
- **F2P Injury Filtering**: Early in the week before official gameday rosters are available, both `predict_fantasy_points.py` and `predict_fantasy_points_regression.py` check the F2P weekly/season data (`f2p_weekly_data.json` or `f2p_{year}_season.json`) and skip predictions for any players marked with an `injuryStatus` of `"IR"` (Injured Reserve) or `"O"` (Out). Statuses like doubtful (`"D"`) or questionable (`"Q"`) are retained and evaluated.
- **Trade Resolution**: When active rosters are loaded, players who have been traded (e.g., Ryan Croddick from Outlaws to Redwoods) are dynamically detected on their new team's roster. Their team code, opponent code, and `game_id` are automatically updated to match their new franchise's game details before final lineup optimization.

---

## ⚠️ Critical Rule: Data Leakage Prevention (Chronological Training)

To prevent data leakage (a "time machine" effect), **the model must only be trained on chronological events occurring prior to the target prediction week**. 
- **Strict Data Exclusion**: When generating predictions for Year Y, Week W, the training set (`df_all`) is filtered via `df_all[~((df_all["year"] == Y) & (df_all["week"] >= W))]` before any feature engineering begins. This mathematically guarantees that no data from the target week or any future weeks of that season is present during feature engineering or training.
- **Unix Epoch `startTime` Sorting**: All player historical records are sorted by their exact UNIX epoch game `startTime` (extracted from the raw event metadata) rather than alphabetically by `eventId`. Alphabetical sorting (e.g. `"game_4"` sorting after `"game_38"`) is strictly forbidden as it puts historical sequences out of order. `startTime` sorting ensures all rolling features (`_season_avg` and `_last3_avg`) and sequence slices (`.tail(3).mean()`) represent mathematically accurate chronological progression.

---

## ⚠️ Critical Rule: Selections Are Per Game, Not Per Week

In some weeks, a team plays **two games** (a double-game week). A player on such a team will appear as **two separate selection options** — one for each game.

**Key rule**: When you select a player, you are selecting them for a **specific game** (identified by `eventId`). You only receive the fantasy points they score in that one game — not both.

This has major implications for the prediction engine:
- **Predictions must be generated per game** (per `eventId`), not aggregated per week.
- Each game has a **different opponent**, so matchup features will differ between a player's two game options.
- The output CSV must clearly indicate which game (`eventId` and opponent) each prediction row refers to, and **must include the player's `officialId`** for downstream matching.
- A player playing twice in a week is effectively **two independent pick options** that should be evaluated and ranked separately.

When comparing predicted tiers across players, always confirm you are comparing picks within the **same game or same selection slot** to avoid mixing apples and oranges.

---

## Data Sources

### Input Files
| File | Role |
|---|---|
| `combined_player_stats_2023.json` | Historical training data |
| `combined_player_stats_2024.json` | Historical training data |
| `combined_player_stats_2025.json` | Most recent training season |
| `combined_player_stats_2026.json` | Current season (grows weekly) |
| `f2p_2026_season.json` | Roster, salary, and matchup data for 2026 |
| `pll-schedule.ics` | Game schedule; parsed to identify who plays in a given week |
| `season_matchups_2026.json` | Tagged defensive matchup data (from matcha.md pipeline) |

### Output Files
| File / Path | Contents |
|---|---|
| `weekN_YYYY_predictions.csv` | Player tier predictions (includes salary and `officialId`) |
| `weekN_YYYY_simulations.csv` | Monte Carlo player simulation trials (10k trials) |
| `/predicta/` | Web-based interactive analysis dashboard |

### Visualization Mapping & UI Advisor (Web UI)
The `predicta` dashboard uses a split-column layout (`2fr 1fr` grid) combining Plotly position charts on the left with the **Predicta Advisor** sidebar on the right:
*   **X-Axis**: **Fantasy Salary (Coins)**. Mapped to actual or season-to-date average salaries to highlight sleepers.
*   **Y-Axis**: **Boom Probability (%)**. Model's confidence of a top 25% performance within the unified boom pool.
*   **Color (Heatmap)**: **Historic Performance vs Opposition**. Green indicates favorable matchups (Ratio > 1.0).
*   **Size**: **90th Percentile Ceiling**. Dot size represents the player's predicted ceiling points (`PredictedPoints`), visually enlarging high-upside plays.
*   **Bidirectional Interactivity**:
    - Hover/Click nodes on the Plotly charts to display custom glassmorphism stats tooltips (which show salary, boom %, opponent defense rating, and regression ceiling points).
    - Click player pills (Consensus Core / Sleepers) or roster table rows in the Advisor sidebar to smoothly center and scroll the corresponding Plotly chart into view, temporarily flash the node with a bright magenta border, and focus the tooltip.
*   **Roster Strategy Selector**: Tab buttons to swap lineups across 4 strategies:
    - **BOOM** (Legacy): Maximizes Expected Value (shows player EV and Boom % columns).
    - **CEILING**: Maximizes predicted 90th percentile ceiling points (shows player EV and Ceiling columns).
    - **STACK BOOM**: Teammate-stacking tournament optimizer (shows player EV and Boom % columns).
    - **STACK CEILING**: Teammate-stacking tournament optimizer (shows player EV and Ceiling columns).

### Offline Caching & Support (`/predicta/sw.js`)
*   **App Shell** (HTML, CSS, JS, Plotly, Google Fonts): Cached via **Cache-First** strategy for zero-latency instant loading, even completely offline.
*   **Dynamic Prediction Caching**: On install, the Service Worker reads `predictions/available` and automatically crawls and pre-caches every single week's predictions. This allows mobile devices to load historical and upcoming weeks without any network calls!
*   **Standalone Execution**: Decoupled from the local Python server. The app can be hosted directly on static providers like **GitHub Pages** (which provides the secure HTTPS origin required for Service Workers on mobile).
*   **Persistent Status Indicator**: A header status pill displays **`🟢 ONLINE`** or **`⚡ OFFLINE — using cached data`** based on connection to the host server.

---

## CLI Interface

### Generate Player Simulations (10,000 Trials)
```bash
python simulate_fantasy_points.py --year 2026 --week 2 --sims 10000
```
- `--year`: The season year to generate simulations for.
- `--week`: The week number.
- `--sims`: Number of trials to run (default `10000`).

### Solve Monte Carlo Roster Optimization
```bash
python roster_optimizer_mc.py --year 2026 --week 2 --objective MC_EV
```
- `--year`: Roster year.
- `--week`: Roster week.
- `--objective`: Optimization objective (`MC_EV`, `MC_Ceiling_90`, `MC_Win_Prob`).

---

## Current State

| Item | Status |
|---|---|
| Core XGBoost pipeline | ✅ Complete |
| Week 1 & 2 predictions | ✅ Exported to CSV |
| Opposition encoding | ✅ Implemented |
| Per-position model split | ✅ Implemented |
| Matchup-strength weighting | ✅ 4-Tier Hierarchy implemented |
| Defensive matchup integration | ✅ Tagged matchups prioritized; fallback to Player-vs-Team and Team-vs-Position |
| Salary integration | ✅ Salaries mapped to prediction output and visualization |
| Per-game output in double-game weeks | ✅ Verified |
| **Defense slot unification** | ✅ SSDM/LSM/Defensemen share one boom pool; `subPosition` preserves opposition granularity and separate UI panels |
| Model evaluation / backtesting | ✅ Complete (via `backtest_compare.py`) |
| Probability calibration | ✅ Complete (via `CalibratedClassifierCV`) |
| Quantile Regression (90th Percentile) | ✅ Complete (via `predict_fantasy_points_regression.py`) |
| Teammate Stacking Optimizer | ✅ Complete (via data-driven correlation model) |
| **Monte Carlo Simulation Model** | ✅ Complete (via `simulate_fantasy_points.py`) |
| **Monte Carlo Roster Optimizer** | ✅ Complete (via `roster_optimizer_mc.py`) |
| **MC Backtest Comparison Harness** | ✅ Complete (via `backtest_compare_mc.py`) |

---

## Next Steps / Open Problems

- [x] **Integrate defensive matchup data** from `season_matchups_2026.json` as a feature.
- [x] **Derive a defensive strength rating** per team based on allowance ratios rather than raw team slug.
- [x] **Unify the Defense slot**: SSDM, LSM, and Defensemen now share one boom pool via merged `positionGroup = "Defense"`.
- [x] **Build a backtesting harness**: train on 2023–2024, predict 2025, compare vs. actual tier labels to measure accuracy.
- [x] **Expand to regression**: Experiment with predicting point totals directly (using Quantile Regression for 90th percentile ceiling) and compare usefulness vs. tier classification.
- [x] **Build Monte Carlo Simulators & Optimizers**: Create standalone scripts (`simulate_fantasy_points.py`, `roster_optimizer_mc.py`) and perform historical validation.
- [ ] **Migrate Predicta web UI & server engine to MC EV**: Replace the legacy standard EV and Boom % selection algorithms in `/predicta/app.js` and the Python server with simulated Monte Carlo Expected Value data.
- [ ] **Audit double-game week logic in MC simulation**: Ensure the simulation remains robust for mid-season double-headers.

