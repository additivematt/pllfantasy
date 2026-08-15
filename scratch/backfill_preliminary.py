import json
import os
import re
import sys
import math

# Add parent directory to path so we can import utils
scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if scripts_dir not in sys.path:
    sys.path.append(scripts_dir)
from utils import get_week_for_event

def parse_ics(ics_path):
    if not os.path.exists(ics_path):
        print(f"Schedule file not found at: {ics_path}")
        return []
    
    with open(ics_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    events = []
    current = {}
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("BEGIN:VEVENT"):
            current = {}
        elif line.startswith("END:VEVENT"):
            events.append(current)
        elif ":" in line:
            k, v = line.split(":", 1)
            current[k] = v
            
    # Filter 2026 events starting from May (regular season + playoffs)
    events_2026 = []
    for ev in events:
        dtstart = ev.get("DTSTART;VALUE=DATE-TIME") or ev.get("DTSTART") or ""
        if dtstart.startswith("2026"):
            # Exclude Championship Series (Feb/March 6v6)
            # DTSTART has format YYYYMMDD...
            date_part = dtstart[:8]
            month = int(date_part[4:6])
            if month >= 5: # May or later
                events_2026.append(ev)
                
    # Sort chronologically by DTSTART
    def get_start_time(ev):
        return ev.get("DTSTART;VALUE=DATE-TIME") or ev.get("DTSTART") or ""
        
    events_2026.sort(key=get_start_time)
    return events_2026

def get_event_id(ev, reg_season_index, qf_count, sf_count):
    summary = ev.get("SUMMARY", "")
    url = ev.get("URL", "")
    if "all-star" in url.lower() or "All-Star" in summary:
        return "2026_allstar_game", reg_season_index, qf_count, sf_count
        
    if "quarterfinal" in url.lower() or "Quarterfinal" in summary:
        m = re.search(r"quarterfinals?-(\d+)", url.lower())
        qf_num = m.group(1) if m else str(qf_count + 1)
        qf_count += 1
        return f"2026_quarterfinal_{qf_num}", reg_season_index, qf_count, sf_count
        
    if "semifinal" in url.lower() or "Semifinal" in summary:
        m = re.search(r"semifinal-(\d+)", url.lower())
        sf_num = m.group(1) if m else str(sf_count + 1)
        sf_count += 1
        return f"2026_semifinal_{sf_num}", reg_season_index, qf_count, sf_count
        
    if "championship" in url.lower() or "Championship" in summary:
        return "2026_championship_game", reg_season_index, qf_count, sf_count
        
    # Regular season game from URL if available
    m = re.search(r"2026-ev-(\d+)", url)
    if m:
        return f"2026_game_{m.group(1)}", reg_season_index, qf_count, sf_count
        
    reg_season_index += 1
    return f"2026_game_{reg_season_index}", reg_season_index, qf_count, sf_count

TEAM_MAP = {
    "Utah Archers": "ARC",
    "Denver Outlaws": "OUT",
    "California Redwoods": "RED",
    "New York Atlas": "ATL",
    "Carolina Chaos": "CHA",
    "Maryland Whipsnakes": "WHP",
    "Philadelphia Waterdogs": "WAT",
    "Boston Cannons": "CAN"
}

def clean_summary_team(team_str):
    team_str = team_str.strip()
    # Handle optional "LC" or other suffixes if any
    for full_name, abbr in TEAM_MAP.items():
        if full_name.lower() in team_str.lower():
            return abbr
    return team_str

def main():
    if len(sys.argv) < 2:
        print("Usage: python scratch/backfill_preliminary.py <week_number>")
        sys.exit(1)
        
    try:
        target_week = int(sys.argv[1])
    except ValueError:
        print("Error: Week number must be an integer.")
        sys.exit(1)
        
    if target_week < 1 or target_week > 14:
        print("Error: Week number must be between 1 and 14.")
        sys.exit(1)
        
    stats_file = os.path.join(scripts_dir, "combined_player_stats_2026.json")
    if not os.path.exists(stats_file):
        print(f"Stats file not found at: {stats_file}")
        sys.exit(1)
        
    # Load stats data
    with open(stats_file, 'r', encoding='utf-8') as f:
        stats_data = json.load(f)
        
    # Collect unique player identities from all existing weeks
    team_players = {}
    for entry in stats_data:
        ident = entry.get("identity")
        if not ident or not ident.get("team"):
            continue
        team = ident["team"]
        slug = ident["slug"]
        
        if team not in team_players:
            team_players[team] = {}
            
        team_players[team][slug] = {
            "slug": slug,
            "officialId": ident.get("officialId"),
            "firstName": ident.get("firstName"),
            "lastName": ident.get("lastName"),
            "position": ident.get("position"),
            "team": team,
            "jerseyNumber": ident.get("jerseyNumber")
        }
        
    # Parse schedule
    ics_path = os.path.join(scripts_dir, "pll-schedule.ics")
    events = parse_ics(ics_path)
    
    # Process events to assign event IDs and filter by target week
    reg_season_index = 0
    qf_count = 0
    sf_count = 0
    
    target_games = []
    
    import datetime
    
    for ev in events:
        event_id, reg_season_index, qf_count, sf_count = get_event_id(ev, reg_season_index, qf_count, sf_count)
        
        # Calculate week using utils
        week_num = get_week_for_event(event_id)
        if week_num == target_week:
            # Parse teams and start time
            summary = ev.get("SUMMARY", "")
            dtstart = ev.get("DTSTART;VALUE=DATE-TIME") or ev.get("DTSTART") or ""
            
            # Convert DTSTART string to unix timestamp
            try:
                dt = datetime.datetime.strptime(dtstart, "%Y%m%dT%H%M%SZ")
                dt = dt.replace(tzinfo=datetime.timezone.utc)
                start_time = str(int(dt.timestamp()))
            except Exception as e:
                print(f"Warning: could not parse DTSTART '{dtstart}': {e}")
                start_time = "0"
                
            # Parse teams
            teams = summary.split(" vs ")
            if len(teams) == 2:
                home = clean_summary_team(teams[0])
                away = clean_summary_team(teams[1])
            else:
                home = "UNK"
                away = "UNK"
                print(f"Warning: summary format unexpected: '{summary}'")
                
            target_games.append({
                "eventId": event_id,
                "homeTeam": home,
                "awayTeam": away,
                "startTime": start_time,
                "summary": summary
            })
            
    if not target_games:
        print(f"No games found in schedule for Week {target_week}.")
        sys.exit(0)
        
    print(f"Found {len(target_games)} games for Week {target_week}:")
    for tg in target_games:
        print(f"  - {tg['eventId']}: {tg['homeTeam']} vs {tg['awayTeam']} (Start: {tg['startTime']})")
        
    # Generate preliminary entries for target week
    preliminary_entries = []
    for game in target_games:
        eventId = game["eventId"]
        home = game["homeTeam"]
        away = game["awayTeam"]
        startTime = game["startTime"]
        
        for team in [home, away]:
            if team in team_players:
                for slug, ident in team_players[team].items():
                    entry = {
                        "identity": ident,
                        "week": target_week,
                        "event": {
                            "eventId": eventId,
                            "startTime": startTime,
                            "eventStatus": 1, # Scheduled/preliminary
                            "homeTeam": home,
                            "awayTeam": away
                        },
                        "f2p": {
                            "salary": 10, # default placeholder salary
                            "projectedPoints": 0.0,
                            "totalPoints": 0.0,
                            "matchupRating": 3,
                            "rosterPositionRank": None,
                            "displayString": ""
                        },
                        "stats": {}
                    }
                    preliminary_entries.append(entry)
                    
    print(f"Generated {len(preliminary_entries)} preliminary player entries for Week {target_week}.")
    
    # Filter out existing entries for the target week to prevent duplicates
    existing_entries = [r for r in stats_data if r.get("week") != target_week]
    
    # Merge and sort
    final_data = existing_entries + preliminary_entries
    final_data = sorted(final_data, key=lambda x: (x.get('week') or 0, x['identity']['slug'], x['event']['eventId']))
    
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=2)
        
    print(f"Successfully updated {stats_file} with Week {target_week} preliminary data.")
    print(f"Total records in dataset now: {len(final_data)}")
    
    # Trigger extract_trial_data to regenerate all_players_stats.json
    print("Triggering extract_trial_data to update the Interrogator UI data...")
    try:
        import extract_trial_data
        extract_trial_data.extract_data()
        print("Done!")
    except Exception as e:
        print(f"Error refreshing interrogator data: {e}")

if __name__ == "__main__":
    main()
