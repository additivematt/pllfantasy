# Predicta Historical Design Decisions & Archived Models

This document archives the design history, retired prediction models, deprecated optimization strategies, and historical baseline backtests that helped shape the active Monte Carlo Expected Value (MC EV) pipeline.

---

## 1. Retired Prediction Models

### Quantile Regression Model (`predict_fantasy_points_regression.py` - DELETED)
* **Core Purpose**: Predicts raw fantasy point ceilings directly, rather than predicting point averages or categorical tiers.
* **Algorithm**: XGBoost Regressor (`XGBRegressor`) with a custom pinball loss objective.
* **Objective Function**: Since standard regression models suffer from a "regression to the mean" compression effect (which is not useful for picking high-scoring outliers needed to win fantasy weeks), this model used 90th percentile quantile regression ($\alpha = 0.9$ pinball loss). Due to environment limits (XGBoost 1.6.2 lacking native `reg:quantileerror` on Windows), this was implemented via a custom objective function with a constant Hessian of `1.0`:
  $$\text{Loss}(y, \hat{y}) = \max(\alpha(y - \hat{y}), (\alpha - 1)(y - \hat{y}))$$
* **Target Variable**: Actual total fantasy points.
* **Features Used**: Identical to classification features (rolling stats, matchup pairing ratings, and defensive allowance ratios).

---

## 2. Deprecated Roster Optimization Strategies

### Teammate & Opponent Correlation Stacking Optimizer (`roster_optimizer_stack.py` - DELETED)
* **Approach**: Employs integer linear programming (ILP) using the `PuLP` library to optimize rosters while factoring in teammate positive correlations and matchup/opponent negative correlations.
* **Correlation Bonuses & Penalties**: Used historical Pearson correlation coefficients ($\text{Corr}_{ij}$) calculated from 2023–2026 game data to adjust the objective score. Linearization was applied via binary quadratic constraints ($z_{ij} = x_i \cdot x_j$):
  $$\text{Bonus/Penalty} = \beta \times \text{Corr}_{ij} \times \min(P_i, P_j)$$
  where $\beta$ is a scaling multiplier (default `1.0`) and $P$ is the player's predicted performance metric (Boom probability or point ceiling).
  * **Positive Stacks ($\text{Corr}_{ij} > 0$)**: Encouraged pairing correlated players (e.g. Same-Team Attack - Attack = `+0.124`).
  * **Negative Penalties ($\text{Corr}_{ij} < 0$)**: Penalized co-rostering mutually-exclusive players in the same lineup:
    * *Same-Team Goalie - Defense/SSDM/LSM*: range `-0.25` to `-0.39` (defensemen stats and goalie save counts are negatively correlated).
    * *Cross-Team Faceoff - Faceoff*: `-0.435` (zero-sum possession battles).
    * *Cross-Team Attack - Goalie*: `-0.182` (attack goals hurt the opposing goalie's score).
* **Configured Variants**:
  * **Stacked Boom % (Tourney)**: Uses calibrated predictions from the Classification Model to maximize joint Boom probability.
  * **Stacked Regression (Tourney)**: Uses predictions from the Quantile Regression Model to maximize joint points ceiling.

### Expected Value (EV) Optimizer (`roster_optimizer_ev.py` / `roster_optimizer.py` - DELETED / Legacy)
* **Approach**: Calculated each player's Expected Value (EV) using classification probabilities combined with historical tier-level averages:
  $$\text{EV} = P(\text{Boom}) \times \text{Avg}(\text{Boom Points}) + (1.0 - P(\text{Boom})) \times \text{Avg}(\text{Non-Boom Points})$$
* **Status**: **Retired** due to the compression of individual player variance caused by position-wide average multipliers.

---

## 3. Rationale for Retiring Boom % & Standard EV

Based on backtest findings, standard `Boom %` (Classification) and `EV Weighted` were retired from our core roster selection pipeline:

1. **Compression of Individual Variance in Standard EV**:
   Standard EV utilizes position-wide averages to multiply the model's classification probabilities:
   $$\text{EV} = P(\text{Boom}) \times \text{Avg}(\text{Boom Points}) + (1.0 - P(\text{Boom})) \times \text{Avg}(\text{Non-Boom Points})$$
   Because $\text{Avg}(\text{Boom Points})$ is a flat constant for all players in a position group (e.g. all Attackmen who boom are assumed to score an average of 25 points), this approach compresses player-specific ceilings. An elite Attackman with a massive historical distribution is evaluated using the exact same multiplier as a budget Attackman, leading to compressed and inaccurate EV estimates.

2. **Arbitrary Thresholding of Boom %**:
   `Boom %` represents a player's probability of scoring in the top 25% of their position group in a week. Optimizing for the sum of `Boom %` treating all "Booms" identically introduces severe thresholding bias. A player who scores 35 points (a massive boom) and a player who scores 18 points (a marginal boom) are weighted identically. Standard Boom % completely ignores the shape and scale of a player's high-scoring outliers.

3. **Superiority of Monte Carlo Expected Value (MC EV)**:
   MC EV simulates the full empirical distribution of each player. Rather than using arbitrary tier boundaries or flat position-wide constants, MC EV bootstraps directly from each player's historical game-by-game scores and scales them by matchup. The expected value is the true mathematical mean of 10,000 simulations:
   - MC EV naturally accounts for individual players with unique ceilings (e.g. high-variance players vs high-floor players).
   - It captures teammate/opponent correlations dynamically via the Copula matrix.
   - It consistently outperformed standard EV Weighted across all seasons (+8% in 2025, +12% in early 2026).

---

## 4. Historical Seasonal Backtest Results (Legacy Baselines)

The tables below record the historical backtests comparing the legacy prediction methods against the Coulda optimal benchmark. Note that these are legacy baselines run prior to the 2026 data leakage fixes and doubleheader database corrections.

### 2025 Seasonal Backtest Results (Weeks 1–14)
* **Total Max Possible points (Coulda Optimizer)**: 4,666.6 pts
* **MC EV** won the season-long backtest with **2,177.4 pts** (46.7% of max), outperforming standard EV Weighted by **161.1 pts** (+8% performance boost).

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

### 2024 Seasonal Backtest Results (Weeks 1–14)
* **Total Max Possible points (Coulda Optimizer)**: 4,560.4 pts

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
