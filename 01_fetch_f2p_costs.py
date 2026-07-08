import argparse
import requests
import json
import os

SEASON_FILE = "f2p_2026_season.json"

def fetch_costs(week):
    url = f"https://f2p.premierlacrosseleague.com/api/pll/v4/fantasy/players/week/{week}"
    headers = {
        'accept': '*/*',
        'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
        'cache-control': 'no-store',
        'pragma': 'no-cache',
        'referer': 'https://f2p.premierlacrosseleague.com/fantasy/players/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36'
    }
    
    print(f"Fetching player costs from F2P API (week {week})...")
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        res_json = r.json()
        new_data = res_json.get("data", {}).get("items", [])
    except Exception as e:
        print(f"Error fetching data: {e}")
        return

    # Tag each record with its week number
    for record in new_data:
        record["week"] = week

    # Load existing season data
    if os.path.exists(SEASON_FILE):
        with open(SEASON_FILE, "r", encoding="utf-8") as f:
            season_data = json.load(f)
    else:
        season_data = []

    # Upsert: deduplicate on officialId + eventId
    existing_keys = {
        (r.get("officialId"), r.get("eventId")): i
        for i, r in enumerate(season_data)
    }

    added, updated = 0, 0
    for record in new_data:
        key = (record.get("officialId"), record.get("eventId"))
        if key in existing_keys:
            season_data[existing_keys[key]] = record
            updated += 1
        else:
            existing_keys[key] = len(season_data)
            season_data.append(record)
            added += 1

    with open(SEASON_FILE, "w", encoding="utf-8") as f:
        json.dump(season_data, f, indent=2)

    # Also keep f2p_weekly_data.json pointing at the current week for combine_datasets.py
    with open("f2p_weekly_data.json", "w", encoding="utf-8") as f:
        json.dump(new_data, f, indent=2)

    weeks_in_file = len({r.get("week") for r in season_data})
    print(f"Week {week}: {added} added, {updated} updated.")
    print(f"Season file now has {len(season_data)} records across {weeks_in_file} week(s).")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", type=int, required=True, help="Week number to fetch")
    args = parser.parse_args()
    fetch_costs(args.week)
