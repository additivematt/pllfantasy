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

Predicta supports multiple prediction models and lineup optimization strategies. This allows testing different statistical hypotheses (predicting categories/tiers vs. exact values/ceilings) and tactical lineup structures (independent value maximization vs. correlation stacking).

---

### 1. Prediction Models

#### A. Classification Model (`predict_fantasy_points.py`)
- **Core Purpose**: Classifies each player's potential performance into three relative tiers and outputs the probability of hitting each tier.
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
- **File Link**: [predict_fantasy_points.py](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/predict_fantasy_points.py)

#### B. Quantile Regression Model (`predict_fantasy_points_regression.py`)
- **Core Purpose**: Predicts raw fantasy point ceilings directly, rather than predicting point averages or categorical tiers.
- **Algorithm**: XGBoost Regressor (`XGBRegressor`) with a custom pinball loss objective.
- **Objective Function**: Since standard regression models suffer from a "regression to the mean" compression effect (which is not useful for picking high-scoring outliers needed to win fantasy weeks), this model uses 90th percentile quantile regression (`alpha = 0.9` pinball loss). Due to environment limits (XGBoost 1.6.2 lacking native `reg:quantileerror` on Windows), this is implemented via a custom objective function with a constant Hessian of `1.0`:
  $$\text{Loss}(y, \hat{y}) = \max(\alpha(y - \hat{y}), (\alpha - 1)(y - \hat{y}))$$
- **Target Variable**: Actual total fantasy points.
- **Features Used**: Identical to the classification features (rolling stats, matchup pairing ratings, and defensive allowance ratios).
- **File Link**: [predict_fantasy_points_regression.py](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/predict_fantasy_points_regression.py)

---

### 2. Roster Optimization Strategies

All optimizers target the core F2P roster requirements (select exactly 7 players within a 200-coin salary budget: 2 Attack, 2 Midfield, 1 Defense [merged SSDM/LSM/Defensemen], 1 Face-off, and 1 Goalie) and automatically pre-filter double-game weeks to retain only the best projected matchup per player (while mapping alternatives for manual swaps).

#### A. Expected Value (EV) Optimizer (`roster_optimizer_ev.py` / `roster_optimizer.py`)
- **Approach**: Calculates each player's Expected Value (EV) using classification probabilities combined with historical tier-level averages (calculated strictly prior to the target week to prevent data leakage):
  $$\text{EV} = P(\text{Boom}) \times \text{Avg}(\text{Boom Points}) + (1.0 - P(\text{Boom})) \times \text{Avg}(\text{Non-Boom Points})$$
- **Optimization Goal**: Maximizes total lineup EV within the 200-coin budget.
- **Best Use Case**: Consistent performance in season-long formats, head-to-head cash matches, and double-up contests where avoiding low floors (busts) is critical.
- **File Links**: [roster_optimizer_ev.py](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/roster_optimizer_ev.py) / [roster_optimizer.py](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/roster_optimizer.py)

#### B. Quantile Regression Optimizer (`roster_optimizer_regression.py`)
- **Approach**: Selects players by maximizing the sum of their predicted 90th percentile ceiling points directly.
- **Optimization Goal**: Maximizes total ceiling points within the 200-coin budget.
- **Best Use Case**: Identifying high-value sleeper selections with enormous ceilings.
- **File Link**: [roster_optimizer_regression.py](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/roster_optimizer_regression.py)

#### C. Teammate Stacking Optimizer (`roster_optimizer_stack.py`)
- **Approach**: Employs integer linear programming (ILP) using the `PuLP` library to optimize rosters while rewarding teammate stacks (players belonging to the same PLL franchise).
- **Correlation Bonus**: Introduces a stacking incentive weight $\beta$ (default `0.15`) that adds a bonus to the objective function when two players $i$ and $j$ from the same team are rostered together:
  $$\text{Bonus} = \beta \times \min(P_i, P_j)$$
  where $P$ is the optimization metric. The optimization is linearized for binary quadratic constraints: $z_{ij} = x_i \cdot x_j$.
- **Configured Variants in Backtesting**:
  - **Stacked Classification** (referred to as **Stacked Boom %**): Uses predictions from the **Classification Model** and optimizes for the `BoomProbability` metric. The stacking bonus rewards pairing players who are both highly likely to have a "Boom" performance on the same team.
  - **Stacked Regression**: Uses predictions from the **Quantile Regression Model** and optimizes for the `PredictedPoints` metric (the 90th percentile points ceiling). The stacking bonus rewards pairing players with very high individual ceilings on the same team.
- **Best Use Case**: High-volatility tournament (GPP) formats. Stacking aligns with high-correlation outcomes (e.g. goals assisted by teammates or general team offensive explosions), creating a higher team ceiling at the cost of consistency.
- **File Link**: [roster_optimizer_stack.py](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/roster_optimizer_stack.py)

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
| `/predicta/` | Web-based interactive analysis dashboard |
| `week2_2026_pick_analysis.png` | Static Cost vs. Boom Heatmap (Legacy) |

### Visualization Mapping & UI Advisor (Web UI)
The `predicta` dashboard uses a split-column layout (`2fr 1fr` grid) combining Plotly position charts on the left with the **Predicta Advisor** sidebar on the right:
*   **X-Axis**: **Fantasy Salary (Coins)**. Mapped to actual or season-to-date average salaries to highlight sleepers.
*   **Y-Axis**: **Boom Probability (%)**. Model's confidence of a top 25% performance within the unified boom pool.
*   **Color (Heatmap)**: **Historic Performance vs Opposition**. Green indicates favorable matchups (Ratio > 1.0).
*   **Size**: **90th Percentile Ceiling**. Dot size represents the player's predicted ceiling points (`PredictedPoints`), visually enlarging high-upside plays.
*   **Bidirectional Interactivity**:
    - Hover/Click nodes on the Plotly charts to display custom glassmorphism stats tooltips (which show salary, boom %, opponent defense rating, and regression ceiling points).
    - Click player pills (Consensus Core / Sleepers) or roster table rows in the Advisor sidebar to smoothly center and scroll the corresponding Plotly chart into view, temporarily flash the node with a bright magenta border, and focus the tooltip.
*   **Roster Strategy Selector**: Tab buttons to swap lineups across 4 strategies, dynamically toggling headers and column stats:
    - **BOOM**: Maximizes Expected Value (shows player EV and Boom % columns).
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

```bash
python predict_fantasy_points.py --year 2026 --week 2
```

- `--year`: The season year to generate predictions for.
- `--week`: The week number to predict. The script resolves which teams play that week from `pll-schedule.ics`.

> **Note on double-game weeks**: When a team plays twice in a week, the script should generate a separate prediction row for each game, labelled by `eventId` and opponent. Do not collapse or average across both games — the user selects one game per player.

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
| Probability calibration | ❌ Raw XGBoost probabilities, not calibrated |
| Quantile Regression (90th Percentile) | ✅ Complete (via `predict_fantasy_points_regression.py`) |
| Teammate Stacking Optimizer | ✅ Complete (via `roster_optimizer_stack.py`) |

---

## Next Steps / Open Problems

- [x] **Integrate defensive matchup data** from `season_matchups_2026.json` as a feature.
- [x] **Derive a defensive strength rating** per team based on allowance ratios rather than raw team slug.
- [x] **Unify the Defense slot**: SSDM, LSM, and Defensemen now share one boom pool via merged `positionGroup = "Defense"`.
- [x] **Build a backtesting harness**: train on 2023–2024, predict 2025, compare vs. actual tier labels to measure accuracy.
- [x] **Expand to regression**: Experiment with predicting point totals directly (using Quantile Regression for 90th percentile ceiling) and compare usefulness vs. tier classification.
- [ ] **Regenerate all 2025 predictions** (weeks 1–14) and **2026 predictions** (weeks 1–3) following the Defense slot unification fix — boom probabilities were previously miscalibrated for D-slot players.
- [ ] **Build a Predicta accuracy metric**: For each historical prediction week, compare `PredictedTier` against the actual tier (derived from real `TotalFantasyPoints`) and report per-position accuracy, tier confusion matrices, and Boom precision/recall. Aim to surface this in the UI or as a summary report alongside each week's predictions.
- [ ] **Calibrate probabilities**: Use `CalibratedClassifierCV` to turn raw XGBoost outputs into reliable probability estimates.
- [ ] **Add salary efficiency scoring**: Combine predicted probability with F2P salary from `f2p_2026_season.json` to rank players by value.
- [ ] **Audit double-game week logic**: Ensure the pipeline remains robust for mid-season double-headers.
