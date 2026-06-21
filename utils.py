import re
import math

def normalize_event_id(event_id):
    """
    Normalizes legacy PLL event IDs (2023-2024) to the modern format (2025+).
    Standard Format: YYYY_game_N, YYYY_quarterfinal_N, YYYY_semifinal_N, YYYY_championship_game
    """
    if not event_id:
        return event_id

    # 1. Legacy Regular Season: game-N-YYYY-MM-DD -> YYYY_game_N
    match = re.match(r"game-(\d+)-(\d{4})-\d{1,2}-\d{1,2}", event_id)
    if match:
        game_num, year = match.groups()
        return f"{year}_game_{game_num}"

    # 2. Legacy Playoffs: playoffs-type-N-YYYY-MM-DD -> YYYY_type_N
    match = re.match(r"playoffs-([a-z]+)-(\d+)-(\d{4})-\d{1,2}-\d{1,2}", event_id)
    if match:
        p_type, p_num, year = match.groups()
        return f"{year}_{p_type}_{p_num}"

    # 3. Legacy Championship: championship-YYYY-MM-DD -> YYYY_championship_game
    match = re.match(r"championship-(\d{4})-\d{1,2}-\d{1,2}", event_id)
    if match:
        year = match.group(1)
        return f"{year}_championship_game"

    # 4. Modern Cleanup: e.g., 2025_championship -> 2025_championship_game
    if "championship" in event_id and "game" not in event_id:
        parts = event_id.split('_')
        if len(parts) >= 2:
            # Check if it looks like YYYY_championship
            if len(parts[0]) == 4 and parts[0].isdigit():
                return f"{parts[0]}_championship_game"

    return event_id

def get_week_for_event(event_id):
    """
    Calculates the Fantasy Week (1-15) based on the standardized event ID.
    Accounts for skipped game IDs in the legacy 2023-2025 data.
    """
    if not event_id:
        return None
    
    # Standardize first to be safe
    eid = normalize_event_id(event_id)
    
    # Extract year if present
    year = None
    match_year = re.search(r"^(\d{4})_", eid)
    if match_year:
        year = int(match_year.group(1))
    
    # Playoffs
    if "quarterfinal" in eid: 
        return 13 if year == 2026 else 12
    if "semifinal" in eid: 
        return 14 if year == 2026 else 13
    if "championship" in eid: 
        return 15 if year == 2026 else 14
    
    # Regular Season
    match = re.search(r"(\d{4})_game_(\d+)", eid)
    if match:
        year = int(match.group(1))
        game_num = int(match.group(2))
        
        if year == 2026:
            if game_num <= 4: return 1
            elif game_num <= 8: return 2
            elif game_num <= 12: return 3
            elif game_num <= 16: return 4
            elif game_num <= 19: return 5
            elif game_num <= 23: return 6
            elif game_num <= 27: return 7
            elif game_num <= 31: return 8
            elif game_num <= 36: return 9
            elif game_num <= 41: return 10
            elif game_num <= 45: return 11
            elif game_num <= 48: return 12
            
        if game_num <= 20:
            return math.ceil(game_num / 4)
        else:
            # Shift back based on known gaps to normalize to a 40-game sequence
            # 2023/2025 skip [21, 22], 2024 skips [21]
            offset = 0
            if year in [2023, 2025] and game_num >= 23:
                offset = 2
            elif year == 2024 and game_num >= 22:
                offset = 1
            
            normalized_num = game_num - offset
            return math.ceil(normalized_num / 4) + 1
            
    return None

