import os
import argparse
import requests
import json
import pandas as pd
import subprocess

# 1. Clean player names for matching (remove spaces, quotes, hyphens, periods, case-insensitive)
def clean_name(name):
    if not name:
        return ""
    return name.replace("'", "").replace("-", "").replace(".", "").replace(" ", "").lower()

# 2. Query official stats REST API for gameday rosters
def fetch_gameday_rosters(year, week):
    url = f"https://api.stats.premierlacrosseleague.com/api/v4/events/gameday-rosters"
    params = {"year": year, "week": week}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Authorization": "Bearer 2<b}_K/x8JU1mn/",
        "content-type": "application/json",
        "authSource": "web"
    }
    
    print(f"Fetching gameday rosters from API: {url} (Year: {year}, Week: {week})...")
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        res = r.json()
        items = res.get("data", {}).get("items", [])
        return items
    except Exception as e:
        print(f"Warning: Failed to fetch gameday rosters from API: {e}")
        return []

# 3. Filter predictions CSV from raw to final
def filter_csv(raw_path, out_path, api_rosters, team_matchups):
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
        
        is_active = False
        active_team = None
        
        # Look for this player in the rosters
        # First check their listed team
        team_roster = api_rosters.get(pred_team, [])
        for p in team_roster:
            clean_p_fn = clean_name(p["firstName"])
            clean_p_ln = clean_name(p["lastName"])
            
            # Match condition: exact or custom typo mapping
            if clean_fn == clean_p_fn and (clean_ln == clean_p_ln or 
               (clean_ln == "molloy" and clean_p_ln == "malloy") or
               (clean_ln == "mcardle" and clean_p_ln == "mckardle")):
                if p.get("injuryStatus") not in ("O", "IR"):
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
                        if p.get("injuryStatus") not in ("O", "IR"):
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
    args = parser.parse_args()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    class_raw = os.path.join(script_dir, f"week{args.week}_{args.year}_predictions_raw.csv")
    reg_raw = os.path.join(script_dir, f"week{args.week}_{args.year}_predictions_regression_raw.csv")
    
    class_out = os.path.join(script_dir, f"week{args.week}_{args.year}_predictions.csv")
    reg_out = os.path.join(script_dir, f"week{args.week}_{args.year}_predictions_regression.csv")
    
    # Get active rosters from API
    roster_items = fetch_gameday_rosters(args.year, args.week)
    
    # Fallback logic: if no rosters are returned, copy raw predictions and warning
    if not roster_items:
        print("\n" + "="*80)
        print("WARNING: Official gameday rosters not available from API yet.")
        print("Predictions file will NOT be filtered to ensure players are not lost.")
        print("="*80)
        
        # Copy raw to output
        if os.path.exists(class_raw):
            import shutil
            shutil.copy2(class_raw, class_out)
            print(f"Copied {class_raw} to {class_out}")
        if os.path.exists(reg_raw):
            import shutil
            shutil.copy2(reg_raw, reg_out)
            print(f"Copied {reg_raw} to {reg_out}")
            
        # Run optimizer anyway with unfiltered data
        print("\nRegenerating advisory report on unfiltered data...")
        subprocess.run(["python", "optimize_weekly.py", "--year", str(args.year), "--week", str(args.week)], cwd=script_dir, check=True)
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
    filter_csv(class_raw, class_out, api_rosters, team_matchups)
    filter_csv(reg_raw, reg_out, api_rosters, team_matchups)
    
    # Regenerate advisory report and optimized lineups
    print("\nRegenerating advisory report by running optimize_weekly.py...")
    subprocess.run(["python", "optimize_weekly.py", "--year", str(args.year), "--week", str(args.week)], cwd=script_dir, check=True)
    print("\nSuccess! Rosters successfully filtered and optimization report updated.")

if __name__ == "__main__":
    main()
