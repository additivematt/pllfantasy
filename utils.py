import re
import math

def normalize_event_id(event_id):
    """
    Normalizes legacy PLL event IDs (2023-2024) to the modern format (2025+).
    Standard Format: YYYY_game_N, YYYY_quarterfinal_N, YYYY_semifinal_N, YYYY_championship_game
    """
    if not event_id:
        return event_id

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

    # 3. Legacy Championship: championship-YYYY-MM-DD -> YYYY_championship_game
    match = re.match(r"championship-(\d{4})-\d{1,2}-\d{1,2}", event_id)
    if match:
        year = match.group(1)
        return f"{year}_championship_game"

    # 4. Modern Cleanup: e.g., 2025_championship -> 2025_championship_game
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
    match_year = re.search(r"^(\d{4})_", eid)
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



