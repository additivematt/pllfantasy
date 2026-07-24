import json
import os
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from graphql_query import GRAPHQL_QUERY
from utils import get_week_for_event
from config import API_TOKEN_STATS

ENDPOINT = "https://api.stats.premierlacrosseleague.com/graphql"
TOKEN = API_TOKEN_STATS

def fetch_player_graphql(slug, query, headers, year):
    payload = {
        "query": query,
        "variables": {
            "slug": slug,
            "year": year,
            "statsYear": year,
            "eventYear": year
        }
    }
    try:
        resp = requests.post(ENDPOINT, headers=headers, json=payload, timeout=10)
        if resp.status_code == 200:
            return resp.json().get('data', {}).get('player')
    except Exception as e:
        print(f"Error fetching {slug}: {e}")
    return None

def main():
    f2p_path = os.path.join(os.path.dirname(__file__), "f2p_2026_season.json")
    if not os.path.exists(f2p_path):
        f2p_path = os.path.join(os.path.dirname(__file__), "f2p_weekly_data.json")
    if not os.path.exists(f2p_path):
        print(f"File not found: {f2p_path}")
        return

    with open(f2p_path, "r", encoding="utf-8") as f:
        f2p_data = json.load(f)

    # Gather unique slugs
    slugs = set(p.get("slug") for p in f2p_data if p.get("slug"))
    print(f"Found {len(slugs)} unique players in F2P data.")

    query = GRAPHQL_QUERY
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    
    graphql_results = {}
    print("Fetching GraphQL data concurrently for 2026...")
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_slug = {executor.submit(fetch_player_graphql, slug, query, headers, 2026): slug for slug in slugs}
        for future in as_completed(future_to_slug):
            slug = future_to_slug[future]
            data = future.result()
            if data:
                graphql_results[slug] = data

    combined_data = []

    for f2p_player in f2p_data:
        slug = f2p_player.get("slug")
        event_id = f2p_player.get("eventId")
        
        # Skip if event cannot be mapped to a valid fantasy week (e.g. All-Star game or Champ Series)
        week = get_week_for_event(event_id)
        if week is None:
            continue
            
        graphql_player = graphql_results.get(slug)
        if not graphql_player:
            continue
            
        all_events = graphql_player.get("allEvents") or []
        
        # Include regular season and postseason (playoffs)
        allowed_segments = ["regular", "post"]
        filtered_events = [ev for ev in all_events if ev.get("seasonSegment", "").lower() in allowed_segments]
        
        # Find matching event in GraphQL
        matched_event = None
        matched_event_stats = None
        for ev in filtered_events:
            # Match the f2p eventId (like "2026_game_1") with graphql slugname
            if ev.get("slugname") == event_id:
                matched_event = ev
                matched_event_stats = ev.get("playerEventStats", {})
                break
                
        # Fallback if exact match not found
        if not matched_event_stats and filtered_events:
            def get_event_type_and_num(eid):
                eid = str(eid).lower()
                m_num = re.search(r'(?:game|quarterfinal|semifinal|championship)[\s_-]*(\d+)', eid)
                num = m_num.group(1) if m_num else None
                if 'champ' in eid: return 'champ', num
                if 'semi' in eid: return 'semi', num
                if 'quarter' in eid: return 'quarter', num
                if 'game' in eid: return 'game', num
                return None, num
                
            type1, num1 = get_event_type_and_num(event_id)
            for ev in filtered_events:
                s_name = ev.get("slugname", "")
                if type1 and s_name:
                    type2, num2 = get_event_type_and_num(s_name)
                    if type1 == type2 and num1 == num2:
                        matched_event = ev
                        matched_event_stats = ev.get("playerEventStats", {})
                        break

        # Combine them
        combined_entry = {
            "identity": {
                "slug": slug,
                "officialId": f2p_player.get("officialId"),
                "firstName": f2p_player.get("firstName"),
                "lastName": f2p_player.get("lastName"),
                "position": f2p_player.get("position"),
                "team": f2p_player.get("currentTeam", {}).get("teamId"),
                "jerseyNumber": f2p_player.get("currentTeam", {}).get("jerseyNumber")
            },
            "week": get_week_for_event(event_id),
            "event": {
                "eventId": event_id,
                "startTime": f2p_player.get("startTime"),
                "eventStatus": f2p_player.get("eventStatus"),
                "homeTeam": matched_event.get("homeTeam", {}).get("officialId") if matched_event else None,
                "awayTeam": matched_event.get("awayTeam", {}).get("officialId") if matched_event else None
            },
            "f2p": {
                "salary": f2p_player.get("salary"),
                "projectedPoints": f2p_player.get("projectedPoints"),
                "totalPoints": f2p_player.get("totalPoints"),
                "matchupRating": f2p_player.get("matchupRating"),
                "rosterPositionRank": f2p_player.get("rosterPositionRank"),
                "displayString": f2p_player.get("displayString")
            },
            "stats": matched_event_stats or {}
        }
        
        # Record the isDNP flag from F2P data if present (only available for the current week)
        for dnp_key in ["isDNP", "isDnp", "dnp"]:
            if dnp_key in f2p_player:
                combined_entry["isDNP"] = f2p_player[dnp_key]
                break
        
        combined_data.append(combined_entry)

    out_path = os.path.join(os.path.dirname(__file__), "combined_player_stats_2026.json")
    
    # Load existing data for upsert
    existing_records = {}
    if os.path.exists(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                
                # Determine which weeks are being updated by the new data
                weeks_to_update = set(get_week_for_event(p.get("eventId")) for p in f2p_data if p.get("eventId"))
                print(f"Updating data for week(s): {weeks_to_update}")
                
                # Key by slug + eventId to allow updates/prevent duplicates,
                # but drop any existing records for the week(s) we are updating to clear out preliminary placeholders.
                for r in old_data:
                    if r.get("week") in weeks_to_update:
                        continue
                    key = f"{r['identity']['slug']}_{r['event']['eventId']}"
                    existing_records[key] = r
            print(f"Loaded {len(existing_records)} existing records for 2026 (excluding updated weeks).")
        except Exception as e:
            print(f"Error loading existing records: {e}")

    # Merge new data
    for record in combined_data:
        key = f"{record['identity']['slug']}_{record['event']['eventId']}"
        existing_records[key] = record

    # Convert back to sorted list
    final_data = sorted(existing_records.values(), key=lambda x: (x['week'] or 0, x['identity']['slug']))

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=2)
        
    print(f"Successfully updated combined dataset at {out_path} (Total: {len(final_data)} records)")

    # Automatically refresh the Interrogator data
    print("Refreshing Player Interrogator data...")
    try:
        import extract_trial_data
        extract_trial_data.extract_data()
    except Exception as e:
        print(f"Error refreshing data: {e}")

if __name__ == "__main__":
    main()
