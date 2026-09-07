# Official 22-Metric 4-Category 6-Column Mobile Reporting Specification

> **Context**: Standardized reporting layout specification for all PLL Fantasy model evaluations and A/B backtests, referenced by [`evaluata`](../SKILL.md).

---

## Strict Formatting Rules

1. **No Code Keys or Units in Table**: Omit code identifiers and unit strings inside table cells to fit mobile screens cleanly without horizontal wrapping.
2. **Separate Category Headings**: Results MUST be presented across 4 distinct category tables with section headers, rather than a single giant table.
3. **2-Yr Pooled Baseline Benchmark**: Always report the 23–25 week pooled benchmark (`2-Yr Control` vs `2-Yr Test`).
4. **Individual Season Deltas**: `2025 Δ` (13 weeks) and `2026 Δ` (10–12 weeks) MUST be reported to catch single-season overfitting.
5. **2-Year Effect Status Narrative**: The `Status (2-Year Effect)` column MUST evaluate the overall pooled effect. Do NOT prefix status text with `"2-Yr"`; use clean, concise color-coded emojis (🟢, 🔴, 🟡) with punchy 2–4 word narrative notes (e.g. `🟢 Lower error (-0.037 pts)`, `🟢 Portfolio Gain (+7.2 pts)`, `🔴 Drop (-8.5 pts)`).

---

## Category 1: Candidate Portfolio & Roster Performance (5 Metrics)
*Evaluates actual fantasy points scored by recommended lineups against out-of-sample ground truth.*

| Metric | 2-Yr Control | 2-Yr Test | 2025 $\Delta$ | 2026 $\Delta$ | Status (2-Year Effect) |
|---|---|---|---|---|---|
| **Top-1 Avg Score** | 172.0 | 163.5 | -10.0 pts | -6.6 pts | 🔴 Drop (-8.5 pts) |
| **Top-5 Mean Score** | 165.2 | 163.6 | -8.4 pts | **+7.2 pts** | 🟡 Split (-1.6 pts) |
| **Top-5 Max Score** | 193.1 | 186.0 | -11.8 pts | -1.0 pts | 🔴 Drop (-7.1 pts) |
| **Top-5 Min Score** | 139.6 | 138.8 | -5.4 pts | **+5.2 pts** | 🟢 Floor Safe (+5.2 pts '26) |
| **Top-5 Max Ceiling %** | 54.5% | 51.1% | -4.3% | -2.1% | 🟡 Minor Drop (-3.4%) |

---

## Category 2: Process Quality — Value Over Replacement (VOR) (3 Metrics)
*Measures individual player selection decisions independent of weekly lineup outcome luck.*

| Metric | 2-Yr Control | 2-Yr Test | 2025 $\Delta$ | 2026 $\Delta$ | Status (2-Year Effect) |
|---|---|---|---|---|---|
| **Avg VOR / Slot** | +10.1 | +9.6 | -1.2 pts | +0.3 pts | 🟢 Strong (+9.6 pts/pick) |
| **Avg VOR / Week** | +70.6 | +66.6 | -8.4 pts | +1.8 pts | 🟢 Strong (+66.6 pts/wk) |
| **Slots Above Median %** | 73.0% | 72.4% | -2.1% | **+1.3%** | 🟢 High (72.4%) |

---

## Category 3: Continuous Accuracy & Position Rank Correlation (10 Metrics)
*Measures raw projection accuracy and relative rank-ordering quality by position.*

| Metric | 2-Yr Control | 2-Yr Test | 2025 $\Delta$ | 2026 $\Delta$ | Status (2-Year Effect) |
|---|---|---|---|---|---|
| **MAE** | 12.333 | 12.296 | -0.037 pts | -0.036 pts | 🟢 Lower error (-0.037 pts) |
| **RMSE** | 15.947 | 15.912 | -0.025 pts | -0.048 pts | 🟢 Lower extreme error |
| **Pearson $r$** | 0.0894 | 0.0891 | -0.0059 | +0.0070 | 🟡 Flat (-0.0003) |
| **Overall Spearman $\rho$** | 0.3517 | 0.3476 | -0.0147 | +0.0096 | 🟡 Flat (-0.0041) |
| **Slot-Weighted Spearman $\rho$** | 0.2850 | 0.2830 | -0.0120 | +0.0080 | 🟡 Flat (-0.0020) |
| **Attack Spearman $\rho$** | 0.2696 | 0.2628 | -0.0395 | +0.0359 | 🟡 Split (-0.0068) |
| **Midfield Spearman $\rho$** | 0.1073 | 0.0905 | -0.0449 | **+0.0198** | 🟡 Split (+0.020 in '26) |
| **Defense Spearman $\rho$** | 0.1767 | 0.1696 | -0.0158 | +0.0043 | 🟡 Flat (-0.0071) |
| **Faceoff Spearman $\rho$** | 0.3259 | 0.3259 | 0.0000 | 0.0000 | 🟢 Unchanged (0.326) |
| **Goalie Spearman $\rho$** | 0.3042 | 0.2191 | -0.1482 | -0.0031 | 🔴 Drop (-0.0851) |

---

## Category 4: Classification, Boom Detection & Calibration (5 Metrics)
*Measures tier classification accuracy and high-upside Boom probability calibration.*

| Metric | 2-Yr Control | 2-Yr Test | 2025 $\Delta$ | 2026 $\Delta$ | Status (2-Year Effect) |
|---|---|---|---|---|---|
| **Tier Accuracy** | 44.9% | 45.4% | +0.7% | +0.2% | 🟢 Improved (+0.5%) |
| **Boom Precision** | 33.3% | 33.9% | +0.8% | +0.4% | 🟢 Improved (+0.6%) |
| **Midfield Boom Precision** | 33.3% | 33.9% | +0.8% | +0.4% | 🟢 Improved (+0.6%) |
| **Boom Recall** | 7.2% | 7.6% | +0.5% | +0.3% | 🟢 Improved (+0.4%) |
| **Boom Brier Score** | 0.1927 | 0.1911 | -0.0013 | -0.0020 | 🟢 Better calibration |
