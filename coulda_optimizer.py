"""
PLL Fantasy Retroactive Optimizer ("Coulda/Shoulda")
--------------------------------------------------
Finds the optimal lineup for a given year and week based on actual points scored.
Adheres to the Mandatory Output Rule specified in agents.md (and the pll-lineup-optimization workspace skill).
"""

import json
import argparse
import sys
import os

def load_data(year, week):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    season_file = os.path.join(script_dir, f"f2p_{year}_season.json")
    matchups_file = os.path.join(script_dir, f"season_matchups_{year}.json")
    
    if not os.path.exists(season_file):
        print(f"Error: Season file {season_file} not found.")
        sys.exit(1)
        
    with open(season_file, "r") as f:
        data = json.load(f)
        
    matchups = {}
    if os.path.exists(matchups_file):
        with open(matchups_file, "r") as f:
            matchups = json.load(f)
    
    # Filter to specific week
    week_data = [p for p in data if p.get("week") == week]
    
    if not week_data:
        print(f"No data found for Year {year}, Week {week}.")
        sys.exit(1)
        
    return week_data, matchups

def get_opponent(player, matchups):
    event_id = player.get("eventId")
    if not event_id or event_id not in matchups:
        return "Unknown"
    
    m = matchups[event_id]
    team_id = player["currentTeam"]["teamId"]
    return m["team_b"] if m["team_a"] == team_id else m["team_a"]

def process_players(week_data, matchups):
    # Map to store all performances per player: officialId -> list of performances
    player_performances = {}
    for p in week_data:
        pid = p["officialId"]
        if pid not in player_performances:
            player_performances[pid] = []
        player_performances[pid].append(p)
    
    # Selection: for each player, keep the best performance for the optimizer
    # But also track alternatives
    optimized_pool = []
    for pid, perfs in player_performances.items():
        # Sort by points descending
        perfs.sort(key=lambda x: -x["totalPoints"])
        best = perfs[0]
        alts = perfs[1:]
        
        # Attach context to the best performance for later display
        best["_opponent"] = get_opponent(best, matchups)
        best["_alternatives"] = []
        for alt in alts:
            alt_info = {
                "points": alt["totalPoints"],
                "eventId": alt["eventId"],
                "gameNumber": alt.get("gameNumber"),
                "opponent": get_opponent(alt, matchups),
                "stats": alt.get("displayString", "")
            }
            best["_alternatives"].append(alt_info)
            
        optimized_pool.append(best)
        
    return optimized_pool

def precompute_best_pairs(pool, max_budget):
    """Returns dict: budget -> (pts, cost, p1, p2) or None"""
    result = {}
    all_pairs = []
    for i in range(len(pool)):
        for j in range(i+1, len(pool)):
            cost = pool[i]["salary"] + pool[j]["salary"]
            if cost <= max_budget:
                pts = pool[i]["totalPoints"] + pool[j]["totalPoints"]
                all_pairs.append((pts, cost, pool[i], pool[j]))
    
    # Sort by pts desc
    all_pairs.sort(key=lambda x: -x[0])
    
    for b in range(max_budget + 1):
        for pair in all_pairs:
            if pair[1] <= b:
                result[b] = pair
                break
        else:
            result[b] = None
    return result

def run_optimizer(players, budget=200):
    # Categorise by position
    attackmen  = sorted([p for p in players if p["position"] == "A"],  key=lambda p: -p["totalPoints"])
    midfielders= sorted([p for p in players if p["position"] == "M"],  key=lambda p: -p["totalPoints"])
    defenders  = sorted([p for p in players if p["position"] in ("D", "SSDM", "LSM")], key=lambda p: -p["totalPoints"])
    faceoffs   = sorted([p for p in players if p["position"] == "FO"], key=lambda p: -p["totalPoints"])
    goalies    = sorted([p for p in players if p["position"] == "G"],  key=lambda p: -p["totalPoints"])

    print(f"Pool Distribution:")
    print(f"  Attackmen: {len(attackmen)} | Midfielders: {len(midfielders)} | Defenders: {len(defenders)} | FO: {len(faceoffs)} | G: {len(goalies)}")
    
    print("Precomputing attacker and midfielder pairs...")
    atk_best = precompute_best_pairs(attackmen, budget)
    mid_best = precompute_best_pairs(midfielders, budget)
    
    best_points = 0
    best_team = None
    
    print("Searching for optimal combination...")
    for fo in faceoffs:
        for g in goalies:
            for d in defenders:
                fixed_cost = fo["salary"] + g["salary"] + d["salary"]
                if fixed_cost > budget:
                    continue
                
                fixed_pts = fo["totalPoints"] + g["totalPoints"] + d["totalPoints"]
                remaining = budget - fixed_cost
                
                # Try all budget splits between A and M pairs
                current_best_combined = -1
                current_best_a = None
                current_best_m = None
                
                for a_budget in range(remaining + 1):
                    m_budget = remaining - a_budget
                    a_pair = atk_best.get(a_budget)
                    m_pair = mid_best.get(m_budget)
                    
                    if a_pair and m_pair:
                        combined = a_pair[0] + m_pair[0]
                        if combined > current_best_combined:
                            current_best_combined = combined
                            current_best_a = a_pair
                            current_best_m = m_pair
                
                if current_best_a and current_best_m:
                    total_pts = fixed_pts + current_best_combined
                    if total_pts > best_points:
                        best_points = total_pts
                        best_team = [current_best_a[2], current_best_a[3], current_best_m[2], current_best_m[3], d, fo, g]

    return best_team, budget

def print_report(team, budget, year, week):
    if not team:
        print(f"\nNo valid team found for {year} Week {week} within {budget} budget.")
        return

    total_cost = sum(p["salary"] for p in team)
    total_pts = sum(p["totalPoints"] for p in team)
    
    # Sorting for display
    pos_order = {"A": 0, "M": 1, "D": 2, "SSDM": 2, "LSM": 2, "FO": 3, "G": 4}
    team_sorted = sorted(team, key=lambda p: (pos_order.get(p["position"], 9), -p["totalPoints"]))
    
    header = f"OPTIMAL {year} WEEK {week} FANTASY LINEUP"
    print(f"\n{'='*95}")
    print(f"  {header}")
    print(f"{'='*95}")
    print(f"{'Slot':<8} {'Player':<22} {'Team':<5} {'Pos':<5} {'Cost':<5} {'Points':<8} {'Game Context'}")
    print(f"{'-'*95}")
    
    slot_labels = {"A": "ATT", "M": "MID", "D": "DEF", "SSDM": "SSDM", "LSM": "LSM", "FO": "FO", "G": "G"}
    
    for p in team_sorted:
        name = f"{p['firstName']} {p['lastName']}"
        slot = slot_labels.get(p["position"], p["position"])
        game_num = f"G{p.get('gameNumber')}" if p.get("gameNumber") else "G1"
        game_ctx = f"{game_num} ({p['eventId']} vs {p['_opponent']})"
        
        print(f"{slot:<8} {name:<22} {p['currentTeam']['teamId']:<5} {p['position']:<5} {p['salary']:<5} {p['totalPoints']:<8.1f} {game_ctx:<20} {p.get('displayString', '')}")
        
        # Print Alternative Games if they exist (Mandatory Output Rule)
        for alt in p["_alternatives"]:
            alt_game_num = f"G{alt['gameNumber']}" if alt['gameNumber'] else "G1"
            print(f"{'':<8} [Alt: {alt_game_num} ({alt['eventId']} vs {alt['opponent']}) = {alt['points']:.1f} pts  {alt['stats']}]")
            
    print(f"{'-'*95}")
    print(f"{'TOTAL':<8} {'':22} {'':5} {'':5} {total_cost:<5} {total_pts:<8.1f}")
    print(f"{'='*95}")
    print(f"Budget Remaining: {budget - total_cost} coins ({100*total_cost/budget:.1f}% used)\n")

def main():
    parser = argparse.ArgumentParser(description="PLL Fantasy Retroactive Optimizer")
    parser.add_argument("--year", type=int, default=2026, help="Season year (e.g. 2026)")
    parser.add_argument("--week", type=int, default=1, help="Season week (e.g. 1)")
    parser.add_argument("--budget", type=int, default=200, help="Coin budget (default 200)")
    args = parser.parse_args()

    print(f"--- Running Coulda Optimizer for {args.year} Week {args.week} ---")
    
    raw_data, matchups = load_data(args.year, args.week)
    processed_pool = process_players(raw_data, matchups)
    optimal_team, final_budget = run_optimizer(processed_pool, args.budget)
    print_report(optimal_team, final_budget, args.year, args.week)

if __name__ == "__main__":
    main()
