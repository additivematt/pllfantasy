import argparse
import json
import os
import re
import requests
import sys
from collections import Counter
from config import (
    F2P_LEADERBOARD_GROUP_ID,
    F2P_LOCAL_LEAGUE_GROUP_ID,
    F2P_FIREBASE_ID_TOKEN
)

# Force UTF-8 encoding for standard output and error to avoid Windows cp1252 encoding crashes
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def clean_name(n):
    return (n or "").replace("'", "").replace("-", "").replace(".", "").replace(" ", "").lower()

def fetch_token_from_refresh_token():
    refresh_token = os.environ.get("F2P_REFRESH_TOKEN") or os.environ.get("F2P_FIREBASE_REFRESH_TOKEN")
    if not refresh_token:
        return None
        
    print("Attempting to exchange long-lived Refresh Token for a fresh ID token...")
    api_key = "AIzaSyC_KdS1W8vxdykpNGdFOJUDkEh92Gjk2Wk"
    url = f"https://securetoken.googleapis.com/v1/token?key={api_key}"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    try:
        r = requests.post(url, data=payload, headers=headers, timeout=10)
        r.raise_for_status()
        res = r.json()
        print("Successfully exchanged Refresh Token for a fresh ID token!")
        return res.get("id_token")
    except Exception as e:
        print(f"Warning: Failed to exchange Refresh Token: {e}")
        return None

def fetch_token_from_credentials():
    email = os.environ.get("F2P_EMAIL")
    password = os.environ.get("F2P_PASSWORD")
    if not email or not password:
        return None
        
    print(f"Attempting automated login for {email} to get Firebase ID token...")
    api_key = "AIzaSyC_KdS1W8vxdykpNGdFOJUDkEh92Gjk2Wk"
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        res = r.json()
        print("Automated login successful! Retrieved fresh ID token.")
        return res.get("idToken")
    except Exception as e:
        print(f"Warning: Automated login failed: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Scrape F2P Leaderboard & Challenger Rosters")
    parser.add_argument("--year", type=int, required=True, help="Season Year (e.g. 2026)")
    parser.add_argument("--week", type=int, required=True, help="Week number (e.g. 7)")
    parser.add_argument("--token", type=str, default=None, help="F2P Firebase JWT ID Token")
    parser.add_argument("--my-team", type=str, default=os.environ.get("F2P_USER_TEAM_NAME", ""), help="Your team name to exclude from rivals list")
    args = parser.parse_args()

    # 1. Resolve Auth Token
    token = args.token or os.environ.get("F2P_FIREBASE_ID_TOKEN") or F2P_FIREBASE_ID_TOKEN
    if not token:
        token = fetch_token_from_refresh_token()
    if not token:
        token = fetch_token_from_credentials()

    if not token:
        print("\n[ERROR] F2P Firebase Authorization ID Token not found.")
        print("Please provide it via one of the following methods:")
        print("  1. Pass the --token <TOKEN> argument.")
        print("  2. Set the F2P_FIREBASE_ID_TOKEN environment variable.")
        print("  3. Set F2P_FIREBASE_ID_TOKEN in config.py.")
        print("  4. Set the F2P_REFRESH_TOKEN environment variable (highly recommended for magic links).")
        print("  5. Set F2P_EMAIL and F2P_PASSWORD environment variables for password login.")
        print("Exiting.\n")
        exit(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    season_file = os.path.join(script_dir, f"f2p_{args.year}_season.json")
    
    # 2. Load Player Map from Season Data
    player_map = {}
    if os.path.exists(season_file):
        try:
            with open(season_file, "r", encoding="utf-8") as f:
                season_data = json.load(f)
            for r in season_data:
                fpid = r.get("fantasyPlayerInfoId")
                if fpid is not None:
                    # Some entries might have week-specific stats, we want to store general details
                    player_map[int(fpid)] = {
                        "name": f"{r.get('firstName', '')} {r.get('lastName', '')}".strip(),
                        "clean_name": clean_name(f"{r.get('firstName', '')}{r.get('lastName', '')}"),
                        "position": r.get("position"),
                        "team": r.get("currentTeam", {}).get("teamId") if isinstance(r.get("currentTeam"), dict) else r.get("clubTeam"),
                        "salary": r.get("salary")
                    }
            print(f"Loaded {len(player_map)} player mappings from {season_file}")
        except Exception as e:
            print(f"Warning: Failed to parse player map from {season_file}: {e}")
    else:
        print(f"Warning: {season_file} not found. Roster player IDs will not be fully resolved.")

    headers = {
        "Authorization": token,
        "accept": "*/*",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "referer": "https://f2p.premierlacrosseleague.com/",
        "origin": "https://f2p.premierlacrosseleague.com"
    }

    # 3. Fetch Top 25 Global Leaderboard
    print(f"\nFetching global leaderboard (Group {F2P_LEADERBOARD_GROUP_ID})...")
    url_global = f"https://f2p.premierlacrosseleague.com/api/fantasy/getGroupById/?groupId={F2P_LEADERBOARD_GROUP_ID}&sortBy=season"
    try:
        r = requests.get(url_global, headers=headers, timeout=10)
        r.raise_for_status()
        global_data = r.json()
    except Exception as e:
        print(f"Error fetching global leaderboard: {e}")
        exit(1)

    global_leaderboard = global_data.get("leaderboard", [])
    top_25 = global_leaderboard[:25]
    print(f"Retrieved top {len(top_25)} global managers.")

    # 4. Fetch Roster for Top 25 Global
    global_selections = []
    print("Fetching global top 25 rosters...")
    for idx, user in enumerate(top_25):
        uid = user.get("firebaseId")
        team_name = user.get("teamName")
        url_roster = f"https://f2p.premierlacrosseleague.com/api/fantasy/challengerFetch/?userId={uid}"
        try:
            res = requests.get(url_roster, headers=headers, timeout=5)
            if res.status_code == 200:
                player_ids = res.json().get("response", {}).get("fantasyPlayerIds", [])
                unresolved_pids = []
                for pid in player_ids:
                    pinfo = player_map.get(int(pid))
                    if pinfo:
                        global_selections.append(pinfo["name"])
                    else:
                        unresolved_pids.append(pid)
                
                if unresolved_pids:
                    print(f"  [{idx+1}/25] Scraped roster for '{team_name}' (⚠️ {len(unresolved_pids)} unresolved IDs: {unresolved_pids})")
                else:
                    print(f"  [{idx+1}/25] Scraped roster for '{team_name}'")
            else:
                print(f"  [{idx+1}/25] Failed to scrape '{team_name}': Status {res.status_code}")
        except Exception as e:
            print(f"  [{idx+1}/25] Error scraping '{team_name}': {e}")

    # 5. Fetch Local League Leaderboard
    print(f"\nFetching local league leaderboard (Group {F2P_LOCAL_LEAGUE_GROUP_ID})...")
    url_local = f"https://f2p.premierlacrosseleague.com/api/fantasy/getGroupById/?groupId={F2P_LOCAL_LEAGUE_GROUP_ID}&sortBy=season"
    try:
        r = requests.get(url_local, headers=headers, timeout=10)
        r.raise_for_status()
        local_data = r.json()
    except Exception as e:
        print(f"Error fetching local league: {e}")
        exit(1)

    local_leaderboard = local_data.get("leaderboard", [])
    print(f"Retrieved {len(local_leaderboard)} local league managers.")

    # Identify top rivals (excluding my team name if provided)
    rival_candidates = []
    for user in local_leaderboard:
        team_name = user.get("teamName", "")
        if args.my_team and clean_name(team_name) == clean_name(args.my_team):
            print(f"Excluding your own team '{team_name}' from rivals list.")
            continue
        rival_candidates.append(user)

    top_3_rivals = rival_candidates[:3]
    print("\nTop 3 Rivals Targeted:")
    for idx, rival in enumerate(top_3_rivals):
         print(f"  #{idx+1}: {rival.get('teamName')} ({rival.get('seasonTotalPoints')} pts)")

    # 6. Fetch Rosters for Local League
    local_selections = []
    local_rival_rosters = {}
    my_team_roster = None
    print("\nFetching local league rosters...")
    for idx, user in enumerate(local_leaderboard):
        uid = user.get("firebaseId")
        team_name = user.get("teamName")
        rank = idx + 1
        points = user.get("seasonTotalPoints")
        
        is_my_team = args.my_team and clean_name(team_name) == clean_name(args.my_team)
        
        url_roster = f"https://f2p.premierlacrosseleague.com/api/fantasy/challengerFetch/?userId={uid}"
        try:
            res = requests.get(url_roster, headers=headers, timeout=5)
            if res.status_code == 200:
                player_ids = res.json().get("response", {}).get("fantasyPlayerIds", [])
                resolved_names = []
                unresolved_pids = []
                for pid in player_ids:
                    pinfo = player_map.get(int(pid))
                    if pinfo:
                        local_selections.append(pinfo["name"])
                        resolved_names.append(pinfo["name"])
                    else:
                        unresolved_pids.append(pid)
                        resolved_names.append(f"Unknown ID {pid}")
                
                roster_info = {
                    "rank": rank,
                    "points": points,
                    "players": resolved_names
                }
                
                local_rival_rosters[team_name] = roster_info
                if is_my_team:
                    my_team_roster = roster_info
                    print(f"  [My Team Roster] Scraped roster for '{team_name}': {resolved_names}")
                elif unresolved_pids:
                    print(f"  [Local Roster] Scraped roster for '{team_name}' (⚠️ {len(unresolved_pids)} unresolved IDs: {unresolved_pids})")
                else:
                    print(f"  [Local Roster] Scraped roster for '{team_name}'")
            else:
                print(f"  [Local Roster] Failed to scrape '{team_name}': Status {res.status_code}")
        except Exception as e:
            print(f"  [Local Roster] Error scraping '{team_name}': {e}")

    # 7. Aggregate Stats
    global_counts = Counter(global_selections)
    n_global_scraped = len(top_25) # Close enough fallback
    global_consensus = []
    for player, count in global_counts.most_common():
        rate = count / 25.0 # Max top 25
        global_consensus.append({
            "name": player,
            "clean_name": clean_name(player),
            "count": count,
            "rate": round(rate, 2)
        })

    local_counts = Counter(local_selections)
    n_local = len(local_leaderboard)
    local_consensus = []
    for player, count in local_counts.most_common():
        rate = count / float(n_local) if n_local > 0 else 0.0
        local_consensus.append({
            "name": player,
            "clean_name": clean_name(player),
            "count": count,
            "rate": round(rate, 2)
        })

    output_payload = {
        "week": args.week,
        "year": args.year,
        "global_top_25": global_consensus,
        "local_league": local_consensus,
        "local_league_rosters": local_rival_rosters
    }

    # 8. Save output
    advisory_dir = os.path.join(script_dir, "predicta", "advisory")
    os.makedirs(advisory_dir, exist_ok=True)
    out_file = os.path.join(advisory_dir, f"week{args.week}_{args.year}_consensus_ownership.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)

    print(f"\nSuccess! Scraped data saved to {out_file}")

    # 9. Update unified challenger rosters history file
    history_file = os.path.join(advisory_dir, "challenger_rosters_history.json")
    history = {}
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f_h:
                history = json.load(f_h)
        except Exception as e_h:
            print(f"Warning: Failed to load existing history file: {e_h}")
            
    year_str = str(args.year)
    week_str = str(args.week)
    if year_str not in history:
        history[year_str] = {}
        
    history[year_str][week_str] = {
        "global_top_25_ownership": {item["name"]: item["count"] for item in global_consensus},
        "local_league_ownership": {item["name"]: item["count"] for item in local_consensus},
        "local_rivals_rosters": local_rival_rosters
    }
    try:
        with open(history_file, "w", encoding="utf-8") as f_h:
            json.dump(history, f_h, indent=2)
        print(f"Successfully updated unified challenger rosters history in {history_file}")
    except Exception as e_h:
        print(f"Error: Failed to save updated history file: {e_h}")

    print("Tip: If you saw warning logs with unresolved IDs, make sure to run:")
    print(f"   python 01_fetch_f2p_costs.py --week {args.week} --year {args.year}")
    print("   first to retrieve the latest players and their IDs from the server.")

if __name__ == "__main__":
    main()
