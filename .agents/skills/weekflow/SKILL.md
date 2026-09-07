---
name: weekflow
description: >-
  Guides the end-to-end 3-phase weekly operational pipeline (pre-game prep, game-day lock, post-game wrap-up).
  Use this skill as the primary entry point when executing the weekly game cycle or checking pipeline order.
  Do NOT use for deep architectural refactoring or design system changes.
---

> [!IMPORTANT]
> **Skill Naming Convention**: This skill is named **weekflow**. In chat responses, explanations, and documentation links, ALWAYS refer to it simply as `weekflow` (or [`weekflow`](file://...)). NEVER output `SKILL.md` or `weekflow/SKILL.md`.

# PLL Fantasy Weekly Workflow (weekflow)

This runbook defines the sequential procedure executed each week as information becomes available.

---

## 🗺️ Master Context Index

Refer to the specialized workspace skills for subsystem deep-dives:
- [fetcha](../fetcha/SKILL.md): Scrapers, GraphQL stats fetching, historical backfills, unified dataset.
- [interrogata](../interrogata/SKILL.md): Player Interrogator UI, career trajectory trend charts, DNP tracking.
- [matcha](../matcha/SKILL.md): Defensive assignment tagging app, backend server, data flows.
- [predicta](../predicta/SKILL.md): XGBoost classifiers, out-of-fold regressors, Monte Carlo simulations.
- [coulda](../coulda/SKILL.md): Retroactive optimal lineups, double-header per-game rules, ceiling benchmarks.
- [evaluata](../evaluata/SKILL.md): Accuracy reports, 22-metric 6-column layout, VOR evaluations.
- [uploada](../uploada/SKILL.md): Git deployment to GitHub Pages, mobile cache updates.
- [styla](../styla/SKILL.md): Obsidian design system tokens, Glassmorphism, animations.
- [improva](../improva/SKILL.md): Active Baseline 15 benchmark, backlog, A/B testing rules.

---

## 📅 Weekly Timeline Overview

```
[Phase 1: Tuesday–Thursday] ──> [Phase 2: Friday (Game-Day -24h)] ──> [Phase 3: Monday (Post-Game)]
   - Fetch weekly salaries         - Official rosters published       - Fetch box stats (GraphQL)
   - Pre-matchup tagging           - Filter inactive players          - Retroactive "Coulda" run
   - Raw model predictions         - MC Simulations & EV Baking       - Accuracy evaluation
                                   - Static UI Compile & Git Push     - Append week to active baseline
```

---

## Phase 1: Pre-Game Prep (Tuesday – Thursday)

### Step 1: Fetch Latest Weekly F2P Data
```bash
python 01_fetch_f2p_costs.py --week <WEEK>
```
*Updates `f2p_2026_season.json` and `f2p_weekly_data.json`.*

### Step 2: (Optional) Preemptive Matchup Tagging
```bash
python scratch/backfill_week<WEEK>_preliminary.py
```
*Creates blank placeholder events in `combined_player_stats_2026.json` for tagger dropdowns.*

### Step 3: Run Raw Predictions
```bash
python 02_predict_probabilities.py --year 2026 --week <WEEK>
```
*Outputs `predicta/predictions/week<WEEK>_2026_predictions_raw.csv` (filters IR/Out players).*

---

## Phase 2: Game-Day Lock (Friday — 24h Before Game-Time)

### Step 4: Apply Active Roster Filter & Update Trades
```bash
python 03_apply_roster_filter.py --year 2026 --week <WEEK>
```
*Filters 19-man active dressing lists, resolves trades, and produces final candidate pool.*

### Step 4b: Scrape Leaderboard & Competitor Rosters
```bash
python 08_scrape_challenger_rosters.py --year 2026 --week <WEEK> --my-team "SogMutts"
```
*Outputs `predicta/advisory/week<WEEK>_2026_consensus_ownership.json`. For authentication setup, see [F2P Token Setup Guide](references/f2p_token_setup.md).*

### Step 5: Run Monte Carlo Simulations
```bash
python 04_simulate_monte_carlo.py --year 2026 --week <WEEK> --sims 10000
```
*Outputs `predicta/predictions/week<WEEK>_2026_simulations.csv`.*

### Step 6: Bake Simulation Stats
```bash
python 05_bake_mc_ev.py 2026 <WEEK>
```
*Bakes `mc_ev`, standard deviation, and `mc_p90` into the prediction dataset.*

### Step 6b: Optimize Lineups
```bash
python 06_optimize_lineups.py --year 2026 --week <WEEK> --seed 42
```
*Updates active baseline roster CSVs (`rosters_mc_ev.csv`, `rosters_mc_win_160.csv`, `rosters_mc_ceil_90.csv`).*

### Step 7: Compile Static JSON Payloads
```bash
python 07_prepare_static_data.py --force
```
*Generates static extensionless JSONs for the dashboard.*

### Step 8: Push to GitHub Pages
Follow [uploada](../uploada/SKILL.md) to stage, commit, and push updates online.

---

## Phase 3: Post-Game Wrap-Up (Monday / Tuesday)

### Step 9: Tag Defensive Matchups (Film Study)
Start the local server and tag assignments at `http://localhost:8000/pllmatcha/`:
```bash
run_or_restart_server.bat
```

### Step 10: Fetch Final Game Stats & Points
```bash
# 1. Fetch actual F2P points
python 01_fetch_f2p_costs.py --week <WEEK>

# 2. Fetch GraphQL box scores
python fetch_fantasy_points.py

# 3. Combine and upsert into unified dataset
python combine_datasets.py
```

### Step 11: Run Retroactive Coulda Roster Optimization
```bash
python coulda_optimizer.py --year 2026 --week <WEEK>
```

### Step 12: Evaluate Prediction Accuracy
```bash
python prediction_model_evaluation_harness.py
```

### Step 12b: Incrementally Append Week to Active Baseline Archive
```bash
python generate_baseline_archive.py --year 2026 --week <WEEK>
```
*Upserts 35 candidate rows into active baseline archive in `baselines/` without disturbing historical weeks.*

---

## 📋 Weekly Script Checklist

| Script / Action | Phase | Input Data | Output Data |
|---|:---:|---|---|
| `01_fetch_f2p_costs.py` | Prep | F2P API | `f2p_weekly_data.json` |
| `02_predict_probabilities.py` | Prep | Historical stats + F2P costs | `_predictions_raw.csv` |
| `03_apply_roster_filter.py` | Lock | Raw predictions + Gameday Roster API | `weekN_YYYY_predictions.csv` |
| `04_simulate_monte_carlo.py` | Lock | Final filtered predictions | `weekN_YYYY_simulations.csv` |
| `05_bake_mc_ev.py` | Lock | Predictions + Simulations | Updated predictions JSON |
| `06_optimize_lineups.py` | Lock | Baked predictions & simulations | Active baseline roster CSVs |
| `07_prepare_static_data.py` | Lock | CSVs + `season_matchups_2026.json` | Static Web UI JSONs |
| `08_scrape_challenger_rosters.py` | Lock | F2P API + Refresh Token | `consensus_ownership.json` |
| Matchup Tagger UI (Matcha) | Post | User film tagging | `season_matchups_2026.json` |
| `fetch_fantasy_points.py` | Post | PLL Stats GraphQL API | Raw stats cache |
| `combine_datasets.py` | Post | Raw stats + F2P costs | `combined_player_stats_2026.json` |
| `coulda_optimizer.py` | Post | Finalized `combined_player_stats` | Optimal retroactive roster |
| `generate_baseline_archive.py` | Post | Finalized stats + active models | Appended baseline roster archive |

---

## Verification Directive
Verify that static outputs exist after Phase 2 compilation:
```bash
python -c "import os; assert os.path.exists('predicta/predictions/2026/<WEEK>') and os.path.exists('interrogata/all_players_stats.json'); print('Static payload verification: OK')"
```

---

> [!NOTE]
> All improvement ideas are tracked centrally in the [improva](../improva/SKILL.md) skill. Do not add new improvement ideas to this file.
