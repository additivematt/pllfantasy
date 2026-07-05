---
name: pll-accuracy-evaluation
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

## Execution and Harness

Evaluation metrics are computed out-of-sample using the decoupled evaluation harness script:
```bash
python prediction_model_evaluation_harness.py
```
This script acts as the single source of truth for backtest accuracy verification.

---

> [!NOTE]
> All improvement ideas are tracked centrally in the [pll-improvements-and-baselines](../improvements_and_baselines/SKILL.md) skill. Do not add new improvement ideas to this file.
