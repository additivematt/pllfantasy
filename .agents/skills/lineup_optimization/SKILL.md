---
name: pll-lineup-optimization
description: Detailed rules for PLL F2P lineup building, per-game double-header roster selection rules, pre-computed pair tables, and retroactive optimizer.
---

# Agent Context: PLL Fantasy Lineup Optimization ("Coulda/Shoulda")

## Purpose

This skill outlines the lineup optimization logic. Use this when benchmarking predictions, finding optimal historical lineups, or extending the retroactive optimizer to new weeks/seasons.

---

## Where This Fits in the Project

```
1. DATA FETCHING  (see pll-data-fetching)
       ↓
2. PREDICTION     (see pll-prediction-engine)
       ↓
3. LINEUP OPTIMIZATION  ← this module (pll-lineup-optimization)
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

## Data Sources

### Input Files
| File | Role |
|---|---|
| `f2p_2026_season.json` | Per-week player salaries and actual fantasy points scored |
| `combined_player_stats_2026.json` | Detailed game-level stats (for deeper analysis) |

### Output
The optimizer prints the optimal lineup and its total score to stdout. Results can be redirected to a file or extended to CSV if needed.

---

## Scripts

| Script | Purpose |
|---|---|
| `coulda_optimizer.py` | General-purpose retroactive optimizer |

---

> [!NOTE]
> All improvement ideas are tracked centrally in the [pll-improvements-and-baselines](../improvements_and_baselines/SKILL.md) skill. Do not add new improvement ideas to this file.
