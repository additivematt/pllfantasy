import json
import os
import sys

# The directory where this script lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

YEARS = ["2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026"]
OUTPUT_FILE = os.path.join(BASE_DIR, "all_players_stats.json")
MATCHUP_FILES = {
    "2023": os.path.join(BASE_DIR, "season_matchups_2023.json"),
    "2024": os.path.join(BASE_DIR, "season_matchups_2024.json"),
    "2025": os.path.join(BASE_DIR, "season_matchups_2025.json"),
    "2026": os.path.join(BASE_DIR, "season_matchups_2026.json")
}

def extract_data(compile_static=False):
    all_players_data = {} # slug -> {player: {}, stats: [], matchup_logs: {}, isActive: bool}
    team_games = {} # year -> team -> eventId -> game_details

    # Extract Stats for ALL players
    for year in YEARS:
        filename = os.path.join(BASE_DIR, f"combined_player_stats_{year}.json")
        if os.path.exists(filename):
            print(f"Processing {filename}...")
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                for entry in data:
                    slug = entry["identity"]["slug"]
                    if slug not in all_players_data:
                        all_players_data[slug] = {
                            "player": {
                                "name": f"{entry['identity']['firstName']} {entry['identity']['lastName']}",
                                "slug": slug,
                                "team": entry["identity"]["team"],
                                "position": entry["identity"]["position"]
                            },
                            "stats": [],
                            "matchup_logs": {},
                            "isActive": False # Will set to true if in 2025 or 2026
                        }
                    
                    # If this entry has empty stats, check if the game is completed (status 2, 3 or not specified) before flagging as DNP.
                    # This prevents future scheduled games (status 0) from being marked as DNP.
                    is_completed = entry.get("event", {}).get("eventStatus", 3) in [2, 3]
                    has_positive_f2p_pts = entry.get("f2p", {}).get("totalPoints") is not None and entry.get("f2p", {}).get("totalPoints") > 0
                    has_display_str = bool(entry.get("f2p", {}).get("displayString"))
                    has_box_stats = bool(entry.get("stats") and len(entry.get("stats")) > 0)

                    if entry.get("isDNP") is True:
                        entry["isDNP"] = True
                    elif is_completed and not has_box_stats and not has_positive_f2p_pts and not has_display_str:
                        entry["isDNP"] = True
                    else:
                        entry["isDNP"] = False

                    all_players_data[slug]["stats"].append(entry)
                    
                    # Update active status if player appears in 2025 or 2026
                    if year in ["2025", "2026"]:
                        all_players_data[slug]["isActive"] = True
                    
                    # Update team to the most recent one found
                    if year == "2026":
                         all_players_data[slug]["player"]["team"] = entry["identity"]["team"]
                         all_players_data[slug]["player"]["position"] = entry["identity"]["position"]
                         
                    # Track games played by each team
                    event_id = entry.get("event", {}).get("eventId")
                    team = entry.get("identity", {}).get("team")
                    if event_id and team:
                        if year not in team_games:
                            team_games[year] = {}
                        if team not in team_games[year]:
                            team_games[year][team] = {}
                        
                        # Store or update game details, prioritizing completed status
                        status = entry.get("event", {}).get("eventStatus", 3)
                        if event_id not in team_games[year][team] or status in [2, 3]:
                            team_games[year][team][event_id] = {
                                "eventId": event_id,
                                "startTime": entry["event"].get("startTime"),
                                "homeTeam": entry["event"].get("homeTeam"),
                                "awayTeam": entry["event"].get("awayTeam"),
                                "week": entry.get("week"),
                                "eventStatus": status
                            }
        else:
            print(f"Warning: {filename} not found.")

    # Detect and inject DNP (Did Not Play) weeks
    print("Detecting and injecting DNP weeks...")
    dnp_injected_count = 0
    for slug, p_data in all_players_data.items():
        player_event_ids = set()
        player_weeks = {} # year -> { week: team }
        
        for entry in p_data["stats"]:
            e_id = entry.get("event", {}).get("eventId")
            if e_id:
                player_event_ids.add(e_id)
                import re
                match_year = re.search(r"(20[1-3]\d)", e_id)
                e_year = match_year.group(1) if match_year else e_id.split('_')[0]
                w = entry.get("week")
                t = entry["identity"]["team"]
                if e_year not in player_weeks:
                    player_weeks[e_year] = {}
                player_weeks[e_year][w] = t
                
        # Inject missing games for each year the player was active
        for e_year, weeks_map in player_weeks.items():
            if e_year in team_games:
                teams_played_for = set(weeks_map.values())
                for team in teams_played_for:
                    if team in team_games[e_year]:
                        for event_id, g_details in team_games[e_year][team].items():
                            g_week = g_details["week"]
                            # Find the closest week they recorded stats to assign their team for this DNP week
                            closest_w = min(weeks_map.keys(), key=lambda w: abs(w - g_week) if w is not None and g_week is not None else 999)
                            assigned_team = weeks_map[closest_w]
                            
                            # Only inject DNP if the team game is completed (status 2 or 3) and not in the player's event list
                            is_comp_game = g_details.get("eventStatus", 3) in [2, 3]
                            if is_comp_game and assigned_team == team and event_id not in player_event_ids:
                                dnp_entry = {
                                    "identity": {
                                        "slug": slug,
                                        "firstName": p_data["player"]["name"].split(' ', 1)[0],
                                        "lastName": p_data["player"]["name"].split(' ', 1)[1] if ' ' in p_data["player"]["name"] else p_data["player"]["name"],
                                        "position": p_data["player"]["position"],
                                        "team": team,
                                        "jerseyNumber": None
                                    },
                                    "week": g_details["week"],
                                    "event": {
                                        "eventId": event_id,
                                        "startTime": g_details["startTime"],
                                        "homeTeam": g_details["homeTeam"],
                                        "awayTeam": g_details["awayTeam"]
                                    },
                                    "f2p": {
                                        "salary": None,
                                        "projectedPoints": None,
                                        "totalPoints": None,
                                        "matchupRating": None,
                                        "rosterPositionRank": None,
                                        "displayString": None
                                    },
                                    "stats": {},
                                    "isDNP": True
                                }
                                p_data["stats"].append(dnp_entry)
                                player_event_ids.add(event_id)
                                dnp_injected_count += 1
                                
    print(f"Injected {dnp_injected_count} DNP logs across all players.")

    # Build lookup mapping of player name -> list of slugs for O(1) matching
    name_to_slugs = {}
    for slug, p_data in all_players_data.items():
        p_name = p_data["player"]["name"]
        if p_name not in name_to_slugs:
            name_to_slugs[p_name] = []
        name_to_slugs[p_name].append(slug)

    # Extract Matchups for each player
    for year, filename in MATCHUP_FILES.items():
        if os.path.exists(filename):
            print(f"Processing {filename}...")
            with open(filename, 'r', encoding='utf-8') as f:
                matchups = json.load(f)
                for game_id, game_data in matchups.items():
                    for m in game_data.get("matchups", []):
                        for p_key in ("playerA", "playerB"):
                            p_name = m.get(p_key)
                            if p_name and p_name in name_to_slugs:
                                for slug in name_to_slugs[p_name]:
                                    if game_id not in all_players_data[slug]["matchup_logs"]:
                                        all_players_data[slug]["matchup_logs"][game_id] = game_data
        else:
            print(f"Warning: {filename} not found.")

    # Sort stats chronologically for each player using event startTime
    for slug, p_data in all_players_data.items():
        p_data["stats"].sort(key=lambda s: int(s.get("event", {}).get("startTime") or 0))

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_players_data, f, indent=2)
    
    print(f"Successfully extracted all player data to {OUTPUT_FILE}")

    if compile_static:
        # Run the static compiler dynamically (loads 07_prepare_static_data.py)
        try:
            import importlib.util
            static_data_path = os.path.join(BASE_DIR, "07_prepare_static_data.py")
            if os.path.exists(static_data_path):
                spec = importlib.util.spec_from_file_location("prepare_static_data", static_data_path)
                prepare_static_data = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(prepare_static_data)
                prepare_static_data.main()
                print("✅ Static compiler finished successfully!")
            else:
                print("❌ Error: 07_prepare_static_data.py not found in scripts directory!")
        except Exception as e:
            print(f"Error running prepare_static_data: {e}")

if __name__ == "__main__":
    compile_flag = "--compile-static" in sys.argv
    extract_data(compile_static=compile_flag)

