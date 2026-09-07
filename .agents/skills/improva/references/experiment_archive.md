# PLL Fantasy Prediction Engine — Completed & Tested Experiment Archive

> **Context**: Archived from `improva` to preserve complete audit trails and experimental post-mortems while keeping the operational runbook concise. For active priorities, see [improva](../SKILL.md).

---

## 1. Completed & Adopted Innovations

### Item 52: Faceoff Bradley-Terry Temporal Decay & Specialist Share Scaling (August 2026) ✅ ADOPTED (Baseline 15)
- **Problem (Quantified)**: FO_Spearman collapsed from 0.445 (2025, formerly strongest position) to 0.007–0.171 (2026, weakest position) — a catastrophic regression where the Faceoff roster slot was near-random.
- **Root Cause Discoveries**:
  1. *Stale Historical Pairings*: The Bradley-Terry model weighted 2023 matchups equally with 2026 matchups ($w=1.0$), anchoring stale ratings to past-prime veterans while underestimating breakout players.
  2. *Platoon / Backup Volume Trap*: In 2026, multiple teams ran faceoff platoons (Atlas: Baptiste 59%, Laliberte 35%; Cannons: McMeekin 76%, Tucci 24%; Waterdogs: Stathakis 60%, Farrell 40%). The model previously projected all eligible FOs on the roster for 100% of the team's faceoff opportunities ($N \approx 28$), generating massive false-positive projections on backups who only took 0–5 draws.
  3. *Platform Scoring Weight Lag*: The FO expected value heuristic retained a legacy 7.0 assist multiplier instead of the official 10.0 platform scoring weight.
- **Implemented Solution**:
  1. *Exponential Recency Decay*: Applied $(1.0 - 0.5)^{\Delta \text{year}}$ decay weighting to historical head-to-head faceoff encounters in Bradley-Terry training.
  2. *Specialist Share Scaling*: Scaled projected faceoff opportunities ($N$) by each player's recent 5-game faceoff share within their team (`fo_share_scaling`).
  3. *Starter Prioritization*: Sorted team specialist lists to ensure head-to-head matchup win probabilities evaluate against the opposing starting specialist.
  4. *Tighter Bayesian Shrinkage Priors & Regularization*: Tightened ground-ball shrinkage from $K=20.0 \rightarrow 10.0$ and game shrinkage from $K=3.0 \rightarrow 2.0$ with $C=0.5$ logistic regularization.
  5. *Platform Scoring Weight Alignment*: Updated assist points multiplier to 10.0 pts.
- **Results (Baseline 15 Adoption)**:
  - *Faceoff Spearman Recovery*: Recovered 2026 FO Spearman correlation from 0.007 $\rightarrow$ **0.400** (+39.3% gain!) while preserving 2025 at 0.475, raising 2-year pooled Faceoff rank correlation to **0.458** (+82.6% lift).
  - *2026 Top-1 Roster Score*: Jumped by **+17.7 pts/wk** (157.9 $\rightarrow$ **175.6 pts/wk**).
  - *2026 Top-5 Candidate Mean*: Jumped by **+18.4 pts/wk** (151.2 $\rightarrow$ **169.6 pts/wk**).
  - *Process Quality (VOR)*: 2026 Average VOR reached **+20.5 pts/slot** with **94.0% of picks scoring above positional median** (79/84 slots).
- **Status**: Integrated in `config.py` and `02_predict_probabilities.py`.

### Item 50: Attack Ranking Recovery (August 2026) ✅ ADOPTED
- **Problem**: Attack Spearman ρ degraded from 0.330 (2025) to 0.191 (2026).
- **Candidates Evaluated (In-Memory Backtest across 2025 & 2026)**:
  - *Candidate A (Opponent Goalie Form Features)*: `opp_goalie_save_pct_last3`, `opp_goalie_ga_last3`
  - *Candidate B (Shot Quality / 2-Pt Goal Features)*: `twoPointGoals_season_avg`, `twoPointGoals_last3_avg`, `two_pt_goal_ratio`
  - *Candidate C (Recency Sample Weighting)*: Scale GBDT sample weights by season recency (`--recency-weight 0.3`)
  - *Candidate D (Combined All)*: Candidates A + B + C combined

| Candidate | 2025 A_Spearman | 2025 Attack MAE | 2025 Pearson r | 2026 A_Spearman | 2026 Attack MAE | 2026 Pearson r |
|---|---|---|---|---|---|---|
| **Control (Baseline 13)** | 0.3250 | 24.624 | 0.2870 | **0.5689** | 22.708 | **0.4365** |
| **Cand A (Goalie Form)** | **0.3299** | 24.618 | 0.2863 | 0.5687 | 22.713 | 0.4284 |
| **Cand B (2-Pt Goals)** | 0.3250 | 24.624 | 0.2867 | 0.5601 | 22.708 | 0.4349 |
| **Cand C (Recency Weights)** | **0.4297** | 24.630 | **0.3226** | 0.5435 | **22.642** | 0.4278 |
| **Cand D (Combined All)** | 0.4237 | 24.631 | 0.3172 | 0.5233 | 22.649 | 0.4236 |

- **Key Discoveries**:
  1. *Baseline 13 Recovery*: Item 33 position-specific hyperparameter tuning recovered 2026 Attack Spearman correlation to **0.5689**.
  2. *Candidate C (Recency Weighting)*: Boosted 2025 Attack Spearman correlation by **+32.2%** ($0.3250 \rightarrow 0.4297$) and Pearson $r$ ($0.2870 \rightarrow 0.3226$), achieving the lowest overall 2026 MAE (22.642 pts).
- **Status**: Recency Sample Weighting (`--recency-weight 0.3`) and Opponent Goalie Form features integrated into `02_predict_probabilities.py` and `feature_engineering.py`.

### Item 49: Midfield Ranking Fix (August 2026) ✅ ADOPTED (Baseline 12)
- **Problem**: Midfield Spearman ρ was near-random (0.089 in 2025, 0.131 in 2026).
- **Fix**: Corrected official platform scoring formula (`calc_fantasy` assist multiplier $7 \rightarrow 10\text{ pts}$, 2-pt goal multiplier $15 \rightarrow 20\text{ pts}$, turnover multiplier $0 \rightarrow -3\text{ pts}$) and incorporated `assists_season_avg`, `assists_last3_avg`, `twoPointGoals_season_avg`, and `twoPointGoals_last3_avg` directly into `FEATURE_LISTS["Midfield"]`.
- **Results**: Boosted 2026 Top-5 Mean roster score by +7.2 pts/wk (149.2 $\rightarrow$ 156.4 pts/wk), 2026 Top-5 Floor by +5.2 pts/wk (124.2 $\rightarrow$ 129.4 pts/wk), and 2026 Midfield Spearman by +15.1% ($\rho \rightarrow 0.1508$).

### Item 48: Boom Precision Optimization & Decision Threshold Tuning ✅ ADOPTED
- **Problem**: Boom Recall vs Boom Precision trade-off. User prioritizes Boom Precision to eliminate false-positive trap picks.
- **Phase 1 Findings**:
  - Challenger 1 ($W=1.0$): Scored 1,489.3 pts (-46.3 pts vs Baseline 10).
  - Challenger 2 ($W=0.75$): Scored 1,315.1 pts (-220.5 pts vs Baseline 10).
  - Challenger 3 ($\tau=0.60$): 1,564.8 pts (+29.2 pts over Baseline 10 control, 42.6% ceiling).
- **Phase 2 Findings (Techniques #1 & #2 across 2025 & 2026 Seasons)**:
  - *Technique #2 (`--volume-floor`) — Standout Winner*: 2026 overall Boom Precision jumped to **32.78%** (+15.28%), Attack Precision to 27.50%, Defense to 30.00%, Goalie to 27.86% ($p=0.0058$). 2025 Boom Precision jumped to 37.32% (+5.39%), Goalie to 28.33% ($p=0.0273$), Tier Accuracy 45.25% ($p=0.0158$).
  - *Technique #1 (`--dual-gate`)*: 2026 Boom Precision 28.43% (+10.93%), 2025 Boom Precision 37.97% (+6.03%), Defense Precision 42.31%.
- **Status**: Added `--volume-floor` and `--dual-gate` CLI flags to `02_predict_probabilities.py`.

### Item 33: Position-Specific Hyperparameter Tuning ✅ ADOPTED (Baseline 13)
- **Problem**: Attack, Midfield, Defense, and Goalie used identical tree depths despite huge sample size disparities.
- **Fix**: TimeSeriesSplit grid search tuned depths and child weights: Attack (depth 4, child 3), Midfield (depth 3, child 5), Defense (depth 4, child 4), Goalie (depth 3, child 10, estimators 75).
- **Results**: +2.8 pts/wk 2026 Top-1 gain, +2.3 pts/wk 2026 Top-5 Mean gain, +4.6 pts/wk 2-year floor protection.

### Item 59: Roster-Slot & Coulda-Weighted Evaluation Metrics ✅ ADOPTED
- **Problem**: Unweighted overall metrics were dominated by depth defenders (~40% of pool) who occupy only 1 of 7 slots.
- **Fix**: Added `Slot_Weighted_Spearman` ($w_A=2/7, w_M=2/7, w_D=1/7, w_{FO}=1/7, w_G=1/7$) and `Coulda_Weighted_Spearman` ($w_A=0.348, w_M=0.285, w_G=0.147, w_D=0.131, w_{FO}=0.088$) to `prediction_model_evaluation_harness.py`.

### Item 38: Faceoff Generative Heuristic Replacement ✅ ADOPTED (Baseline 10)
- **Problem**: GBDT classifier achieved 0% Boom precision and 0% Boom recall for Faceoff.
- **Fix**: Replaced GBDT with generative Bradley-Terry head-to-head win probability model and propensity-shrunk stats.
- **Results**: +134.3 points improvement in 2025, resolving the faceoff prediction bottleneck.

### Item 37: Boom Recall Optimization (Asymmetric Class Weighting) ✅ ADOPTED (Baseline 5)
- **Problem**: Equal misclassification costs produced ~50% precision but only ~25% recall.
- **Fix**: Swept weights 1.5x, 2.0x, 2.5x, 3.0x. Optimal weight 2.0 yielded statistically significant gain (+222.3 pts in 2025, $p=0.0436$; +262.5 pts in 2026, $p=0.0712$).

### Item 36: DNP Rolling Feature Pollution Bug Fix ✅ ADOPTED (Baseline 3)
- **Problem**: `add_rolling_features()` included DNP rows, dragging rolling stats toward zero for scratched/injured players.
- **Fix**: Isolated active players (`isDNP != True`), computed rolling/EWMA features exclusively on active games, and forward-filled gaps.

### Item 27: Complete Data Leakage Elimination (July 2026) ✅ ADOPTED (Baseline 1)
- **27a**: Matchup ratings converted from global career averages to expanding cumulative means.
- **27b**: Shuffled KFold replaced with chronological `TimeSeriesSplit(n_splits=5)`.
- **27c**: Replaced multi-season global quantile tiers with `assign_tiers_expanding`.
- **27d**: MC copula correlation matrix frozen to historical pre-target-year data.
- **27e**: Global pace/goal fallbacks restricted to prior seasons.
- **27f**: MC bootstrap pool restricted to exclude target-year and future games.

### Item 11: Distributional Statistics Pre-computation ✅ ADOPTED
- Pre-calculated `mc_ev`, `mc_std`, `mc_p10`, `mc_p25`, `mc_p75`, `mc_p90` into compact JSON, eliminating runtime parsing of 23MB simulation CSVs.

### Item 9: Salary as a Feature (Market Consensus) ✅ ADOPTED (Baseline 9)
- On leak-free Baseline 8, setting `SALARY_AS_FEATURE = True` produced +50.8 pts in 2025 and +176.1 pts in 2026.

---

## 2. Tested & Rejected Experiments

### Item 53: Goalie Feature Enrichment (August 2026) ❌ REJECTED
- **Candidates Evaluated**:
  - Cand 1 (FO Adv + Opp Rating): Drop -1.1 pts/wk T5 Mean.
  - Cand 2 (Goalie GBs & CTs): Mixed (+1.3 pts T5 Mean, -1.2 pts Top-1).
  - Cand 3 (Opp Shots & Goals): Strongest modern signal (+0.1 pts '26 T5 Mean, +0.9 pts '26 T5 Max, +2.4 pts '26 Floor, +2.3 pts 2-Yr MC_WIN_160 Top-1).
  - Cand 4, 5, 6: Inconsistent or mixed results.
- **Production 25-Week Pipeline Trial (Candidate 3)**:
  - 2026 MC_EV: T5 Mean +0.1 pts, T5 Max +0.9 pts, Floor +2.4 pts, Top-1 -3.1 pts.
  - 2025 MC_EV: Top-1 167.7 pts/wk (-7.9 pts drag vs Baseline 15's 175.6 pts/wk).
  - Continuous Error: MAE 11.449, RMSE 17.450, Brier 0.1953, Boom Prec 25.3% (+0.3%).
- **Rejection Rationale**: -7.9 pt drag on 2025 MC_EV violated cross-season parity standard. Config flag kept dormant (`FEATURE_GOALIE_OPP_SHOTS_ENABLED = False`).

### Item 60: Position-Tailored Decision Thresholds & Positional Steepness ❌ REJECTED
- **Candidate 1 (Part A: Positional Decision Thresholds $\tau_{\text{pos}}$)**:
  - $\tau_A=0.45, \tau_M=0.35, \tau_D=0.42, \tau_G=0.58, \tau_{FO}=0.50$.
  - Midfield Boom Precision improved +1.3% (32.5%), but overall Boom Precision dropped to 35.8% (-4.8%), Boom Recall dropped to 30.3% (-6.6%), Tier Accuracy dropped to 42.5% (-2.9%).
- **Candidate 2 (Part B: Positional Variance Steepness in MC)**:
  - Scaled slope by variance: $\text{mult} = (1.0 - 0.5 S_{\text{pos}}) + S_{\text{pos}} \cdot P(\text{Boom})$.
  - MC_EV Top-1 collapsed from 175.6 $\rightarrow$ 169.2 pts/wk (-6.4 pts/wk; '25: -3.8 pts, '26: -9.2 pts).
  - MC_WIN_160 Top-1 collapsed from 170.0 $\rightarrow$ 164.4 pts/wk (-5.6 pts/wk).
  - MC_CEIL_90 Top-1 dropped from 173.9 $\rightarrow$ 169.2 pts/wk (-4.7 pts/wk).
- **Diagnosis: Probability Domain Distortion**:
  - The linear steepness multiplier pivots symmetrically at $P(\text{Boom}) = 50\%$. Real PLL Boom probabilities virtually never reach 50% (medians: Attack 37.1%, Defense 36.2%, Midfield 30.7%, Faceoff 20.7%). Operating strictly below 50%, steeper positions ($S_A=1.26$) receive a permanent penalty while flatter positions ($S_D=0.69$) receive structural inflation, starving elite attackers in the 200-coin knapsack optimizer.

### Item 61: Positional Scoring Variance & Salary-Scaled Loss Weights ❌ REJECTED
- **Candidate 1 ($\alpha = 1.0$)**: Top-1 Score 169.0 pts (-6.6 pts/wk), MC_Ceil_90 163.6 pts (-10.3 pts/wk), despite Slot-Weighted Spearman gaining +7.3% and Goalie Spearman surging +41.8%.
- **Candidate 2 ($\alpha = 0.25$, Milder)**: Top-1 Score 166.8 pts (-8.8 pts/wk), MC_Ceil_90 158.2 pts (-15.7 pts/wk), despite Slot-Weighted Spearman gaining +12.2% and Attack Spearman gaining +18.0%.
- **Diagnosis: The Salary Knapsack Paradox**: Downweighting low-salary players destroyed tail calibration on cheap budget enablers (5–15 coins) needed to afford superstars under the 200-coin salary cap, causing low-ceiling budget traps that bust.

### Item 47: Opponent Defensive Form by Position — Retest vs Baseline 15 ❌ REJECTED
- Retested `opp_fp_allowed_to_position_last3` across 23 weeks (2025: 13, 2026: 10).
- Top-1 Score collapsed by -6.2 pts/wk (145.9 pts; '26: -15.4 pts). Top-5 Mean fell -5.8 pts.
- Diluted Boom Precision by -2.2% and Midfield Boom Precision by -3.4%, inducing false-positive traps.

### Item 47 (Legacy): Historical Data Expansion (2019–2022 Injection) ❌ REJECTED
- 2025 Season scored 1806.6 pts (-412.7 pts degradation vs Baseline 10, $p=0.023$).
- Synthetic features smoothed out variance; meta drift (rule/pace changes) poisoned modern predictions.

### Item 45: Standalone Point-Direct Regression & Challenger Models ❌ REJECTED
- Pure Direct Point Regression achieved lower MAE (11.55) but compressed ceilings (39.1% ceiling vs Baseline 10's 47.4%). Stacking was confirmed necessary.

### Item 46: Mathematical Pace & Possession Factor Estimation ❌ REJECTED
- Converting counting stats into possession rates severely degraded scores (-219.8 pts in 2025 MC_EV, -486.7 pts in MC_Win_160) because rate normalization destroys absolute volume signals used by tree splits.

### Venue Context (Home/Away Feature) ❌ REJECTED
- PLL touring weekend format eliminates traditional home field advantages.

### Item 51: VOR-Based A/B Testing Framework ❌ CLOSED
- Redundant. Fully subsumed by the mandatory 22-metric 6-column reporting framework.

---

## 3. August 2026 Advanced Modeling Trials

### 1. Option C Selection Metrics & Threshold Tuning Audit (Item 48/49)
- Swept 8 configurations across 21 valid weeks in `scratch/run_selection_sweep.py`.
- Discovered that threshold and sample-weight tuning alter UI text tags ("Boom" vs "Average") but leave continuous point expectation rankings within position groups 100% unchanged (all 8 configurations yielded identical 15.9% Selection Hit Rate and 0.5013 NDCG@K).

### 2. Option A Learning-to-Rank (XGBRanker V1 & V2) Trials
- Evaluated `objective='rank:ndcg'` and slate-relative features via `scratch/run_ltr_backtest.py`.
- Improved Coulda Max roster overlap (+6.6% in 2026), but degraded total roster score by -170.5 pts in 2025 and -71.8 pts in 2026 because ordinal rankers lack absolute point scaling needed for budget-constrained linear programming.

### 3. No-Salary-Cap Experiment
- Evaluated pure 7-player position picks without salary constraints.
- In 2026, LTR ranker score (1,237.5 pts / 42.9% ceiling) converged almost identically with Baseline 10 (1,242.2 pts / 43.1% ceiling) with only a 4.7 pt difference across 8 weeks. Validated that LTR matches regression when budget constraints are absent, but salary-capped play requires continuous point magnitude estimates.

### 4. Player Viability & Elimination Audit (75% Non-Viable Pool)
- Out of 320 unique active players, 240 players (75.0%) never appeared in a single winning Coulda Max roster across 21 evaluated weeks. Only 80 players (25.0%) ever proved viable.
- Identified criteria: max single-game points < 15.0 pts (112 players), season average < 8.0 pts (161 players), active 3+ weeks but max points < 12.0 pts (56 players).

### 5. Option E: Two-Stage Elimination Pipeline Trial
- Pre-filtering bottom 75% non-viable players improved continuous point errors (2026 MAE 11.55 vs 11.95 pts) and boosted Boom Precision (+13.9% in 2026 to 31.37%), but dropped Boom Recall (3.6–6.4%), causing slight underestimation of tournament upside. Adopted as a hybrid recommendation for UI dashboard projections.

### 6. Top-25% Position Error Analysis
- Attackers: standard GBDT pulls outlier predictions toward the mean, under-projecting top Attackers (-8.1 to -14.9 pts bias).
- Goalies: under-projects 15+ save ceiling games (-5.3 to -10.9 pts bias).
- Midfielders: best overall calibration (bias $\approx 0.0$ pts).
- Defenders: lowest MAE (9.5–10.7 pts).

### 7. Absolute Fantasy Point Thresholds & Decision Cutoff Sweep
- Evaluated fixed absolute thresholds (Attack $\ge 30$, Midfield $\ge 22$, Defense $\ge 18$, Goalie $\ge 30$, Faceoff $\ge 25$). Boosted 2026 Boom Precision to 33.12% (+15.6% over Baseline 10). Recommended 30.0% Decision Cutoff for UI badge rendering.

### 8. Decoupled Single-Source EV Experiment (No Double Counting)
- Tested Regressor-Only EV (2,243.6 pts in '25 / 1,038.2 pts in '26) vs Classifier-Only EV (2,270.3 pts in '25 / 1,195.5 pts in '26) vs Baseline 10 Ensembled Control (2,440.8 pts in '25 / 1,274.0 pts in '26).
- Proved that combining continuous point expectations with tier probabilities is beneficial ensembling, outperforming Regressor-Only by +235.8 pts in 2026.

### 9. Opponent Team Defensive Rating Multi-Year Rolling Window Research Note
- Evaluated rolling windows of 5, 8, 10 games per opponent within a single season; discovered they return identical results to season-to-date due to 10-game regular seasons. Noted need for multi-year carryover to evaluate properly.
