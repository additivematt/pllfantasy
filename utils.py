import re
import math

def normalize_event_id(event_id):
    """
    Normalizes legacy PLL event IDs (2023-2024) to the modern format (2025+).
    Standard Format: YYYY_game_N, YYYY_quarterfinal_N, YYYY_semifinal_N, YYYY_championship_game
    """
    if not event_id:
        return event_id

    # Standardize -ev- to _game_ first so game numbers match consistently
    event_id = re.sub(r"-ev-(\d+)", r"_game_\1", event_id)

    # Mapping for numbered playoff games to standard playoff names
    PLAYOFF_GAME_MAP = {
        "2026_game_49": "2026_quarterfinal_1",
        "2026_game_50": "2026_quarterfinal_2",
        "2026_game_51": "2026_semifinal_1",
        "2026_game_52": "2026_semifinal_2",
        "2026_game_54": "2026_championship_game",
    }
    if event_id in PLAYOFF_GAME_MAP:
        return PLAYOFF_GAME_MAP[event_id]

    # 1. Legacy Regular Season: game-N-YYYY-MM-DD -> YYYY_game_N
    match = re.match(r"game-(\d+)-(\d{4})-\d{1,2}-\d{1,2}", event_id)
    if match:
        game_num, year = match.groups()
        return f"{year}_game_{game_num}"

    # 2. Legacy Playoffs: playoffs-type-N-YYYY-MM-DD -> YYYY_type_N
    match = re.match(r"playoffs-([a-z]+)-(\d+)-(\d{4})-\d{1,2}-\d{1,2}", event_id)
    if match:
        p_type, p_num, year = match.groups()
        return f"{year}_{p_type}_{p_num}"

    # 3. Modern Playoffs: YYYY-quarterfinals-N or YYYY-semifinal-N -> YYYY_quarterfinal_N / YYYY_semifinal_N
    match = re.match(r"(\d{4})-(quarterfinals?|semifinals?|championship)-(\d+)", event_id)
    if match:
        year, p_type, p_num = match.groups()
        p_type = p_type.rstrip('s')
        if p_type == "championship":
            return f"{year}_championship_game"
        return f"{year}_{p_type}_{p_num}"

    # 4. Modern Championship with hyphens: YYYY-championship-game or YYYY-championship
    match = re.match(r"(\d{4})-championship(?:-game)?", event_id)
    if match:
        return f"{match.group(1)}_championship_game"

    # 5. Legacy Championship: championship-YYYY-MM-DD -> YYYY_championship_game
    match = re.match(r"championship-(\d{4})-\d{1,2}-\d{1,2}", event_id)
    if match:
        year = match.group(1)
        return f"{year}_championship_game"

    # 5. Modern Cleanup: e.g., 2025_championship -> 2025_championship_game
    if "championship" in event_id and "game" not in event_id:
        parts = event_id.split('_')
        if len(parts) >= 2:
            # Check if it looks like YYYY_championship
            if len(parts[0]) == 4 and parts[0].isdigit():
                return f"{parts[0]}_championship_game"

    return event_id

def get_week_for_event(event_id):
    """
    Calculates the Fantasy Week (1-15) based on the standardized event ID.
    Accounts for skipped game IDs in the legacy 2023-2025 data.
    """
    if not event_id:
        return None
    
    # Standardize first to be safe
    eid = normalize_event_id(event_id)
    
    if "allstar" in eid.replace("-", "").replace("_", "").lower():
        return None

    # Extract year if present
    year = None
    match_year = re.search(r"^(\d{4})[-_]", eid)
    if match_year:
        year = int(match_year.group(1))
    
    # Playoffs
    if "quarterfinal" in eid: 
        return 14 if year == 2026 else 12
    if "semifinal" in eid: 
        return 15 if year == 2026 else 13
    if "championship" in eid: 
        return 16 if year == 2026 else 14
    
    # Regular Season
    match = re.search(r"(\d{4})_game_(\d+)", eid)
    if match:
        year = int(match.group(1))
        game_num = int(match.group(2))
        
        if year == 2026:
            if game_num <= 4: return 1
            elif game_num <= 8: return 2
            elif game_num <= 12: return 3
            elif game_num <= 16: return 4
            elif game_num <= 19: return 5
            elif game_num in (21, 22, 23, 24): return 6  # game_20 rescheduled to week 10
            elif game_num in (25, 26, 27, 28): return 8
            elif game_num in (29, 30, 31, 32): return 9
            elif game_num in (20, 33, 34, 35, 36): return 10  # 20=Waterdogs vs Outlaws rescheduled
            elif game_num in (37, 38, 39, 40, 41): return 11
            elif game_num in (42, 43, 44, 45): return 12
            elif game_num in (46, 47, 48): return 13
            elif game_num in (49, 50): return 14
            elif game_num in (51, 52): return 15
            elif game_num >= 53: return 16
            
        if game_num <= 20:
            return math.ceil(game_num / 4)
        else:
            # Shift back based on known gaps to normalize to a 40-game sequence
            # 2023/2025 skip [21, 22], 2024 skips [21]
            offset = 0
            if year in [2023, 2025] and game_num >= 23:
                offset = 2
            elif year == 2024 and game_num >= 22:
                offset = 1
            
            normalized_num = game_num - offset
            return math.ceil(normalized_num / 4) + 1
            
    return None

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
    pts = (s.get("onePointGoals", 0) * 10 + s.get("twoPointGoals", 0) * 20 + s.get("assists", 0) * 10 + s.get("turnovers", 0) * -3 + s.get("goalsAgainst", 0) * -1 + s.get("twoPointGoalsAgainst", 0) * -2 + s.get("faceoffsWon", 0) * 0.8 + (s.get("faceoffs", 0) - s.get("faceoffsWon", 0)) * -0.5 + s.get("groundBalls", 0) + s.get("saves", 0) * 3 + s.get("causedTurnovers", 0) * 10)
    if s.get("onePointGoals", 0) + s.get("twoPointGoals", 0) >= 3: pts += 5
    if s.get("assists", 0) >= 3: pts += 5
    if s.get("causedTurnovers", 0) >= 3: pts += 5
    if s.get("saves", 0) >= 15: pts += 5
    return pts

def clean_name(name):
    if not name:
        return ""
    return name.replace("'", "").replace("-", "").replace(".", "").replace(" ", "").lower()

def get_standard_pos(pos):
    pos = str(pos).upper().strip()
    if pos in ['A', 'ATTACK']: return 'A'
    if pos in ['M', 'MIDFIELD', 'MID']: return 'M'
    if pos in ['D', 'DEFENSE', 'DEF', 'SSDM', 'LSM']: return 'D'
    if pos in ['FO', 'FACEOFF']: return 'FO'
    if pos in ['G', 'GOALIE']: return 'G'
    return pos

def run_mc_ev_optimizer(players, budget=200):
    import pulp
    prob = pulp.LpProblem("MC_EV_Optimizer", pulp.LpMaximize)
    player_vars = {}
    for i, p in enumerate(players):
        player_vars[i] = pulp.LpVariable(f"x_{i}", cat='Binary')
    prob += pulp.lpSum([p['sim_ev'] * player_vars[i] for i, p in enumerate(players)]), "Total_EV"
    prob += pulp.lpSum([p['salary'] * player_vars[i] for i, p in enumerate(players)]) <= budget, "Budget"
    pos_requirements = {'A': 2, 'M': 2, 'D': 1, 'FO': 1, 'G': 1}
    for r_pos, count in pos_requirements.items():
        prob += pulp.lpSum([
            player_vars[i] for i, p in enumerate(players)
            if get_standard_pos(p['positionGroup']) == r_pos
        ]) == count, f"Count_{r_pos}"
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[prob.status] == 'Optimal':
        selected_indices = [i for i, var in player_vars.items() if pulp.value(var) == 1]
        return [players[i] for i in selected_indices]
    return None

def generate_random_valid_lineup(players, budget=200):
    import numpy as np
    attackmen = [p for p in players if get_standard_pos(p['positionGroup']) == 'A']
    midfielders = [p for p in players if get_standard_pos(p['positionGroup']) == 'M']
    defenders = [p for p in players if get_standard_pos(p['positionGroup']) == 'D']
    faceoffs = [p for p in players if get_standard_pos(p['positionGroup']) == 'FO']
    goalies = [p for p in players if get_standard_pos(p['positionGroup']) == 'G']
    
    for _ in range(100):
        selected = []
        if len(attackmen) < 2: continue
        selected.extend(np.random.choice(attackmen, size=2, replace=False))
        if len(midfielders) < 2: continue
        selected.extend(np.random.choice(midfielders, size=2, replace=False))
        if len(defenders) < 1: continue
        selected.append(np.random.choice(defenders))
        if len(faceoffs) < 1: continue
        selected.append(np.random.choice(faceoffs))
        if len(goalies) < 1: continue
        selected.append(np.random.choice(goalies))
        
        total_cost = sum(p['salary'] for p in selected)
        if total_cost <= budget:
            return selected
    return None

def evaluate_lineup_mc(lineup, sim_matrix, objective, target_win_score=165.0):
    import numpy as np
    indices = [p['sim_idx'] for p in lineup]
    lineup_sim_scores = sim_matrix[:, indices].sum(axis=1)
    if objective == 'MC_EV':
        return np.mean(lineup_sim_scores)
    elif objective == 'MC_Ceiling_90':
        return np.percentile(lineup_sim_scores, 90)
    elif objective == 'MC_Win_Prob':
        return np.mean(lineup_sim_scores > target_win_score)
    return 0.0

def run_local_search(players, sim_matrix, objective, initial_lineup, budget=200, target_win_score=165.0, restarts=10):
    best_lineup = list(initial_lineup)
    best_val = evaluate_lineup_mc(best_lineup, sim_matrix, objective, target_win_score)
    
    for r in range(restarts):
        if r == 0:
            current_lineup = list(initial_lineup)
        else:
            current_lineup = generate_random_valid_lineup(players, budget)
            if current_lineup is None:
                continue
                
        current_val = evaluate_lineup_mc(current_lineup, sim_matrix, objective, target_win_score)
        
        improved = True
        while improved:
            improved = False
            
            pool_by_pos = {}
            for p in players:
                p_pos = get_standard_pos(p['positionGroup'])
                pool_by_pos.setdefault(p_pos, []).append(p)
                
            for i in range(len(current_lineup)):
                curr_player = current_lineup[i]
                pos_group = get_standard_pos(curr_player['positionGroup'])
                
                best_swap_player = None
                best_swap_val = current_val
                
                for candidate in pool_by_pos.get(pos_group, []):
                    if candidate['sim_idx'] == curr_player['sim_idx']:
                        continue
                    if any(p['firstName'] == candidate['firstName'] and p['lastName'] == candidate['lastName'] for p in current_lineup):
                        continue
                        
                    test_lineup = list(current_lineup)
                    test_lineup[i] = candidate
                    
                    cost = sum(p['salary'] for p in test_lineup)
                    if cost > budget:
                        continue
                        
                    val = evaluate_lineup_mc(test_lineup, sim_matrix, objective, target_win_score)
                    if val > best_swap_val:
                        best_swap_val = val
                        best_swap_player = candidate
                        
                if best_swap_player is not None:
                    current_lineup[i] = best_swap_player
                    current_val = best_swap_val
                    improved = True
                    
        if current_val > best_val:
            best_val = current_val
            best_lineup = current_lineup
            
    return best_lineup

def get_eval_weeks(year, script_dir=None):
    """
    Dynamically discovers all played or predicted fantasy weeks for a given season year.
    Inspected data sources:
    1. combined_player_stats_{year}.json
    2. predicta/predictions/week{W}_{year}_predictions.csv
    Excludes All-Star week (week 7) if no valid fantasy points exist.
    """
    import os, json
    if script_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
    weeks = set()
    stats_file = os.path.join(script_dir, f"combined_player_stats_{year}.json")
    if os.path.exists(stats_file):
        try:
            with open(stats_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for p in data:
                w = p.get("week")
                f2p = p.get("f2p", {})
                if w is not None and (f2p.get("totalPoints") is not None or p.get("stats")):
                    weeks.add(int(w))
        except Exception:
            pass

    pred_dir = os.path.join(script_dir, "predicta", "predictions")
    if os.path.exists(pred_dir):
        for fname in os.listdir(pred_dir):
            if fname.startswith("week") and fname.endswith(f"_{year}_predictions.csv"):
                try:
                    w = int(fname.split("_")[0].replace("week", ""))
                    weeks.add(w)
                except ValueError:
                    pass

    # Exclude exhibition/All-Star weeks where 0 fantasy points were scored
    weeks_to_remove = []
    if stats_file and os.path.exists(stats_file):
        for w in list(weeks):
            w_pts = sum((p.get("f2p", {}).get("totalPoints") or 0) for p in data if p.get("week") == w)
            if w_pts == 0:
                weeks_to_remove.append(w)
    for w in weeks_to_remove:
        weeks.remove(w)

    return sorted(list(weeks))

def get_latest_baseline_num(baselines_dir=None):
    """
    Dynamically finds the highest existing baseline archive number in baselines/ directory.
    Defaults to 11 if no archives are found.
    """
    import os
    if baselines_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        baselines_dir = os.path.join(script_dir, "baselines")
    if not os.path.exists(baselines_dir):
        return 11
    max_num = 11
    for fname in os.listdir(baselines_dir):
        if fname.startswith("rosters_") and "_baseline_" in fname and fname.endswith(".csv"):
            try:
                num_part = fname.split("_baseline_")[-1].replace(".csv", "")
                n = int(num_part)
                if n > max_num:
                    max_num = n
            except ValueError:
                pass
    return max_num

def get_designated_goalie_starters(year, week, goalies=None, script_dir=None):
    """
    Determines the single starting goalie per team for a given year and week.
    Returns:
      starters_dict: dict mapping (clean_name(first) + '_' + clean_name(last)) -> bool
                     and (officialId) -> bool. True for starter, False for backup.
    
    Resolution Order:
    1. Manual overrides from goalie_starters.json (authoritative).
    2. Automated multi-signal heuristic:
       - Official F2P projectedPoints (weight 2.0)
       - F2P salary (weight 1.0)
       - Recent starts bonus (+25 pts if started/saves within last 2 active weeks)
       - Injury status penalty (-100 pts for 'IR' or 'O')
       The goalie with the highest composite score on each team is designated as the starter.
    """
    import os
    import json
    from collections import defaultdict
    if script_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))

    def _clean(n):
        return (n or "").replace("'", "").replace("-", "").replace(".", "").replace(" ", "").lower()

    # 1. Load manual overrides if present
    overrides_file = os.path.join(script_dir, "goalie_starters.json")
    team_overrides = {}
    if os.path.exists(overrides_file):
        try:
            with open(overrides_file, "r", encoding="utf-8") as f:
                ov_data = json.load(f)
            y_str, w_str = str(year), str(week)
            team_overrides = ov_data.get(y_str, {}).get(w_str, {})
        except Exception as e:
            print(f"Warning: Failed to load {overrides_file}: {e}")

    # 2. Gather goalies if not provided
    raw_goalies = []
    if goalies is not None:
        if hasattr(goalies, "to_dict"):
            raw_goalies = goalies.to_dict(orient="records")
        elif isinstance(goalies, list):
            raw_goalies = goalies
    else:
        f2p_path = os.path.join(script_dir, f"f2p_{year}_season.json")
        if os.path.exists(f2p_path):
            try:
                with open(f2p_path, "r", encoding="utf-8") as f:
                    f2p_all = json.load(f)
                for p in f2p_all:
                    if p.get("week") == week:
                        pos = p.get("position")
                        if pos in ("G", "Goalie"):
                            t = p.get("currentTeam", {}).get("teamId") or p.get("team")
                            raw_goalies.append({
                                "firstName": p.get("firstName"),
                                "lastName": p.get("lastName"),
                                "officialId": p.get("officialId"),
                                "team": t,
                                "salary": p.get("salary", 10),
                                "projectedPoints": p.get("projectedPoints", 0.0),
                                "injuryStatus": p.get("injuryStatus")
                            })
            except Exception as e:
                print(f"Warning: Failed to load goalies from {f2p_path}: {e}")

    # Supplement missing fields from F2P data if needed
    f2p_lookup = {}
    f2p_path = os.path.join(script_dir, f"f2p_{year}_season.json")
    if os.path.exists(f2p_path):
        try:
            with open(f2p_path, "r", encoding="utf-8") as f:
                f2p_all = json.load(f)
            for p in f2p_all:
                if p.get("week") == week:
                    fn = p.get("firstName")
                    ln = p.get("lastName")
                    ck = _clean(fn) + "_" + _clean(ln)
                    f2p_lookup[ck] = p
                    if p.get("officialId"):
                        f2p_lookup[p["officialId"]] = p
        except Exception:
            pass

    # Find recent starts / games with saves prior to this week (leakage-free)
    last_started_week = {}
    stats_file = os.path.join(script_dir, f"combined_player_stats_{year}.json")
    if os.path.exists(stats_file):
        try:
            with open(stats_file, "r", encoding="utf-8") as f:
                comb = json.load(f)
            for p in comb:
                pw = p.get("week")
                if pw is not None and pw < week:
                    pos = p.get("identity", {}).get("position")
                    if pos in ("G", "Goalie"):
                        saves = p.get("stats", {}).get("saves", 0)
                        ga = p.get("stats", {}).get("goalsAgainst", 0)
                        f2p_pts = p.get("f2p", {}).get("totalPoints") or 0
                        if saves > 0 or ga > 0 or f2p_pts > 5:
                            fn = p.get("identity", {}).get("firstName")
                            ln = p.get("identity", {}).get("lastName")
                            ck = _clean(fn) + "_" + _clean(ln)
                            last_started_week[ck] = max(last_started_week.get(ck, 0), pw)
                            pid = p.get("identity", {}).get("officialId")
                            if pid:
                                last_started_week[pid] = max(last_started_week.get(pid, 0), pw)
        except Exception:
            pass

    # Group goalies by team
    team_goalies = defaultdict(list)
    for g in raw_goalies:
        team = g.get("team") or g.get("team_id")
        if not team and "currentTeam" in g and isinstance(g["currentTeam"], dict):
            team = g["currentTeam"].get("teamId")
        if team:
            team_goalies[str(team).upper()].append(g)

    starter_flags = {}

    for t_code, g_list in team_goalies.items():
        if len(g_list) == 1:
            g = g_list[0]
            ck = _clean(g.get("firstName")) + "_" + _clean(g.get("lastName"))
            starter_flags[ck] = True
            if g.get("officialId"):
                starter_flags[g["officialId"]] = True
            continue

        # Check for explicit manual override for this team
        override_val = team_overrides.get(t_code)
        if override_val:
            clean_ov = _clean(override_val)
            for g in g_list:
                ck = _clean(g.get("firstName")) + "_" + _clean(g.get("lastName"))
                pid = str(g.get("officialId") or "")
                is_ov = (clean_ov == ck) or (clean_ov in ck) or (clean_ov == pid) or (clean_ov == _clean(g.get("firstName") + " " + g.get("lastName")))
                starter_flags[ck] = is_ov
                if pid:
                    starter_flags[pid] = is_ov
            continue

        # Score goalies using multi-signal heuristic
        scored = []
        for g in g_list:
            fn = g.get("firstName")
            ln = g.get("lastName")
            ck = _clean(fn) + "_" + _clean(ln)
            pid = str(g.get("officialId") or "")

            f2p_info = f2p_lookup.get(ck) or f2p_lookup.get(pid) or {}
            
            proj = float(g.get("projectedPoints") or f2p_info.get("projectedPoints") or 0.0)
            sal = float(g.get("salary") or f2p_info.get("salary") or 10.0)
            inj = g.get("injuryStatus") or f2p_info.get("injuryStatus")
            
            score = 0.0
            score += proj * 2.0
            score += sal * 1.0
            if inj in ("IR", "O"):
                score -= 100.0
            
            last_w = last_started_week.get(ck) or last_started_week.get(pid) or 0
            if last_w > 0 and (week - last_w) <= 2:
                score += 25.0

            scored.append((score, sal, g))

        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        winner = scored[0][2]
        winner_ck = _clean(winner.get("firstName")) + "_" + _clean(winner.get("lastName"))
        winner_pid = str(winner.get("officialId") or "")

        for s_score, s_sal, g in scored:
            ck = _clean(g.get("firstName")) + "_" + _clean(g.get("lastName"))
            pid = str(g.get("officialId") or "")
            is_st = (ck == winner_ck) or (pid and pid == winner_pid)
            starter_flags[ck] = is_st
            if pid:
                starter_flags[pid] = is_st

    return starter_flags

def is_designated_starter(first, last, official_id=None, starters_dict=None):
    if not starters_dict:
        return True
    ck = (first or "").replace("'", "").replace("-", "").replace(".", "").replace(" ", "").lower() + "_" + \
         (last or "").replace("'", "").replace("-", "").replace(".", "").replace(" ", "").lower()
    if ck in starters_dict:
        return starters_dict[ck]
    if official_id and official_id in starters_dict:
        return starters_dict[official_id]
    return True




