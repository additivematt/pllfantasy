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
    positionName
    allEvents(year: $year) {
      slugname
      seasonSegment
      homeTeam {
        fullName
        officialId
      }
      awayTeam {
        fullName
        officialId
      }
      playerEventStats {
        onePointGoals
        twoPointGoals
        assists
        turnovers
        goalsAgainst
        twoPointGoalsAgainst
        faceoffsWon
        faceoffs
        groundBalls
        saves
        causedTurnovers
      }
    }
  }
}
"""

def calc_fantasy(row):
    one_point_goals = row.get('onePointGoals') or 0
    two_point_goals = row.get('twoPointGoals') or 0
    assists = row.get('assists') or 0
    turnovers = row.get('turnovers') or 0
    goals_against = row.get('goalsAgainst') or 0
    two_point_goals_against = row.get('twoPointGoalsAgainst') or 0
    faceoffs_won = row.get('faceoffsWon') or 0
    faceoffs = row.get('faceoffs') or 0
    ground_balls = row.get('groundBalls') or 0
    saves = row.get('saves') or 0
    caused_turnovers = row.get('causedTurnovers') or 0
    
    points = (
        one_point_goals * 10 +
        two_point_goals * 20 +
        assists * 10 +
        turnovers * -3 +
        goals_against * -1 +
        two_point_goals_against * -2 +
        faceoffs_won * 0.8 +
        (faceoffs - faceoffs_won) * -0.5 +
        ground_balls +
        saves * 3 +
        caused_turnovers * 10
    )
    
    if (one_point_goals + two_point_goals) >= 3: points += 5
    if assists >= 3: points += 5
    if caused_turnovers >= 3: points += 5
    if saves >= 15: points += 5
    
    rounded_points = round(points, 1)
    if rounded_points % 1 == 0:
        return int(rounded_points)
    return rounded_points

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

def fetch_player_data(slug, year, headers):
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

def get_allstar_points(year):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    
    slugs = fetch_slugs_for_year(year, headers)
    print(f"Fetched {len(slugs)} player slugs for {year}")
    
    player_points = []
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_slug = {executor.submit(fetch_player_data, slug, year, headers): slug for slug in slugs}
        for future in as_completed(future_to_slug):
            player_data = future.result()
            if not player_data:
                continue
            
            events = player_data.get('allEvents') or []
            for ev in events:
                segment = (ev.get('seasonSegment') or '').lower()
                slugname = (ev.get('slugname') or '').lower()
                
                # Check for All-Star event
                if 'allstar' in segment or 'all-star' in slugname or 'allstar' in slugname:
                    stats = ev.get('playerEventStats')
                    if stats:
                        # Check if any stats are recorded
                        has_stats = any(stats.get(k) is not None and stats.get(k) != 0 for k in stats)
                        if has_stats:
                            fp = calc_fantasy(stats)
                            player_points.append({
                                "name": f"{player_data['firstName']} {player_data['lastName']}",
                                "position": player_data.get('positionName'),
                                "fp": fp,
                                "stats": stats
                            })
                            
    # Sort descending by fantasy points
    player_points.sort(key=lambda x: x['fp'], reverse=True)
    return player_points

if __name__ == "__main__":
    for year in [2024, 2025]:
        print(f"\n--- ALL-STAR GAME FANTASY POINTS ({year}) ---")
        points_list = get_allstar_points(year)
        # Write to a JSON file in scratch
        output_file = f"scratch/allstar_points_{year}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(points_list, f, indent=2)
        print(f"Saved {len(points_list)} records to {output_file}")
        
        # Print top 15
        for idx, item in enumerate(points_list[:15]):
            st = item['stats']
            print(f"{idx+1}. {item['name']} ({item['position']}): {item['fp']} pts (1G={st.get('onePointGoals')}, 2G={st.get('twoPointGoals')}, A={st.get('assists')}, GB={st.get('groundBalls')}, CT={st.get('causedTurnovers')}, S={st.get('saves')})")
