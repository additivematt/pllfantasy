---
name: coulda
description: Detailed rules for PLL F2P lineup building, per-game double-header roster selection rules, pre-computed pair tables, and retroactive optimizer.
---

# Agent Context: PLL Fantasy Lineup Optimization ("Coulda/Shoulda")

## Purpose

This skill outlines the lineup optimization logic. Use this when benchmarking predictions, finding optimal historical lineups, or extending the retroactive optimizer to new weeks/seasons.

---

## Where This Fits in the Project

```
1. DATA FETCHING  (see fetcha)
       ↓
2. PREDICTION     (see predicta)
       ↓
3. LINEUP OPTIMIZATION  ← this module (coulda)
```

This stage answers: *"Given what actually happened, what was the best team we could have picked?"* This is the ceiling benchmark against which the prediction engine is evaluated.

---

## Roster Rules (PLL F2P Fantasy)

Every lineup must satisfy all of the following:

| Slot | Eligible Positions | Count |
|---|---|---|
| Attackman | A | 2 |
| Midfielder | M | 2 |
| Defender | D, SSDM, or LSM | 1 |
| Faceoff Specialist | FO | 1 |
| Goalie | G | 1 |
| **Budget** | — | ≤ 200 coins |

---

## ⚠️ Critical Rule: Selections Are Per Game, Not Per Week

In some weeks, a team plays **two games** within the same fantasy week. A player on such a team is available as **two separate pick options** — one for each game.

**The rule**: Selecting a player locks them in for **one specific game** (one `eventId`). You score only the points they earn in that game. You do not get points from both games.

For the retroactive optimizer this means:
- **The optimizer must be run per game**, not per week. Each `eventId` within a week is a separate optimization problem.
- In a double-game week, a player who plays Game A and Game B appears in the eligible pool for **both** runs — but can only be selected in one.
- The "coulda" benchmark must specify which game each selected player is attributed to. Reporting a weekly total without stating the game-per-player is ambiguous.
- When examining `f2p_2026_season.json`, confirm which `eventId` each player's `totalPoints` entry corresponds to before using it as an optimizer input.

---

## ⚠️ Mandatory Output Rule: Always Report Game Context

Every time an optimizer result is presented — in code output, in chat, or in any report — **each selected player must be accompanied by their specific game context**. This is non-negotiable for players who appeared in multiple games within the week.

For every player in the optimal lineup, always display:

| Field | Description |
|---|---|
| `eventId` | The specific game ID this player's points are attributed to (e.g., `2026_game_3`) |
| `gameNumber` | The game number within the week (Game 1, Game 2, etc.) |
| Opponent | The opposing team in that game (derived from `season_matchups_2026.json`) |
| Points | The `totalPoints` earned **in that specific game** |
| Stats | The `displayString` for that game (e.g., `4GB, 5CT`) |

**Why this matters:** A player who plays twice in a week has two separate entries with different `eventId` values and potentially very different scores. Reporting only the player name and total points is ambiguous — the reader cannot tell which game to attribute the performance to or whether the optimizer chose the better of the two appearances.

**Example of correct output for a double-game-week player:**
```
DEF  Mitchell Dunham  ARC   D   cost=3   pts=59.0  Game 2 (2026_game_3 vs OUT)  4GB, 5CT
     [Alt game: Game 1 (2026_game_1 vs RED) = 36.0 pts  4GB, 3CT — not selected]
```

---

## Algorithm Design

### Problem
Finding the optimal 7-player lineup across 100+ eligible players within the budget constraint is a combinatorial optimization problem. Brute force is too slow due to combinatorial explosion (especially for the 2-slot positions requiring pair evaluation).

### Solution: Pre-computed Pair Tables
The `coulda_optimizer.py` script implements a **"smarter search"**:
1. Pre-compute all valid **Attackman pairs** and their combined cost + points.
2. Pre-compute all valid **Midfielder pairs** similarly.
3. For each valid combination of FO + G + D (single slots), compute the remaining budget and look up the best pair from the pre-sorted pair tables.
4. Combine to find the globally optimal lineup.

This reduces the search space dramatically while still guaranteeing the true optimum.

---

## Live Optimizer (`06_optimize_lineups.py`)

The live optimizer is used during **Phase 2 (Game-Day Lock)** to select the best roster for the upcoming week based on models and Monte Carlo simulations. It solves:
1. **EV Baseline Roster**: Linear programming (LP) using PuLP to maximize the stacked regressor expected points subject to positional constraints and the 200 F2P coin budget.
2. **Monte Carlo Optimization (MC_EV, MC_Win_160, MC_Ceil_90)**: Since joint distributions and player correlations are non-linear, a randomized local search heuristic runs (using restarts and local searches in `utils.py`) to find optimal rosters that maximize simulated expected value, probability of scoring over 160.0, or 90th-percentile ceiling.
3. **Consensus & Differential Roster**: If a competitor ownership JSON file is scraped and present (e.g. from top 25 global players), it solves LP to find either the consensus-maximizing roster or a differential roster.

#### Execution:
```bash
python 06_optimize_lineups.py --year 2026 --week <WEEK>
```

---

## Data Sources

### Input Files
| File | Role |
|---|---|
| `f2p_2026_season.json` | Per-week player salaries and actual fantasy points scored |
| `combined_player_stats_2026.json` | Detailed game-level stats (for deeper analysis) |
| `predicta/predictions/weekN_YYYY_predictions.csv` | Stacked classifier & regressor outputs (loaded by `06_optimize_lineups.py`) |
| `predicta/predictions/weekN_YYYY_simulation_stats.json` | Baked Monte Carlo simulation stats (Item 11) for fast lookup |
| `predicta/predictions/weekN_YYYY_simulations.csv` | Full simulation trial matrix (loaded fallback for EV and win probabilities) |
| `predicta/advisory/weekN_YYYY_consensus_ownership.json` | Competitor rosters and ownership rates (scraped via `08_scrape_challenger_rosters.py`) |

### Output
- **`coulda_optimizer.py`**: Prints the retroactive optimal lineup and its total score to stdout.
- **`06_optimize_lineups.py`**: Outputs multiple optimized roster suggestions (EV Baseline, MC EV, MC Win 160, MC Ceil 90, Consensus, Differential) to stdout and logs reports.

---

## Scripts

| Script | Purpose |
|---|---|
| `coulda_optimizer.py` | General-purpose retroactive optimizer ("Coulda/Shoulda") |
| `06_optimize_lineups.py` | Live forward-looking roster optimizer using linear programming & local search heuristics |

---

> [!NOTE]
> All improvement ideas are tracked centrally in the [improva](../improvements_and_baselines/SKILL.md) skill. Do not add new improvement ideas to this file.
