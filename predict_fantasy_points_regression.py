import json
import os
import pandas as pd
import numpy as np
import re
import argparse
from datetime import datetime, timezone
from xgboost import XGBRegressor
from sklearn.preprocessing import StandardScaler

# ── Team Mapping ─────────────────────────────────────────────────────────────
TEAM_NAME_TO_ID = {
    "California Redwoods": "RED",
    "Denver Outlaws": "OUT",
    "Philadelphia Waterdogs": "WAT",
    "Boston Cannons": "CAN",
    "Maryland Whipsnakes": "WHP",
    "New York Atlas": "ATL",
    "Utah Archers": "ARC",
    "Carolina Chaos": "CHA",
}

def quantile_obj(y_true, y_pred):
    alpha = 0.9
    errors = y_true - y_pred
    grad = np.where(errors >= 0, -alpha, 1.0 - alpha)
    hess = np.ones_like(y_true)
    return grad, hess

def assign_position_group(pos):
    """Merged position group used for tier assignment and model training.
    SSDM, LSM, and Defensemen share the 'Defense' pool so boom thresholds
    reflect all players competing for the same F2P roster slot."""
    pos = str(pos).upper()
    if pos in ["A", "ATTACK"]: return "Attack"
    if pos in ["M", "MIDFIELD"]: return "Midfield"
    if pos in ["SSDM", "LSM", "D", "DEFENSE", "DEFENSEMEN"]: return "Defense"
    if pos in ["FO", "FACEOFF"]: return "Faceoff"
    if pos in ["G", "GOALIE"]: return "Goalie"
    return "Unknown"

def assign_sub_position(pos):
    """Granular sub-position used for opposition ratings and visualisation.
    Keeps SSDM/LSM together and Defensemen separate within the Defense slot."""
    pos = str(pos).upper()
    if pos in ["A", "ATTACK"]: return "Attack"
    if pos in ["M", "MIDFIELD"]: return "Midfield"
    if pos in ["SSDM", "LSM"]: return "SSDM"
    if pos in ["D", "DEFENSE", "DEFENSEMEN"]: return "Defensemen"
    if pos in ["FO", "FACEOFF"]: return "Faceoff"
    if pos in ["G", "GOALIE"]: return "Goalie"
    return "Unknown"

def calc_fantasy(s):
    pts = (s.get("onePointGoals", 0) * 10 + s.get("twoPointGoals", 0) * 15 + s.get("assists", 0) * 7 + s.get("faceoffsWon", 0) * 0.8 + (s.get("faceoffs", 0) - s.get("faceoffsWon", 0)) * -0.5 + s.get("groundBalls", 0) + s.get("saves", 0) * 3 + s.get("causedTurnovers", 0) * 10)
    if s.get("onePointGoals", 0) + s.get("twoPointGoals", 0) >= 3: pts += 5
    if s.get("assists", 0) >= 3: pts += 5
    if s.get("causedTurnovers", 0) >= 3: pts += 5
    if s.get("saves", 0) >= 15: pts += 5
    return pts

def load_stats_json(path):
    import re
    yr_match = re.search(r'combined_player_stats_(\d{4})', path)
    yr = int(yr_match.group(1)) if yr_match else None
    with open(path, encoding="utf-8") as f: data = json.load(f)
    rows = []
    for p in data:
        ident, stats, f2p, evt = p.get("identity", {}), p.get("stats", {}), p.get("f2p", {}), p.get("event", {})
        fp = f2p.get("totalPoints") if f2p.get("totalPoints") is not None else calc_fantasy(stats)
        team = ident.get("team")
        home, away = evt.get("homeTeam"), evt.get("awayTeam")
        opponent = home if team == away else away
        row = {"firstName": ident.get("firstName"), "lastName": ident.get("lastName"), "position": ident.get("position"), "team": team, "opponent": opponent, "eventId": evt.get("eventId"), "TotalFantasyPoints": fp, "week": p.get("week"), "year": yr, "startTime": evt.get("startTime", 0)}
        for k, v in stats.items(): row[k] = v
        rows.append(row)
    df = pd.DataFrame(rows)
    df["positionGroup"] = df["position"].apply(assign_position_group)
    df["subPosition"] = df["position"].apply(assign_sub_position)
    return df

def parse_schedule(ics_path, year, week_number):
    with open(ics_path, encoding="utf-8") as f: text = f.read()
    blocks = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.DOTALL)
    games = []
    for b in blocks:
        def field(n):
            m = re.search(rf"^{n}:(.+)$", b, re.MULTILINE)
            return m.group(1).strip() if m else ""
        url, dts = field("URL"), field("DTSTART")
        if f"{year}-ev-" not in url: continue
        try: dt = datetime.strptime(dts, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except: continue
        games.append({"summary": field("SUMMARY"), "url": url, "dt": dt, "iso_week": dt.isocalendar()[1]})
    if not games: return [], []
    u_weeks = sorted(set(g["iso_week"] for g in games))
    w_map = {w: i+1 for i, w in enumerate(u_weeks)}
    w_games = [g for g in games if w_map[g["iso_week"]] == week_number]
    matchups = []
    for g in w_games:
        m = re.search(r"^(.+?) vs (.+)$", g["summary"])
        if not m: continue
        tA, tB = m.group(1).strip(), m.group(2).strip()
        matchups.append({"game_id": re.search(r"(\d{4}-ev-\d+)$", g["url"]).group(1), "team_a": TEAM_NAME_TO_ID.get(tA, tA), "team_b": TEAM_NAME_TO_ID.get(tB, tB), "team_a_name": tA, "team_b_name": tB, "startTime": g["dt"].timestamp()})
    return matchups, u_weeks

def add_rolling_features(df):
    df = df.sort_values(["firstName", "lastName", "startTime"])
    
    # 1. Rest Advantage
    if "startTime" in df.columns:
        df["startTime"] = pd.to_numeric(df["startTime"], errors="coerce")
        df["days_since_last_game"] = df.groupby(["firstName", "lastName"])["startTime"].diff() / 86400.0
        df["days_since_last_game"] = df["days_since_last_game"].fillna(7.0)
    else:
        df["days_since_last_game"] = 7.0

    # 2 & 3. Touches & ShotPct
    cols = ["shots", "groundBalls", "saves", "faceoffsWon", "assists", "causedTurnovers", "touches", "shotPct"]
    for c in cols:
        if c not in df.columns: df[c] = 0
        df[f"{c}_season_avg"] = df.groupby(["firstName", "lastName"])[c].transform(lambda x: x.expanding().mean().shift(1))
        df[f"{c}_last3_avg"] = df.groupby(["firstName", "lastName"])[c].transform(lambda x: x.rolling(3, min_periods=1).mean().shift(1))
    df["fp_season_avg"] = df.groupby(["firstName", "lastName"])["TotalFantasyPoints"].transform(lambda x: x.expanding().mean().shift(1))
    df["fp_last3_avg"] = df.groupby(["firstName", "lastName"])["TotalFantasyPoints"].transform(lambda x: x.rolling(3, min_periods=1).mean().shift(1))
    df["fp_lag1"] = df.groupby(["firstName", "lastName"])["TotalFantasyPoints"].shift(1)
    
    df["shotPct_anomaly"] = df["shotPct_last3_avg"] - df["shotPct_season_avg"]
    
    if "faceoffs" in df.columns and "faceoffsWon" in df.columns:
        df["faceoffPct"] = df["faceoffsWon"] / df["faceoffs"].replace(0, np.nan)
        df["faceoffPct_season_avg"] = df.groupby(["firstName", "lastName"])["faceoffPct"].transform(lambda x: x.expanding().mean().shift(1))
        df["faceoffPct_last3_avg"] = df.groupby(["firstName", "lastName"])["faceoffPct"].transform(lambda x: x.rolling(3, min_periods=1).mean().shift(1))
        
        # 4. Team FO Advantage
        team_fo = df.groupby(["eventId", "team", "startTime"], as_index=False)[["faceoffsWon", "faceoffs"]].sum()
        team_fo = team_fo.sort_values(["team", "startTime"])
        team_fo["team_foPct"] = team_fo["faceoffsWon"] / team_fo["faceoffs"].replace(0, np.nan)
        team_fo["team_foPct_season_avg"] = team_fo.groupby("team")["team_foPct"].transform(lambda x: x.expanding().mean().shift(1))
        
        df = df.merge(team_fo[["eventId", "team", "team_foPct_season_avg"]], on=["eventId", "team"], how="left")
        opp_fo = team_fo[["eventId", "team", "team_foPct_season_avg"]].rename(columns={"team": "opponent", "team_foPct_season_avg": "opp_foPct_season_avg"})
        df = df.merge(opp_fo, on=["eventId", "opponent"], how="left")
        
        df["team_foPct_season_avg"] = df["team_foPct_season_avg"].fillna(0.5)
        df["opp_foPct_season_avg"] = df["opp_foPct_season_avg"].fillna(0.5)
        df["team_faceoff_advantage"] = df["team_foPct_season_avg"] - df["opp_foPct_season_avg"]
    else:
        df["team_faceoff_advantage"] = 0.0

    return df

def load_all_matchups(script_dir):
    all_m = {}
    for yr in range(2023, 2027):
        p = os.path.join(script_dir, f"season_matchups_{yr}.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f: all_m.update(json.load(f))
    return all_m

def compute_defender_ratings(df_all, matchups_by_game):
    p_avgs = df_all.groupby(["firstName", "lastName"])["TotalFantasyPoints"].mean().to_dict()
    m_res = []
    for gid, gdata in matchups_by_game.items():
        ms = gdata.get("matchups", [])
        grows = df_all[df_all["eventId"] == gid]
        if grows.empty: continue
        for m in ms:
            pA, pB = m["playerA"], m["playerB"]
            rA = grows[(grows["firstName"] + " " + grows["lastName"]) == pA]
            rB = grows[(grows["firstName"] + " " + grows["lastName"]) == pB]
            if not rA.empty and not rB.empty:
                rA, rB = rA.iloc[0], rB.iloc[0]
                def add(oN, dN, oR, dR):
                    oAvg = p_avgs.get(tuple(oN.split(" ", 1)), 0)
                    if oAvg > 5: m_res.append({"off_name": oN, "defender": dN, "def_team": dR["team"], "off_pos": oR["positionGroup"], "ratio": oR["TotalFantasyPoints"] / oAvg})
                add(pA, pB, rA, rB); add(pB, pA, rB, rA)
    
    dfB = df_all.copy()
    a_df = pd.DataFrame([{"firstName": k[0], "lastName": k[1], "p_avg": v} for k, v in p_avgs.items()])
    dfB = dfB.merge(a_df, on=["firstName", "lastName"], how="left")
    dfB = dfB[dfB["p_avg"] > 5].copy()
    dfB["ratio"] = dfB["TotalFantasyPoints"] / dfB["p_avg"]
    # Use subPosition so SSDM and Defensemen have separate opposition ratings
    team_def = dfB.groupby(["opponent", "subPosition"])["ratio"].mean().to_dict()
    p_vs_t = dfB.groupby(["firstName", "lastName", "opponent"])["ratio"].mean().to_dict()
    p_vs_t = {((k[0], k[1]), k[2]): v for k, v in p_vs_t.items()}
    def_r, pair_r = {}, {}
    if m_res:
        df_res = pd.DataFrame(m_res)
        def_r = df_res.groupby("defender")["ratio"].mean().to_dict()
        pair_r = df_res.groupby(["off_name", "defender"])["ratio"].mean().to_dict()
    return def_r, team_def, pair_r, p_vs_t

FEATURE_LISTS = {
    "Attack":   ["fp_season_avg", "fp_last3_avg", "fp_lag1", "shots_season_avg", "shots_last3_avg", "assists_season_avg", "assists_last3_avg", "touches_season_avg", "touches_last3_avg", "shotPct_anomaly", "days_since_last_game", "team_faceoff_advantage", "pairing_rating", "opponent_rating", "player_vs_team_rating", "team_def_rating"],
    "Midfield": ["fp_season_avg", "fp_last3_avg", "fp_lag1", "shots_season_avg", "shots_last3_avg", "groundBalls_season_avg", "groundBalls_last3_avg", "touches_season_avg", "touches_last3_avg", "shotPct_anomaly", "days_since_last_game", "team_faceoff_advantage", "pairing_rating", "opponent_rating", "player_vs_team_rating", "team_def_rating"],
    "Defense":  ["fp_season_avg", "fp_last3_avg", "fp_lag1", "groundBalls_season_avg", "groundBalls_last3_avg", "causedTurnovers_season_avg", "causedTurnovers_last3_avg", "days_since_last_game", "team_faceoff_advantage", "pairing_rating", "opponent_rating", "player_vs_team_rating", "team_def_rating"],
    "Faceoff":  ["fp_season_avg", "fp_last3_avg", "fp_lag1", "faceoffsWon_season_avg", "faceoffsWon_last3_avg", "faceoffPct_season_avg", "faceoffPct_last3_avg", "days_since_last_game", "team_faceoff_advantage", "pairing_rating", "opponent_rating", "player_vs_team_rating", "team_def_rating"],
    "Goalie":   ["fp_season_avg", "fp_last3_avg", "fp_lag1", "saves_season_avg", "saves_last3_avg", "days_since_last_game", "pairing_rating", "player_vs_team_rating", "team_def_rating"],
}

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
            
    if not matchups:
        print("No matchups found.")
        return
        
    df_all = pd.concat([load_stats_json(os.path.join(sDir, f"combined_player_stats_{yr}.json")) for yr in range(2023, args.year + 1) if os.path.exists(os.path.join(sDir, f"combined_player_stats_{yr}.json"))], ignore_index=True).fillna(0)
    
    # Prevent Data Leakage: Exclude events from the target year that are >= target week
    df_all = df_all[~((df_all["year"] == args.year) & (df_all["week"] >= args.week))]
    
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
    std_avgs = std_df.groupby(["firstName", "lastName"])["TotalFantasyPoints"].mean().to_dict() if not std_df.empty else {}
        
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

        roster_rows = []
        for p in fallback_data:
            ident = p.get("identity", {})
            f2p = p.get("f2p", {})
            first = ident.get("firstName")
            last = ident.get("lastName")
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
                "salary": salary
            })
        roster = pd.DataFrame(roster_rows).drop_duplicates(subset=["firstName", "lastName", "team"])
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
                        "salary": salary
                    })
            roster = pd.DataFrame(roster_rows).drop_duplicates(subset=["firstName", "lastName", "team"])
        else:
            print(f"Error: Neither {combP} nor {f2pP} found.")
            return

    team_current_foPct = df_all.groupby("team")[["faceoffsWon", "faceoffs"]].apply(lambda x: x["faceoffsWon"].sum() / max(1, x["faceoffs"].sum())).to_dict()
    
    test_rows = []
    for m in matchups:
        for t, opp in [(m["team_a"], m["team_b"]), (m["team_b"], m["team_a"])]:
            t_df = roster[roster["team"] == t].merge(p_avgs, on=["firstName", "lastName", "positionGroup"], how="left")
            if t_df.empty: continue
            t_df["opponent"], t_df["game_id"] = opp, m["game_id"]
            if "last_startTime" in t_df.columns and m.get("startTime"):
                t_df["days_since_last_game"] = (m["startTime"] - t_df["last_startTime"]) / 86400.0
                t_df["days_since_last_game"] = t_df["days_since_last_game"].fillna(7.0)
            else:
                t_df["days_since_last_game"] = 7.0
            
            t_df["team_faceoff_advantage"] = team_current_foPct.get(t, 0.5) - team_current_foPct.get(opp, 0.5)
            
            tm = t_df.apply(lambda r: get_feats(r, m_by_g.get(m["game_id"], {}).get("matchups", [])), axis=1, result_type='expand')
            t_df["pairing_rating"], t_df["opponent_rating"], t_df["player_vs_team_rating"], t_df["team_def_rating"] = tm[0], tm[1], tm[2], tm[3]
            test_rows.append(t_df)
    df_test = pd.concat(test_rows, ignore_index=True).fillna(1.0)

    df_train = df_all.dropna(subset=["TotalFantasyPoints"]).copy()
    
    preds_out = []
    for pg, feats in FEATURE_LISTS.items():
        df_pg = df_train[df_train["positionGroup"] == pg].dropna(subset=feats + ["TotalFantasyPoints"])
        if len(df_pg) < 15: continue
        sc = StandardScaler()
        Xs = sc.fit_transform(df_pg[feats])
        
        # Train XGBRegressor on raw fantasy points using 90th percentile custom quantile objective
        mod = XGBRegressor(n_estimators=100, random_state=42, objective=quantile_obj).fit(Xs, df_pg["TotalFantasyPoints"])
        
        tp = df_test[df_test["positionGroup"] == pg]
        if tp.empty: continue
        Xt = sc.transform(tp[feats])
        pPts = mod.predict(Xt)
        
        for i, (_, r) in enumerate(tp.iterrows()):
            preds_out.append({**r.to_dict(), "PredictedPoints": max(0.0, round(float(pPts[i]), 2))})

    if preds_out:
        df_o = pd.DataFrame(preds_out)
        oP = os.path.join(sDir, f"week{args.week}_{args.year}_predictions_regression.csv")
        df_o.to_csv(oP, index=False)
        print(f"Saved {len(df_o)} regression predictions to {oP}")
    else:
        print("No predictions generated.")

if __name__ == "__main__":
    main()
