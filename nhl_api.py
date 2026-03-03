import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# NHL API Base URL
BASE_URL = "https://api-web.nhle.com/v1"

def convert_utc_to_est(utc_str):
    """Converts UTC time string (e.g., 2026-03-01T20:00:00Z) to EST."""
    try:
        # Removing 'Z' if it's there
        utc_str = utc_str.replace('Z', '')
        # Parsing ISO format
        dt_utc = datetime.fromisoformat(utc_str)
        # EST is UTC-5
        dt_est = dt_utc - timedelta(hours=5)
        return dt_est.strftime("%I:%M %p")
    except Exception as e:
        print(f"Error converting time: {e}")
        return utc_str

def get_todays_games():
    # Today's date (dynamically fetched)
    date_str = datetime.now().strftime("%Y-%m-%d")
    url = f"{BASE_URL}/schedule/{date_str}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        games = []
        for game_week in data.get('gameWeek', []):
            if game_week['date'] == date_str:
                for game in game_week.get('games', []):
                    games.append({
                        'id': game['id'],
                        'home': game['homeTeam']['abbrev'],
                        'away': game['awayTeam']['abbrev'],
                        'home_name': game['homeTeam'].get('commonName', {}).get('default', game['homeTeam']['abbrev']),
                        'away_name': game['awayTeam'].get('commonName', {}).get('default', game['awayTeam']['abbrev']),
                        'home_score': game['homeTeam'].get('score', 0),
                        'away_score': game['awayTeam'].get('score', 0),
                        'gameState': game['gameState'],
                        'period': game.get('periodDescriptor', {}).get('number', 0),
                        'periodType': game.get('periodDescriptor', {}).get('periodType', 'REG'),
                        'time': convert_utc_to_est(game['startTimeUTC']),
                        'venue': game.get('venue', {}).get('default', 'N/A')
                    })
        return games
    except Exception as e:
        print(f"Error fetching games: {e}")
        return []

def get_weekly_schedule():
    """Returns games for the entire current week."""
    url = f"{BASE_URL}/schedule/now"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        weekly_games = []
        for game_day in data.get('gameWeek', []):
            date = game_day['date']
            games = []
            for game in game_day.get('games', []):
                games.append({
                    'id': game['id'],
                    'date': date,
                    'home': game['homeTeam']['abbrev'],
                    'away': game['awayTeam']['abbrev'],
                    'home_name': game['homeTeam'].get('commonName', {}).get('default', game['homeTeam']['abbrev']),
                    'away_name': game['awayTeam'].get('commonName', {}).get('default', game['awayTeam']['abbrev']),
                    'time': convert_utc_to_est(game['startTimeUTC']),
                    'venue': game.get('venue', {}).get('default', 'N/A')
                })
            weekly_games.append({
                'date': date,
                'games': games
            })
        return weekly_games
    except Exception as e:
        print(f"Error fetching weekly schedule: {e}")
        return []

def get_standings(date=None):
    if date:
        url = f"{BASE_URL}/standings/{date}"
    else:
        url = f"{BASE_URL}/standings/now"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get('standings', [])
    except Exception as e:
        print(f"Error fetching standings: {e}")
        return []

def get_news():
    """Scrapes NHL news headlines from ESPN and categorizes them."""
    url = "https://www.espn.com/nhl/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    news_items = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        seen_titles = set()
        
        # Search for links that look like news headlines
        for section in soup.find_all('section'):
            for link in section.find_all('a'):
                title = link.get_text().strip()
                
                # Filter for headline-like text (length and relevance)
                if 20 < len(title) < 150 and title not in seen_titles:
                    # Look for keywords to categorize
                    category = "MAJOR NEWS"
                    lower_title = title.lower()
                    
                    if any(kw in lower_title for kw in ['injury', 'injured', 'ir', 'surgery', 'out for', 'leaves game', 'day-to-day']):
                        category = "INJURY"
                    elif any(kw in lower_title for kw in ['fire', 'interim', 'hire', 'coach', 'bench']):
                        category = "COACHING"
                    elif any(kw in lower_title for kw in ['trade', 'acquired', 'deal', 'swap', 'move', 'tracker']):
                        category = "TRADE"
                    elif any(kw in lower_title for kw in ['signing', 'sign', 'extension', 'contract', 'recall', 'assign', 'waive']):
                        category = "TRANSACTION"
                    elif any(kw in lower_title for kw in ['training', 'practice', 'skate', 'camp']):
                        category = "TRAINING"
                    elif any(kw in lower_title for kw in ['suspended', 'suspension', 'fine', 'dps']):
                        category = "DISCIPLINE"
                    
                    # Some headlines might be menu items or ads, we try to filter those out
                    if any(ignore in lower_title for ignore in ['watch', 'listen', 'fantasy', 'espn+', 'app', 'sign up', 'subscribe']):
                        continue

                    news_items.append({
                        "category": category,
                        "title": title,
                        "description": "Click for full story on ESPN.com"
                    })
                    seen_titles.add(title)
                    
                    if len(news_items) >= 10:
                        break
            if len(news_items) >= 10:
                break
                
    except Exception as e:
        print(f"Error scraping news: {e}")
        # Fallback to some hardcoded items if scraping fails entirely
        return [
            {"category": "NEWS", "title": "Real-time news unavailable", "description": "Check your connection or visit NHL.com/news"}
        ]
    
    # If we found nothing, provide fallback
    if not news_items:
        return [{"category": "NEWS", "title": "No major headlines found", "description": "Check back later for updates."}]
        
    return news_items

def get_player_stats():
    # Fetching league leaders for simplicity. 
    # Hardcoded to 20252026 as 'current' doesn't seem to work for this endpoint.
    url = f"{BASE_URL}/skater-stats-leaders/20252026/2" # 2 for Regular Season
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get('goals', []) # Returns list of top goal scorers
    except Exception as e:
        print(f"Error fetching player stats: {e}")
        return []

def get_top_lines():
    # This is complex to fetch directly. We'll use a placeholder or 
    # fetch team roster info if a specific team is selected.
    # For now, general top performers.
    return {
        "oline": ["McDavid", "Draisaitl", "Hyman"],
        "dline": ["Makar", "Toews"],
        "goalie": ["Hellebuyck"]
    }

def get_teams():
    """Returns a sorted list of all team abbreviations and names from the standings."""
    standings = get_standings()
    teams = []
    for team in standings:
        teams.append({
            'abbrev': team['teamAbbrev']['default'],
            'name': team['teamName']['default'],
            'conference': team['conferenceName'],
            'division': team['divisionName'],
            'logo': team['teamLogo']
        })
    return sorted(teams, key=lambda x: x['name'])

def get_team_roster(team_abbrev):
    """Fetches the current roster for a team."""
    url = f"{BASE_URL}/roster/{team_abbrev}/current"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching roster for {team_abbrev}: {e}")
        return {}

def get_player_details(player_id):
    """Fetches detailed info for a player."""
    url = f"{BASE_URL}/player/{player_id}/landing"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching player {player_id}: {e}")
        return {}

def get_head_coaches():
    """Returns a static dictionary of current head coaches (as of early 2026/late 2025)."""
    # Note: These may change during a season. 
    # This list is based on common knowledge/Wikipedia as suggested.
    return {
        "ANA": ("Greg Cronin", "CA"),
        "BOS": ("Joe Sacco (Interim)", "MA"),
        "BUF": ("Lindy Ruff", "NY"),
        "CGY": ("Ryan Huska", "AB"),
        "CAR": ("Rod Brind'Amour", "NC"),
        "CHI": ("Luke Richardson", "IL"),
        "COL": ("Jared Bednar", "CO"),
        "CBJ": ("Dean Evason", "OH"),
        "DAL": ("Pete DeBoer", "TX"),
        "DET": ("Derek Lalonde", "MI"),
        "EDM": ("Kris Knoblauch", "AB"),
        "FLA": ("Paul Maurice", "FL"),
        "LAK": ("Jim Hiller", "CA"),
        "MIN": ("John Hynes", "MN"),
        "MTL": ("Martin St. Louis", "QC"),
        "NSH": ("Andrew Brunette", "TN"),
        "NJ D": ("Sheldon Keefe", "NJ"),
        "NJD": ("Sheldon Keefe", "NJ"),
        "NYI": ("Patrick Roy", "NY"),
        "NYR": ("Peter Laviolette", "NY"),
        "OTT": ("Travis Green", "ON"),
        "PHI": ("John Tortorella", "PA"),
        "PIT": ("Mike Sullivan", "PA"),
        "SJS": ("Ryan Warsofsky", "CA"),
        "SEA": ("Dan Bylsma", "WA"),
        "STL": ("Drew Bannister", "MO"),
        "TBL": ("Jon Cooper", "FL"),
        "TOR": ("Craig Berube", "ON"),
        "UTA": ("André Tourigny", "UT"),
        "VAN": ("Rick Tocchet", "BC"),
        "VGK": ("Bruce Cassidy", "NV"),
        "WSH": ("Spencer Carbery", "DC"),
        "WPG": ("Scott Arniel", "MB")
    }

def get_game_boxscore(game_id):
    """Fetches the boxscore/game stats for a specific game."""
    url = f"{BASE_URL}/gamecenter/{game_id}/boxscore"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching boxscore for game {game_id}: {e}")
        return {}

def get_team_schedule(team_abbrev, season="20252026"):
    """Fetches the full season schedule for a specific team."""
    url = f"{BASE_URL}/club-schedule-season/{team_abbrev}/{season}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        games = []
        for game in data.get('games', []):
            games.append({
                'id': game['id'],
                'date': game['gameDate'],
                'home': game['homeTeam']['abbrev'],
                'away': game['awayTeam']['abbrev'],
                'home_name': game['homeTeam'].get('commonName', {}).get('default', game['homeTeam']['abbrev']),
                'away_name': game['awayTeam'].get('commonName', {}).get('default', game['awayTeam']['abbrev']),
                'home_score': game['homeTeam'].get('score', 0),
                'away_score': game['awayTeam'].get('score', 0),
                'gameState': game['gameState'],
                'time': convert_utc_to_est(game['startTimeUTC']),
                'venue': game.get('venue', {}).get('default', 'N/A')
            })
        return games
    except Exception as e:
        print(f"Error fetching schedule for {team_abbrev}: {e}")
        return []

if __name__ == "__main__":
    print("Testing NHL API Fetcher...")
    games = get_todays_games()
    print(f"Games today: {games}")
    
    standings = get_standings()
    print(f"Standings count: {len(standings)}")
    if standings:
        print(f"First team in standings: {standings[0]['teamAbbrev']['default']} - {standings[0]['points']} pts")
