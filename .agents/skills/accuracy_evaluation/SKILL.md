---
name: evaluata
description: Instructions for assigning ground truth performance tiers (Boom, Average, Bust), evaluating classifier accuracy, and precision/recall reporting.
---

# Agent Context: Predicta Evaluation Engine

## Purpose

This skill outlines the methodology for evaluating the accuracy of the `predicta` machine learning pipeline. Use this when working on model evaluation, backtesting, or improving accuracy metrics.

## Methodology

### 1. Data Sources
- **Predictions**: `weekN_YYYY_predictions.csv` (The model's outputs).
- **Actuals**: `combined_player_stats_YYYY.json` (The ground truth fantasy points scored).
- Players who did not play (i.e., those who do not have an entry in the actuals JSON for that week) are explicitly excluded from the evaluation, as the model cannot predict scratches.

### 2. Tier Assignment (Ground Truth)
Actual tiers are determined dynamically based on the distribution of points scored by players *who actually played* in that week's games. Players are bucketed by their major `positionGroup` (Attack, Midfield, Defense, Goalie, Faceoff).

- **Boom**: Top 25% (Scores `> q75`)
- **Average**: Middle 50% (Scores `> q25` and `≤ q75`)
- **Bust**: Bottom 25% (Scores `≤ q25`)

### 3. The "Clustering" Nuance
> [!WARNING]
> You will frequently observe that the **Bust** tier contains significantly more than 25% of the player population. This is a mathematical reality of fantasy lacrosse scoring, not a bug.

Fantasy point distributions exhibit a heavy right-skew, especially for defensive players and some midfielders. A large percentage of the population will score `0` or `1` point. 

Because the `pd.cut` interval is right-inclusive (`(-inf, q25]`), if `q25 = 0.0` and 40% of the player pool scores `0.0`, all 40% of those players will be classified as Busts. Conversely, high scores (Booms) are spread out, meaning the top 25% cutoff usually results in a much cleaner 25% slice of the population without massive ties on the boundary.

### 4. Metrics Evaluated
The evaluation harness outputs several key metrics to measure model performance:
- **Overall Accuracy**: Total correct tier predictions / Total players evaluated.
- **Confusion Matrix**: A cross-tabulation of Predicted vs. Actual tiers.
- **Per-Position Accuracy**: Accuracy isolated by `positionGroup`.
- **Boom Precision**: Out of all players the model predicted to Boom, how many actually Boomed? (Minimizes false positives / traps).
- **Boom Recall**: Out of all players who actually Boomed, how many did the model successfully predict? (Maximizes finding the ceiling).
- **Thresholds**: The explicit `q25` and `q75` point cutoffs for that week to provide context on the scoring environment.

### 5. Top-5 Candidate Roster Pool Metrics (Mandatory for Roster Backtests)
> [!IMPORTANT]
> To eliminate single-lineup random outcome noise (where 1 player scratch or boom/bust outcome creates 50+ point swings in small 10–13 slate samples), **all future roster backtests MUST evaluate the Top-5 Candidate Roster Pool**. 

> [!CAUTION]
> **STRICT MANDATE: Baseline CSV Archives MUST Always Store All Top-5 Candidate Lineups (Ranks 1 to 5)**:
> When creating, archiving, or populating baseline roster CSVs (`baselines/rosters_<strategy>_baseline_<N>.csv`), the files MUST ALWAYS contain all 5 distinct candidate rosters for every week (with a `lineup_rank` column `1..5`, yielding 35 player rows per week $\times N_{\text{weeks}}$). **NEVER delete, strip, or filter out ranks 2 through 5** from baseline roster CSV archives.

For every backtested week, the evaluation harness calculates:
1. **`Top-1 Score`**: The actual points scored by the single #1 recommended lineup.
2. **`Top-5 Mean Score`**: The average actual points scored across all top 5 recommended lineups.
3. **`Top-5 Max Score`**: The maximum actual points scored by the best lineup present in the top 5 advisory recommendations (measures if a slate-winning roster was present in the candidate pool).
4. **`Top-5 Min Score`**: The minimum actual points scored (floor risk) among the top 5 recommendations.
5. **`Top-5 Max Ceiling %`**: `Top-5 Max Score / Coulda Max` (the ratio of the candidate pool's best roster to the theoretical optimal ceiling).

---

### 6. Primary Reporting Metric: Average Weekly Score (Mandatory Default)
> [!IMPORTANT]
> **Reporting Standard (Average Weekly Score > Raw Season Total)**:
> By default, all roster evaluation summaries, backtests, and comparison tables MUST report **Average Weekly Score** ($\text{Total Score} / N_{\text{weeks}}$) as the primary performance metric.
> 
> Because different seasons and backtests evaluate varying numbers of weeks (e.g. 13 weeks in 2025 vs 10 weeks in 2026), raw total season scores obscure true per-week performance and complicate direct comparison. Reporting Average Weekly Score standardizes all roster metrics onto a clear, intuitive per-week scale (e.g. 188.6 pts/wk vs 168.8 pts/wk).

## Execution and Harness

Evaluation metrics are computed out-of-sample using the decoupled evaluation harness script [prediction_model_evaluation_harness.py](file:///f:/Google%20Drive/Documents/Hobbies/Lacrosse/PLL%20fantasy/scripts/prediction_model_evaluation_harness.py):
```bash
python prediction_model_evaluation_harness.py
```
This script acts as the single source of truth for backtest accuracy verification.

### Example Output Snippet
```text
ATTACK     | Acc: 47.1% (24/51) | Boom Prec: 60.0% | Rec: 23.1% | Bust <= 0.0 | Boom > 25.0
MIDFIELD   | Acc: 40.3% (25/62) | Boom Prec: 42.9% | Rec: 21.4% | Bust <= 0.0 | Boom > 17.0
DEFENSE    | Acc: 41.8% (38/91) | Boom Prec: 41.2% | Rec: 28.0% | Bust <= 0.0 | Boom > 10.4
FACEOFF    | Acc: 21.4% ( 3/14) | Boom Prec:  0.0% | Rec:  0.0% | Bust <= 0.0 | Boom > 11.6
GOALIE     | Acc: 26.1% ( 6/23) | Boom Prec: 66.7% | Rec: 33.3% | Bust <= 0.0 | Boom > 23.2
```

---

> [!NOTE]
> All improvement ideas are tracked centrally in the [improva](../improvements_and_baselines/SKILL.md) skill. Do not add new improvement ideas to this file.
