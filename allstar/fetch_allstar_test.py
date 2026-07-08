import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

ENDPOINT = "https://api.stats.premierlacrosseleague.com/graphql"
TOKEN = "N)eIKy1rZ%/%fm1WhM7tuVcrR*UIsc"

QUERY = """
query GetPlayerEvents($slug: ID!, $year: Int!) {
  player(slug: $slug, forYear: $year) {
    firstName
    lastName
    allEvents(year: $year) {
      slugname
      seasonSegment
      eventStatus
      gameStatus
      homeTeam {
        fullName
        officialId
      }
      awayTeam {
        fullName
        officialId
      }
      playerEventStats {
        goals
        assists
        points
        groundBalls
        causedTurnovers
        saves
      }
    }
  }
}
"""

def fetch_slugs_for_year(year, headers):
    query = """
    query($year: Int) {
      allTeams(year: $year) {
        officialId
        players {
          slug
        }
      }
    }
    """
    resp = requests.post(
        ENDPOINT,
        headers=headers,
        json={"query": query, "variables": {"year": year}},
        timeout=10
    )
    slugs = set()
    if resp.status_code == 200:
        teams = resp.json().get("data", {}).get("allTeams") or []
        for team in teams:
            for player in team.get("players") or []:
                if player.get("slug"):
                    slugs.add(player["slug"])
    return list(slugs)

def fetch_player_allstar(slug, year, headers):
    payload = {
        "query": QUERY,
        "variables": {"slug": slug, "year": year}
    }
    try:
        resp = requests.post(ENDPOINT, headers=headers, json=payload, timeout=10)
        if resp.status_code == 200:
            return resp.json().get('data', {}).get('player')
    except Exception:
        pass
    return None

def scan_year(year):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    
    print(f"\nScanning year {year}...")
    slugs = fetch_slugs_for_year(year, headers)
    print(f"Found {len(slugs)} player slugs for {year}.")
    
    allstar_events_data = {}
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_slug = {executor.submit(fetch_player_allstar, slug, year, headers): slug for slug in slugs}
        for future in as_completed(future_to_slug):
            slug = future_to_slug[future]
            player_data = future.result()
            if not player_data:
                continue
            
            events = player_data.get('allEvents') or []
            for ev in events:
                segment = (ev.get('seasonSegment') or '').lower()
                slugname = (ev.get('slugname') or '').lower()
                
                # Check if it is an All-Star event
                if 'allstar' in segment or 'all-star' in slugname or 'allstar' in slugname:
                    event_id = ev.get('slugname')
                    if event_id not in allstar_events_data:
                        home = ev.get('homeTeam', {}) or {}
                        away = ev.get('awayTeam', {}) or {}
                        allstar_events_data[event_id] = {
                            "eventId": event_id,
                            "segment": ev.get('seasonSegment'),
                            "status": ev.get('eventStatus'),
                            "homeTeam": home.get('fullName', 'N/A'),
                            "awayTeam": away.get('fullName', 'N/A'),
                            "players_with_stats": []
                        }
                    
                    stats = ev.get('playerEventStats')
                    if stats:
                        # Check if player actually had any statistics (at least played or had non-zero metrics)
                        # Sometimes playerEventStats exists but has all nulls/zeros
                        has_metrics = any(stats.get(k) is not None and stats.get(k) > 0 for k in ['goals', 'assists', 'points', 'groundBalls', 'causedTurnovers', 'saves'])
                        if has_metrics:
                            allstar_events_data[event_id]["players_with_stats"].append({
                                "name": f"{player_data['firstName']} {player_data['lastName']}",
                                "stats": stats
                            })
                            
    if not allstar_events_data:
        print(f"No All-Star game data found online for {year}.")
    else:
        for event_id, data in allstar_events_data.items():
            print(f"\nFound Event: {event_id}")
            print(f"  Segment: {data['segment']}")
            print(f"  Matchup: {data['homeTeam']} vs {data['awayTeam']}")
            print(f"  Status: {data['status']}")
            print(f"  Players with recorded stats: {len(data['players_with_stats'])}")
            if data['players_with_stats']:
                print("  Sample stats:")
                # print top 5 players with stats
                for p in sorted(data['players_with_stats'], key=lambda x: x['stats'].get('points') or 0, reverse=True)[:5]:
                    st = p['stats']
                    print(f"    - {p['name']}: Goals={st.get('goals')}, Assists={st.get('assists')}, Points={st.get('points')}, GB={st.get('groundBalls')}, CT={st.get('causedTurnovers')}, Saves={st.get('saves')}")

if __name__ == "__main__":
    for y in [2023, 2024, 2025, 2026]:
        scan_year(y)
