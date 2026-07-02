# PLL Fantasy Weekly Workflow Explainer

This document outlines the step-by-step procedure required each week as information becomes available. Following this workflow chronologically ensures that predictions, matchups, and optimizations are mathematically accurate and synchronized across all dashboards.

---

## 🗺️ Master Context Index

If you are a new AI agent onboarded to this project, use this document as your entry point. Refer to the following specialized documentation files for deep-dive context on specific subsystems:

| Document | Purpose & Scope |
|---|---|
| [fetcha.md](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/fetcha.md) | **Data pipeline**: Scrapers, GraphQL stats fetching, historical backfilling, and unified dataset consolidation. |
| [interrogata.md](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/interrogata.md) | **Player Interrogator UI**: Career trajectory trend charts, historical matchup averages, and DNP tracking. |
| [matcha.md](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/matcha.md) | **Matchup Tagging UI**: Manual defensive assignment tagger app scope, backend server, and data flows. |
| [predicta.md](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/predicta.md) | **Prediction Engine**: XGBoost classifiers, quantile regressors, Monte Carlo simulations, and EV baking. |
| [coulda.md](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/coulda.md) | **Retroactive Optimization**: Calculating historical max-possible scores under F2P salary limits. |
| [evaluata.md](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/evaluata.md) | **Accuracy Reports**: Ground truth assignment, scoring distribution ties, and accuracy evaluation logic. |
| [uploada.md](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/uploada.md) | **Deployment**: Git commands, GitHub Pages static assets compilation, and offline Service Worker cache updates. |
| [styla.md](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/styla.md) | **Design System**: UI aesthetic requirements, Glassmorphism, animations, and Electric Purple color tokens. |

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
Run the F2P scraping script to get player salaries, projections, and injury statuses for the target week. This updates [f2p_2026_season.json](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/f2p_2026_season.json) and [f2p_weekly_data.json](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/f2p_weekly_data.json).
```bash
python 01_fetch_f2p_costs.py --week <WEEK>
```

#### Step 2: (Optional) Preemptive Matchup Tagging
If you want to tag matchups in the UI before F2P has released stats for the week, you can generate placeholder entries using a backfill script:
```bash
python scratch/backfill_week<WEEK>_preliminary.py
```
> [!NOTE]
> This parses team schedules and generates blank placeholder events in [combined_player_stats_2026.json](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/combined_player_stats_2026.json) so the games immediately show up in the Matchup Tagger UI dropdowns.

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
> This script reads the raw predictions, filters out scratched players, updates traded players' matchups, writes `predicta/predictions/week<WEEK>_2026_predictions.csv`, and automatically calls [06_optimize_lineups.py](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/06_optimize_lineups.py) to generate the baseline advisory report.

#### Step 4b: Scrape Leaderboard & Competitor Rosters
Once competitor rosters lock and become visible (or when you want to pull consensus selections), scrape the global top 25 leaders and your local league rivals:
```bash
python 08_scrape_challenger_rosters.py --year 2026 --week <WEEK> --my-team "<YOUR_TEAM_NAME>"
```
*Outputs: `predicta/advisory/week<WEEK>_2026_consensus_ownership.json`.*

> [!TIP]
> **Automated Login**:
> 1. **Refresh Token (Recommended for Magic Links)**: Extract your Firebase refresh token from your browser's Local Storage once and set it as the `F2P_REFRESH_TOKEN` environment variable. The script will exchange it for a fresh ID token automatically.
> 2. **Password Login**: If your account has a password, set `F2P_EMAIL` and `F2P_PASSWORD` environment variables.
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

#### Step 7: Compile Static JSON Payloads
Generate the extensionless JSON files read by the service worker in the Web UI.
```bash
python 07_prepare_static_data.py
```
> [!TIP]
> This script scans all prediction and advisory outputs and prepares static files in [predicta/predictions/](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/predicta/predictions/) and [predicta/advisory/](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/predicta/advisory/).

#### Step 8: Push to GitHub Pages
Pushes the compiled static payloads to GitHub. The changes will build and be live on GitHub Pages in about 30 seconds.
```powershell
# Stage the modified data files
scratch\mingit\cmd\git.exe add interrogata/all_players_stats.json predicta/predictions/ predicta/advisory/

# Create the commit
scratch\mingit\cmd\git.exe commit -m "Update week <WEEK> predictions & simulations"

# Push to GitHub
scratch\mingit\cmd\git.exe push origin main
```
> [!WARNING]
> This terminal command uses a portable Git client configured specifically for your **main laptop** credentials. If running on another PC, please commit and push via **GitHub Desktop** or the **GitHub Web Interface**.

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
> Saving matchups to [season_matchups_2026.json](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/season_matchups_2026.json) automatically triggers [extract_trial_data.py](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/extract_trial_data.py) to compile the player database.

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
Compare the predicted tiers against the actual outcomes and generate the weekly accuracy report:
```bash
python predicta_accuracy_report.py (DELETED) --year 2026 --week <WEEK>
```

---

## 📋 Weekly Script Checklist

| Script / Action | Phase | Input Data | Output Data |
|---|:---:|---|---|
| [01_fetch_f2p_costs.py](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/01_fetch_f2p_costs.py) | Prep | F2P API | `f2p_weekly_data.json` |
| [02_predict_probabilities.py](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/02_predict_probabilities.py) | Prep | Historical stats + F2P costs | `_predictions_raw.csv` |
| [03_apply_roster_filter.py](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/03_apply_roster_filter.py) | Lock | Raw predictions + Gameday Roster API | `predicta/predictions/weekN_YYYY_predictions.csv` |
| [04_simulate_monte_carlo.py](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/04_simulate_monte_carlo.py) | Lock | `predicta/predictions/weekN_YYYY_predictions.csv` | `predicta/predictions/weekN_YYYY_simulations.csv` |
| [05_bake_mc_ev.py](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/05_bake_mc_ev.py) | Lock | Predictions + Simulations | Updated final predictions |
| [07_prepare_static_data.py](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/07_prepare_static_data.py) | Lock | CSVs + [season_matchups_2026.json](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/season_matchups_2026.json) | Static Web UI JSONs |
| [08_scrape_challenger_rosters.py](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/08_scrape_challenger_rosters.py) | Lock | F2P API + Refresh Token | `weekN_YYYY_consensus_ownership.json` |
| Matchup Tagger UI (Matcha) | Post | User manual tagging | [season_matchups_2026.json](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/season_matchups_2026.json) |
| [fetch_fantasy_points.py](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/fetch_fantasy_points.py) | Post | PLL Stats GraphQL API | Raw stats cache |
| [combine_datasets.py](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/combine_datasets.py) | Post | Raw stats + F2P costs | `combined_player_stats_2026.json` |
| [coulda_optimizer.py](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/coulda_optimizer.py) | Post | Finalized `combined_player_stats_2026.json` | Optimal retroactive roster |
| [predicta_accuracy_report.py (DELETED)](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/predicta_accuracy_report.py (DELETED)) | Post | Finalized stats + predictions | Accuracy metrics / report |

---

## 🔑 One-Time Setup for F2P Refresh Token Automation

If your account logs in via a passwordless Magic Link, you will need to extract your long-lived Firebase **Refresh Token** once and set it as an environment variable so the weekly scraper runs automatically without manual intervention.

### Extraction Steps:
1. Open your browser and go to the [F2P platform](https://f2p.premierlacrosseleague.com).
2. Open **Developer Tools** (`F12`), navigate to the **Application** (or **Storage**) tab, and select **IndexedDB** -> **`firebaseLocalStorageDb`** -> **`firebaseLocalStorage`**.
3. Locate the row where the key starts with `firebase:authUser:...`.
4. Inside the JSON value of that row, expand the `value` object, then expand `stsTokenManager`, and copy the value of **`refreshToken`**.
5. Save the token as a User environment variable on your machine:
   ```powershell
   [System.Environment]::SetEnvironmentVariable('F2P_REFRESH_TOKEN', 'YOUR_REFRESH_TOKEN', 'User')
   ```

---

> [!NOTE]
> All improvement ideas are tracked centrally in [improva.md](file:///g:/My%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/improva.md). Do not add new improvement ideas to this file.
