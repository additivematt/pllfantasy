import json
import os
import pandas as pd
import numpy as np
import re
from datetime import datetime, timezone
import config
from utils import assign_position_group, assign_sub_position, calc_fantasy, clean_name, get_week_for_event

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

FEATURE_LISTS = {
    "Attack":   ["fp_season_avg", "fp_last3_avg", "fp_lag1", "shots_season_avg", "shots_last3_avg", "assists_season_avg", "assists_last3_avg", "touches_season_avg", "touches_last3_avg", "shotPct_anomaly", "days_since_last_game", "team_faceoff_advantage", "pairing_rating", "opponent_rating", "player_vs_team_rating", "team_def_rating", "team_vacated_touch_share", "team_inactive_fp_avg", "opp_def_health", "opp_goalie_health"],
    "Midfield": ["fp_season_avg", "fp_last3_avg", "fp_lag1", "shots_season_avg", "shots_last3_avg", "assists_season_avg", "assists_last3_avg", "groundBalls_season_avg", "groundBalls_last3_avg", "touches_season_avg", "touches_last3_avg", "shotPct_anomaly", "days_since_last_game", "team_faceoff_advantage", "pairing_rating", "opponent_rating", "player_vs_team_rating", "team_def_rating", "team_vacated_touch_share", "team_inactive_fp_avg", "opp_ssdm_health"],
    "Defense":  ["fp_season_avg", "fp_last3_avg", "fp_lag1", "groundBalls_season_avg", "groundBalls_last3_avg", "causedTurnovers_season_avg", "causedTurnovers_last3_avg", "days_since_last_game", "team_faceoff_advantage", "pairing_rating", "opponent_rating", "player_vs_team_rating", "team_def_rating"],
    "Faceoff":  ["fp_season_avg", "fp_last3_avg", "fp_lag1", "faceoffsWon_season_avg", "faceoffsWon_last3_avg", "faceoffPct_season_avg", "faceoffPct_last3_avg", "days_since_last_game", "team_faceoff_advantage", "pairing_rating", "opponent_rating", "player_vs_team_rating", "team_def_rating"],
    "Goalie":   ["fp_season_avg", "fp_last3_avg", "fp_lag1", "saves_season_avg", "saves_last3_avg", "days_since_last_game", "pairing_rating", "player_vs_team_rating", "team_def_rating"],
}

if getattr(config, "TRIMMED_FEATURES_ENABLED", False):
    FEATURE_LISTS["Attack"] = [f for f in FEATURE_LISTS["Attack"] if f not in ["opp_goalie_health", "team_vacated_touch_share", "team_inactive_fp_avg", "shotPct_anomaly"]]
    FEATURE_LISTS["Midfield"] = [f for f in FEATURE_LISTS["Midfield"] if f not in ["pairing_rating", "team_vacated_touch_share", "team_inactive_fp_avg", "shotPct_anomaly"]]
    FEATURE_LISTS["Goalie"] = [f for f in FEATURE_LISTS["Goalie"] if f not in ["pairing_rating"]]

if getattr(config, "EWMA_ENABLED", False):
    for pos, feats in FEATURE_LISTS.items():
        if "fp_ewma_4" not in feats:
            feats.append("fp_ewma_4")

if getattr(config, "FEATURE_ATTACK_2PT_GOALS_ENABLED", False):
    for f in ["twoPointGoals_season_avg", "twoPointGoals_last3_avg", "two_pt_goal_ratio"]:
        if f not in FEATURE_LISTS["Attack"]:
            FEATURE_LISTS["Attack"].append(f)

if getattr(config, "FEATURE_ATTACK_GOALIE_FORM_ENABLED", False):
    for f in ["opp_goalie_save_pct_last3", "opp_goalie_ga_last3"]:
        if f not in FEATURE_LISTS["Attack"]:
            FEATURE_LISTS["Attack"].append(f)

def load_stats_json(path):
    yr_match = re.search(r'combined_player_stats_(\d{4})', path)
    yr = int(yr_match.group(1)) if yr_match else None
    with open(path, encoding="utf-8") as f: data = json.load(f)
    rows = []
    for p in data:
        ident, stats, f2p, evt = p.get("identity", {}), p.get("stats", {}), p.get("f2p", {}), p.get("event", {})
        is_dnp = p.get("isDNP", False)
        if is_dnp:
            fp = np.nan
        else:
            fp = f2p.get("totalPoints") if f2p.get("totalPoints") is not None else calc_fantasy(stats)
        team = ident.get("team")
        home, away = evt.get("homeTeam"), evt.get("awayTeam")
        opponent = home if team == away else away
        row = {"firstName": ident.get("firstName"), "lastName": ident.get("lastName"), "position": ident.get("position"), "team": team, "opponent": opponent, "eventId": evt.get("eventId"), "TotalFantasyPoints": fp, "week": p.get("week"), "year": yr, "startTime": evt.get("startTime", 0), "isDNP": is_dnp, "salary": f2p.get("salary"), "f2p_projected_points": f2p.get("projectedPoints"), "f2p_matchup_rating": f2p.get("matchupRating")}
        if not is_dnp:
            for k, v in stats.items(): row[k] = v
        rows.append(row)
    df = pd.DataFrame(rows)
    df["positionGroup"] = df["position"].apply(assign_position_group)
    df["subPosition"] = df["position"].apply(assign_sub_position)
    return df

def load_all_players_stats(path, target_year, target_week):
    """Load from consolidated all_players_stats.json, including DNP rows.
    Excludes rows from target_year >= target_week to prevent data leakage."""
    with open(path, encoding="utf-8") as f: data = json.load(f)
    rows = []
    for slug, p_data in data.items():
        for entry in p_data.get("stats", []):
            ident = entry.get("identity", {})
            stats = entry.get("stats", {})
            f2p = entry.get("f2p", {})
            evt = entry.get("event", {})
            e_id = evt.get("eventId", "")
            yr_match = re.search(r'(?:^|-|_)(\d{4})(?:-|_|$)', e_id)
            yr = int(yr_match.group(1)) if yr_match else None
            w = entry.get("week")
            if yr is not None and (yr > target_year or (yr == target_year and w is not None and w >= target_week)):
                continue
            is_dnp = entry.get("isDNP", False)
            if is_dnp:
                fp = np.nan
            else:
                fp = f2p.get("totalPoints") if f2p.get("totalPoints") is not None else calc_fantasy(stats)
            team = ident.get("team")
            home, away = evt.get("homeTeam"), evt.get("awayTeam")
            opponent = home if team == away else away
            row = {"firstName": ident.get("firstName"), "lastName": ident.get("lastName"), "position": ident.get("position"), "team": team, "opponent": opponent, "eventId": e_id, "TotalFantasyPoints": fp, "week": w, "year": yr, "startTime": float(evt.get("startTime", 0)), "isDNP": is_dnp, "salary": f2p.get("salary"), "f2p_projected_points": f2p.get("projectedPoints"), "f2p_matchup_rating": f2p.get("matchupRating")}
            if not is_dnp:
                for k, v in stats.items(): row[k] = v
            rows.append(row)
    df = pd.DataFrame(rows)
    df["positionGroup"] = df["position"].apply(assign_position_group)
    df["subPosition"] = df["position"].apply(assign_sub_position)
    return df

def parse_schedule(ics_path, year, week_number):
    with open(ics_path, encoding="utf-8") as f: text = f.read()
    blocks = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.DOTALL)
    matchups = []
    u_weeks = set()
    for b in blocks:
        def field(n):
            m = re.search(rf"^{n}:(.+)$", b, re.MULTILINE)
            return m.group(1).strip() if m else ""
        url, dts = field("URL"), field("DTSTART")
        if f"{year}-ev-" not in url: continue
        try: dt = datetime.strptime(dts, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except: continue
        
        game_id_raw = re.search(r"(\d{4}-ev-\d+)$", url).group(1)
        # Normalize to YYYY_game_X
        game_id_norm = game_id_raw.replace("-ev-", "_game_").replace("-", "_")
        g_week = get_week_for_event(game_id_norm)
        
        if g_week is not None:
            u_weeks.add(g_week)
            if g_week == week_number:
                summary = field("SUMMARY")
                m = re.search(r"^(.+?) vs (.+)$", summary)
                if m:
                    tA, tB = m.group(1).strip(), m.group(2).strip()
                    matchups.append({
                        "game_id": game_id_raw,
                        "team_a": TEAM_NAME_TO_ID.get(tA, tA),
                        "team_b": TEAM_NAME_TO_ID.get(tB, tB),
                        "team_a_name": tA,
                        "team_b_name": tB,
                        "startTime": dt.timestamp()
                    })
    return matchups, sorted(list(u_weeks))

def compute_game_pace_features(df_all, target_matchups, target_year, target_week):
    """Computes expected pace and goals using rolling team histories prior to target week/year."""
    game_stats = {}
    for eventId, grp in df_all.groupby("eventId"):
        if grp.empty: continue
        start_time = grp["startTime"].iloc[0]
        active = grp[grp["isDNP"] != True]
        teams = active["team"].dropna().unique()
        if len(teams) != 2:
            continue
        t1, t2 = teams[0], teams[1]
        
        if getattr(config, "PACE_ADJUSTED_RATES_ENABLED", False):
            g1 = active[active["team"] == t1][["shots", "turnovers"]].fillna(0).sum(axis=1).sum()
            g2 = active[active["team"] == t2][["shots", "turnovers"]].fillna(0).sum(axis=1).sum()
        else:
            # Sum goals scored by players on each team in this event
            g1 = active[active["team"] == t1][["onePointGoals", "twoPointGoals"]].fillna(0).sum(axis=1).sum()
            g2 = active[active["team"] == t2][["onePointGoals", "twoPointGoals"]].fillna(0).sum(axis=1).sum()
        
        game_stats[eventId] = {
            "eventId": eventId,
            "startTime": start_time,
            "team_a": t1,
            "team_b": t2,
            "goals_a": g1,
            "goals_b": g2
        }
        
    all_team_goals = []
    for g in game_stats.values():
        all_team_goals.extend([g["goals_a"], g["goals_b"]])
    
    def get_team_rolling_goals(team, before_time):
        prior = [g for g in game_stats.values() if g["startTime"] < before_time and (g["team_a"] == team or g["team_b"] == team)]
        prior = sorted(prior, key=lambda x: x["startTime"])[-10:] # last 10 games
        
        # Calculate expanding local global average goals for games prior to before_time
        prior_global_goals = []
        for g in game_stats.values():
            if g["startTime"] < before_time:
                prior_global_goals.extend([g["goals_a"], g["goals_b"]])
        local_global_avg = np.mean(prior_global_goals) if prior_global_goals else 12.0
        
        scored = []
        allowed = []
        for g in prior:
            if g["team_a"] == team:
                scored.append(g["goals_a"])
                allowed.append(g["goals_b"])
            else:
                scored.append(g["goals_b"])
                allowed.append(g["goals_a"])
                
        avg_scored = np.mean(scored) if len(scored) >= 3 else local_global_avg
        avg_allowed = np.mean(allowed) if len(allowed) >= 3 else local_global_avg
        return avg_scored, avg_allowed

    # Calculate expected pace for historical games
    expected_paces = {}
    expected_goals_team = {}
    for eventId, g in game_stats.items():
        st = g["startTime"]
        tA = g["team_a"]
        tB = g["team_b"]
        
        avg_s_A, avg_a_A = get_team_rolling_goals(tA, st)
        avg_s_B, avg_a_B = get_team_rolling_goals(tB, st)
        
        exp_s_A = (avg_s_A + avg_a_B) / 2.0
        exp_s_B = (avg_s_B + avg_a_A) / 2.0
        
        expected_paces[eventId] = exp_s_A + exp_s_B
        expected_goals_team[(eventId, tA)] = exp_s_A
        expected_goals_team[(eventId, tB)] = exp_s_B
        
    all_exp_paces = list(expected_paces.values())
    global_league_avg_pace = np.mean(all_exp_paces) if all_exp_paces else 24.0
    
    # Map to training df_all with expanding league average pace and global average goals fallbacks
    expected_pace_col = []
    game_pace_col = []
    team_exp_goals = []
    opp_exp_goals = []
    
    for idx, r in df_all.iterrows():
        eid = r["eventId"]
        t = r["team"]
        opp = r["opponent"]
        st = r["startTime"]
        
        # Calculate local/expanding global average goals and pace for the game's start time
        prior_global_goals = []
        for g in game_stats.values():
            if g["startTime"] < st:
                prior_global_goals.extend([g["goals_a"], g["goals_b"]])
        local_global_avg_goals = np.mean(prior_global_goals) if prior_global_goals else 12.0
        
        prior_paces = [p for e, p in expected_paces.items() if game_stats[e]["startTime"] < st]
        local_league_avg_pace = np.mean(prior_paces) if prior_paces else 24.0
        
        exp_pace = expected_paces.get(eid, local_league_avg_pace)
        expected_pace_col.append(exp_pace)
        game_pace_col.append(exp_pace / local_league_avg_pace)
        
        team_exp_goals.append(expected_goals_team.get((eid, t), local_global_avg_goals))
        opp_exp_goals.append(expected_goals_team.get((eid, opp), local_global_avg_goals))
        
    df_all["expected_pace"] = expected_pace_col
    df_all["game_pace"] = game_pace_col
    df_all["team_expected_goals"] = team_exp_goals
    df_all["opp_expected_goals"] = opp_exp_goals
    
    # Map to target week matchups (test set)
    test_pace_map = {}
    test_expected_goals = {}
    for m in target_matchups:
        gid = m["game_id"]
        tA = m["team_a"]
        tB = m["team_b"]
        st = m.get("startTime") or 9e9
        
        avg_s_A, avg_a_A = get_team_rolling_goals(tA, st)
        avg_s_B, avg_a_B = get_team_rolling_goals(tB, st)
        
        exp_s_A = (avg_s_A + avg_a_B) / 2.0
        exp_s_B = (avg_s_B + avg_a_A) / 2.0
        exp_pace = exp_s_A + exp_s_B
        
        test_pace_map[gid] = exp_pace
        test_expected_goals[(gid, tA)] = exp_s_A
        test_expected_goals[(gid, tB)] = exp_s_B
        
    return df_all, test_pace_map, test_expected_goals, global_league_avg_pace, np.mean(all_team_goals) if all_team_goals else 12.0

def add_rolling_features(df):
    df = df.sort_values(["firstName", "lastName", "startTime"])
    
    if "startTime" in df.columns:
        df["startTime"] = pd.to_numeric(df["startTime"], errors="coerce")
        df["days_since_last_game"] = df.groupby(["firstName", "lastName"])["startTime"].diff() / 86400.0
        df["days_since_last_game"] = df["days_since_last_game"].fillna(7.0)
    else:
        df["days_since_last_game"] = 7.0

    # Separate active subset to prevent DNP rows (zeros/nans) from polluting rolling stats
    active_mask = (df["isDNP"] != True) if "isDNP" in df.columns else pd.Series(True, index=df.index)
    df_active = df[active_mask].copy()

    if getattr(config, "PACE_ADJUSTED_RATES_ENABLED", False):
        poss_df = df_active[["eventId", "team", "shots", "turnovers"]].fillna(0)
        poss_df["poss"] = poss_df["shots"] + poss_df["turnovers"]
        team_poss_series = poss_df.groupby(["eventId", "team"])["poss"].transform("sum")
        team_poss_series = team_poss_series.replace(0, np.nan)
        
        cols_to_normalize = ["shots", "groundBalls", "saves", "faceoffsWon", "assists", "causedTurnovers", "touches"]
        for c in cols_to_normalize:
            if c in df_active.columns:
                df_active[c] = (df_active[c] / team_poss_series) * 10.0

    cols = ["shots", "groundBalls", "saves", "faceoffsWon", "assists", "causedTurnovers", "touches", "shotPct", "assistOpportunities", "shotsOnGoal", "shotsOnGoalPct", "turnovers", "twoPointGoals"]
    for c in cols:
        if c not in df_active.columns: df_active[c] = np.nan
        df_active[f"{c}_season_avg"] = df_active.groupby(["firstName", "lastName"])[c].transform(lambda x: x.expanding().mean().shift(1))
        df_active[f"{c}_last3_avg"] = df_active.groupby(["firstName", "lastName"])[c].transform(lambda x: x.rolling(3, min_periods=1).mean().shift(1))
    
    df_active["fp_season_avg"] = df_active.groupby(["firstName", "lastName"])["TotalFantasyPoints"].transform(lambda x: x.expanding().mean().shift(1))
    df_active["fp_last3_avg"] = df_active.groupby(["firstName", "lastName"])["TotalFantasyPoints"].transform(lambda x: x.rolling(3, min_periods=1).mean().shift(1))
    df_active["fp_lag1"] = df_active.groupby(["firstName", "lastName"])["TotalFantasyPoints"].shift(1)
    
    df_active["turnover_rate_per_touch"] = (df_active["turnovers_season_avg"] / (df_active["touches_season_avg"] + 1e-5)).fillna(0.0)
    df_active["sog_rate_per_touch"] = (df_active["shotsOnGoal_season_avg"] / (df_active["touches_season_avg"] + 1e-5)).fillna(0.0)
    df_active["assist_opp_rate_per_touch"] = (df_active["assistOpportunities_season_avg"] / (df_active["touches_season_avg"] + 1e-5)).fillna(0.0)
    
    if getattr(config, "EWMA_ENABLED", False):
        df_active["fp_ewma_4"] = df_active.groupby(["firstName", "lastName"])["TotalFantasyPoints"].transform(lambda x: x.ewm(halflife=4, min_periods=1).mean().shift(1))

    # Re-integrate calculated stats back into main dataframe and forward-fill DNP gaps
    new_cols = []
    for c in cols:
        new_cols.extend([f"{c}_season_avg", f"{c}_last3_avg"])
    new_cols.extend(["fp_season_avg", "fp_last3_avg", "fp_lag1"])
    if getattr(config, "EWMA_ENABLED", False):
        new_cols.append("fp_ewma_4")

    for c in new_cols:
        df[c] = np.nan
        df.loc[active_mask, c] = df_active[c]
        df[c] = df.groupby(["firstName", "lastName"])[c].ffill()

    df["shotPct_anomaly"] = df["shotPct_last3_avg"] - df["shotPct_season_avg"]
    
    if "faceoffs" in df.columns and "faceoffsWon" in df.columns:
        df_active["faceoffPct"] = df_active["faceoffsWon"] / df_active["faceoffs"].replace(0, np.nan)
        df_active["faceoffPct_season_avg"] = df_active.groupby(["firstName", "lastName"])["faceoffPct"].transform(lambda x: x.expanding().mean().shift(1))
        df_active["faceoffPct_last3_avg"] = df_active.groupby(["firstName", "lastName"])["faceoffPct"].transform(lambda x: x.rolling(3, min_periods=1).mean().shift(1))
        
        fo_cols = ["faceoffPct", "faceoffPct_season_avg", "faceoffPct_last3_avg"]
        for c in fo_cols:
            df[c] = np.nan
            df.loc[active_mask, c] = df_active[c]
            df[c] = df.groupby(["firstName", "lastName"])[c].ffill()
            
        fo_df = df[df["isDNP"] != True].copy() if "isDNP" in df.columns else df.copy()
        team_fo = fo_df.groupby(["eventId", "team", "startTime"], as_index=False)[["faceoffsWon", "faceoffs"]].sum()
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

    # Roster injury features
    df["player_exp_touches"] = df["touches_season_avg"].fillna(0.0)
    df["is_dnp"] = (df.get("isDNP", False) == True).astype(float) if "isDNP" in df.columns else 0.0
    df["dnp_touches_contrib"] = df["player_exp_touches"] * df["is_dnp"]
    df["dnp_fp_contrib"] = df["fp_season_avg"].fillna(0.0) * df["is_dnp"]
    df["dnp_fp_count"] = df["is_dnp"]
    
    team_inj = df.groupby(["eventId", "team"], as_index=False).agg(
        total_exp_touches=("player_exp_touches", "sum"),
        total_dnp_touches=("dnp_touches_contrib", "sum"),
        total_dnp_fp=("dnp_fp_contrib", "sum"),
        total_dnp_count=("dnp_fp_count", "sum")
    )
    team_inj["team_vacated_touch_share"] = team_inj["total_dnp_touches"] / team_inj["total_exp_touches"].replace(0, np.nan)
    team_inj["team_vacated_touch_share"] = team_inj["team_vacated_touch_share"].fillna(0.0)
    team_inj["team_inactive_fp_avg"] = team_inj["total_dnp_fp"] / team_inj["total_dnp_count"].replace(0, np.nan)
    team_inj["team_inactive_fp_avg"] = team_inj["team_inactive_fp_avg"].fillna(0.0)
    df = df.merge(team_inj[["eventId", "team", "team_vacated_touch_share", "team_inactive_fp_avg"]], on=["eventId", "team"], how="left")
    df["team_vacated_touch_share"] = df["team_vacated_touch_share"].fillna(0.0)
    df["team_inactive_fp_avg"] = df["team_inactive_fp_avg"].fillna(0.0)

    if getattr(config, "USAGE_HEALTH_FEATURES_ENABLED", False):
        df["is_active_ssdm"] = np.where((df.get("subPosition", "") == "SSDM") & (df["is_dnp"] == 0.0), df["fp_season_avg"].fillna(0.0) + 1.0, 0.0) if "subPosition" in df.columns else 0.0
        df["is_active_def"] = np.where((df.get("subPosition", "") == "Defensemen") & (df["is_dnp"] == 0.0), df["fp_season_avg"].fillna(0.0) + 1.0, 0.0) if "subPosition" in df.columns else 0.0
    else:
        df["is_active_ssdm"] = np.where((df.get("subPosition", "") == "SSDM") & (df["is_dnp"] == 0.0), 1.0, 0.0) if "subPosition" in df.columns else 0.0
        df["is_active_def"] = np.where((df.get("subPosition", "") == "Defensemen") & (df["is_dnp"] == 0.0), 1.0, 0.0) if "subPosition" in df.columns else 0.0

    game_def = df.groupby(["eventId", "team", "startTime"], as_index=False).agg(
        active_ssdm=("is_active_ssdm", "sum"),
        active_def=("is_active_def", "sum")
    )
    game_def = game_def.sort_values(["team", "startTime"])
    game_def["ssdm_avg"] = game_def.groupby("team")["active_ssdm"].transform(lambda x: x.expanding().mean().shift(1))
    game_def["def_avg"] = game_def.groupby("team")["active_def"].transform(lambda x: x.expanding().mean().shift(1))
    game_def["team_ssdm_health"] = np.minimum(1.0, game_def["active_ssdm"] / game_def["ssdm_avg"].replace(0, np.nan))
    game_def["team_def_health_idx"] = np.minimum(1.0, game_def["active_def"] / game_def["def_avg"].replace(0, np.nan))
    game_def["team_ssdm_health"] = game_def["team_ssdm_health"].fillna(1.0)
    game_def["team_def_health_idx"] = game_def["team_def_health_idx"].fillna(1.0)
    
    df = df.merge(game_def[["eventId", "team", "team_ssdm_health", "team_def_health_idx"]], on=["eventId", "team"], how="left")
    opp_def = game_def[["eventId", "team", "team_ssdm_health", "team_def_health_idx"]].rename(
        columns={"team": "opponent", "team_ssdm_health": "opp_ssdm_health", "team_def_health_idx": "opp_def_health"}
    )
    df = df.merge(opp_def, on=["eventId", "opponent"], how="left")
    df["opp_ssdm_health"] = df["opp_ssdm_health"].fillna(1.0)
    df["opp_def_health"] = df["opp_def_health"].fillna(1.0)

    # Opponent Goalie Health
    goalies = df[df.get("subPosition", pd.Series(dtype=str)) == "Goalie"].copy() if "subPosition" in df.columns else pd.DataFrame()
    if not goalies.empty:
        goalies["starter_score"] = goalies["fp_season_avg"].fillna(0.0)
        idx_starters = goalies.groupby(["eventId", "team"])["starter_score"].idxmax()
        starters = goalies.loc[idx_starters, ["eventId", "team", "firstName", "lastName"]].rename(
            columns={"firstName": "g_first", "lastName": "g_last"}
        )
        goalies = goalies.merge(starters, on=["eventId", "team"], how="left")
        goalies["is_starter_active"] = np.where(
            (goalies["firstName"] == goalies["g_first"]) & (goalies["lastName"] == goalies["g_last"]) & (goalies["is_dnp"] == 0.0), 1.0, 0.0
        )
        goalie_health = goalies.groupby(["eventId", "team"])["is_starter_active"].max().reset_index()
        goalie_health = goalie_health.rename(columns={"team": "opponent", "is_starter_active": "opp_goalie_health"})
        df = df.merge(goalie_health, on=["eventId", "opponent"], how="left")
    else:
        df["opp_goalie_health"] = 1.0
    df["opp_goalie_health"] = df["opp_goalie_health"].fillna(1.0)

    df["touches_anomaly"] = (df["touches_last3_avg"] - df["touches_season_avg"]).fillna(0.0)

    df = df.drop(columns=["player_exp_touches", "is_dnp", "dnp_touches_contrib", "dnp_fp_contrib", "dnp_fp_count", "is_active_ssdm", "is_active_def"], errors="ignore")
    return df

def load_all_matchups(script_dir):
    all_m = {}
    for yr in range(2023, 2027):
        p = os.path.join(script_dir, f"season_matchups_{yr}.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f: all_m.update(json.load(f))
    return all_m

def compute_defender_ratings(df_all, matchups_by_game, max_games_per_team=None):
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
    
    if max_games_per_team is not None and not dfB.empty:
        # Filter dfB to only the last N games per opponent
        recent_gids = dfB.groupby("opponent")["eventId"].unique().apply(lambda gids: list(gids)[-max_games_per_team:]).explode().dropna().unique()
        dfB = dfB[dfB["eventId"].isin(recent_gids)].copy()

    use_shrinkage = getattr(config, "SHRINKAGE_ENABLED", False)
    k_val = getattr(config, "SHRINKAGE_K", 5)
    
    def apply_shrinkage(groupby_obj):
        agg = groupby_obj.agg(["mean", "count"])
        if use_shrinkage:
            return (agg["count"] / (agg["count"] + k_val) * agg["mean"] + k_val / (agg["count"] + k_val) * 1.0).to_dict()
        return agg["mean"].to_dict()

    team_def = apply_shrinkage(dfB.groupby(["opponent", "subPosition"])["ratio"])
    p_vs_t = apply_shrinkage(dfB.groupby(["firstName", "lastName", "opponent"])["ratio"])
    p_vs_t = {((k[0], k[1]), k[2]): v for k, v in p_vs_t.items()}
    
    def_r, pair_r = {}, {}
    if m_res:
        df_res = pd.DataFrame(m_res)
        def_r = apply_shrinkage(df_res.groupby("defender")["ratio"])
        pair_r = apply_shrinkage(df_res.groupby(["off_name", "defender"])["ratio"])
    return def_r, team_def, pair_r, p_vs_t

def add_matchup_ratings(df_all, matchups_by_game, leakage_fix_enabled):
    if df_all.empty:
        return df_all, {}, {}, {}, {}

    # Initialize result columns in df_all
    df_all = df_all.copy()
    df_all["pairing_rating"] = 1.0
    df_all["opponent_rating"] = 1.0
    df_all["player_vs_team_rating"] = 1.0
    df_all["team_def_rating"] = 1.0
    df_all["team_def_rating_last3"] = 1.0
    
    if not leakage_fix_enabled:
        # Legacy behavior: global computation with look-ahead leakage
        def_r, team_def, pair_r, pvst_r = compute_defender_ratings(df_all, matchups_by_game)
        _, team_def_l3, _, _ = compute_defender_ratings(df_all, matchups_by_game, max_games_per_team=3)
        
        def get_feats_row(row):
            pN = f"{row['firstName']} {row['lastName']}"
            gID = row.get("eventId") or row.get("game_id")
            ms = matchups_by_game.get(gID, {}).get("matchups", [])
            pR, iR = 1.0, 1.0
            for m in ms:
                opp = m["playerB"] if m["playerA"] == pN else (m["playerA"] if m["playerB"] == pN else None)
                if opp: pR, iR = pair_r.get((pN, opp), 1.0), def_r.get(opp, 1.0); break
            pvst = pvst_r.get(((row["firstName"], row["lastName"]), row["opponent"]), 1.0)
            sub_pos = row.get("subPosition", row["positionGroup"])
            t_def = team_def.get((row["opponent"], sub_pos), 1.0)
            t_def_l3 = team_def_l3.get((row["opponent"], sub_pos), 1.0)
            return pd.Series([pR, iR, pvst, t_def, t_def_l3])
            
        if not df_all.empty:
            mf = df_all.apply(get_feats_row, axis=1, result_type='expand')
            df_all["pairing_rating"] = mf[0]
            df_all["opponent_rating"] = mf[1]
            df_all["player_vs_team_rating"] = mf[2]
            df_all["team_def_rating"] = mf[3]
            df_all["team_def_rating_last3"] = mf[4]
            
        return df_all, def_r, team_def, pair_r, pvst_r
    
    else:
        # Chronological expanding window behavior (leakage-free)
        game_sort_keys = {}
        for gid, grp in df_all.groupby("eventId"):
            y = grp["year"].iloc[0]
            w = grp["week"].iloc[0]
            st = grp["startTime"].iloc[0] if "startTime" in grp.columns else 0.0
            try:
                st_val = float(st)
            except (ValueError, TypeError):
                st_val = 0.0
            game_sort_keys[gid] = (st_val if st_val > 0 else 0.0, int(y), int(w))
            
        sorted_gids = sorted(game_sort_keys.keys(), key=lambda gid: game_sort_keys[gid])
        
        # Loop through each game
        for idx, gid in enumerate(sorted_gids):
            # Prior completed games
            prior_gids = sorted_gids[:idx]
            if len(prior_gids) == 0:
                continue
                
            df_hist = df_all[df_all["eventId"].isin(prior_gids)]
            if df_hist.empty:
                continue
                
            # Compute ratings on prior history (supporting optional TEAM_DEF_MAX_GAMES setting/env var)
            def_max_env = os.environ.get("TEAM_DEF_MAX_GAMES", None)
            def_max_val = int(def_max_env) if def_max_env and def_max_env != "None" else getattr(config, "TEAM_DEF_MAX_GAMES", None)
            def_r, team_def, pair_r, pvst_r = compute_defender_ratings(df_hist, matchups_by_game, max_games_per_team=def_max_val)
            _, team_def_l3, _, _ = compute_defender_ratings(df_hist, matchups_by_game, max_games_per_team=3)
            
            # Map ratings to the rows belonging to current game `gid`
            g_rows = df_all[df_all["eventId"] == gid]
            if g_rows.empty:
                continue
                
            g_rows_idx = g_rows.index
            
            def get_feats_row_expanding(row):
                pN = f"{row['firstName']} {row['lastName']}"
                ms = matchups_by_game.get(gid, {}).get("matchups", [])
                pR, iR = 1.0, 1.0
                for m in ms:
                    opp = m["playerB"] if m["playerA"] == pN else (m["playerA"] if m["playerB"] == pN else None)
                    if opp: pR, iR = pair_r.get((pN, opp), 1.0), def_r.get(opp, 1.0); break
                pvst = pvst_r.get(((row["firstName"], row["lastName"]), row["opponent"]), 1.0)
                sub_pos = row.get("subPosition", row["positionGroup"])
                t_def = team_def.get((row["opponent"], sub_pos), 1.0)
                t_def_l3 = team_def_l3.get((row["opponent"], sub_pos), 1.0)
                return pd.Series([pR, iR, pvst, t_def, t_def_l3])
                
            # Compute features for rows in this game
            mf = g_rows.apply(get_feats_row_expanding, axis=1, result_type='expand')
            df_all.loc[g_rows_idx, "pairing_rating"] = mf[0]
            df_all.loc[g_rows_idx, "opponent_rating"] = mf[1]
            df_all.loc[g_rows_idx, "player_vs_team_rating"] = mf[2]
            df_all.loc[g_rows_idx, "team_def_rating"] = mf[3]
            df_all.loc[g_rows_idx, "team_def_rating_last3"] = mf[4]
            
        # Compute the final ratings using 100% of df_all to serve as the prediction (test-set) lookups
        def_r_final, team_def_final, pair_r_final, pvst_r_final = compute_defender_ratings(df_all, matchups_by_game)
        
        return df_all, def_r_final, team_def_final, pair_r_final, pvst_r_final


def assign_tiers_expanding(grp):
    q25 = grp.expanding(min_periods=10).quantile(0.25).shift(1).bfill().fillna(8.0)
    q75 = grp.expanding(min_periods=10).quantile(0.75).shift(1).bfill().fillna(25.0)
    
    conditions = [
        grp < q25,
        (grp >= q25) & (grp <= q75),
        grp > q75
    ]
    return pd.Series(np.select(conditions, ["Bust", "Average", "Boom"], default="Average"), index=grp.index)


def filter_played_only(df):
    if df.empty:
        return df
    is_active = (df["isDNP"] != True) & df["TotalFantasyPoints"].notna()
    is_goalie = (df["positionGroup"] == "Goalie")
    saves = df["saves"] if "saves" in df.columns else 0
    ga = df["goalsAgainst"] if "goalsAgainst" in df.columns else 0
    fp = df["TotalFantasyPoints"] if "TotalFantasyPoints" in df.columns else 0
    goalie_played = (saves > 0) | (ga > 0) | (fp > 0)
    played = (~is_goalie & is_active) | (is_goalie & is_active & goalie_played)
    return df[played].copy()

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
