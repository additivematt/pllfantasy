---
name: matcha
description: Instructions for the matchup tagging web application backend (server.py) and UI, capturing manual defensive assignments from film.
---

# Agent Context: PLL Matchup Tagger (matcha)

## Purpose

This skill outlines the matchup tagging interface and data pipeline. Use this when updating the tagging UI, modifying the matchup server backend, or integrating defensive matchup features into the prediction engine.

> [!NOTE]
> **Design System**: All Matcha UI development must follow the [styla](../styla/SKILL.md) guide (Electric Purple aesthetic).
> **Hosted Address**: [http://localhost:8000/pllmatcha/](http://localhost:8000/pllmatcha/)

---

## Where This Fits in the Project

```
1. DATA FETCHING  (see fetcha)
       |
2a. MATCHUP TAGGING  ← this module (parallel enrichment layer)
       |
       ↓ (feeds into)
2b. PREDICTION    (see predicta)
       ↓
3. LINEUP OPTIMIZATION  (see coulda)
```

The matchup tagger is an **enrichment layer** that captures human-observable defensive assignment data from game film. This data is not available via any API and must be manually tagged by watching recordings. The tagged output (`season_matchups_2026.json`) is consumed by the prediction engine as a feature.

---

## Background: Why Manual Tagging?

An automated Computer Vision approach was explored (YOLO + DeepSORT for player tracking), but was deprioritized due to:
- Broadcast camera angles making consistent player ID unreliable
- Hardware/runtime constraints for real-time inference

The current approach is a **human-in-the-loop manual tagging interface** optimized for speed.

---

## Application: `scripts/matchup_tagger/`

A locally-served web application. Run the Python backend to serve the UI in a browser.

### Key Features
| Feature | Description |
|---|---|
| **Dynamic roster loading** | Pulls live player data from `combined_player_stats_[YEAR].json` |
| **Positional grouping** | Dropdowns sorted by position (Attack, Defense, Midfield, FO, G) in fixed order |
| **Jersey number display** | Player names shown with jersey numbers for easy film matching |
| **Unique validation** | A player selected in one matchup row is automatically disabled in all others |
| **Pre-population** | Revisiting a partially-tagged game reloads existing rows automatically |
| **Game-keyed persistence** | All tags saved to `season_matchups_{year}.json` keyed by Game ID |

### Stack
- **Frontend**: Vanilla HTML5 + CSS3 (Glassmorphism design) + JavaScript
- **Backend**: `server.py` — lightweight Python HTTP server
- **No external dependencies** beyond Python stdlib

### To Run

You can start or manage the local Python server in one of two ways:

#### 1. Using CLI:
```bash
python scripts/matchup_tagger/server.py
```
Then open [http://localhost:8000/pllmatcha/](http://localhost:8000/pllmatcha/) in a browser.

#### 2. Using Windows Helper Batch Scripts:
- **[run_or_restart_server.bat](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/run_or_restart_server.bat)**: Runs the server locally on port 8000 and automatically restarts it if it is already running.
- **[stop_server.bat](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/stop_server.bat)**: Safely kills the local Python server process.

---

## Data Flow

```
combined_player_stats_YYYY.json   ← source of roster/player data
         ↓
    server.py (backend)
         ↓
  index.html + JS (UI)
         ↓ (user tags matchups)
season_matchups_YYYY.json         ← output: matchup records keyed by Game ID
         ↓
  extract_trial_data.py          ← merges stats + matchups
         ↓
  all_players_stats.json          ← consumed by Player Interrogator
         ↓
  02_predict_probabilities.py       ← consumes matchup data as features
```

### Automated Extraction Workflow
The `server.py` is configured to automatically trigger `extract_trial_data.py` every time a matchup is saved. This ensures that any new defensive assignments are immediately available for analysis in the **Player Interrogator** without manual script execution.

---

## Output Schema: `season_matchups_2026.json`

The JSON structure maps matchups keyed by Game ID (`eventId`):

```json
{
  "2026_game_N": {
    "year": "2026",
    "game_id": "2026_game_3",
    "team_a": "ARC",
    "team_b": "OUT",
    "matchups": [
      {
        "playerA": "player-name",
        "playerB": "player-name"
      },
      ...
    ],
    "timestamp": "2026-05-12T23:55:58.306Z"
  }
}
```

### Field Definitions:
- **`year`**: The season year as a string.
- **`game_id`**: The canonical normalized `eventId` for the game.
- **`team_a` / `team_b`**: The 3-character team abbreviations (e.g. `ARC`, `OUT`, `RED`).
- **`matchups`**: A list of tag pairings representing individual assignments.
  - **`playerA` / `playerB`**: The full names of the matched-up players (one is typically an offensive shooter and the other is their primary covering defender). This mapping is symmetric; prediction feature extractors check both sides to match the player.
- **`timestamp`**: The ISO-8601 UTC timestamp of the last save.

### ⚠️ Per-Game Keying and Double-Game Weeks

Matchups are stored by **Game ID** (`eventId`), not by week. This is the correct design:
- In double-game weeks where a team plays twice, each game gets its own key (e.g., `2026_game_5` and `2026_game_9`) and must be tagged separately.
- When feeding matchup data into the prediction engine, always join on `eventId` — never assume a single matchup record covers both games in a week.
- A player's defensive assignment may differ between their two games in a week (different opponent, different personnel).

---

> [!NOTE]
> All improvement ideas are tracked centrally in the [improva](../improva/SKILL.md) skill. Do not add new improvement ideas to this file.
