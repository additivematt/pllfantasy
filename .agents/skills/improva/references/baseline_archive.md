# PLL Fantasy Prediction Engine — Historical Baselines Archive (Baselines 1–14)

> **Context**: Archived from `improva` to preserve complete historical benchmarking records while maintaining a lightweight operational runbook. For the active baseline, see [improva](../SKILL.md).

---

## Baseline Roster Generation & Archiving Policy

Every time a new baseline is established and rosters are saved to `baselines/`:
1. Include actual player scores in the `.csv` files as an `actualPoints` column by running `scratch/append_actual_points.py` (matching `rosters_*_baseline_*.csv`).
2. Cross-reference selected player names and `eventId`s against `combined_player_stats_YYYY.json` to calculate and write fantasy points.
3. This preserves out-of-sample scores directly inside roster artifacts without subsequent lookups or re-evaluations.

> [!CAUTION]
> **STRICT MANDATE: Baseline CSV Archives MUST Always Store All Top-5 Candidate Lineups (Ranks 1 to 5)**:
> When creating, archiving, or populating baseline roster CSVs (`baselines/rosters_<strategy>_baseline_<N>.csv`), the files MUST ALWAYS contain all 5 distinct candidate rosters for every week (with a `lineup_rank` column `1..5`, yielding 35 player rows per week $\times N_{\text{weeks}}$). **NEVER delete, strip, or filter out ranks 2 through 5** from baseline roster CSV archives. Ranks 2–5 are mandatory for evaluating Top-5 portfolio performance metrics (`Top-5 Mean`, `Top-5 Max`, `Top-5 Min`, `Top-5 Max Ceiling %`).

---

## Historical Baselines (1–9) Summary & Audit Notes

> [!WARNING]
> **Historic Baselines Compromised:**
> Baselines 1 through 8 were compromised by a combination of pipeline bugs (stale file retention), database corrections (doubleheaders), and data leakage (future-leaking matchup ratings, non-chronological cross-validation, and full-season tier thresholds). Baseline 1 was the first clean attempt (1 July 2026), but subsequent audits uncovered additional refinements:

- **Baseline 1 (Leak-Free — 1 July 2026)**: ⚠️ Superseded. First leak-free attempt after resolving 6 leakage sources. Floor of 46.3% Ceiling % for MC_EV in 2025.
- **Baseline 2 (Leak-Free + EWMA — 3 July 2026)**: ⚠️ Superseded. Enabled EWMA features. Compromised by DNP pollution in rolling averages and invalid All-Star game data.
- **Baseline 3 (DNP-Clean Rolling Features — 8 July 2026)**: ⚠️ Superseded. Compromised by pipeline bug where `03_apply_roster_filter.py` was skipped during backtests, causing artificial score inflation.
- **Baseline 4 (DNP-Clean Rolling Features — Corrected Pipeline — 13 July 2026)**: ⚠️ Superseded. First true leak-free baseline for DNP-cleaned features. Established 2000.0 pts for MC_EV in 2025 (42.7% Ceiling).
- **Baseline 5 (Asymmetric Class Weighting — Optimal Boom Weight 2.0 — 14 July 2026)**: ⚠️ Superseded. Applied class weight of 2.0 to penalize missed Booms, lifting tournament strategies.
- **Baseline 6 (Optimal Weight 2.0 + Pool Blending K=15 — 15 July 2026)**: ⚠️ Superseded. Enabled Smooth MC Historical Pool Blending ($K=15$).
- **Baseline 7 (DNP Feature Pollution Fix — 15 July 2026)**: ⚠️ Superseded. Fixed DNP feature pollution bug in prediction averages.
- **Baseline 8 (Codebase Audit & Fallback Fixes — 15 July 2026)**: ⚠️ Superseded. Fixed missing stat fallbacks and string parsing bugs prior to Salary feature integration.
- **Baseline 9 (Market Consensus: Salary As Feature — 16 July 2026)**: ⚠️ Superseded. Set `SALARY_AS_FEATURE = True` in production config, incorporating normalized salary percentile into GBDT.

---

## Baseline 10 (Bradley-Terry & Generative Heuristic — 17 July 2026, Updated 24 July 2026)

- **Description**: Bypassed GBDT classifier for Faceoff and implemented a generative Bradley-Terry matchup win probability model scaled by expected pace and shrunk player stats (ground balls, goals, assists, CTs). Restored clean `>= 2023` training pool cutoff and enforced `seed=42` across `02`, `03`, `04`, `06`.
- **Roster Files**: `baselines/rosters_<strategy>_baseline_10.csv`.

| Season | Strategy | Total Score | Coulda Max | Ceiling % | Notes / Evaluated Weeks |
|---|---|---|---|---|---|
| 2025 | MC_EV | 2219.3 | 4679.1 | 47.4% | +134.3 pts vs Baseline 9 |
| 2025 | MC_Ceil_90 | 2322.8 | 4679.1 | 49.6% | +35.5 pts |
| 2025 | MC_Win_160 | 2290.9 | 4679.1 | 49.0% | +72.8 pts |
| 2026 | MC_EV | 1473.0 | 3676.2 | 40.1% | Deterministic W1–W6, W8–W11 (All 10 played weeks) |
| 2026 | MC_Win_160 | 1522.8 | 3676.2 | 41.4% | High-floor win-threshold strategy (+49.8 pts vs EV) |
| 2026 | MC_Ceil_90 | 1232.9 | 3676.2 | 33.5% | 90th percentile ceiling strategy |

---

## Baseline 11 (Player-Anchored EV — 7 August 2026, Superseded)

- **Description**: Fixed Monte Carlo expected value calculation to use **Player-Anchored EV** ($\text{EV} = \text{player\_fp\_avg} \times (0.5 + P_{\text{Boom}} / 100)$), anchoring expectations to player caliber while using $P_{\text{Boom}}$ as dynamic matchup factor. Eliminated position-mean regression penalties on superstars.

| Season | Strategy | Top-1 (Avg/Wk) | Top-5 Mean (Avg/Wk) | Top-5 Max (Avg/Wk) | Top-5 Min (Avg/Wk) | Coulda Max (Avg/Wk) | Top-5 Max Ceiling % |
|---|---|---|---|---|---|---|---|
| **2025** | `MC_EV` | 182.6 pts/wk | 177.5 pts/wk | 201.9 pts/wk | 151.5 pts/wk | 353.2 pts/wk | 57.2% |
| **2025** | `MC_Win_160` | 171.3 pts/wk | 177.5 pts/wk | 202.4 pts/wk | 153.6 pts/wk | 353.2 pts/wk | 57.3% |
| **2025** | `MC_Ceil_90` | 184.2 pts/wk | 180.0 pts/wk | 206.7 pts/wk | 152.5 pts/wk | 353.2 pts/wk | 58.5% |
| **2026** | `MC_EV` | 158.2 pts/wk | 149.2 pts/wk | 181.7 pts/wk | 124.2 pts/wk | 357.0 pts/wk | 50.9% |
| **2026** | `MC_Win_160` | 153.1 pts/wk | 147.6 pts/wk | 175.1 pts/wk | 124.2 pts/wk | 357.0 pts/wk | 49.0% |
| **2026** | `MC_Ceil_90` | 154.6 pts/wk | 143.5 pts/wk | 176.2 pts/wk | 113.5 pts/wk | 357.0 pts/wk | 49.4% |

**Baseline 11 Process-Quality Metrics (MC_EV Top-1)**:

| Season | Avg VOR/Slot | VOR/Week | Slots Above Median | Spearman ρ (Overall) | A | M | D | FO | G |
|---|---|---|---|---|---|---|---|---|---|
| **2025** | +8.2 | +57.6 | 69.2% (63/91) | 0.363 | 0.330 | 0.089 | 0.128 | 0.445 | 0.339 |
| **2026** | +12.5 | +87.4 | 77.9% (60/77) | 0.337 | 0.191 | 0.131 | 0.240 | 0.171 | 0.259 |

---

## Baseline 12 (Midfield Assist & 2-Pt Goal Features + Platform Scoring Fix — 12 August 2026, Superseded)

- **Description**: Corrected platform scoring formula (`calc_fantasy` assist multiplier $7 \rightarrow 10\text{ pts}$, 2-pt goal multiplier $15 \rightarrow 20\text{ pts}$, turnover multiplier $0 \rightarrow -3\text{ pts}$) and incorporated `assists_season_avg`, `assists_last3_avg`, `twoPointGoals_season_avg`, `twoPointGoals_last3_avg` directly into `FEATURE_LISTS["Midfield"]`. Boosted 2026 Top-5 Mean by +7.2 pts/wk and Midfield Spearman by +15.1%.

| Season | Strategy | Top-1 (Avg/Wk) | Top-5 Mean (Avg/Wk) | Top-5 Max (Avg/Wk) | Top-5 Min (Avg/Wk) | Coulda Max (Avg/Wk) | Top-5 Max Ceiling % |
|---|---|---|---|---|---|---|---|
| **2025** | `MC_EV` | 181.7 pts/wk | 172.2 pts/wk | 199.1 pts/wk | 146.8 pts/wk | 359.9 pts/wk | 55.3% |
| **2025** | `MC_Win_160` | 179.6 pts/wk | 173.9 pts/wk | 200.4 pts/wk | 149.3 pts/wk | 359.9 pts/wk | 55.7% |
| **2025** | `MC_Ceil_90` | 177.7 pts/wk | 182.0 pts/wk | 209.8 pts/wk | 154.6 pts/wk | 359.9 pts/wk | 58.3% |
| **2026** | `MC_EV` | 141.0 pts/wk | 145.8 pts/wk | 167.1 pts/wk | 128.1 pts/wk | 372.9 pts/wk | 44.8% |
| **2026** | `MC_Win_160` | 141.4 pts/wk | 143.7 pts/wk | 165.2 pts/wk | 127.1 pts/wk | 372.9 pts/wk | 44.3% |
| **2026** | `MC_Ceil_90` | 140.0 pts/wk | 139.7 pts/wk | 162.2 pts/wk | 114.5 pts/wk | 372.9 pts/wk | 43.5% |

**Baseline 12 Process-Quality Metrics (MC_EV Top-1)**:

| Season | Avg VOR/Slot | VOR/Week | Slots Above Median | Spearman ρ (Overall) | A | M | D | FO | G |
|---|---|---|---|---|---|---|---|---|---|
| **2025** | +7.0 | +49.2 | 67.1% (61/91) | 0.348 | 0.291 | 0.049 | 0.112 | 0.445 | 0.191 |
| **2026** | +12.8 | +89.2 | 79.2% (61/77) | 0.347 | 0.227 | 0.151 | 0.244 | 0.171 | 0.256 |

---

## Baseline 13 (Position-Specific Hyperparameter Tuning — August 2026, Superseded)

- **Description**: Integrated position-specific GBDT hyperparameters (`position_hyperparams_item33.json`) across `XGBRegressor` and `XGBClassifier`:
  - **Attack**: `max_depth=4`, `min_child_weight=3`, `learning_rate=0.05`, `n_estimators=100`
  - **Midfield**: `max_depth=3`, `min_child_weight=5`, `learning_rate=0.05`, `n_estimators=100`
  - **Defense**: `max_depth=4`, `min_child_weight=4`, `learning_rate=0.05`, `n_estimators=100`
  - **Goalie**: `max_depth=3`, `min_child_weight=10`, `learning_rate=0.05`, `n_estimators=75`
- **Key Gains**: +2.8 pts/wk 2026 Top-1 score, +2.3 pts/wk 2026 Top-5 Mean, +4.6 pts/wk 2-year floor protection.
- **Roster Files**: `baselines/rosters_mc_ev_baseline_13.csv`, `baselines/rosters_mc_win_160_baseline_13.csv`, `baselines/rosters_mc_ceil_90_baseline_13.csv`.

---

## Baseline 14 (Multi-Position Recency Weighting — 16 August 2026, Superseded)

- **Description**: Incorporated Recency Sample Weighting ($\text{factor}=0.3$) across all non-faceoff positions (Attack, Midfield, Defense, Goalie) alongside Baseline 13 position-specific hyperparameters.
- **Key Gains**:
  - Boosted 2025 Attack Spearman correlation by +32.2% ($0.3250 \rightarrow 0.4297$), maintaining 0.5435 in 2026.
  - Defense Spearman correlation reached 0.6121 in 2026 with 8.283 MAE.
  - Goalie Spearman rose to 0.5270 in 2026 (+9.2%).
  - 2-Year Top-1 roster score increased by +2.1 pts/wk (166.1 pts/wk).

| Season | Strategy | Top-1 (Avg/Wk) | Top-5 Mean (Avg/Wk) | Top-5 Max (Avg/Wk) | Top-5 Min (Avg/Wk) | Coulda Max (Avg/Wk) | Top-5 Max Ceiling % |
|---|---|---|---|---|---|---|---|
| **2025** | `MC_EV` | 171.5 pts/wk | 174.8 pts/wk | 202.1 pts/wk | 148.8 pts/wk | 359.9 pts/wk | 56.1% |
| **2025** | `MC_Win_160` | 175.3 pts/wk | 176.5 pts/wk | 203.4 pts/wk | 151.3 pts/wk | 359.9 pts/wk | 56.5% |
| **2025** | `MC_Ceil_90` | 172.7 pts/wk | 184.6 pts/wk | 212.8 pts/wk | 156.6 pts/wk | 359.9 pts/wk | 59.1% |
| **2026** | `MC_EV` | 157.9 pts/wk | 151.2 pts/wk | 173.4 pts/wk | 132.6 pts/wk | 372.9 pts/wk | 46.5% |
| **2026** | `MC_Win_160` | 153.6 pts/wk | 149.8 pts/wk | 171.8 pts/wk | 131.2 pts/wk | 372.9 pts/wk | 46.1% |
| **2026** | `MC_Ceil_90` | 151.9 pts/wk | 145.7 pts/wk | 168.2 pts/wk | 118.9 pts/wk | 372.9 pts/wk | 45.1% |

**Baseline 14 Process-Quality Metrics (MC_EV Top-1)**:

| Season | Avg VOR/Slot | VOR/Week | Slots Above Median | Spearman ρ (Overall) | A | M | D | FO | G |
|---|---|---|---|---|---|---|---|---|---|
| **2025** | +8.0 | +56.2 | 70.2% (64/91) | 0.384 | 0.430 | 0.413 | 0.439 | 0.445 | 0.298 |
| **2026** | +13.3 | +92.7 | 81.2% (63/77) | 0.353 | 0.544 | 0.481 | 0.612 | 0.171 | 0.527 |
