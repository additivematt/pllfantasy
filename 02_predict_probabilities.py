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
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import KFold
from utils import assign_position_group, assign_sub_position, calc_fantasy, clean_name
from feature_engineering import (
    TEAM_NAME_TO_ID,
    FEATURE_LISTS,
    load_stats_json,
    load_all_players_stats,
    parse_schedule,
    add_rolling_features,
    load_all_matchups,
    compute_defender_ratings,
    assign_tiers,
    filter_played_only,
    get_historical_average_salary
)

def quantile_obj(y_true, y_pred):
    alpha = 0.9
    errors = y_true - y_pred
    grad = np.where(errors >= 0, -alpha, 1.0 - alpha)
    hess = np.ones_like(y_true)
    return grad, hess


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--week", type=int, required=True)
    args = p.parse_args()
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
    df_all = df_all.fillna(0)

    df_all = add_rolling_features(df_all)
    m_by_g = load_all_matchups(sDir)
    def_r, team_def, pair_r, pvst_r = compute_defender_ratings(df_all, m_by_g)

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
        mf = df_all.apply(get_feats, axis=1, result_type='expand')
        df_all["pairing_rating"], df_all["opponent_rating"], df_all["player_vs_team_rating"], df_all["team_def_rating"] = mf[0], mf[1], mf[2], mf[3]
    else: df_all["pairing_rating"], df_all["opponent_rating"], df_all["player_vs_team_rating"], df_all["team_def_rating"] = 1.0, 1.0, 1.0, 1.0

    def calc_player_avgs(grp):
        res = {
            "fp_season_avg": grp["TotalFantasyPoints"].mean(),
            "fp_last3_avg": grp["TotalFantasyPoints"].tail(3).mean(),
            "fp_lag1": grp["TotalFantasyPoints"].iloc[-1] if not grp.empty else 0,
        }
        cols_to_avg = ["shots", "groundBalls", "saves", "faceoffsWon", "assists", "causedTurnovers", "faceoffPct", "touches", "shotPct"]
        for c in cols_to_avg:
            if c in grp.columns:
                res[f"{c}_season_avg"] = grp[c].mean()
                res[f"{c}_last3_avg"] = grp[c].tail(3).mean()
            else:
                res[f"{c}_season_avg"] = grp["TotalFantasyPoints"].mean()
                res[f"{c}_last3_avg"] = grp["TotalFantasyPoints"].tail(3).mean()
        res["last_startTime"] = grp["startTime"].iloc[-1] if "startTime" in grp.columns and not grp.empty else 0
        return pd.Series(res)

    p_avgs = df_all.groupby(["firstName", "lastName", "positionGroup"]).apply(calc_player_avgs).reset_index()
    p_avgs["shotPct_anomaly"] = p_avgs["shotPct_last3_avg"] - p_avgs["shotPct_season_avg"]

    # Calculate season-to-date average for each player in the target season
    std_df = df_all[df_all["year"] == args.year]
    if not std_df.empty:
        std_avgs = std_df.groupby(["firstName", "lastName"])["TotalFantasyPoints"].mean().to_dict()
    else:
        std_avgs = {}
        
    # Calculate overall historical average as secondary fallback
    overall_avgs = df_all.groupby(["firstName", "lastName"])["TotalFantasyPoints"].mean().to_dict()

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
    if os.path.exists(combP):
        with open(combP, encoding="utf-8") as f: comb_d = json.load(f)
        fallback_data = [p for p in comb_d if p.get("week") == args.week]
        
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
            
            # Filter out injured reserve (IR) and out (O) players
            if off_id in injured_keys or (clean_name_local(first), clean_name_local(last)) in injured_keys:
                print(f"  Skipping injured/out player (fallback_data): {first} {last}")
                continue
                
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
                        std_avg = std_avgs.get((first, last), 0)
                        if std_avg > 0:
                            salary = int(round(std_avg))
                        else:
                            overall_avg = overall_avgs.get((first, last), 0)
                            salary = int(round(overall_avg)) if overall_avg > 0 else 10
                    
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
                    first = p.get("firstName")
                    last = p.get("lastName")
                    
                    # Filter out injured reserve (IR) and out (O) players
                    injury_status = p.get("injuryStatus")
                    if injury_status in ("IR", "O"):
                        print(f"  Skipping injured/out player (f2d): {first} {last} (Status: {injury_status})")
                        continue
                        
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

        # Compare against historical seasonal averages for opponent
        hist_opp = df_all[df_all["team"] == opp_id]
        hist_ssdm_avg = hist_opp[hist_opp["subPosition"] == "SSDM"].groupby("eventId").size().mean() if not hist_opp.empty else None
        hist_def_avg = hist_opp[hist_opp["subPosition"] == "Defensemen"].groupby("eventId").size().mean() if not hist_opp.empty else None

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
            if "eventId" in t_roster.columns:
                t_roster = t_roster[t_roster["eventId"].apply(lambda eid: not eid or match_game_ids(eid, m["game_id"]))]
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
    df_test = pd.concat(test_rows, ignore_index=True).fillna(1.0)

    df_train = df_all.dropna(subset=["TotalFantasyPoints"]).copy()
    df_train = filter_played_only(df_train)
    df_train["PerformanceTier"] = df_train.groupby("positionGroup")["TotalFantasyPoints"].transform(assign_tiers)
    
    importance_data = {}
    shap_data = {}
    preds_out = []
    for pg, feats in FEATURE_LISTS.items():
        df_pg = df_train[df_train["positionGroup"] == pg].dropna(subset=feats + ["PerformanceTier"]).copy()
        tp = df_test[df_test["positionGroup"] == pg].copy()
        if len(df_pg) < 15 or tp.empty: continue
        
        # 1. Stacking: Out-of-fold point predictions on training data (5-Fold CV)
        df_pg["PredictedPoints"] = 0.0
        kf = KFold(n_splits=5, shuffle=True, random_state=42)
        
        for train_idx, val_idx in kf.split(df_pg):
            train_fold = df_pg.iloc[train_idx]
            val_fold = df_pg.iloc[val_idx]
            
            sc_fold = StandardScaler()
            X_tr = sc_fold.fit_transform(train_fold[feats])
            X_val = sc_fold.transform(val_fold[feats])
            
            reg_fold = XGBRegressor(n_estimators=100, random_state=42, objective=quantile_obj)
            reg_fold.fit(X_tr, train_fold["TotalFantasyPoints"])
            
            df_pg.loc[df_pg.index[val_idx], "PredictedPoints"] = reg_fold.predict(X_val)
            
        # 2. Stacking: Fit regression on entire training set and predict on test set
        sc_all = StandardScaler()
        X_all_reg = sc_all.fit_transform(df_pg[feats])
        X_test_reg = sc_all.transform(tp[feats])
        
        reg_full = XGBRegressor(n_estimators=100, random_state=42, objective=quantile_obj)
        reg_full.fit(X_all_reg, df_pg["TotalFantasyPoints"])
        
        tp["PredictedPoints"] = reg_full.predict(X_test_reg)
        
        # 3. Add PredictedPoints to classification feature list
        pg_feats = feats + ["PredictedPoints"]
        
        # 4. Standard scale final features (including stacked prediction)
        sc_clf = StandardScaler()
        X_tr_clf = sc_clf.fit_transform(df_pg[pg_feats])
        X_te_clf = sc_clf.transform(tp[pg_feats])
        
        # 5. Calibrated Classification
        le = LabelEncoder()
        ye = le.fit_transform(df_pg["PerformanceTier"].astype(str))
        
        base_clf = XGBClassifier(n_estimators=100, random_state=42)
        try:
            mod = CalibratedClassifierCV(estimator=base_clf, method='isotonic', cv=3)
        except TypeError:
            mod = CalibratedClassifierCV(base_estimator=base_clf, method='isotonic', cv=3)
        mod.fit(X_tr_clf, ye)
        
        # 5b. Extract and log classifier feature importances and SHAP values
        try:
            importances = np.mean([c.base_estimator.feature_importances_ for c in mod.calibrated_classifiers_], axis=0)
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
                    explainer_clf = shap.TreeExplainer(c.base_estimator)
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
            preds_out.append({**r.to_dict(), "PredictedTier": pL[i], "BoomProbability": round(pP[i][bI]*100, 1) if bI >= 0 else 0})

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
