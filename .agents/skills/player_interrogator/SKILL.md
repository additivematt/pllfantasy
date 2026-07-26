---
name: interrogata
description: Documentation for the Player Interrogator UI, including DNP tracking, Chart.js trend charts, position-specific logs, and offline Service Worker caching.
---

# Player Stats Interrogator (interrogata)

## Purpose

This skill documents the Player Stats Interrogator analytics UI, a league-wide performance analytics dashboard for the PLL Fantasy toolset. Use this when modifying or troubleshooting the Interrogator dashboard.

> [!NOTE]
> **Design System**: All Interrogator UI development must follow the [styla](../design_system/SKILL.md) guide (Electric Purple aesthetic).
> **Hosted Address (Local)**: [http://localhost:8000/interrogata/](http://localhost:8000/interrogata/)
> **Hosted Address (Public)**: [https://additivematt.github.io/pllfantasy/interrogata/](https://additivematt.github.io/pllfantasy/interrogata/) (GitHub Pages secure origin)

---

## Core Objective
To enable data-driven fantasy decisions by visualizing a player's career trajectory and their specific historical effectiveness against upcoming opponents.

---

## System Architecture

### 1. Data Pipeline ([extract_trial_data.py](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/extract_trial_data.py))
- **Source**: Unified JSON datasets (`combined_player_stats_[YEAR].json`) and tagger output (`season_matchups_[YEAR].json`).
- **Processing**: Extracts **all players** across the entire league. It tags each player with an `isActive` status if they have recorded stats in the 2025 or 2026 seasons.
- **DNP (Did Not Play) Detection**: Maps all games played by each franchise in a season. If a player was active on a team in a given year, but did not register any stats for a week where their franchise played a game, the pipeline automatically generates a placeholder stat entry with `isDNP: true` to capture games missed due to injury, scratches, or reserve assignments.
- **Automation**: The pipeline is automatically triggered by both the Matchup Tagger server (on save) and the `combine_datasets.py` script (on stat merge), ensuring real-time data synchronization across all tools.
- **Output**: Copies `all_players_stats.json` directly into `interrogata/` (making it fully self-contained).

### 2. Frontend Interface (`/interrogata/`)
- **Technology**: Vanilla HTML5, CSS3, and JavaScript (ES6+), powered by **Chart.js**.
- **Hosting & Live Updates**: Hosted statically via **GitHub Pages**. Assets (`app.js`, `index.html`, `all_players_stats.json`) load directly over HTTPS without any Service Worker caching layers, ensuring updates pushed to GitHub are immediately live.
- **Layout**: Full-width performance trend chart, historical matchup context cards, and a detailed game log.
- **Filtering**: Supports filtering by **Team**, **Position**, and **Active Status** (2025/26).

### 3. Server Compatibility (`/matchup_tagger/server.py`)
- **Role**: Shared local Python server (Port 8000) serving the Matchup Tagger, and dynamically routing `/interrogata/` and `/predicta/` locally.
- **Decoupled Static Execution**: Because the frontend reads `./all_players_stats.json` relatively, it no longer requires the local Python server when uploaded to a static host like **GitHub Pages**.

---

## Key Features & Logic

### DNP (Did Not Play) Visualization
- **Muted Game Logs**: In the game log table, games marked as DNP are rendered with `opacity: 0.45`, italicized text, and a neutral gray color to clearly distinguish them from active games. The fantasy points (FP) column explicitly displays `"DNP"`, and all stat columns display a dash (`-`).
- **Clean Trend Lines**: The performance line chart skips plotting points for DNP weeks, bridging the gap with a continuous line (`spanGaps: true`) rather than pulling the trend line down to zero points. This prevents weeks a player missed from skewing their historical fantasy scoring trajectory.

### Dynamic Opponent Detection
- **Multi-Opponent Support**: Correcting identifying and highlighting players who have **two games** in a single week (double-headers). The UI displays both opponents and their respective historical context.
- **Resilient Parsing**: If explicit home/away metadata is missing (common for future games), it parses the opponent from the schedule display string (e.g., "vs BOS").
- **Normalization**: Automatically maps inconsistent team codes (e.g., `BOS` -> `CAN`, `MDW` -> `WHP`) to ensure historical data lookups are accurate.
- **Dynamic Fantasy Cost**: Displays the player's F2P coin cost (salary) for the selected game (eventId) dynamically in the opponent's highlight header card, accounting for separate costs for each game in a double-header week.

### Visualization & Filtering
- **Multi-Color Highlighting**: In double-header weeks, the chart and game log use distinct colors (Gold and Cyan) to distinguish between the two opponents.
- **Historical Averages**: The "Matchup Context" section displays the player's average fantasy points from their last 4 games against the specific upcoming opponent, styled for high visibility.
- **Enhanced Sorting**: The player dropdown is sorted by **Surname** and uses the `Lastname, First Initial.` format for improved league-wide navigation.

### Performance Trend Chart
- **Discontinuous Years**: Visual "hard breaks" represent gaps between seasons.
- **Intra-Season Dotted Lines**: Bye weeks and the All-Star break are bridged with dotted lines to maintain flow while noting the break.
- **Contextual Highlighting**: Points against the current target opponent are highlighted in **Gold**.

### Data Formatting & UX
- **Point Normalization**: Fantasy points are rounded to a maximum of 1 decimal place. Integers are displayed without decimals (e.g., `12`).
- **Position Grouping**: The "Defense" filter automatically groups both Close Defense (D) and LSM players for easier roster management.
- **Recent Trends**: Matchup cards are limited to the 4 most recent games for focused analysis.
- **Position-Specific Game Log**: The detailed game log table headers and columns dynamically update based on the player's position:
  - **Goalie (G)**: Renders position-relevant stats, specifically **Assists (A)**, **Caused Turnovers (CT)**, **Ground Balls (GB)**, **Goals Against (GA)**, and **Saves**, while suppressing irrelevant metrics like goals, turnovers, and touches.
  - **Faceoff (FO)**: Displays **Faceoffs Won (FOW)** and **Faceoffs Lost (FOL)** alongside general scoring metrics, while suppressing touches.
  - **Other Positions**: Displays standard metrics including Goals (G), Assists (A), Caused Turnovers (CT), Turnovers (TO), Ground Balls (GB), and Touches (T).
- **F2P Coin Cost**: A dedicated "Cost" column displays the player's F2P coin salary (numerical value only) in the game log, falling back to a dash (`-`) for historical seasons prior to F2P salary availability.

---

## Data Schema (`all_players_stats.json`)
```json
{
  "player-slug": {
    "player": { "name": "...", "slug": "...", "team": "...", "position": "..." },
    "stats": [ ... ],
    "matchup_logs": { ... },
    "isActive": true
  }
}
```

---

> [!NOTE]
> All improvement ideas are tracked centrally in the [improva](../improvements_and_baselines/SKILL.md) skill. Do not add new improvement ideas to this file.
