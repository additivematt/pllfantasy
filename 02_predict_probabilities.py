import json
import os
import pandas as pd
import numpy as np
import re
import argparse
from datetime import datetime, timezone
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SHAP_AVAILABLE = False
try:
    import shap
    SHAP_AVAILABLE = True
except Exception as e:
    print(f"Warning: SHAP library not available or failed to load. SHAP plots will be skipped. Error: {e}")

from xgboost import XGBClassifier, XGBRegressor
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import KFold, TimeSeriesSplit
from utils import assign_position_group, assign_sub_position, calc_fantasy, clean_name
import config
from config import GAME_PACE_ENABLED, DATA_LEAKAGE_FIX_ENABLED, EWMA_ENABLED, SALARY_AS_FEATURE, SALARY_AS_FEATURE_POSITIONS, USAGE_HEALTH_FEATURES_ENABLED, FACEOFF_HEURISTIC_ENABLED
from feature_engineering import (
    TEAM_NAME_TO_ID,
    FEATURE_LISTS,
    load_stats_json,
    load_all_players_stats,
    parse_schedule,
    add_rolling_features,
    load_all_matchups,
    compute_defender_ratings,
    add_matchup_ratings,
    assign_tiers_expanding,
    filter_played_only,
    get_historical_average_salary,
    compute_game_pace_features
)

def quantile_obj(y_true, y_pred, sample_weight=None):
    alpha = 0.9
    errors = y_true - y_pred
    grad = np.where(errors >= 0, -alpha, 1.0 - alpha)
    hess = np.ones_like(y_true)
    if sample_weight is not None:
        grad = grad * sample_weight
        hess = hess * sample_weight
    return grad, hess


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--week", type=int, required=True)
    # Game pace toggle: defaults to config.GAME_PACE_ENABLED, overridable via CLI
    pace_group = p.add_mutually_exclusive_group()
    pace_group.add_argument("--pace-scale", action="store_true", default=None, help="Enable game pace scaling of GBDT features")
    pace_group.add_argument("--no-pace-scale", action="store_true", default=None, help="Disable game pace scaling of GBDT features")
    p.add_argument("--boom-weight", type=float, default=2.0, help="Asymmetric sample weight for 'Boom' class in classifier training")
    p.add_argument("--hyperparams-file", type=str, default=None, help="Path to JSON file containing position-specific XGBoost hyperparameters")
    p.add_argument("--recency-weight", type=float, default=getattr(config, "RECENCY_WEIGHT_DEFAULT", 0.3), help="Recency sample weight factor for training samples")
    args = p.parse_args()
    # Resolve pace scaling: CLI overrides config toggle
    if args.pace_scale:
        args.use_pace_scale = True
    elif args.no_pace_scale:
        args.use_pace_scale = False
    else:
        args.use_pace_scale = GAME_PACE_ENABLED
    sDir = os.path.dirname(__file__)
    matchups, _ = parse_schedule(os.path.join(sDir, "pll-schedule.ics"), args.year, args.week)
    
    # Fallback to combined_player_stats for historical schedule if ICS doesn't cover this year
    if not matchups:
        combP = os.path.join(sDir, f"combined_player_stats_{args.year}.json")
        if os.path.exists(combP):
            with open(combP, encoding="utf-8") as f: comb_d = json.load(f)
            week_games = {}
            for p in comb_d:
                if p.get("week") == args.week:
                    evt = p.get("event", {})
                    g_id = evt.get("eventId")
                    if g_id and g_id not in week_games:
                        week_games[g_id] = {"team_a": evt.get("homeTeam"), "team_b": evt.get("awayTeam"), "game_id": g_id.replace("_game_", "-ev-")}
            matchups = list(week_games.values())
            
    if not matchups: return
    # Load from consolidated all_players_stats.json (includes DNP rows, leakage-safe)
    all_stats_path = os.path.join(sDir, "all_players_stats.json")
    if os.path.exists(all_stats_path):
        df_all = load_all_players_stats(all_stats_path, args.year, args.week)
    else:
        # Fallback to per-year files if all_players_stats.json missing
        df_all = pd.concat([load_stats_json(os.path.join(sDir, f"combined_player_stats_{yr}.json")) for yr in range(2023, args.year + 1) if os.path.exists(os.path.join(sDir, f"combined_player_stats_{yr}.json"))], ignore_index=True)
        df_all = df_all[~((df_all["year"] == args.year) & (df_all["week"] >= args.week))]
    
    # Filter training pool to years >= 2023 for clean Baseline 10 standard
    df_all = df_all[df_all["year"] >= 2023].copy()
    stat_cols = ["shots", "groundBalls", "saves", "faceoffsWon", "assists", "causedTurnovers", "touches", "goalsAgainst"]
    for c in stat_cols:
        if c in df_all.columns:
            df_all[c] = df_all[c].fillna(0)

    # Compute rolling game pace features
    df_all, test_pace_map, test_expected_goals, league_avg_pace, global_avg_goals = compute_game_pace_features(
        df_all, matchups, args.year, args.week
    )

    df_all = add_rolling_features(df_all)
    m_by_g = load_all_matchups(sDir)
    df_all, def_r, team_def, pair_r, pvst_r = add_matchup_ratings(df_all, m_by_g, DATA_LEAKAGE_FIX_ENABLED)

    if os.environ.get("RANDOM_NOISE_CONTROL_ENABLED") == "True":
        np.random.seed(42)
        for nf in ["random_noise_1", "random_noise_2", "random_noise_3", "random_noise_4"]:
            df_all[nf] = np.random.randn(len(df_all))

    def get_feats(row, gml=None):
        pN = f"{row['firstName']} {row['lastName']}"
        gID = row.get("eventId") or row.get("game_id")
        ms = gml or m_by_g.get(gID, {}).get("matchups", [])
        pR, iR = 1.0, 1.0
        for m in ms:
            opp = m["playerB"] if m["playerA"] == pN else (m["playerA"] if m["playerB"] == pN else None)
            if opp: pR, iR = pair_r.get((pN, opp), 1.0), def_r.get(opp, 1.0); break
        pvst = pvst_r.get(((row["firstName"], row["lastName"]), row["opponent"]), 1.0)
        # Look up team_def by subPosition (SSDM vs Defensemen) for granular opposition ratings
        sub_pos = row.get("subPosition", row["positionGroup"])
        return pd.Series([pR, iR, pvst, team_def.get((row["opponent"], sub_pos), 1.0)])

    if not df_all.empty:
        # Scale matchup ratings by game pace (Option C) — gated by config.GAME_PACE_ENABLED
        if args.use_pace_scale:
            for col in ["pairing_rating", "opponent_rating", "player_vs_team_rating", "team_def_rating"]:
                df_all[col] = df_all[col] * df_all["game_pace"]
    else:
        df_all["pairing_rating"], df_all["opponent_rating"], df_all["player_vs_team_rating"], df_all["team_def_rating"] = 1.0, 1.0, 1.0, 1.0

    def calc_player_avgs(grp):
        is_goalie = (grp["positionGroup"] == "Goalie")
        saves = grp["saves"] if "saves" in grp.columns else 0
        ga = grp["goalsAgainst"] if "goalsAgainst" in grp.columns else 0
        fp = grp["TotalFantasyPoints"] if "TotalFantasyPoints" in grp.columns else 0
        goalie_played = (saves > 0) | (ga > 0) | (fp > 0)
        grp_active = grp[(grp["isDNP"] != True) & (~is_goalie | goalie_played)]
        use_grp = grp_active if not grp_active.empty else grp
        res = {
            "fp_season_avg": use_grp["TotalFantasyPoints"].mean(),
            "fp_last3_avg": use_grp["TotalFantasyPoints"].tail(3).mean(),
            "fp_last5_avg": use_grp["TotalFantasyPoints"].tail(5).mean(),
            "fp_last10_avg": use_grp["TotalFantasyPoints"].tail(10).mean(),
            "fp_last15_avg": use_grp["TotalFantasyPoints"].tail(15).mean(),
            "n_games_played": len(grp_active) if not grp_active.empty else 0,
            "fp_lag1": use_grp["TotalFantasyPoints"].iloc[-1] if not use_grp.empty else 0,
        }
        if EWMA_ENABLED:
            res["fp_ewma_4"] = use_grp["TotalFantasyPoints"].ewm(halflife=4, min_periods=1).mean().iloc[-1] if not use_grp.empty else 0.0
        cols_to_avg = ["shots", "groundBalls", "saves", "faceoffsWon", "assists", "causedTurnovers", "faceoffPct", "touches", "shotPct", "assistOpportunities", "shotsOnGoal", "shotsOnGoalPct", "turnovers", "twoPointGoals"]
        for c in cols_to_avg:
            if c in use_grp.columns:
                res[f"{c}_season_avg"] = use_grp[c].mean()
                res[f"{c}_last3_avg"] = use_grp[c].tail(3).mean()
            else:
                res[f"{c}_season_avg"] = 0.0
                res[f"{c}_last3_avg"] = 0.0
        res["last_startTime"] = use_grp["startTime"].iloc[-1] if "startTime" in use_grp.columns and not use_grp.empty else 0
        return pd.Series(res)

    p_avgs = df_all.groupby(["firstName", "lastName", "positionGroup"]).apply(calc_player_avgs).reset_index()
    p_avgs["shotPct_anomaly"] = p_avgs["shotPct_last3_avg"] - p_avgs["shotPct_season_avg"]
    p_avgs["turnover_rate_per_touch"] = (p_avgs["turnovers_season_avg"] / (p_avgs["touches_season_avg"] + 1e-5)).fillna(0.0)
    p_avgs["sog_rate_per_touch"] = (p_avgs["shotsOnGoal_season_avg"] / (p_avgs["touches_season_avg"] + 1e-5)).fillna(0.0)
    p_avgs["assist_opp_rate_per_touch"] = (p_avgs["assistOpportunities_season_avg"] / (p_avgs["touches_season_avg"] + 1e-5)).fillna(0.0)

    # Filter to active games only for fallbacks
    df_active_only = df_all[df_all["isDNP"] != True]

    # Calculate season-to-date average for each player in the target season
    std_df = df_active_only[df_active_only["year"] == args.year]
    if not std_df.empty:
        std_avgs = std_df.groupby(["firstName", "lastName"])["TotalFantasyPoints"].mean().to_dict()
    else:
        std_avgs = {}
        
    # Calculate overall historical average as secondary fallback
    overall_avgs = df_active_only.groupby(["firstName", "lastName"])["TotalFantasyPoints"].mean().to_dict()

    def get_historical_average_salary(first, last, current_year, s_dir):
        sals = []
        for yr in range(current_year - 1, 2023, -1):
            path = os.path.join(s_dir, f"combined_player_stats_{yr}.json")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f_yr:
                    data_yr = json.load(f_yr)
                for p_yr in data_yr:
                    ident_yr = p_yr.get("identity", {})
                    if ident_yr.get("firstName") == first and ident_yr.get("lastName") == last:
                        sal_yr = p_yr.get("f2p", {}).get("salary", 0)
                        if sal_yr and sal_yr > 0:
                            sals.append(sal_yr)
                if sals:
                    break
        return sum(sals) / len(sals) if sals else None

    avg_salaries = {}
    is_placeholder = False

    combP = os.path.join(sDir, f"combined_player_stats_{args.year}.json")
    has_combined_week_data = False
    if os.path.exists(combP):
        with open(combP, encoding="utf-8") as f: comb_d = json.load(f)
        fallback_data = [p for p in comb_d if p.get("week") == args.week]
        if len(fallback_data) > 0:
            has_combined_week_data = True
            
    if has_combined_week_data:
        salary_history = {}
        for p in comb_d:
            w = p.get("week", 1)
            if w < args.week:
                ident = p.get("identity", {})
                first = ident.get("firstName")
                last = ident.get("lastName")
                sal = p.get("f2p", {}).get("salary", 0)
                if sal and sal > 0:
                    key = (first, last)
                    if key not in salary_history:
                        salary_history[key] = []
                    salary_history[key].append(sal)
        avg_salaries = {k: sum(v)/len(v) for k, v in salary_history.items() if v}
        
        target_salaries = [p.get("f2p", {}).get("salary", 0) for p in fallback_data]
        if target_salaries and len(set(target_salaries)) <= 1:
            is_placeholder = True

        # Load F2P data to check for injured reserve (IR) and out (O) players
        injured_keys = set()
        clean_name_local = lambda n: (n or "").replace("'", "").replace("-", "").replace(".", "").replace(" ", "").lower()
        f2p_paths = [
            os.path.join(sDir, f"f2p_{args.year}_season.json"),
            os.path.join(sDir, "f2p_weekly_data.json")
        ]
        f2p_data_local = []
        for path in f2p_paths:
            if os.path.exists(path):
                try:
                    with open(path, encoding="utf-8") as f_f2p:
                        f2p_data_local = json.load(f_f2p)
                    break
                except Exception as e:
                    print(f"Error loading {path}: {e}")
                    
        for p in f2p_data_local:
            if p.get("week") == args.week:
                injury_status = p.get("injuryStatus")
                if injury_status in ("IR", "O"):
                    if p.get("officialId"):
                        injured_keys.add(p.get("officialId"))
                    first_clean = clean_name_local(p.get("firstName"))
                    last_clean = clean_name_local(p.get("lastName"))
                    injured_keys.add((first_clean, last_clean))

        roster_rows = []
        for p in fallback_data:
            ident = p.get("identity", {})
            f2p = p.get("f2p", {})
            first = ident.get("firstName")
            last = ident.get("lastName")
            off_id = ident.get("officialId")
            
            # Filter out injured reserve (IR) and out (O) players (disabled to allow gameday roster filtering)
            # if off_id in injured_keys or (clean_name_local(first), clean_name_local(last)) in injured_keys:
            #     print(f"  Skipping injured/out player (fallback_data): {first} {last}")
            #     continue
                
            salary = f2p.get("salary", 0)
            
            if not salary or salary == 0 or is_placeholder or (args.year == 2025 and args.week in [12, 13, 14]):
                avg_sal = avg_salaries.get((first, last))
                if avg_sal and avg_sal > 0:
                    salary = int(round(avg_sal))
                else:
                    hist_avg_sal = get_historical_average_salary(first, last, args.year, sDir)
                    if hist_avg_sal:
                        salary = int(round(hist_avg_sal))
                    else:
                        salary = 15
                    
            roster_rows.append({
                "firstName": first,
                "lastName": last,
                "team": ident.get("team"),
                "positionGroup": assign_position_group(ident.get("position")),
                "subPosition": assign_sub_position(ident.get("position")),
                "officialId": ident.get("officialId", "00000"),
                "salary": salary,
                "eventId": p.get("event", {}).get("eventId")
            })
        roster = pd.DataFrame(roster_rows).drop_duplicates(subset=["firstName", "lastName", "team", "eventId"])
    else:
        f2pP = os.path.join(sDir, f"f2p_{args.year}_season.json")
        if os.path.exists(f2pP):
            with open(f2pP, encoding="utf-8") as f: f2d = json.load(f)
            
            salary_history = {}
            for p in f2d:
                w = p.get("week", 1)
                if w < args.week:
                    first = p.get("firstName")
                    last = p.get("lastName")
                    sal = p.get("salary", 0)
                    if sal and sal > 0:
                        key = (first, last)
                        if key not in salary_history:
                            salary_history[key] = []
                        salary_history[key].append(sal)
            avg_salaries = {k: sum(v)/len(v) for k, v in salary_history.items() if v}
            
            target_week_data = [p for p in f2d if p.get("week") == args.week]
            target_salaries = [p.get("salary", 0) for p in target_week_data]
            if target_salaries and len(set(target_salaries)) <= 1:
                is_placeholder = True

            roster_rows = []
            for p in f2d:
                if p.get("week") == args.week:
                    event_id = p.get("eventId") or ""
                    if "allstar" in event_id.replace("-", "").replace("_", "").lower():
                        continue
                    first = p.get("firstName")
                    last = p.get("lastName")
                    
                    # Filter out injured reserve (IR) and out (O) players (disabled to allow gameday roster filtering)
                    # injury_status = p.get("injuryStatus")
                    # if injury_status in ("IR", "O"):
                    #     print(f"  Skipping injured/out player (f2d): {first} {last} (Status: {injury_status})")
                    #     continue
                        
                    salary = p.get("salary", 0)
                    if not salary or salary == 0 or is_placeholder:
                        avg_sal = avg_salaries.get((first, last))
                        if avg_sal and avg_sal > 0:
                            salary = int(round(avg_sal))
                        else:
                            hist_avg_sal = get_historical_average_salary(first, last, args.year, sDir)
                            if hist_avg_sal:
                                salary = int(round(hist_avg_sal))
                            else:
                                std_avg = std_avgs.get((first, last), 0)
                                if std_avg > 0:
                                    salary = int(round(std_avg))
                                else:
                                    overall_avg = overall_avgs.get((first, last), 0)
                                    salary = int(round(overall_avg)) if overall_avg > 0 else 10
                    roster_rows.append({
                        "firstName": first,
                        "lastName": last,
                        "team": p["currentTeam"]["teamId"],
                        "positionGroup": assign_position_group(p["position"]),
                        "subPosition": assign_sub_position(p["position"]),
                        "officialId": p.get("officialId", "00000"),
                        "salary": salary,
                        "eventId": p.get("eventId")
                    })
            roster = pd.DataFrame(roster_rows).drop_duplicates(subset=["firstName", "lastName", "team", "eventId"])
        else:
            print(f"Error: Neither {combP} nor {f2pP} found.")
            return

    if roster.empty or "team" not in roster.columns:
        print(f"Error: No roster or player data available for {args.year} Week {args.week}.")
        return

    team_current_foPct = df_all.groupby("team")[["faceoffsWon", "faceoffs"]].apply(lambda x: x["faceoffsWon"].sum() / max(1, x["faceoffs"].sum())).to_dict()
    
    gameday_path = os.path.join(sDir, f"gameday_rosters_week{args.week}.json")
    api_roster_by_team = {}  # team_id -> list of player dicts
    if os.path.exists(gameday_path):
        with open(gameday_path, encoding="utf-8") as f: gr = json.load(f)
        for ev in gr.get("data", {}).get("items", []):
            for side in ["homeTeam", "awayTeam"]:
                t = ev.get(side) or {}
                tid = t.get("officialId")
                if tid:
                    api_roster_by_team.setdefault(tid, []).extend(t.get("gamedayRoster") or [])
    else:
        # Backtest fallback: load actual active/DNP status from all_players_stats.json
        stats_path = os.path.join(sDir, "all_players_stats.json")
        if os.path.exists(stats_path):
            import re
            print(f"No live gameday roster found. Simulating rosters from {stats_path} for {args.year} Week {args.week}...")
            with open(stats_path, encoding="utf-8") as f:
                all_stats = json.load(f)
            for slug, p_data in all_stats.items():
                for entry in p_data.get("stats", []):
                    e_id = entry.get("event", {}).get("eventId", "")
                    yr_match = re.search(r'^(\d{4})_', e_id)
                    yr = int(yr_match.group(1)) if yr_match else None
                    if yr == args.year and entry.get("week") == args.week:
                        ident = entry.get("identity", {})
                        tid = ident.get("team")
                        if tid:
                            is_dnp = entry.get("isDNP", False)
                            api_roster_by_team.setdefault(tid, []).append({
                                "firstName": ident.get("firstName") or slug.split("-")[0].capitalize(),
                                "lastName": ident.get("lastName") or slug.split("-")[-1].capitalize(),
                                "rosterStatus": "active" if not is_dnp else "scratched",
                                "position": ident.get("position") or "M"
                            })

    # Build per-team injury metrics using the gameday roster and player seasonal averages
    def compute_test_injury_feats(team_id, opp_id):
        """Returns (vacated_touch_share, inactive_fp_avg, opp_ssdm_health, opp_def_health, opp_goalie_health)"""
        # Team own vacated touch share and inactive fp avg
        t_vacated_touch = 0.0
        t_inactive_fp_sum = 0.0
        t_inactive_count = 0
        t_total_exp_touches = 0.0

        team_roster_players = roster[roster["team"] == team_id]
        gameday_players = api_roster_by_team.get(team_id, [])
        if gameday_players:
            # Build set of active gameday player names for quick lookup
            active_gameday_names = set()
            for gp in gameday_players:
                rs = gp.get("rosterStatus", "active")
                is_inj = gp.get("injuryStatus") in ("O", "IR")
                if rs in ("active", "starter") and not is_inj:
                    fn = clean_name(gp.get("firstName", ""))
                    ln = clean_name(gp.get("lastName", ""))
                    active_gameday_names.add((fn, ln))

            for _, r_row in team_roster_players.iterrows():
                fn = clean_name(r_row["firstName"])
                ln = clean_name(r_row["lastName"])
                # Match to p_avgs for this player
                matched = p_avgs[(p_avgs["firstName"].apply(clean_name) == fn) & (p_avgs["lastName"].apply(clean_name) == ln)]
                if matched.empty:
                    continue
                r = matched.iloc[0]
                exp_touches = float(r.get("touches_season_avg", 0) or 0)
                t_total_exp_touches += exp_touches
                
                # Check if active
                is_active = (fn, ln) in active_gameday_names
                if not is_active:
                    t_vacated_touch += exp_touches
                    fp_avg = float(r.get("fp_season_avg", 0) or 0)
                    t_inactive_fp_sum += fp_avg
                    t_inactive_count += 1

        vts = t_vacated_touch / t_total_exp_touches if t_total_exp_touches > 0 else 0.0
        inact_fp = t_inactive_fp_sum / t_inactive_count if t_inactive_count > 0 else 0.0

        # Opponent defensive health (from opponent gameday roster)
        opp_players = api_roster_by_team.get(opp_id, [])
        active_ssdm, active_def = 0.0, 0.0
        opp_goalie_players = []
        hist_opp = df_all[df_all["team"] == opp_id]

        if USAGE_HEALTH_FEATURES_ENABLED:
            if opp_players:
                for gp in opp_players:
                    rs = gp.get("rosterStatus", "active")
                    is_inj = gp.get("injuryStatus") in ("O", "IR")
                    is_active = rs in ("active", "starter") and not is_inj
                    pos = str(gp.get("position", "")).upper()
                    if pos in ("SSDM", "LSM"):
                        fn = clean_name(gp.get("firstName", ""))
                        ln = clean_name(gp.get("lastName", ""))
                        matched = p_avgs[(p_avgs["firstName"].apply(clean_name) == fn) & (p_avgs["lastName"].apply(clean_name) == ln)]
                        fp_avg = float(matched.iloc[0].get("fp_season_avg", 0) or 0) if not matched.empty else 0.0
                        weight = fp_avg + 1.0
                        if is_active: active_ssdm += weight
                    elif pos == "D":
                        fn = clean_name(gp.get("firstName", ""))
                        ln = clean_name(gp.get("lastName", ""))
                        matched = p_avgs[(p_avgs["firstName"].apply(clean_name) == fn) & (p_avgs["lastName"].apply(clean_name) == ln)]
                        fp_avg = float(matched.iloc[0].get("fp_season_avg", 0) or 0) if not matched.empty else 0.0
                        weight = fp_avg + 1.0
                        if is_active: active_def += weight
                    elif pos == "G":
                        fn = clean_name(gp.get("firstName", ""))
                        ln = clean_name(gp.get("lastName", ""))
                        matched = p_avgs[(p_avgs["firstName"].apply(clean_name) == fn) & (p_avgs["lastName"].apply(clean_name) == ln)]
                        fp_avg = float(matched.iloc[0].get("fp_season_avg", 0) or 0) if not matched.empty else 0.0
                        opp_goalie_players.append({"fp_avg": fp_avg, "is_active": is_active})

            if not hist_opp.empty:
                hist_active_ssdm = hist_opp[(hist_opp["subPosition"] == "SSDM") & (hist_opp["isDNP"] != True)].copy()
                hist_active_ssdm["weight"] = hist_active_ssdm["fp_season_avg"].fillna(0.0) + 1.0
                hist_ssdm_avg = hist_active_ssdm.groupby("eventId")["weight"].sum().mean()

                hist_active_def = hist_opp[(hist_opp["subPosition"] == "Defensemen") & (hist_opp["isDNP"] != True)].copy()
                hist_active_def["weight"] = hist_active_def["fp_season_avg"].fillna(0.0) + 1.0
                hist_def_avg = hist_active_def.groupby("eventId")["weight"].sum().mean()
            else:
                hist_ssdm_avg, hist_def_avg = None, None
        else:
            if opp_players:
                for gp in opp_players:
                    rs = gp.get("rosterStatus", "active")
                    is_inj = gp.get("injuryStatus") in ("O", "IR")
                    is_active = rs in ("active", "starter") and not is_inj
                    pos = str(gp.get("position", "")).upper()
                    if pos in ("SSDM", "LSM") and is_active: active_ssdm += 1
                    if pos == "D" and is_active: active_def += 1
                    if pos == "G":
                        fn = clean_name(gp.get("firstName", ""))
                        ln = clean_name(gp.get("lastName", ""))
                        matched = p_avgs[(p_avgs["firstName"].apply(clean_name) == fn) & (p_avgs["lastName"].apply(clean_name) == ln)]
                        fp_avg = float(matched.iloc[0].get("fp_season_avg", 0) or 0) if not matched.empty else 0.0
                        opp_goalie_players.append({"fp_avg": fp_avg, "is_active": is_active})

            hist_opp_active = hist_opp[hist_opp["isDNP"] != True] if not hist_opp.empty else pd.DataFrame()
            hist_ssdm_avg = hist_opp_active[hist_opp_active["subPosition"] == "SSDM"].groupby("eventId").size().mean() if not hist_opp_active.empty else None
            hist_def_avg = hist_opp_active[hist_opp_active["subPosition"] == "Defensemen"].groupby("eventId").size().mean() if not hist_opp_active.empty else None

        opp_ssdm_h = min(1.0, active_ssdm / hist_ssdm_avg) if (hist_ssdm_avg and hist_ssdm_avg > 0 and opp_players) else 1.0
        opp_def_h = min(1.0, active_def / hist_def_avg) if (hist_def_avg and hist_def_avg > 0 and opp_players) else 1.0

        # Goalie health: is the highest-avg goalie active?
        opp_goalie_h = 1.0
        if opp_goalie_players:
            best = max(opp_goalie_players, key=lambda x: x["fp_avg"])
            opp_goalie_h = 1.0 if best["is_active"] else 0.0

        return vts, inact_fp, opp_ssdm_h, opp_def_h, opp_goalie_h

    def match_game_ids(id1, id2):
        if not id1 or not id2:
            return False
        def clean(s):
            return s.replace("_game_", "_").replace("-ev-", "_").replace("-", "_").lower()
        return clean(id1) == clean(id2)

    test_rows = []
    for m in matchups:
        for t, opp in [(m["team_a"], m["team_b"]), (m["team_b"], m["team_a"])]:
            t_roster = roster[roster["team"] == t]
            if t_roster.empty:
                continue
            if "eventId" in t_roster.columns:
                t_roster = t_roster[t_roster["eventId"].apply(lambda eid: not eid or match_game_ids(eid, m["game_id"]))]
            if t_roster.empty:
                continue
            t_df = t_roster.merge(p_avgs, on=["firstName", "lastName", "positionGroup"], how="left")
            if t_df.empty: continue
            t_df["opponent"], t_df["game_id"] = opp, m["game_id"]
            if "last_startTime" in t_df.columns and m.get("startTime"):
                t_df["days_since_last_game"] = (m["startTime"] - t_df["last_startTime"]) / 86400.0
                t_df["days_since_last_game"] = t_df["days_since_last_game"].fillna(7.0)
            else:
                t_df["days_since_last_game"] = 7.0
            
            t_df["team_faceoff_advantage"] = team_current_foPct.get(t, 0.5) - team_current_foPct.get(opp, 0.5)
            
            # Compute injury/roster features for this matchup
            vts, inact_fp, opp_ssdm_h, opp_def_h, opp_goalie_h = compute_test_injury_feats(t, opp)
            t_df["team_vacated_touch_share"] = vts
            t_df["team_inactive_fp_avg"] = inact_fp
            t_df["opp_ssdm_health"] = opp_ssdm_h
            t_df["opp_def_health"] = opp_def_h
            t_df["opp_goalie_health"] = opp_goalie_h
            
            tm = t_df.apply(lambda r: get_feats(r, m_by_g.get(m["game_id"], {}).get("matchups", [])), axis=1, result_type='expand')
            t_df["pairing_rating"], t_df["opponent_rating"], t_df["player_vs_team_rating"], t_df["team_def_rating"] = tm[0], tm[1], tm[2], tm[3]
            test_rows.append(t_df)
    
    if not test_rows:
        print("[ERROR] No test rows generated.")
        return df_all, pd.DataFrame()
        
    df_test = pd.concat(test_rows, ignore_index=True)
    if os.environ.get("RANDOM_NOISE_CONTROL_ENABLED") == "True":
        np.random.seed(42 + args.year * 100 + args.week)
        for nf in ["random_noise_1", "random_noise_2", "random_noise_3", "random_noise_4"]:
            df_test[nf] = np.random.randn(len(df_test))
    matchup_cols = ["pairing_rating", "opponent_rating", "player_vs_team_rating", "team_def_rating", "team_faceoff_advantage"]
    for mc in matchup_cols:
        if mc in df_test.columns:
            df_test[mc] = df_test[mc].fillna(1.0)
    df_test = df_test.fillna(0.0)
    
    # Feature Engineering Injectiongs by game pace (Option C) — gated by config.GAME_PACE_ENABLED
    df_test["expected_pace"] = df_test["game_id"].map(test_pace_map).fillna(24.0)
    df_test["game_pace"] = df_test["expected_pace"] / league_avg_pace
    if args.use_pace_scale:
        for col in ["pairing_rating", "opponent_rating", "player_vs_team_rating", "team_def_rating"]:
            df_test[col] = df_test[col] * df_test["game_pace"]

    # Dynamic salary features injection
    if SALARY_AS_FEATURE:
        print("[INFO] Salary as a feature is ENABLED.")
        for pg, feats in FEATURE_LISTS.items():
            if SALARY_AS_FEATURE_POSITIONS.get(pg, True):
                if "salary_normalized" not in feats:
                    feats.append("salary_normalized")
                if "salary_percentile" not in feats:
                    feats.append("salary_percentile")
                print(f"  Position: {pg} -> features: {feats}")

        # Compute salary features on df_all (training pool)
        df_all["salary"] = pd.to_numeric(df_all["salary"], errors="coerce")
        pre_2023_mask = df_all["year"] < 2023
        synth_salaries = (df_all["fp_season_avg"].fillna(0.0) * 1.3333) + 1.3333
        synth_salaries = synth_salaries.clip(10.0, 50.0)
        df_all.loc[pre_2023_mask, "salary"] = df_all.loc[pre_2023_mask, "salary"].fillna(synth_salaries)
        df_all["salary"] = df_all["salary"].fillna(10.0)
        df_all["salary_normalized"] = df_all["salary"] / 50.0
        # Percentile rank within (year, week, positionGroup)
        df_all["salary_percentile"] = df_all.groupby(["year", "week", "positionGroup"])["salary"].rank(pct=True).fillna(0.5)

        # Compute salary features on df_test (test pool)
        df_test["salary"] = pd.to_numeric(df_test["salary"], errors="coerce").fillna(10.0)
        df_test["salary_normalized"] = df_test["salary"] / 50.0
        # Percentile rank within positionGroup for the current week
        df_test["salary_percentile"] = df_test.groupby("positionGroup")["salary"].rank(pct=True).fillna(0.5)

    # Dynamic usage and health features injection
    if USAGE_HEALTH_FEATURES_ENABLED:
        print("[INFO] Usage & Health Features (Item 10) are ENABLED.")
        for pg in ["Attack", "Midfield"]:
            if "touches_anomaly" not in FEATURE_LISTS[pg]:
                FEATURE_LISTS[pg].append("touches_anomaly")
                print(f"  Position: {pg} -> injected features: {FEATURE_LISTS[pg]}")
        # Compute touches_anomaly on df_test
        df_test["touches_anomaly"] = (df_test["touches_last3_avg"] - df_test["touches_season_avg"]).fillna(0.0)

    df_train = df_all.dropna(subset=["TotalFantasyPoints"]).copy()
    df_train = filter_played_only(df_train)
    df_train = df_train.sort_values("startTime")
    df_train["PerformanceTier"] = df_train.groupby("positionGroup")["TotalFantasyPoints"].transform(assign_tiers_expanding)
    
    importance_data = {}
    shap_data = {}
    preds_out = []
    for pg, feats in FEATURE_LISTS.items():
        # Ensure all requested features exist in df_train and df_test
        for f in feats:
            if f not in df_train.columns:
                df_train[f] = 0.0
            if f not in df_test.columns:
                df_test[f] = 0.0
                
        df_pg = df_train[df_train["positionGroup"] == pg].dropna(subset=feats + ["PerformanceTier"]).copy()
        df_pg = df_pg.sort_values("startTime").copy()
        tp = df_test[df_test["positionGroup"] == pg].copy()
        if len(df_pg) < 15 or tp.empty: continue
        
        if pg == "Faceoff" and FACEOFF_HEURISTIC_ENABLED:
            print("  [INFO] Running Faceoff Bradley-Terry & Generative Heuristic instead of GBDT...")
            
            # A. Fit Bradley-Terry Model on df_train
            df_train_fo = df_train[(df_train["positionGroup"] == "Faceoff") & (df_train["faceoffs"] > 0)].copy()
            
            matchup_dataset = []
            for g_id, g_df in df_train_fo.groupby("eventId"):
                teams = g_df["team"].dropna().unique()
                if len(teams) >= 2:
                    t1, t2 = teams[0], teams[1]
                    p1_rows = g_df[g_df["team"] == t1].sort_values(by="faceoffs", ascending=False)
                    p2_rows = g_df[g_df["team"] == t2].sort_values(by="faceoffs", ascending=False)
                    if not p1_rows.empty and not p2_rows.empty:
                        p1 = p1_rows.iloc[0]
                        p2 = p2_rows.iloc[0]
                        matchup_dataset.append({
                            "player_a": f"{p1['firstName']} {p1['lastName']}",
                            "player_b": f"{p2['firstName']} {p2['lastName']}",
                            "fow_a": p1["faceoffsWon"],
                            "fow_b": p2["faceoffsWon"]
                        })
            
            fo_players = sorted(list(df_train_fo.apply(lambda r: f"{r['firstName']} {r['lastName']}", axis=1).unique()))
            
            player_ratings = {}
            if fo_players and matchup_dataset:
                player_to_idx = {p: i for i, p in enumerate(fo_players)}
                X_bt = []
                y_bt = []
                w_bt = []
                for m in matchup_dataset:
                    pa = m["player_a"]
                    pb = m["player_b"]
                    wa = m["fow_a"]
                    wb = m["fow_b"]
                    tot = wa + wb
                    if tot == 0: continue
                    
                    x_vec = np.zeros(len(fo_players))
                    x_vec[player_to_idx[pa]] = 1.0
                    x_vec[player_to_idx[pb]] = -1.0
                    
                    X_bt.append(x_vec)
                    y_bt.append(1.0)
                    w_bt.append(wa)
                    
                    X_bt.append(x_vec)
                    y_bt.append(0.0)
                    w_bt.append(wb)
                
                if X_bt:
                    X_bt = np.array(X_bt)
                    y_bt = np.array(y_bt)
                    w_bt = np.array(w_bt)
                    bt_model = LogisticRegression(fit_intercept=False, C=1.0)
                    bt_model.fit(X_bt, y_bt, sample_weight=w_bt)
                    ratings = bt_model.coef_[0]
                    player_ratings = {fo_players[i]: ratings[i] for i in range(len(fo_players))}
            
            # B. Compute player-specific shrunk stats
            df_train_fo_active = df_train_fo[df_train_fo["faceoffs"] > 0]
            
            global_gb_rate = df_train_fo_active["groundBalls"].sum() / max(1, df_train_fo_active["faceoffsWon"].sum())
            global_ct_rate = df_train_fo_active["causedTurnovers"].mean()
            global_a_rate = df_train_fo_active["assists"].mean()
            global_g_rate = df_train_fo_active["goals"].mean()
            
            if pd.isna(global_gb_rate) or global_gb_rate == 0: global_gb_rate = 0.49
            if pd.isna(global_ct_rate) or global_ct_rate == 0: global_ct_rate = 0.26
            if pd.isna(global_a_rate) or global_a_rate == 0: global_a_rate = 0.16
            if pd.isna(global_g_rate) or global_g_rate == 0: global_g_rate = 0.35
            
            player_sums = {}
            for (f_name, l_name), grp in df_train_fo_active.groupby(["firstName", "lastName"]):
                player_sums[(f_name, l_name)] = {
                    "games": len(grp),
                    "faceoffsWon": grp["faceoffsWon"].sum(),
                    "groundBalls": grp["groundBalls"].sum(),
                    "causedTurnovers": grp["causedTurnovers"].sum(),
                    "assists": grp["assists"].sum(),
                    "goals": grp["goals"].sum()
                }
            
            # C. Predict on test week
            test_fo_by_team = {}
            for _, r in tp.iterrows():
                test_fo_by_team.setdefault(r["team"], []).append(f"{r['firstName']} {r['lastName']}")
                
            for _, r in tp.iterrows():
                pN = f"{r['firstName']} {r['lastName']}"
                opp_team = r["opponent"]
                opp_fos = test_fo_by_team.get(opp_team, [])
                opp_pN = opp_fos[0] if opp_fos else None
                
                r_a = player_ratings.get(pN, 0.0)
                r_b = player_ratings.get(opp_pN, 0.0) if opp_pN else 0.0
                
                p_win = 1.0 / (1.0 + np.exp(-(r_a - r_b)))
                
                exp_goals = test_pace_map.get(r["game_id"], 24.0)
                N = 4.0 + exp_goals
                
                fow = N * p_win
                
                p_key = (r["firstName"], r["lastName"])
                p_data = player_sums.get(p_key, {"games": 0, "faceoffsWon": 0, "groundBalls": 0, "causedTurnovers": 0, "assists": 0, "goals": 0})
                
                games = p_data["games"]
                fow_sum = p_data["faceoffsWon"]
                gb_sum = p_data["groundBalls"]
                ct_sum = p_data["causedTurnovers"]
                a_sum = p_data["assists"]
                g_sum = p_data["goals"]
                
                # Shrink ground balls per FOW (K=20 faceoffs won prior)
                if fow_sum > 0:
                    gb_per_fow = gb_sum / fow_sum
                    gb_rate_shrunk = (fow_sum / (fow_sum + 20.0)) * gb_per_fow + (20.0 / (fow_sum + 20.0)) * global_gb_rate
                else:
                    gb_rate_shrunk = global_gb_rate
                    
                # Shrink other stats per game (K=3.0 games prior)
                ct_rate_shrunk = (games / (games + 3.0)) * (ct_sum / max(1, games)) + (3.0 / (games + 3.0)) * global_ct_rate
                a_rate_shrunk = (games / (games + 3.0)) * (a_sum / max(1, games)) + (3.0 / (games + 3.0)) * global_a_rate
                g_rate_shrunk = (games / (games + 3.0)) * (g_sum / max(1, games)) + (3.0 / (games + 3.0)) * global_g_rate
                
                opp_def_scale = r.get("team_def_rating", 1.0)
                a_rate_shrunk = a_rate_shrunk * opp_def_scale
                g_rate_shrunk = g_rate_shrunk * opp_def_scale
                
                ev = 0.8 * fow - 0.5 * (N - fow) + gb_rate_shrunk * fow + 10.0 * ct_rate_shrunk + 7.0 * a_rate_shrunk + 10.0 * g_rate_shrunk
                
                # D. Convert to pseudo-BoomProbability and pseudo-PredictedTier
                fo_train_tiers = df_train[(df_train["positionGroup"] == "Faceoff") & (df_train["PerformanceTier"].notna())]
                boom_avg = fo_train_tiers[fo_train_tiers["PerformanceTier"] == "Boom"]["TotalFantasyPoints"].mean()
                nonboom_avg = fo_train_tiers[fo_train_tiers["PerformanceTier"] != "Boom"]["TotalFantasyPoints"].mean()
                
                if pd.isna(boom_avg) or boom_avg == 0: boom_avg = 25.0
                if pd.isna(nonboom_avg) or nonboom_avg == 0: nonboom_avg = 8.0
                
                pseudo_p = (ev - nonboom_avg) / (boom_avg - nonboom_avg)
                pseudo_prob = np.clip(pseudo_p * 100.0, 0.0, 100.0)
                
                if pseudo_prob > 50.0:
                    tier = "Boom"
                elif pseudo_prob < 20.0:
                    tier = "Bust"
                else:
                    tier = "Average"
                    
                preds_out.append({
                    **r.to_dict(),
                    "PredictedPoints": round(float(ev), 2),
                    "PredictedTier": tier,
                    "BoomProbability": round(float(pseudo_prob), 1),
                    "fo_win_prob": round(float(p_win) * 100, 1),
                    "expected_fow": round(float(fow), 2),
                    "expected_fot": round(float(N), 2)
                })
            continue
        
        # 1. Stacking: Out-of-fold point predictions on training data (5-Fold CV using TimeSeriesSplit)
        df_pg["PredictedPoints"] = 0        # Load tuned hyperparams if provided
        hparams_kwargs = {"n_estimators": 100, "random_state": 42}
        if args.hyperparams_file and os.path.exists(args.hyperparams_file):
            try:
                with open(args.hyperparams_file) as hf:
                    hparams_dict = json.load(hf)
                    if pg in hparams_dict:
                        hparams_kwargs.update(hparams_dict[pg])
                        print(f"  [INFO] Applying tuned hyperparams for {pg}: {hparams_dict[pg]}")
            except Exception as ex:
                print(f"  [WARNING] Failed to load hyperparams file: {ex}")

        # Recency sample weighting (Item 50): scale sample weights by season recency when requested
        rec_w_val = getattr(args, "recency_weight", 0.0) or float(os.environ.get("RECENCY_WEIGHT_DEFAULT", "0.3"))
        if rec_w_val > 0 and "year" in df_pg.columns and pg in ["Attack", "Midfield", "Defense", "Goalie"]:
            years_vec = df_pg["year"].fillna(2023)
            recency_w = 1.0 + rec_w_val * (years_vec - 2023)
            print(f"  [INFO] Applying recency sample weighting for {pg} (factor={rec_w_val})")
        else:
            recency_w = None

        # 1. Out-of-Fold Stacking: Fit regression on expanding window / TimeSeriesSplit
        tscv_reg = TimeSeriesSplit(n_splits=3)
        predicted_mask = np.zeros(len(df_pg), dtype=bool)
        
        for train_idx, val_idx in tscv_reg.split(df_pg):
            train_fold = df_pg.iloc[train_idx]
            val_fold = df_pg.iloc[val_idx]
            
            sc_fold = StandardScaler()
            X_tr = sc_fold.fit_transform(train_fold[feats])
            X_val = sc_fold.transform(val_fold[feats])
            
            reg_fold = XGBRegressor(objective=quantile_obj, **hparams_kwargs)
            if recency_w is not None:
                w_tr = recency_w.iloc[train_idx].values
                reg_fold.fit(X_tr, train_fold["TotalFantasyPoints"], sample_weight=w_tr)
            else:
                reg_fold.fit(X_tr, train_fold["TotalFantasyPoints"])
            
            df_pg.loc[df_pg.index[val_idx], "PredictedPoints"] = reg_fold.predict(X_val)
            predicted_mask[val_idx] = True
        
        # 2. Stacking: Fit regression on entire training set and predict on test set
        sc_all = StandardScaler()
        X_all_reg = sc_all.fit_transform(df_pg[feats])
        X_test_reg = sc_all.transform(tp[feats])
        
        reg_full = XGBRegressor(objective=quantile_obj, **hparams_kwargs)
        if recency_w is not None:
            reg_full.fit(X_all_reg, df_pg["TotalFantasyPoints"], sample_weight=recency_w.values)
        else:
            reg_full.fit(X_all_reg, df_pg["TotalFantasyPoints"])
        
        tp["PredictedPoints"] = reg_full.predict(X_test_reg)
        
        # 3. Add PredictedPoints to classification feature list
        pg_feats = feats + ["PredictedPoints"]
        
        # 4. Filter out rows without leak-free stacked predictions, then scale
        clf_train = df_pg[predicted_mask].copy()
        if len(clf_train) < 10:
            clf_train = df_pg.copy() # Fallback if data is too small
            
        sc_clf = StandardScaler()
        X_tr_clf = sc_clf.fit_transform(clf_train[pg_feats])
        X_te_clf = sc_clf.transform(tp[pg_feats])
        
        # 5. Calibrated Classification
        le = LabelEncoder()
        ye = le.fit_transform(clf_train["PerformanceTier"].astype(str))
        base_clf = XGBClassifier(**hparams_kwargs)
        try:
            mod = CalibratedClassifierCV(estimator=base_clf, method='isotonic', cv=TimeSeriesSplit(n_splits=3))
        except TypeError:
            mod = CalibratedClassifierCV(base_estimator=base_clf, method='isotonic', cv=TimeSeriesSplit(n_splits=3))
            
        clf_recency_w = recency_w.loc[clf_train.index].values if recency_w is not None else np.ones(len(clf_train))
        if args.boom_weight != 1.0:
            print(f"  [INFO] Applying asymmetric class weighting: Boom weight = {args.boom_weight}")
            sample_weights = np.where(clf_train["PerformanceTier"] == 'Boom', args.boom_weight, 1.0) * clf_recency_w
            mod.fit(X_tr_clf, ye, sample_weight=sample_weights)
        else:
            sample_weights = clf_recency_w
            mod.fit(X_tr_clf, ye, sample_weight=sample_weights)
        
        # 5b. Extract and log classifier feature importances and SHAP values
        try:
            estimators = [getattr(c, "estimator", getattr(c, "base_estimator", None)) for c in mod.calibrated_classifiers_]
            importances = np.mean([est.feature_importances_ for est in estimators if est is not None], axis=0)
            importance_data[pg] = (pg_feats, importances)
            
            # Print top 5 features to console
            sorted_idx = np.argsort(importances)[::-1]
            print(f"\nTop 5 features for {pg} Classifier:")
            for rank, s_idx in enumerate(sorted_idx[:5]):
                print(f"  {rank+1}. {pg_feats[s_idx]}: {importances[s_idx]:.4f}")
        except Exception as e:
            print(f"Error extracting GBDT feature importance for {pg}: {e}")
            
        if SHAP_AVAILABLE:
            try:
                shap_values_clf_list = []
                is_list_format = True
                for c in mod.calibrated_classifiers_:
                    est = getattr(c, "estimator", getattr(c, "base_estimator", None))
                    explainer_clf = shap.TreeExplainer(est)
                    shap_vals_fold = explainer_clf.shap_values(X_tr_clf)
                    if not isinstance(shap_vals_fold, list):
                        is_list_format = False
                    shap_values_clf_list.append(shap_vals_fold)

                if is_list_format:
                    num_classes_pg = len(shap_values_clf_list[0])
                    shap_values_clf_avg = []
                    for class_idx in range(num_classes_pg):
                        class_shap_avg = np.mean([fold_vals[class_idx] for fold_vals in shap_values_clf_list], axis=0)
                        shap_values_clf_avg.append(class_shap_avg)
                else:
                    shap_values_clf_avg = np.mean(shap_values_clf_list, axis=0)
                    
                shap_data[pg] = (shap_values_clf_avg, X_tr_clf, pg_feats, le.classes_)
            except Exception as e:
                print(f"Warning: SHAP calculation failed for {pg} ({type(e).__name__}: {e})")
        
        pL = le.inverse_transform(mod.predict(X_te_clf))
        pP = mod.predict_proba(X_te_clf)
        
        bI = list(le.classes_).index("Boom") if "Boom" in le.classes_ else -1
        for i, (_, r) in enumerate(tp.iterrows()):
            preds_out.append({
                **r.to_dict(),
                "PredictedTier": pL[i],
                "BoomProbability": round(pP[i][bI]*100, 1) if bI >= 0 else 0,
                "fo_win_prob": 0.0,
                "expected_fow": 0.0,
                "expected_fot": 0.0
            })

    # 6. Generate consolidated Feature Importance and SHAP plots
    fi_dir = os.path.join(sDir, "predicta", "predictions", "feature_importance", f"week{args.week}_{args.year}")
    os.makedirs(fi_dir, exist_ok=True)
    
    position_groups = ["Attack", "Midfield", "Defense", "Faceoff", "Goalie"]
    
    # Plot standard GBDT feature importances
    if importance_data:
        try:
            fig, axes = plt.subplots(3, 2, figsize=(16, 22))
            axes_flat = axes.flatten()
            
            for idx, pg in enumerate(position_groups):
                ax = axes_flat[idx]
                if pg in importance_data:
                    pg_feats, importances = importance_data[pg]
                    indices = np.argsort(importances)
                    
                    # Horizontal bar plot
                    ax.barh(np.array(pg_feats)[indices], importances[indices], color='skyblue')
                    ax.set_title(f"Feature Importance (Mean Gain) - {pg}", fontsize=14, fontweight='bold')
                    ax.tick_params(axis='both', which='major', labelsize=10)
                else:
                    ax.text(0.5, 0.5, f"No data for {pg}", ha='center', va='center', fontsize=12)
            
            # Hide the empty 6th subplot
            axes_flat[5].axis('off')
            plt.tight_layout()
            imp_plot_path = os.path.join(fi_dir, "classifier_importances.png")
            plt.savefig(imp_plot_path, bbox_inches='tight')
            plt.close()
            print(f"Saved consolidated feature importances plot to {imp_plot_path}")
        except Exception as e:
            print(f"Error plotting consolidated feature importances: {e}")
            
    # Plot SHAP summary plots
    if SHAP_AVAILABLE and shap_data:
        try:
            fig, axes = plt.subplots(3, 2, figsize=(18, 24))
            axes_flat = axes.flatten()
            for idx, pg in enumerate(position_groups):
                ax = axes_flat[idx]
                plt.sca(ax)
                if pg in shap_data:
                    shap_vals, X_tr_clf, pg_feats, classes = shap_data[pg]
                    shap.summary_plot(
                        shap_vals,
                        X_tr_clf,
                        feature_names=pg_feats,
                        class_names=list(classes),
                        show=False,
                        plot_size=None
                    )
                    plt.title(f"SHAP Summary - {pg}", fontsize=14, fontweight='bold', pad=15)
                    plt.tick_params(axis='both', which='major', labelsize=10)
                else:
                    ax.text(0.5, 0.5, f"No SHAP data for {pg}", ha='center', va='center', fontsize=12)
            
            # Hide the empty 6th subplot
            axes_flat[5].axis('off')
            plt.tight_layout()
            shap_plot_path = os.path.join(fi_dir, "classifier_shap.png")
            plt.savefig(shap_plot_path, bbox_inches='tight')
            plt.close()
            print(f"Saved consolidated SHAP summary plot to {shap_plot_path}")
        except Exception as e:
            print(f"Error plotting consolidated SHAP summary plots: {e}")

    df_o = pd.DataFrame(preds_out)
    output_dir = os.path.join(sDir, "predicta", "predictions")
    os.makedirs(output_dir, exist_ok=True)
    oP = os.path.join(output_dir, f"week{args.week}_{args.year}_predictions_raw.csv")
    df_o.to_csv(oP, index=False)
    print(f"Saved {len(df_o)} predictions to {oP}")

if __name__ == "__main__":
    main()
