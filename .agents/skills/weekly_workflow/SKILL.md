---
name: weekflow
description: Explains the weekly timeline (pre-game, game-day lock, post-game) and step-by-step update process for PLL Fantasy.
---

# PLL Fantasy Weekly Workflow Explainer

This document outlines the step-by-step procedure required each week as information becomes available. Following this workflow chronologically ensures that predictions, matchups, and optimizations are mathematically accurate and synchronized across all dashboards.

---

## 🗺️ Master Context Index

If you are a new AI agent onboarded to this project, use this document as your entry point. Refer to the following specialized workspace skills for deep-dive context on specific subsystems:

| Skill | Purpose & Scope |
|---|---|
| [fetcha](../data_fetching/SKILL.md) | **Data pipeline**: Scrapers, GraphQL stats fetching, historical backfilling, and unified dataset consolidation. |
| [interrogata](../player_interrogator/SKILL.md) | **Player Interrogator UI**: Career trajectory trend charts, historical matchup averages, and DNP tracking. |
| [matcha](../matchup_tagger/SKILL.md) | **Matchup Tagging UI**: Manual defensive assignment tagger app scope, backend server, and data flows. |
| [predicta](../prediction_engine/SKILL.md) | **Prediction Engine**: XGBoost classifiers, quantile regressors, Monte Carlo simulations, and EV baking. |
| [coulda](../lineup_optimization/SKILL.md) | **Retroactive Optimization**: Calculating historical max-possible scores under F2P salary limits. |
| [evaluata](../accuracy_evaluation/SKILL.md) | **Accuracy Reports**: Ground truth assignment, scoring distribution ties, and accuracy evaluation logic. |
| [uploada](../deployment/SKILL.md) | **Deployment**: Git commands, GitHub Pages static assets compilation, and offline Service Worker cache updates. |
| [styla](../design_system/SKILL.md) | **Design System**: UI aesthetic requirements, Glassmorphism, animations, and Electric Purple color tokens. |
| [improva](../improvements_and_baselines/SKILL.md) | **Backlog & Baseline Tracking**: Feature pipeline, Baseline 2 evaluation metrics, and A/B testing rules. |

---

## 📅 Weekly Timeline & Workflow Overview

The weekly cycle is divided into three distinct phases based on when official data is released:

```
[Phase 1: Tuesday–Thursday] ──> [Phase 2: Friday (Game-Day -24h)] ──> [Phase 3: Monday (Post-Game)]
   - Fetch weekly salaries         - Official rosters published       - Fetch box stats (GraphQL)
   - Pre-matchup tagging           - Filter inactive players          - Retroactive "Coulda" run
   - Raw model predictions         - MC Simulations & EV Baking       - Accuracy evaluation
                                   - Static UI Compile & Git Push
```

---

## 🛠️ Step-by-Step Instructions

### Phase 1: Pre-Game Prep (Tuesday – Thursday)
*When player salaries and initial weekly projections are updated on the F2P platform.*

#### Step 1: Fetch Latest Weekly F2P Data
Run the F2P scraping script to get player salaries, projections, and injury statuses for the target week. This updates `f2p_2026_season.json` and `f2p_weekly_data.json`.
```bash
python 01_fetch_f2p_costs.py --week <WEEK>
```

#### Step 2: (Optional) Preemptive Matchup Tagging
If you want to tag matchups in the UI before F2P has released stats for the week, you can generate placeholder entries using a backfill script:
```bash
python scratch/backfill_week<WEEK>_preliminary.py
```
> [!NOTE]
> This parses team schedules and generates blank placeholder events in `combined_player_stats_2026.json` so the games immediately show up in the Matchup Tagger UI dropdowns.

#### Step 3: Run Raw predictions
Execute the prediction models on the raw (unfiltered) rosters. These scripts automatically filter out players on Injured Reserve (`IR`) or marked Out (`O`).
```bash
# 1. Run Classification Model (Boom Probability & Tiers)
python 02_predict_probabilities.py --year 2026 --week <WEEK>

# (Deprecated: Quantile Regression model removed in Tier 1 Refactoring)
```
*Outputs: `predicta/predictions/week<WEEK>_2026_predictions_raw.csv`.*

---

### Phase 2: Game-Day Lock (Friday — 24 Hours Before Game-Time)
*When official gameday rosters are finalized and published by the league.*

#### Step 4: Apply Active Roster Filter & Update Trades
Official rosters are used to filter out inactive scratches (dressing list limited to 19 active players) and update team codes for traded players.
```bash
python 03_apply_roster_filter.py --year 2026 --week <WEEK>
```
> [!IMPORTANT]
> This script reads the raw predictions, filters out scratched players, updates traded players' matchups, writes `predicta/predictions/week<WEEK>_2026_predictions.csv`, and automatically calls `06_optimize_lineups.py` to generate the baseline advisory report.

#### Step 4b: Scrape Leaderboard & Competitor Rosters
Once competitor rosters lock and become visible (or when you want to pull consensus selections), scrape the global top 25 leaders and your local league rivals:
```bash
python 08_scrape_challenger_rosters.py --year 2026 --week <WEEK> --my-team "<YOUR_TEAM_NAME>"
```
*Outputs: `predicta/advisory/week<WEEK>_2026_consensus_ownership.json`.*

> [!TIP]
> **Automated Login**:
> 1. **Refresh Token (.env file / Env Var)**: Save your long-lived Firebase refresh token as `F2P_REFRESH_TOKEN` in a local `.env` file or environment variable. The script will exchange it for a fresh ID token automatically.
> 2. **Password Login (.env file / Env Var)**: If your account has a password, set `F2P_EMAIL` and `F2P_PASSWORD` in your `.env` file.
> 3. **Manual**: If neither is set, pass a fresh token via `--token <JWT_TOKEN>`.

#### Step 5: Run Monte Carlo Simulations
Run 10,000 Monte Carlo trials for the week's games. This models joint scoring distributions and team/opponent correlations using the Copula structure.
```bash
python 04_simulate_monte_carlo.py --year 2026 --week <WEEK> --sims 10000
```
*Outputs: `predicta/predictions/week<WEEK>_2026_simulations.csv`.*

#### Step 6: Bake Simulation Stats
Inject the Monte Carlo Expected Value (`mc_ev`), standard deviation, and 90th percentile ceiling (`mc_p90`) directly into the final prediction file.
```bash
python 05_bake_mc_ev.py 2026 <WEEK>
```

#### Step 6b: Optimize Lineups & Update Active Baseline Roster CSVs
Execute the roster optimizer to update the active baseline roster files (`rosters_mc_ev.csv`, `rosters_mc_win_160.csv`, `rosters_mc_ceil_90.csv`).
```bash
python 06_optimize_lineups.py --year 2026 --week <WEEK> --seed 42
```
> [!IMPORTANT]
> This step establishes the single source of truth for all active baseline rosters.

#### Step 7: Compile Static JSON Payloads
Generate the extensionless JSON files read by the Web UI. `07_prepare_static_data.py` pulls roster selections directly from the saved active baseline roster CSVs (`rosters_mc_ev.csv`, `rosters_mc_win_160.csv`, `rosters_mc_ceil_90.csv`), guaranteeing 100% parity between the evaluation harness and the Web UI.
```bash
python 07_prepare_static_data.py --force
```

#### Step 8: Push to GitHub Pages
Pushes the compiled static payloads to GitHub. The changes will build and be live on GitHub Pages in about 30 seconds.
```powershell
# Stage the modified data files
git add interrogata/all_players_stats.json predicta/predictions/ predicta/advisory/

# Create the commit
git commit -m "Update week <WEEK> predictions & simulations"

# Push to GitHub
git push origin main
```

---

### Phase 3: Post-Game Wrap-Up (Monday / Tuesday)
*When all games are completed and stats are officially recorded.*

#### Step 9: Tag Defensive Matchups (film study)
Start the local server and open the Matchup Tagger UI to record defensive assignments observed during game film:
```bash
# 1. Start the server
run_or_restart_server.bat

# 2. Open http://localhost:8000/pllmatcha/ in your web browser
```
> [!NOTE]
> Saving matchups to `season_matchups_2026.json` automatically triggers `extract_trial_data.py` to compile the player database.

#### Step 10: Fetch Final Game Stats & Points
Retrieve actual box scores and final fantasy points to grow the season training dataset:
```bash
# 1. Fetch actual F2P points
python 01_fetch_f2p_costs.py --week <WEEK>

# 2. Fetch GraphQL box scores
python fetch_fantasy_points.py

# 3. Combine and upsert into the unified 2026 JSON dataset
python combine_datasets.py
```

#### Step 11: Run Retroactive "Coulda" Roster Optimization
Find the mathematically optimal roster that could have been selected for the week, providing the maximum ceiling benchmark:
```bash
python coulda_optimizer.py --year 2026 --week <WEEK>
```

#### Step 12: Evaluate Prediction Accuracy
Compare the predicted tiers against the actual outcomes using the evaluation harness:
```bash
python prediction_model_evaluation_harness.py
```

---

## 📋 Weekly Script Checklist

| Script / Action | Phase | Input Data | Output Data |
|---|:---:|---|---|
| `01_fetch_f2p_costs.py` | Prep | F2P API | `f2p_weekly_data.json` |
| `02_predict_probabilities.py` | Prep | Historical stats + F2P costs | `_predictions_raw.csv` |
| `03_apply_roster_filter.py` | Lock | Raw predictions + Gameday Roster API | `predicta/predictions/weekN_YYYY_predictions.csv` |
| `04_simulate_monte_carlo.py` | Lock | `predicta/predictions/weekN_YYYY_predictions.csv` | `predicta/predictions/weekN_YYYY_simulations.csv` |
| `05_bake_mc_ev.py` | Lock | Predictions + Simulations | Updated final predictions |
| `07_prepare_static_data.py` | Lock | CSVs + `season_matchups_2026.json` | Static Web UI JSONs |
| `08_scrape_challenger_rosters.py` | Lock | F2P API + Refresh Token | `weekN_YYYY_consensus_ownership.json` |
| Matchup Tagger UI (Matcha) | Post | User manual tagging | `season_matchups_2026.json` |
| `fetch_fantasy_points.py` | Post | PLL Stats GraphQL API | Raw stats cache |
| `combine_datasets.py` | Post | Raw stats + F2P costs | `combined_player_stats_2026.json` |
| `coulda_optimizer.py` | Post | Finalized `combined_player_stats_2026.json` | Optimal retroactive roster |

---

## 🔑 One-Time Setup for F2P Refresh Token Automation

To run the weekly scraper automatically without manual token copy-paste or HAR file exports, you can set up a local `.env` file with your credentials or refresh token.

### Setup Steps:
1. Copy the template [.env.example](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/.env.example) to a new file named `.env` in the scripts directory.
2. Fill in **one** of the authentication methods:
   * **Method A (Email & Password)**: If your account uses a password, enter your email and password in the `.env` file.
   * **Method B (Refresh Token)**: If you log in via Magic Link, extract your long-lived Firebase **Refresh Token** from your browser's IndexedDB and enter it as `F2P_REFRESH_TOKEN` in the `.env` file.

### Easy IndexedDB Token Extraction:
1. Open your browser to the logged-in [F2P leagues page](https://f2p.premierlacrosseleague.com/fantasy/leagues).
2. Open **Developer Tools** (`F12`), go to the **Console** tab.
3. Paste the following JavaScript and press **Enter**:
   ```javascript
   (async function() {
     const db = await new Promise((res, rej) => {
       const req = indexedDB.open("firebaseLocalStorageDb");
       req.onsuccess = () => res(req.result);
       req.onerror = rej;
     });
     const tx = db.transaction("firebaseLocalStorage", "readonly");
     const store = tx.objectStore("firebaseLocalStorage");
     const records = await new Promise((res) => {
       const req = store.getAll();
       req.onsuccess = () => res(req.result);
     });
     if (records && records.length > 0) {
       const token = records[0].value.stsTokenManager?.refreshToken || records[0].value.refreshToken;
       console.log("Your F2P_REFRESH_TOKEN is:\n\n" + token);
     } else {
       console.error("No active session found in IndexedDB.");
     }
   })();
   ```
4. Copy the printed token and save it in your `.env` file.

---

> [!NOTE]
> All improvement ideas are tracked centrally in the [improva](../improvements_and_baselines/SKILL.md) skill. Do not add new improvement ideas to this file.
