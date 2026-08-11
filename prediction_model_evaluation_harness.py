"""
PLL Fantasy Prediction Model Evaluation Harness
------------------------------------------------
This harness acts as an independent, decoupled evaluator and auditor for PLL Fantasy
predictive models and roster optimization algorithms.

It operates by consuming standardized prediction CSVs and roster CSVs, auditing them
against game rules, matching selections against ground truth actual box scores, and
computing accuracy/performance metrics.

Expected Inputs:
----------------
1. Roster File (--rosters <path>):
   A single CSV file containing the selected lineups across evaluated weeks/years:
   Columns:
     - year: Season year (int, e.g. 2025)
     - week: Game week (int, e.g. 1)
     - firstName: Player's first name (str)
     - lastName: Player's last name (str)
     - position: Selected position slot (str: A, M, D, FO, G)
     - salary: Player's F2P salary cost (int)
     - eventId: The specific game ID (str, e.g. 2025_game_1)

2. Prediction Directory (--predictions <dir_path>):
   A folder containing weekly prediction CSVs named `week<W>_<Y>_predictions.csv`:
   Columns:
     - firstName: Player's first name (str)
     - lastName: Player's last name (str)
     - eventId: The specific game ID (str, e.g. 2025_game_1)
     - PredictedPoints: expected value or ceiling forecast (float) [Optional]
     - PredictedTier: predicted tier - Bust, Average, Boom (str) [Optional]
     - BoomProbability: probability of a Boom performance, 0-100 (float) [Optional]

3. Ground Truth Data (Local JSONs):
   Uses `combined_player_stats_YYYY.json` stored in the same directory as this script.
"""

import os
import sys
import json
import argparse
import math
import pandas as pd
import numpy as np
import scipy.stats as stats
import pulp

# ── Roster & Position Definitions ─────────────────────────────────────────────
VALID_POSITIONS = {"A", "M", "D", "FO", "G"}
POSITION_LIMITS = {
    "A": 2,
    "M": 2,
    "D": 1,
    "FO": 1,
    "G": 1
}
BUDGET_LIMIT = 200
LINEUP_SIZE = 7

def clean_name(n):
    """Normalize player names to handle spelling, casing, punctuation, and whitespaces."""
    return (n or "").replace("'", "").replace("-", "").replace(".", "").replace(" ", "").lower()

def clean_event_id(eid):
    """Normalize event ID formats to ensure matching across sources (e.g. 2026_game_1 vs 2026-ev-1)."""
    if not eid:
        return ""
    s = str(eid).lower().strip()
    for delimiter in ["_game_", "_quarterfinal_", "_semifinal_", "_championship_", "-game-", "-quarterfinal-", "-semifinal-", "-championship-", "_ev_", "-ev-"]:
        s = s.replace(delimiter, "ev")
    s = s.replace("_", "-")
    return clean_name(s)

def get_standard_pos(pos):
    """Normalize position codes to standard A, M, D, FO, G."""
    pos = str(pos).upper().strip()
    if pos in {"A", "ATTACK", "ATT"}: return "A"
    if pos in {"M", "MIDFIELD", "MID"}: return "M"
    if pos in {"D", "DEFENSE", "DEF", "SSDM", "LSM"}: return "D"
    if pos in {"FO", "FACEOFF"}: return "FO"
    if pos in {"G", "GOALIE"}: return "G"
    return pos

# ── Ground Truth Statistics Database ──────────────────────────────────────────
class StatsDatabase:
    def __init__(self, script_dir):
        self.script_dir = script_dir
        self.stats_cache = {}  # year -> list of records

    def load_year(self, year):
        if year in self.stats_cache:
            return self.stats_cache[year]

        file_path = os.path.join(self.script_dir, f"combined_player_stats_{year}.json")
        if not os.path.exists(file_path):
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.stats_cache[year] = data
        return data

    def get_actual_points(self, year, week, first, last, event_id=None):
        data = self.load_year(year)
        if not data:
            return None

        c_first, c_last = clean_name(first), clean_name(last)
        
        matches = []
        for p in data:
            if p.get("week") == week:
                ident = p.get("identity", {})
                evt = p.get("event", {})
                if clean_name(ident.get("firstName")) == c_first and clean_name(ident.get("lastName")) == c_last:
                    if event_id is None or clean_event_id(evt.get("eventId")) == clean_event_id(event_id):
                        f2p = p.get("f2p", {})
                        stats_dict = p.get("stats", {})
                        pts = f2p.get("totalPoints")
                        if pts is None:
                            # Recompute using scoring rules if totalPoints missing
                            pts = self._calc_fantasy(stats_dict)
                        matches.append(pts)
        
        if not matches:
            return None
        # Return average or first if multiple matches found (usually should be unique per eventId)
        return matches[0]

    def get_week_players(self, year, week):
        """Returns all player records for a given week (includes actual points and salary)."""
        data = self.load_year(year)
        if not data:
            return []

        players = []
        for p in data:
            if p.get("week") == week:
                ident = p.get("identity", {})
                evt = p.get("event", {})
                f2p = p.get("f2p", {})
                stats_dict = p.get("stats", {})
                is_dnp = p.get("isDNP", False)
                
                # Filter out goalies that didn't play at all if they have no stats
                pos = get_standard_pos(ident.get("position"))
                pts = f2p.get("totalPoints") if f2p.get("totalPoints") is not None else self._calc_fantasy(stats_dict)
                
                if pos == "G" and not is_dnp:
                    saves = stats_dict.get("saves", 0)
                    ga = stats_dict.get("goalsAgainst", 0)
                    if saves == 0 and ga == 0 and pts == 0:
                        continue # Scratched goalie

                players.append({
                    "firstName": ident.get("firstName"),
                    "lastName": ident.get("lastName"),
                    "position": pos,
                    "salary": int(f2p.get("salary", 10)) if f2p.get("salary") is not None else 10,
                    "eventId": evt.get("eventId"),
                    "actualPoints": pts,
                    "isDNP": is_dnp
                })
        return players

    def _calc_fantasy(self, s):
        pts = (s.get("onePointGoals", 0) * 10 + s.get("twoPointGoals", 0) * 20 + s.get("assists", 0) * 10 + s.get("turnovers", 0) * -3 + s.get("goalsAgainst", 0) * -1 + s.get("twoPointGoalsAgainst", 0) * -2 + s.get("faceoffsWon", 0) * 0.8 + (s.get("faceoffs", 0) - s.get("faceoffsWon", 0)) * -0.5 + s.get("groundBalls", 0) + s.get("saves", 0) * 3 + s.get("causedTurnovers", 0) * 10)
        if s.get("onePointGoals", 0) + s.get("twoPointGoals", 0) >= 3: pts += 5
        if s.get("assists", 0) >= 3: pts += 5
        if s.get("causedTurnovers", 0) >= 3: pts += 5
        if s.get("saves", 0) >= 15: pts += 5
        return pts

# ── Roster Auditor & Scorer ──────────────────────────────────────────────────
class RosterEvaluator:
    def __init__(self, stats_db):
        self.stats_db = stats_db

    def audit_and_score(self, df_roster, year, week):
        """Audits weekly roster according to rules and returns actual points scored."""
        week_roster = df_roster[(df_roster["year"] == year) & (df_roster["week"] == week)].copy()
        
        # If baseline file contains all 5 candidate ranks, evaluate rank 1 for Top-1 score
        if "lineup_rank" in week_roster.columns:
            week_roster = week_roster[week_roster["lineup_rank"] == 1].copy()

        if week_roster.empty:
            return None, ["Roster is empty."]

        errors = []
        
        # 1. Size Check
        if len(week_roster) != LINEUP_SIZE:
            errors.append(f"Invalid roster size: got {len(week_roster)} players, expected {LINEUP_SIZE}.")

        # 2. Budget Check
        total_salary = week_roster["salary"].sum()
        if total_salary > BUDGET_LIMIT:
            errors.append(f"Salary budget exceeded: total cost is {total_salary} coins (limit: {BUDGET_LIMIT}).")

        # 3. Position Constraints Check
        week_roster["norm_pos"] = week_roster["position"].apply(get_standard_pos)
        pos_counts = week_roster["norm_pos"].value_counts().to_dict()
        
        for pos, limit in POSITION_LIMITS.items():
            count = pos_counts.get(pos, 0)
            if count != limit:
                errors.append(f"Position slot mismatch for '{pos}': got {count}, expected {limit}.")

        # 4. Duplicate Check
        week_roster["clean_full"] = week_roster.apply(lambda r: clean_name(r["firstName"]) + "_" + clean_name(r["lastName"]), axis=1)
        duplicates = week_roster[week_roster.duplicated(subset=["clean_full"])]["clean_full"].tolist()
        if duplicates:
            errors.append(f"Duplicate player selections detected: {duplicates}.")

        # 5. Score Matching
        total_actual_points = 0.0
        missing_players = []
        
        for _, row in week_roster.iterrows():
            pts = self.stats_db.get_actual_points(
                year, week, row["firstName"], row["lastName"], row.get("eventId")
            )
            if pts is None:
                missing_players.append(f"{row['firstName']} {row['lastName']} (eventId: {row.get('eventId')})")
            else:
                total_actual_points += pts

        if missing_players:
            errors.append(f"Could not find ground truth actual points for players: {missing_players}. Assumed 0 points.")

        return total_actual_points, errors

    def evaluate_top5_pool(self, df_roster, year, week):
        """Evaluates the candidate pool of Top 5 distinct recommended rosters per week.

        Computes Top-1, Top-5 Mean, Top-5 Max, and Top-5 Min scores.
        """
        week_df = df_roster[(df_roster["year"] == year) & (df_roster["week"] == week)].copy()
        if week_df.empty or "lineup_rank" not in week_df.columns:
            return None

        rank_scores = []
        ranks = sorted(week_df["lineup_rank"].unique())
        
        for r in ranks:
            rank_roster = week_df[week_df["lineup_rank"] == r]
            if len(rank_roster) != LINEUP_SIZE:
                continue
            r_pts = 0.0
            for _, row in rank_roster.iterrows():
                pts = self.stats_db.get_actual_points(
                    year, week, row["firstName"], row["lastName"], row.get("eventId")
                )
                r_pts += pts if pts is not None else 0.0
            rank_scores.append(r_pts)

        if not rank_scores:
            return None

        return {
            "top1": rank_scores[0],
            "scores": rank_scores,
            "mean": float(np.mean(rank_scores)),
            "max": float(np.max(rank_scores)),
            "min": float(np.min(rank_scores)),
            "n_ranks": len(rank_scores)
        }

    def compute_vor(self, df_roster, year, week, week_players):
        """Computes Value Over Replacement (VOR) for each selected player.

        VOR = Player Actual FP - Median FP of all players who played at that
        position that week. Measures whether each individual selection decision
        beat the positional baseline, independent of lineup-level luck.
        """
        week_roster = df_roster[(df_roster["year"] == year) & (df_roster["week"] == week)].copy()
        if "lineup_rank" in week_roster.columns:
            week_roster = week_roster[week_roster["lineup_rank"] == 1].copy()

        if week_roster.empty:
            return None

        # Build per-position median FP from all players who actually played
        # (exclude DNPs which scored 0 but weren't real options)
        pos_points = {}  # position -> list of actual FP
        for p in week_players:
            if p.get("isDNP"):
                continue
            pos = p["position"]
            pts = p.get("actualPoints", 0) or 0
            pos_points.setdefault(pos, []).append(pts)

        pos_medians = {}
        for pos, pts_list in pos_points.items():
            pos_medians[pos] = float(np.median(pts_list))

        # Compute VOR for each roster slot
        week_roster["norm_pos"] = week_roster["position"].apply(get_standard_pos)
        player_details = []
        total_vor = 0.0

        for _, row in week_roster.iterrows():
            pos = row["norm_pos"]
            actual = self.stats_db.get_actual_points(
                year, week, row["firstName"], row["lastName"], row.get("eventId")
            )
            if actual is None:
                actual = 0.0

            median_fp = pos_medians.get(pos, 0.0)
            vor = actual - median_fp

            detail = {
                "player": f"{row['firstName']} {row['lastName']}",
                "position": pos,
                "actual": actual,
                "pos_median": median_fp,
                "vor": vor
            }
            player_details.append(detail)
            total_vor += vor

        n_players = len(player_details)
        avg_vor = total_vor / n_players if n_players > 0 else 0.0

        # Aggregate per-position
        per_position = {}
        for d in player_details:
            per_position.setdefault(d["position"], []).append(d)

        return {
            "total_vor": total_vor,
            "avg_vor": avg_vor,
            "per_position": per_position,
            "player_details": player_details
        }

# ── Coulda Optimal Solver ─────────────────────────────────────────────────────
def solve_coulda_optimal(players):
    """Solve the retroactive optimal lineup using integer linear programming (PuLP)."""
    if not players:
        return 0.0, []

    prob = pulp.LpProblem("CouldaRetroactiveOptimizer", pulp.LpMaximize)
    
    # Decisions: 1 if player-game performance is selected, 0 otherwise
    player_vars = []
    for i, p in enumerate(players):
        var = pulp.LpVariable(f"x_{i}", cat=pulp.LpBinary)
        player_vars.append((var, p))
        
    # Objective: Maximize total actual points
    prob += pulp.lpSum(var * p["actualPoints"] for var, p in player_vars)
    
    # Constraint 1: Budget limit
    prob += pulp.lpSum(var * p["salary"] for var, p in player_vars) <= BUDGET_LIMIT
    
    # Constraint 2: Total lineup size
    prob += pulp.lpSum(var for var, _ in player_vars) == LINEUP_SIZE
    
    # Constraint 3: Position limits
    for pos, limit in POSITION_LIMITS.items():
        prob += pulp.lpSum(var for var, p in player_vars if p["position"] == pos) == limit
        
    # Constraint 4: Unique player constraint (cannot select same player twice in different events)
    player_map = {}
    for var, p in player_vars:
        key = clean_name(p["firstName"]) + "_" + clean_name(p["lastName"])
        player_map.setdefault(key, []).append(var)
        
    for name, vars_list in player_map.items():
        prob += pulp.lpSum(vars_list) <= 1

    # Solve quietly
    solver = pulp.PULP_CBC_CMD(msg=False)
    prob.solve(solver)
    
    if pulp.LpStatus[prob.status] != "Optimal":
        return 0.0, []
        
    optimal_score = pulp.value(prob.objective)
    selected_team = [p for var, p in player_vars if pulp.value(var) > 0.5]
    
    return optimal_score, selected_team

# ── Prediction Quality Evaluator ──────────────────────────────────────────────
class PredictionEvaluator:
    def __init__(self, stats_db):
        self.stats_db = stats_db

    def evaluate_week(self, pred_csv_path, year, week):
        if not os.path.exists(pred_csv_path):
            return None

        df_pred = pd.read_csv(pred_csv_path)
        actuals = self.stats_db.get_week_players(year, week)
        if not actuals or df_pred.empty:
            return None

        # Build actuals map for matching
        actuals_map = {}
        for a in actuals:
            key = (clean_name(a["firstName"]), clean_name(a["lastName"]), clean_event_id(a["eventId"]))
            actuals_map[key] = a

        # Merge predictions with actuals
        merged_rows = []
        for _, row in df_pred.iterrows():
            eid = row.get("eventId") or row.get("game_id")
            if not eid:
                continue
            key = (clean_name(row["firstName"]), clean_name(row["lastName"]), clean_event_id(eid))
            if key in actuals_map:
                merged_rows.append({
                    **row.to_dict(),
                    "actualPoints": actuals_map[key]["actualPoints"],
                    "positionGroup": actuals_map[key]["position"],
                    "isDNP": actuals_map[key]["isDNP"]
                })

        if not merged_rows:
            return None

        df_eval = pd.DataFrame(merged_rows)
        # Exclude DNPs for accuracy evaluations
        df_eval = df_eval[df_eval["isDNP"] != True].copy()

        metrics = {}

        # 1. Regression Metrics (MAE, RMSE, R2, Correlation)
        if "PredictedPoints" in df_eval.columns:
            y_true = df_eval["actualPoints"]
            y_pred = df_eval["PredictedPoints"]
            
            mae = np.mean(np.abs(y_true - y_pred))
            rmse = np.sqrt(np.mean((y_true - y_pred)**2))
            r2 = 1.0 - (np.sum((y_true - y_pred)**2) / np.sum((y_true - np.mean(y_true))**2)) if np.sum((y_true - np.mean(y_true))**2) > 0 else 0
            corr, _ = stats.pearsonr(y_true, y_pred) if len(y_true) > 1 and np.std(y_pred) > 0 else (0.0, 1.0)
            
            metrics["MAE"] = mae
            metrics["RMSE"] = rmse
            metrics["R_Squared"] = r2
            metrics["Pearson_Correlation"] = corr

            # Spearman Rank Correlation (overall and per-position)
            # Measures rank-ordering accuracy: did we correctly order who
            # would outscore whom? This is what the optimizer needs.
            if len(y_true) > 5 and np.std(y_pred) > 0:
                spearman_rho, _ = stats.spearmanr(y_true, y_pred)
                metrics["Spearman_Correlation"] = spearman_rho

                # Per-position Spearman (minimum 5 players to compute)
                for pos in ["A", "M", "D", "FO", "G"]:
                    df_pos = df_eval[df_eval["positionGroup"] == pos]
                    if len(df_pos) >= 5 and np.std(df_pos["PredictedPoints"]) > 0:
                        pos_rho, _ = stats.spearmanr(df_pos["actualPoints"], df_pos["PredictedPoints"])
                        metrics[f"{pos}_Spearman"] = pos_rho

        # 2. Classification Metrics (Accuracy, Boom Precision/Recall, Brier Score)
        if "BoomProbability" in df_eval.columns or "PredictedTier" in df_eval.columns:
            # Assign Ground Truth Tiers dynamically (matching predicta_accuracy_report rules)
            df_eval["ActualTier"] = df_eval.groupby("positionGroup")["actualPoints"].transform(self._assign_tiers)
            
            if "PredictedTier" in df_eval.columns:
                correct = (df_eval["PredictedTier"].astype(str).str.lower() == df_eval["ActualTier"].astype(str).str.lower())
                metrics["Tier_Accuracy"] = correct.mean()
                
                # Boom metrics
                pred_boom = df_eval["PredictedTier"].astype(str).str.lower() == "boom"
                act_boom = df_eval["ActualTier"].astype(str).str.lower() == "boom"
                
                boom_precision = np.sum(pred_boom & act_boom) / np.sum(pred_boom) if np.sum(pred_boom) > 0 else 0.0
                boom_recall = np.sum(pred_boom & act_boom) / np.sum(act_boom) if np.sum(act_boom) > 0 else 0.0
                
                metrics["Boom_Precision"] = boom_precision
                metrics["Boom_Recall"] = boom_recall

                # Position-specific Boom metrics
                for pos in ["A", "M", "D", "FO", "G"]:
                    df_pos = df_eval[df_eval["positionGroup"] == pos]
                    if df_pos.empty:
                        continue
                    pred_boom_pos = df_pos["PredictedTier"].astype(str).str.lower() == "boom"
                    act_boom_pos = df_pos["ActualTier"].astype(str).str.lower() == "boom"
                    
                    pos_prec = np.sum(pred_boom_pos & act_boom_pos) / np.sum(pred_boom_pos) if np.sum(pred_boom_pos) > 0 else 0.0
                    pos_rec = np.sum(pred_boom_pos & act_boom_pos) / np.sum(act_boom_pos) if np.sum(act_boom_pos) > 0 else 0.0
                    
                    metrics[f"{pos}_Boom_Precision"] = pos_prec
                    metrics[f"{pos}_Boom_Recall"] = pos_rec

            if "BoomProbability" in df_eval.columns:
                # Brier score (mean squared error of predicted boom probability vs binary boom indicator)
                act_boom_binary = (df_eval["ActualTier"].astype(str).str.lower() == "boom").astype(float)
                pred_boom_prob = df_eval["BoomProbability"] / 100.0
                brier = np.mean((pred_boom_prob - act_boom_binary) ** 2)
                metrics["Boom_Brier_Score"] = brier

        return metrics

    def _assign_tiers(self, s):
        if len(s) < 4:
            # Fallback if too few players
            return pd.Series(["Average"] * len(s), index=s.index)
        q25, q75 = s.quantile(0.25), s.quantile(0.75)
        # Handle case where boundaries overlap due to ties on 0 points
        if q25 == q75:
            q75 = q25 + 0.01
        return pd.cut(s, bins=[-np.inf, q25, q75, np.inf], labels=["Bust", "Average", "Boom"])

# ── Logging Database ──────────────────────────────────────────────────────────
class EvaluationLog:
    def __init__(self, log_path):
        self.log_path = log_path

    def load(self):
        if not os.path.exists(self.log_path):
            return {}
        with open(self.log_path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}

    def save(self, data):
        with open(self.log_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def append_run(self, label, year, weeks_data, summary_metrics):
        db = self.load()
        db[label] = {
            "timestamp": pd.Timestamp.now().isoformat(),
            "year": year,
            "weeks": weeks_data,
            "summary": summary_metrics
        }
        self.save(db)
        print(f"Run evaluation successfully logged under label: '{label}'")

# ── Paired t-Test Comparison ──────────────────────────────────────────────────
def compare_runs(log_path, label1, label2):
    if not os.path.exists(log_path):
        print(f"Error: Log file {log_path} not found.")
        return

    with open(log_path, "r", encoding="utf-8") as f:
        db = json.load(f)

    if label1 not in db or label2 not in db:
        print(f"Error: Could not find both labels ('{label1}', '{label2}') in log.")
        return

    run1 = db[label1]
    run2 = db[label2]

    if run1["year"] != run2["year"]:
        print(f"Warning: Comparing different seasons ({run1['year']} vs {run2['year']}).")

    weeks1 = run1["weeks"]
    weeks2 = run2["weeks"]

    # Match weeks
    common_weeks = sorted(list(set(weeks1.keys()).intersection(weeks2.keys())))
    if not common_weeks:
        print("Error: No overlapping weeks to compare.")
        return

    scores1 = [weeks1[w]["actual_score"] for w in common_weeks]
    scores2 = [weeks2[w]["actual_score"] for w in common_weeks]
    coulda_scores = [weeks1[w]["coulda_score"] for w in common_weeks]

    # Calculate t-test
    diffs = np.array(scores2) - np.array(scores1)
    mean_diff = np.mean(diffs)
    
    # Paired t-test requires at least 2 samples
    if len(diffs) >= 2:
        t_stat, p_value = stats.ttest_rel(scores2, scores1)
    else:
        t_stat, p_value = 0.0, 1.0

    print(f"\n{'='*75}")
    print(f" STATISTICAL COMPARISON REPORT")
    print(f" Baseline (Run A): {label1}")
    print(f" Challenger (Run B): {label2}")
    print(f" Evaluated Weeks: {common_weeks}")
    print(f"{'='*75}")
    
    print(f"{'Week':<8} | {'Run A score':<12} | {'Run B score':<12} | {'Difference':<10} | {'Coulda max':<10}")
    print(f"{'-'*75}")
    for i, w in enumerate(common_weeks):
        print(f"Week {w:<3} | {scores1[i]:<12.1f} | {scores2[i]:<12.1f} | {diffs[i]:<+10.1f} | {coulda_scores[i]:<10.1f}")
    print(f"{'-'*75}")
    
    sumA, sumB, sumC = sum(scores1), sum(scores2), sum(coulda_scores)
    print(f"TOTAL    | {sumA:<12.1f} | {sumB:<12.1f} | {sumB-sumA:<+10.1f} | {sumC:<10.1f}")
    print(f"Avg/Week | {np.mean(scores1):<12.1f} | {np.mean(scores2):<12.1f} | {mean_diff:<+10.1f} | {np.mean(coulda_scores):<10.1f}")
    print(f"Ceiling% | {100*sumA/sumC:<11.1f}% | {100*sumB/sumC:<11.1f}% | {100*(sumB-sumA)/sumC:<+9.1f}% | 100.0%")
    print(f"{'='*75}")
    
    print(f"Paired t-test results:")
    print(f"  Mean Point Difference per Week: {mean_diff:+.2f} points")
    print(f"  t-statistic: {t_stat:.4f}")
    print(f"  p-value: {p_value:.4f}")
    
    if p_value < 0.05:
        verdict = "STATISTICALLY SIGNIFICANT"
        if mean_diff > 0:
            verdict += " IMPROVEMENT (Run B is better)"
        else:
            verdict += " DEGRADATION (Run A is better)"
    else:
        verdict = "NO STATISTICALLY SIGNIFICANT DIFFERENCE"
        
    print(f"  Verdict: {verdict}")
    print(f"{'='*75}\n")

# ── Main Script Entry Point ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="PLL Fantasy Prediction & Roster Independent Evaluation Harness")
    parser.add_argument("--rosters", type=str, required=False, help="Path to optimized rosters CSV file.")
    parser.add_argument("--predictions", type=str, required=False, help="Path to predictions directory.")
    parser.add_argument("--year", type=int, default=2025, help="Target year for evaluation (default: 2025).")
    parser.add_argument("--weeks", type=str, default="all", help="Weeks to evaluate, comma separated list or 'all'.")
    parser.add_argument("--label", type=str, default=None, help="Label to log the evaluation results.")
    parser.add_argument("--compare", type=str, default=None, help="Compare two run labels: 'labelA,labelB'.")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(script_dir, "evaluation_runs_log.json")

    # Mode 1: Statistical Comparison
    if args.compare:
        parts = args.compare.split(",")
        if len(parts) != 2:
            print("Error: Compare format must be 'labelA,labelB'.")
            sys.exit(1)
        compare_runs(log_path, parts[0].strip(), parts[1].strip())
        return

    # Mode 2: Roster & Prediction Evaluation
    if not args.rosters:
        print("Error: --rosters path must be specified to run evaluation.")
        parser.print_help()
        sys.exit(1)

    if not os.path.exists(args.rosters):
        print(f"Error: Roster file {args.rosters} not found.")
        sys.exit(1)

    df_roster = pd.read_csv(args.rosters)

    # Initialize components
    stats_db = StatsDatabase(script_dir)
    roster_eval = RosterEvaluator(stats_db)
    pred_eval = PredictionEvaluator(stats_db)

    # Resolve weeks
    if args.weeks.lower() == "all":
        # Load stats for the target year to find all weeks
        data = stats_db.load_year(args.year)
        if not data:
            print(f"Error: No stats data json found for Year {args.year}.")
            sys.exit(1)
        weeks = sorted(list(set(p.get("week") for p in data if p.get("week"))))
    else:
        try:
            weeks = [int(w.strip()) for w in args.weeks.split(",")]
        except ValueError:
            print("Error: --weeks must be a comma-separated list of integers.")
            sys.exit(1)

    print(f"\n{'='*75}")
    print(f" PLL FANTASY EVALUATION HARNESS RUN")
    print(f" Target Season: {args.year} | Weeks: {weeks}")
    print(f" Roster File: {args.rosters}")
    if args.predictions:
        print(f" Predictions Dir: {args.predictions}")
    print(f"{'='*75}")

    weeks_data = {}
    total_score = 0.0
    total_coulda = 0.0
    r_errors_accum = []
    
    # Track classification & regression metric averages
    metrics_history = []
    # Track VOR across all weeks
    all_vor_details = []  # flat list of per-player VOR dicts across all weeks
    weekly_vor_totals = []  # per-week total VOR

    for w in weeks:
        print(f"Evaluating Week {w}...")
        
        # 1. Coulda retro optimum solver
        week_players = stats_db.get_week_players(args.year, w)
        coulda_score, coulda_lineup = solve_coulda_optimal(week_players)
        
        # 2. Roster scoring and auditing
        score, errors = roster_eval.audit_and_score(df_roster, args.year, w)
        
        if score is None:
            print(f"  -> Skipping Week {w}: Roster missing.")
            continue
            
        if errors:
            print(f"  -> Rule Auditing Warnings/Errors for Week {w}:")
            for err in errors:
                print(f"     [WARNING] {err}")
                r_errors_accum.append(f"Week {w}: {err}")

        # 3. Model Accuracy Evaluation (optional)
        pred_metrics = {}
        if args.predictions:
            pred_file = os.path.join(args.predictions, f"week{w}_{args.year}_predictions.csv")
            m = pred_eval.evaluate_week(pred_file, args.year, w)
            if m:
                pred_metrics = m
                metrics_history.append(m)

        # 4. Value Over Replacement (VOR) computation
        vor_result = roster_eval.compute_vor(df_roster, args.year, w, week_players)
        vor_summary = {}
        if vor_result:
            vor_summary = {
                "total_vor": vor_result["total_vor"],
                "avg_vor": vor_result["avg_vor"],
                "per_position": {
                    pos: round(np.mean([d["vor"] for d in details]), 1)
                    for pos, details in vor_result["per_position"].items()
                }
            }
            all_vor_details.extend(vor_result["player_details"])
            weekly_vor_totals.append(vor_result["total_vor"])

        # 5. Top-5 Candidate Roster Pool Evaluation
        top5_result = roster_eval.evaluate_top5_pool(df_roster, args.year, w)
        top5_summary = {}
        if top5_result:
            max_ceil_pct = (top5_result["max"] / coulda_score * 100.0) if coulda_score > 0 else 0.0
            mean_ceil_pct = (top5_result["mean"] / coulda_score * 100.0) if coulda_score > 0 else 0.0
            top5_summary = {
                "top1": top5_result["top1"],
                "mean": top5_result["mean"],
                "max": top5_result["max"],
                "min": top5_result["min"],
                "max_ceil_pct": max_ceil_pct,
                "mean_ceil_pct": mean_ceil_pct
            }

        pct_of_coulda = (score / coulda_score * 100.0) if coulda_score > 0 else 0.0
        vor_str = f" | VOR: {vor_result['total_vor']:+.1f} (avg {vor_result['avg_vor']:+.1f}/slot)" if vor_result else ""
        print(f"  -> Score: {score:.1f} pts | Coulda Optimal: {coulda_score:.1f} pts ({pct_of_coulda:.1f}% of ceiling){vor_str}")
        if top5_summary:
            print(f"     [Top-5 Pool] Top-1: {top5_summary['top1']:.1f} | Mean: {top5_summary['mean']:.1f} | Max: {top5_summary['max']:.1f} ({top5_summary['max_ceil_pct']:.1f}% ceil) | Min: {top5_summary['min']:.1f}")
        
        weeks_data[str(w)] = {
            "actual_score": score,
            "coulda_score": coulda_score,
            "pct_of_ceiling": pct_of_coulda,
            "errors": errors,
            "prediction_metrics": pred_metrics,
            "vor": vor_summary,
            "top5": top5_summary
        }
        
        total_score += score
        total_coulda += coulda_score

    # Aggregate summaries
    print(f"\n{'='*75}")
    print(f" SEASON SUMMARY REPORT ({args.year})")
    print(f"{'='*75}")
    
    # Check if Top-5 data is present across weeks
    has_top5 = any("top5" in wd and wd["top5"] for wd in weeks_data.values())

    total_pct = (total_score / total_coulda * 100.0) if total_coulda > 0 else 0.0

    if has_top5:
        print(f"{'Week':<6} | {'Top-1 Score':<11} | {'Top-5 Mean':<11} | {'Top-5 Max':<11} | {'Coulda Max':<11} | {'Top-5 Max Ceil %':<16} | {'Total VOR':<9}")
        print(f"{'-'*85}")
        for w in sorted(weeks_data.keys(), key=int):
            wd = weeks_data[w]
            t5 = wd.get("top5", {})
            vor_val = wd.get("vor", {}).get("total_vor")
            vor_str = f"{vor_val:+.1f}" if vor_val is not None else "N/A"
            t1_val = t5.get("top1", wd["actual_score"])
            t5_mean = t5.get("mean", 0.0)
            t5_max = t5.get("max", 0.0)
            max_ceil = t5.get("max_ceil_pct", 0.0)
            print(f"W{w:<4} | {t1_val:<11.1f} | {t5_mean:<11.1f} | {t5_max:<11.1f} | {wd['coulda_score']:<11.1f} | {max_ceil:<16.1f}% | {vor_str}")
        print(f"{'-'*85}")
        
        n_wks = len(weeks_data)
        avg_t1 = total_score / n_wks
        avg_t5_mean = sum(wd.get("top5", {}).get("mean", 0.0) for wd in weeks_data.values()) / n_wks
        avg_t5_max = sum(wd.get("top5", {}).get("max", 0.0) for wd in weeks_data.values()) / n_wks
        avg_t5_min = sum(wd.get("top5", {}).get("min", 0.0) for wd in weeks_data.values()) / n_wks
        avg_coulda = total_coulda / n_wks
        avg_max_ceil = (avg_t5_max / avg_coulda * 100.0) if avg_coulda > 0 else 0.0
        avg_t1_ceil = (avg_t1 / avg_coulda * 100.0) if avg_coulda > 0 else 0.0

        print(f"TOTAL  | {total_score:<11.1f} | {avg_t5_mean*n_wks:<11.1f} | {avg_t5_max*n_wks:<11.1f} | {total_coulda:<11.1f} | {avg_max_ceil:<16.1f}% |")
        print(f"AVG/WK | {avg_t1:<11.1f} | {avg_t5_mean:<11.1f} | {avg_t5_max:<11.1f} | {avg_coulda:<11.1f} | {avg_max_ceil:<16.1f}% |")
        print(f" (Top-1 Avg: {avg_t1:.1f} pts/wk ({avg_t1_ceil:.1f}% ceil) | Top-5 Min Avg: {avg_t5_min:.1f} pts/wk)")
        print(f"{'='*85}")
    else:
        print(f"{'Week':<8} | {'Lineup Score':<12} | {'Coulda Ceiling':<15} | {'Ceiling %':<10} | {'Total VOR':<10}")
        print(f"{'-'*75}")
        for w in sorted(weeks_data.keys(), key=int):
            wd = weeks_data[w]
            vor_val = wd.get('vor', {}).get('total_vor')
            vor_str = f"{vor_val:+.1f}" if vor_val is not None else "N/A"
            print(f"Week {w:<3} | {wd['actual_score']:<12.1f} | {wd['coulda_score']:<15.1f} | {wd['pct_of_ceiling']:<9.1f}% | {vor_str}")
        print(f"{'-'*75}")
        
        print(f"TOTAL    | {total_score:<12.1f} | {total_coulda:<15.1f} | {total_pct:<9.1f}% |")
        print(f"Avg/Week | {total_score/len(weeks_data):<12.1f} | {total_coulda/len(weeks_data):<15.1f} | {total_pct:<9.1f}% |")
        print(f"{'='*75}")

    # Output predictions accuracy report if present
    summary_metrics = {
        "total_score": total_score,
        "total_coulda": total_coulda,
        "pct_of_ceiling": total_pct,
        "num_weeks": len(weeks_data)
    }

    # VOR Season Summary
    if all_vor_details:
        season_avg_vor = np.mean([d["vor"] for d in all_vor_details])
        season_total_vor = sum(weekly_vor_totals)
        season_avg_weekly_vor = np.mean(weekly_vor_totals) if weekly_vor_totals else 0.0
        n_positive = sum(1 for d in all_vor_details if d["vor"] > 0)
        n_total = len(all_vor_details)
        pct_above_replacement = 100.0 * n_positive / n_total if n_total > 0 else 0.0

        print(f"\nValue Over Replacement (VOR) Summary ({n_total} player-slot decisions):")
        print(f"  Season Avg VOR/Slot:    {season_avg_vor:+.1f} pts")
        print(f"  Season Avg VOR/Week:    {season_avg_weekly_vor:+.1f} pts")
        print(f"  Slots Above Median:     {n_positive}/{n_total} ({pct_above_replacement:.1f}%)")

        # Per-position VOR breakdown
        pos_vor = {}
        for d in all_vor_details:
            pos_vor.setdefault(d["position"], []).append(d["vor"])
        print(f"  Per-Position Avg VOR:")
        for pos in ["A", "M", "D", "FO", "G"]:
            if pos in pos_vor:
                vals = pos_vor[pos]
                pos_above = sum(1 for v in vals if v > 0)
                print(f"    {pos:<3}: {np.mean(vals):+6.1f} pts/slot  ({pos_above}/{len(vals)} above median)")

        summary_metrics["vor_avg_per_slot"] = season_avg_vor
        summary_metrics["vor_avg_per_week"] = season_avg_weekly_vor
        summary_metrics["vor_pct_above_replacement"] = pct_above_replacement
        summary_metrics["vor_total_decisions"] = n_total

    if metrics_history:
        print("\nPrediction Quality Metrics (Averaged across evaluated weeks):")
        avg_metrics = {}
        for k in metrics_history[0].keys():
            avg_metrics[k] = np.mean([m[k] for m in metrics_history if k in m])
            print(f"  - {k:<25}: {avg_metrics[k]:.4f}")
            summary_metrics[f"avg_{k}"] = avg_metrics[k]

    if r_errors_accum:
        print(f"\nCompiled Roster Rule Auditing Anomalies ({len(r_errors_accum)}):")
        for err in r_errors_accum[:10]:
            print(f"  - {err}")
        if len(r_errors_accum) > 10:
            print("  - ... list truncated")

    # Logging to runs database
    if args.label:
        eval_log = EvaluationLog(log_path)
        eval_log.append_run(args.label, args.year, weeks_data, summary_metrics)

if __name__ == "__main__":
    main()
