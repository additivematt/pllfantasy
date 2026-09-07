---
name: evaluata
description: >-
  Computes prediction accuracy, ground truth tiers, Boom precision/recall, and VOR process-quality metrics.
  Use this skill when evaluating model accuracy, running the 22-metric evaluation harness, or auditing
  A/B backtests. Do NOT use for training models or generating live predictions.
---

> [!IMPORTANT]
> **Skill Naming Convention**: This skill is named **evaluata**. In chat responses, explanations, and documentation links, ALWAYS refer to it simply as `evaluata` (or [`evaluata`](file://...)). NEVER output `SKILL.md` or `evaluata/SKILL.md`.

# Predicta Evaluation Engine (evaluata)

This skill outlines the methodology for evaluating the accuracy of the `predicta` machine learning pipeline. Use this when working on model evaluation, backtesting, or auditing accuracy metrics.

---

## 1. Methodology & Data Sources

- **Predictions**: `weekN_YYYY_predictions.csv` (Model outputs).
- **Actuals**: `combined_player_stats_YYYY.json` (Ground truth fantasy points scored).
- **Exclusion**: Players who did not play (scratches / DNPs) are excluded from evaluation.

### Ground Truth Tier Assignment
Actual tiers are determined dynamically based on the distribution of points scored by players *who actually played* that week, bucketed by major `positionGroup` (Attack, Midfield, Defense, Goalie, Faceoff):
- **Boom**: Top 25% (Scores `> q75`)
- **Average**: Middle 50% (Scores `> q25` and `≤ q75`)
- **Bust**: Bottom 25% (Scores `≤ q25`)

> [!WARNING]
> The **Bust** tier frequently contains >25% of the player population due to right-inclusive clustering at `0.0` or `1.0` points for depth defenders. Conversely, high scores (Booms) are spread out, providing cleaner 25% thresholds.

---

## 2. Key Metrics Evaluated

1. **Overall & Positional Accuracy**: Total correct tier predictions / Total players evaluated.
2. **Boom Precision**: Out of all players predicted to Boom, how many actually Boomed? (User's primary metric to avoid traps).
3. **Boom Recall**: Out of all players who actually Boomed, how many did the model predict?
4. **Brier Score**: Mean squared error of predicted Boom probability vs binary Boom indicator.
5. **Spearman Rank Correlation ($\rho$)**: Measures rank-ordering accuracy overall and per-position (A, M, D, FO, G).
6. **Slot-Weighted Spearman (`Slot_Weighted_Spearman`)**: Weights positional correlations by roster slots ($w_A=2/7, w_M=2/7, w_D=1/7, w_{FO}=1/7, w_G=1/7$). Resolves the depth-defender population trap (~40% of pool).
7. **Coulda-Weighted Spearman (`Coulda_Weighted_Spearman`)**: Weights correlations by historical points contribution to winning Coulda lineups ($w_A=0.348, w_M=0.285, w_G=0.147, w_D=0.131, w_{FO}=0.088$).

---

## 3. Mandatory Top-5 Candidate Roster Pool Metrics

To eliminate single-lineup outcome luck, all roster backtests MUST evaluate the **Top-5 Candidate Roster Pool**:
- **`Top-1 Score`**: Points scored by the #1 recommended lineup.
- **`Top-5 Mean Score`**: Average points scored across all top 5 recommended lineups.
- **`Top-5 Max Score`**: Maximum points scored by the best lineup in the top 5 pool.
- **`Top-5 Min Score`**: Floor risk among the top 5 recommendations.
- **`Top-5 Max Ceiling %`**: `Top-5 Max Score / Coulda Max`.

> [!CAUTION]
> **Baseline CSV Archives MUST Always Store All Top-5 Candidate Lineups (Ranks 1 to 5)**:
> Baseline CSV files (`baselines/rosters_<strategy>_baseline_<N>.csv`) MUST ALWAYS contain all 5 distinct candidate rosters for every week (`lineup_rank` 1..5, 35 player rows/wk). Never filter out ranks 2 through 5.

---

## 4. Value Over Replacement (VOR) — Process-Quality Metric

VOR measures individual player selection decisions independent of lineup outcome luck:
$$\text{VOR} = \text{Player Actual FP} - \text{Median FP (all players who played at that position that week)}$$

- **Season Avg VOR/Slot**: Mean VOR across all player-slot decisions ($N \approx 77\text{–}91$).
- **Season Avg VOR/Week**: Mean weekly total VOR.
- **Slots Above Median (%)**: Percentage of picks that beat the positional median (Random = 50%).

---

## 5. Mandatory 22-Metric 6-Column Mobile Layout

ALL A/B backtests, feature sweeps, and baseline reports MUST present results using the standardized 6-column format across 4 category tables:
`Metric | 2-Yr Control | 2-Yr Test | 2025 Δ | 2026 Δ | Status (2-Year Effect)`

> [!NOTE]
> For the complete table templates, column specifications, and sample numbers, see the [22-Metric Mobile Reporting Specification](references/reporting_spec.md).

> [!CAUTION]
> **STRICT BAN on Deterministic Proxies**: Single-pass MILP on raw $y_{\text{pred}}$ is strictly forbidden. All evaluations MUST execute the full 5-stage production pipeline (`02` $\rightarrow$ `03` $\rightarrow$ `04` $\rightarrow$ `05` $\rightarrow$ `06_optimize_lineups.py`).

---

## 6. Execution & Verification

### Running the Evaluation Harness
Run the decoupled evaluation harness script:
```bash
python prediction_model_evaluation_harness.py
```

### Detached Execution for Long Backtests
For multi-week backtests and sweeps, always execute via detached background runners to prevent SSH disconnection aborts. See [Detached Execution Guide](references/detached_execution.md).

### Closed-Loop Verification
After executing `prediction_model_evaluation_harness.py`:
1. Confirm the process completes with exit code 0.
2. Confirm the printed output includes accuracy rows for all 5 position groups (ATTACK, MIDFIELD, DEFENSE, FACEOFF, GOALIE) and the VOR Summary block.

---

> [!NOTE]
> All improvement ideas are tracked centrally in the [improva](../improva/SKILL.md) skill. Do not add new improvement ideas to this file.
