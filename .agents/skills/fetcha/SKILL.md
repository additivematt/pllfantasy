---
name: fetcha
description: Scrapes F2P player costs/salaries, queries GraphQL box scores, backfills history, and merges into the unified player dataset.
---

> [!IMPORTANT]
> **Skill Naming Convention**: This skill is named **fetcha**. In chat responses, explanations, and documentation links, ALWAYS refer to it simply as `fetcha` (or [`fetcha`](file://...)). NEVER output `SKILL.md` or `fetcha/SKILL.md`.

# Agent Context: PLL Fantasy Data Fetching Pipeline

## Purpose

This skill outlines the PLL data fetching, ingestion, and integration pipeline. Use this when retrieving new game data, backfilling historical stats, or maintaining the unified dataset.

> [!IMPORTANT]
> **DO NOT waste time performing manual player, team, or matchup stats analysis.** 
> The scope of this module is strictly data fetching, execution, consistency, and pipeline automation. Downstream analysis is handled by other tools (such as the Player Interrogator UI). When asked to "get the stats" or run this pipeline, execute the update scripts, verify that the data loads correctly, and stop there. Do not summarize player performances, draft top performer tables, or write matchup narratives unless explicitly requested.

---

## Where This Fits in the Project

```
1. DATA FETCHING  ← this module (fetcha)
       ↓
2. PREDICTION     (see predicta)
       ↓
3. LINEUP OPTIMIZATION  (see coulda)
```

Everything downstream depends on the data produced here. **Run this pipeline first** after each game week before running predictions or optimization.

---

## Data Sources

### 1. F2P API (Fantasy-to-Play Platform)
- **Provides**: Player salaries (coin costs), weekly fantasy point projections, matchup ratings, injury status
- **Fetched via**: `01_fetch_f2p_costs.py --week N`
- **Persisted in**: `f2p_2026_season.json` (upsert by week — never overwrites previous weeks)
- **Also produces**: `f2p_weekly_data.json` (latest week's raw snapshot)

### 2. GraphQL API (PLL Official Stats)
- **Provides**: Granular per-game box stats — goals, assists, ground balls, caused turnovers, saves, shots, etc.
- **Fetched via**: `fetch_fantasy_points.py` (live 2026 season), `generate_historical_data.py` (backfill 2023–2025)
- **GraphQL queries stored in**: `graphql_query.py` (standalone module; no external archive dependency)
- **Key query**: `allTeams(year: YYYY)` — use this (not `currentTeams`) to ensure retired/inactive players appear in historical data

### 3. Unified Combined Dataset
- **Built by**: `combine_datasets.py` (2026 live updates) or `generate_historical_data.py` (historical backfill)
- **Persistence**: **Upsert behavior**. `combine_datasets.py` merges new weekly data into the existing `combined_player_stats_2026.json` file rather than overwriting it, allowing the season dataset to grow week-by-week.
- **Schema**: Keyed by `playerSlug + eventId`; each record includes:
    - `"week"`: Top-level integer (1-14). See `scripts/utils.py` for mapping logic.
    - `"identity"`: Player metadata.
    - `"event"`: Game details (eventId, startTime, home/away).
    - `"f2p"`: Fantasy points and cost data.
    - `"stats"`: Raw GraphQL granular statistics.
- **Fantasy point formula**: Custom formula applied during combine step (goals, assists, GBs, CTs, saves each have defined weights — verify in `combine_datasets.py`)

---

## ⚠️ Critical Rule: Data Must Be Per Game (eventId), Not Per Week

In some weeks, a team plays **two games**. A player on such a team has stats for two separate `eventId`s within the same fantasy week.

**Selection rule**: Fantasy players select a player for **one specific game** and only score points from that game. This means:
- The pipeline must **preserve per-game granularity** — never aggregate or collapse multiple games within a week into a single record.
- `combined_player_stats_YYYY.json` naturally handles this correctly since it keys by `playerSlug + eventId`.
- `f2p_2026_season.json` must also preserve per-game entries. Verify that a player with two games in a week has **two separate entries**, each with its own `eventId`, not a single merged/summed record.
- When downstream scripts (predicta, coulda) read weekly data, they must join on `eventId`, not just player slug + week number.

---

## ⚠️ Critical Rule: Season Segments

The PLL GraphQL API separates data into segments:
- `regular`: The primary 10-week regular season.
- `post`: Playoff games (semifinals, championships).
- `champseries`: The winter 6v6 tournament.
- `allstar`: The All-Star game.

**The pipeline (`scripts/combine_datasets.py` and `scripts/generate_historical_data.py`) is configured to include both `regular` and `post` segments.** This ensures that fantasy performance history includes high-stakes playoff games. `champseries` and `allstar` data are currently excluded to maintain focus on the standard 10v10 format.

---

## ⚠️ Critical Rule: Event ID Consistency

The naming convention for `eventId` changed significantly between the 2023 and 2025 seasons. 
- **2023 Legacy**: `game-13-2023-07-07` or `playoffs-quarterfinal-1-2023-9-1`
- **2025+ Modern**: `2025_game_13` or `2025_quarterfinal_1`

**Action required**: When joining or filtering across seasons, always use `utils.normalize_event_id(eventId)` to ensure strings match. Never assume `eventId` from 2023 will match a key generated using 2025 logic. Reference `scripts/utils.py` for the implementation.

---

## Pipeline Verification Checklist

After running the pipeline, it is a highly recommended practice to programmatically verify that all critical rules and data constraints have been followed. Make sure to verify:
- **Per-Game Granularity**: Check `f2p_2026_season.json` and `combined_player_stats_2026.json` to confirm that players with multiple games in a single week have distinct, separate entries for each `eventId` (never merged, summed, or aggregated into a single record).
- **Segment Inclusion**: Check that only standard `regular` and `post` season segments are included, and no `champseries` or `allstar` data has polluted the files.
- **Event ID Consistency**: Confirm all cross-season references resolve correctly using `utils.normalize_event_id()`.
- **Field Completeness**: Run validation checks for any unexpected `None` or zero values in essential metadata fields (such as `team`, `position`, `totalPoints`, etc.).

---

## File Inventory

| File | Description | Status |
|---|---|---|
| [01_fetch_f2p_costs.py](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/01_fetch_f2p_costs.py) | Fetches weekly F2P salary/projection data; `--week N` arg | ✅ Production |
| [fetch_fantasy_points.py](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/fetch_fantasy_points.py) | Fetches 2026 live GraphQL game stats | ✅ Production |
| [generate_historical_data.py](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/generate_historical_data.py) | Backfills 2023–2025 historical stats | ✅ Production |
| [combine_datasets.py](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/combine_datasets.py) | Merges F2P + GraphQL into unified JSON | ✅ Production |
| [graphql_query.py](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/graphql_query.py) | Houses all GraphQL query strings | ✅ Production |
| [extract_trial_data.py](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/extract_trial_data.py) | Compiles the unified stats into player-level JSON for Interrogata/Matcha | ✅ Production |
| [f2p_2026_season.json](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/f2p_2026_season.json) | Persistent F2P record for all 2026 weeks | ✅ Growing |
| [f2p_weekly_data.json](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/f2p_weekly_data.json) | Latest week's raw F2P snapshot | ✅ Updated weekly |
| [combined_player_stats_2023.json](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/combined_player_stats_2023.json) | Full 2023 historical dataset (~3 MB) | ✅ Complete |
| [combined_player_stats_2024.json](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/combined_player_stats_2024.json) | Full 2024 historical dataset (~3 MB) | ✅ Complete |
| [combined_player_stats_2025.json](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/combined_player_stats_2025.json) | Full 2025 historical dataset (~3 MB) | ✅ Complete |
| [combined_player_stats_2026.json](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/combined_player_stats_2026.json) | Growing 2026 live dataset (includes placeholders) | ✅ Growing |

---

## Team Name Normalization

The league rebranded **Chrome LC (CHR)** → **Denver Outlaws (OUT)** between seasons. A mapping rule in the pipeline handles this automatically so player history is continuous across the transition.

---

## Weekly Update Workflow

After each game week:

```bash
# Step 1: Fetch new F2P data (salaries + projected/actual points)
python 01_fetch_f2p_costs.py --week N

# Step 2: Fetch new GraphQL game stats
python fetch_fantasy_points.py

# Step 3: Merge into the unified combined dataset
python combine_datasets.py  # Automatically refreshes all_players_stats.json

# Step 4: (Optional) Verify combined file reflects the new week's data
# Step 5: Push the compiled files to GitHub to update the online UIs (see uploada)
```

### Preemptive Future Week Matchup Tagging
If the F2P website has not yet released data for a future week but you want to preemptively pick expected matchups in the Matchup Tagger UI:
1. Run `python scratch/backfill_weekN_preliminary.py` (replacing `N` with the target week — which parses rosters from previous weeks and maps them to scheduled games).
2. The script updates `combined_player_stats_2026.json` with preliminary placeholder entries and automatically updates `all_players_stats.json` via `extract_trial_data.py`.
3. Open the Matchup Tagger UI and you will immediately see the target week's options and team rosters!
4. Once the real data is released and games are played, running the standard `combine_datasets.py` workflow will automatically overwrite these temporary placeholders with official F2P/GraphQL stats.

---

> [!NOTE]
> All improvement ideas are tracked centrally in the [improva](../improva/SKILL.md) skill. Do not add new improvement ideas to this file.
