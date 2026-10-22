import os
import argparse
import requests
import json
import pandas as pd
import subprocess
from config import API_TOKEN_ROSTER

# 1. Clean player names for matching (remove spaces, quotes, hyphens, periods, case-insensitive)
def clean_name(name):
    if not name:
        return ""
    return name.replace("'", "").replace("-", "").replace(".", "").replace(" ", "").lower()

# 2. Query official stats REST API for gameday rosters (or local fallback)
def fetch_gameday_rosters(year, week):
    s_dir = os.path.dirname(os.path.abspath(__file__))
    local_candidates = [os.path.join(s_dir, f"gameday_rosters_{year}_week{week}.json")]
    if int(year) == 2026:
        local_candidates.append(os.path.join(s_dir, f"gameday_rosters_week{week}.json"))

    def _filter_year_items(items_list):
        valid = []
        for ev in items_list:
            slug = str(ev.get("slug") or ev.get("id") or "")
            if slug and slug[:4].isdigit() and int(slug[:4]) != int(year):
                continue
            valid.append(ev)
        return valid

    for local_path in local_candidates:
        if os.path.exists(local_path):
            try:
                with open(local_path, "r", encoding="utf-8") as f:
                    res = json.load(f)
                    items = _filter_year_items(res.get("data", {}).get("items", []))
                    if items:
                        print(f"Loaded {len(items)} events from local roster file: {local_path}")
                        return items
            except Exception as e:
                print(f"Warning: Failed to load local roster file: {e}")

    url = f"https://api.stats.premierlacrosseleague.com/api/v4/events/gameday-rosters"
    params = {"year": year, "week": week}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Authorization": f"Bearer {API_TOKEN_ROSTER}",
        "content-type": "application/json",
        "authSource": "web"
    }
    
    print(f"Fetching gameday rosters from API: {url} (Year: {year}, Week: {week})...")
    try:
        r = requests.get(url, params=params, headers=headers, timeout=5)
        r.raise_for_status()
        res = r.json()
        items = _filter_year_items(res.get("data", {}).get("items", []))
        if items:
            return items
    except Exception as e:
        print(f"Warning: Failed to fetch gameday rosters from API: {e}")

    return []

# 3. Filter predictions CSV from raw to final
def filter_csv(raw_path, out_path, api_rosters, team_matchups, injured_keys=None):
    if injured_keys is None:
        injured_keys = set()
    print(f"\nFiltering predictions file: {raw_path} -> {out_path}")
    if not os.path.exists(raw_path):
        print(f"File {raw_path} does not exist. Skipping.")
        return
        
    df = pd.read_csv(raw_path)
    filtered_rows = []
    
    matched_count = 0
    trade_count = 0
    
    for idx, row in df.iterrows():
        fn = row["firstName"]
        ln = row["lastName"]
        pred_team = row["team"]
        
        clean_fn = clean_name(fn)
        clean_ln = clean_name(ln)
        
        if (clean_fn, clean_ln) in injured_keys or str(row.get("injuryStatus", "")).upper() in ("O", "IR"):
            continue
        
        is_active = False
        active_team = None
        
        # Look for this player in the rosters (using gameday rosterStatus, NOT mutable API injuryStatus)
        # First check their listed team
        team_roster = api_rosters.get(pred_team, [])
        for p in team_roster:
            clean_p_fn = clean_name(p["firstName"])
            clean_p_ln = clean_name(p["lastName"])
            
            # Match condition: exact or custom typo mapping
            if clean_fn == clean_p_fn and (clean_ln == clean_p_ln or 
               (clean_ln == "molloy" and clean_p_ln == "malloy") or
               (clean_ln == "mcardle" and clean_p_ln == "mckardle")):
                if p.get("rosterStatus", "active") in ("active", "starter"):
                    is_active = True
                    active_team = pred_team
                break
                
        # If not found on their listed team, check other teams (detect trades!)
        if not is_active:
            for t_code, roster in api_rosters.items():
                if t_code == pred_team:
                    continue
                for p in roster:
                    clean_p_fn = clean_name(p["firstName"])
                    clean_p_ln = clean_name(p["lastName"])
                    if clean_fn == clean_p_fn and (clean_ln == clean_p_ln or 
                       (clean_ln == "molloy" and clean_p_ln == "malloy") or
                       (clean_ln == "mcardle" and clean_p_ln == "mckardle") or
                       (clean_ln == "croddick" and clean_p_ln == "croddick")): # Ryan Croddick trade
                        if p.get("rosterStatus", "active") in ("active", "starter"):
                            is_active = True
                            active_team = t_code
                        break
                if is_active:
                    break
                    
        if is_active:
            # Handle Trades: Update team, opponent, and game_id if team changed
            if active_team != pred_team:
                print(f"  Traded player detected: {fn} {ln} ({pred_team} -> {active_team})")
                row["team"] = active_team
                
                # Update matchup details if we have them for the new team
                if active_team in team_matchups:
                    row["opponent"] = team_matchups[active_team]["opponent"]
                    row["game_id"] = team_matchups[active_team]["game_id"]
                    print(f"    Updated matchup: vs {row['opponent']} (Game: {row['game_id']})")
                trade_count += 1
                
            filtered_rows.append(row)
            matched_count += 1
            
    df_filtered = pd.DataFrame(filtered_rows)
    df_filtered.to_csv(out_path, index=False)
    print(f"Successfully filtered: {matched_count} active players retained (original had {len(df)}). Trades updated: {trade_count}")

def main():
    parser = argparse.ArgumentParser(description="Filter prediction CSV files using live official gameday rosters.")
    parser.add_argument("--year", type=int, default=2026, help="Target year (default: 2026)")
    parser.add_argument("--week", type=int, default=4, help="Target week (default: 4)")
    parser.add_argument("--no-opt", action="store_true", help="Skip running downstream optimization")
    args = parser.parse_args()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    predictions_dir = os.path.join(script_dir, "predicta", "predictions")
    os.makedirs(predictions_dir, exist_ok=True)
    
    class_raw = os.path.join(predictions_dir, f"week{args.week}_{args.year}_predictions_raw.csv")
    class_out = os.path.join(predictions_dir, f"week{args.week}_{args.year}_predictions.csv")
    
    # Build week-specific F2P injured_keys (pre-game IR/O status)
    injured_keys = set()
    f2p_season_path = os.path.join(script_dir, f"f2p_{args.year}_season.json")
    if os.path.exists(f2p_season_path):
        try:
            with open(f2p_season_path, "r", encoding="utf-8") as f_f2p:
                for p_f2p in json.load(f_f2p):
                    if p_f2p.get("week") == args.week and p_f2p.get("injuryStatus") in ("IR", "O"):
                        injured_keys.add((clean_name(p_f2p.get("firstName")), clean_name(p_f2p.get("lastName"))))
        except Exception:
            pass

    # Get active rosters from API
    roster_items = fetch_gameday_rosters(args.year, args.week)
    
    # Fallback logic: if no rosters are returned, filter only week-specific F2P IR/O players and copy to output
    if not roster_items:
        print("\n" + "="*80)
        print("WARNING: Official gameday rosters not available from API yet.")
        print("Filtering only week-specific F2P IR/O players.")
        print("="*80)
        
        if os.path.exists(class_raw):
            df_raw_fb = pd.read_csv(class_raw)
            if injured_keys:
                keep_mask = df_raw_fb.apply(lambda r: (clean_name(r.get("firstName")), clean_name(r.get("lastName"))) not in injured_keys, axis=1)
                df_raw_fb = df_raw_fb[keep_mask].copy()
            df_raw_fb.to_csv(class_out, index=False)
            print(f"Saved {len(df_raw_fb)} players from {class_raw} to {class_out}")
            
        # Run optimizer anyway with unfiltered data
        if not args.no_opt:
            print("\nRegenerating advisory report on unfiltered data...")
            subprocess.run(["python", "06_optimize_lineups.py", "--year", str(args.year), "--week", str(args.week)], cwd=script_dir, check=True)
        return
        
    # Map rosters: team_id -> list of player objects
    api_rosters = {}
    for ev in roster_items:
        for side in ["homeTeam", "awayTeam"]:
            t = ev.get(side) or {}
            team_id = t.get("officialId")
            if not team_id:
                continue
            roster = t.get("gamedayRoster") or []
            if team_id not in api_rosters:
                api_rosters[team_id] = []
            api_rosters[team_id].extend(roster)
            
    # Extract matchup mapping from raw predictions to update traded players
    team_matchups = {}
    if os.path.exists(class_raw):
        df_orig = pd.read_csv(class_raw)
        for idx, row in df_orig.iterrows():
            t = row["team"]
            opp = row["opponent"]
            gid = row["game_id"]
            if t not in team_matchups:
                team_matchups[t] = {"opponent": opp, "game_id": gid}
                
    # Filter predictions CSVs
    filter_csv(class_raw, class_out, api_rosters, team_matchups, injured_keys=injured_keys)
    
    # Regenerate advisory report and optimized lineups
    if not args.no_opt:
        print("\nRegenerating advisory report by running 06_optimize_lineups.py...")
        subprocess.run(["python", "06_optimize_lineups.py", "--year", str(args.year), "--week", str(args.week)], cwd=script_dir, check=True)
        print("\nSuccess! Rosters successfully filtered and optimization report updated.")
    else:
        print("\nSkipping advisory report generation as requested (--no-opt).")

if __name__ == "__main__":
    main()
