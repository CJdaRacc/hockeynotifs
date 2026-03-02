import dearpygui.dearpygui as dpg
import nhl_api
from win10toast_persist import ToastNotifier
import threading
import time
import requests
import io
import sys
import json
import os
from datetime import datetime
from pystray import Icon, Menu, MenuItem
from PIL import Image
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM

# Today's date is 2026-03-02
APP_TITLE = "NHL Hockey Notifier"

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Global state
SETTINGS_FILE = resource_path("settings.json")

default_settings = {
    "show_comparative": False,
    "show_news": False,
    "show_top_lines": False,
    "show_player_stats": False,
    "notify_starts": False,
    "notify_goals": False,
    "notify_daily": False,
    "theme": {
        "text": [255, 255, 255, 255],
        "background": [30, 30, 30, 255],
        "active_tab": [45, 45, 48, 255],
        "button": [60, 60, 65, 255],
        "header": [51, 51, 55, 255],
        "rounding": 5.0,
        "padding": 8.0,
        "font_scale": 1.0
    },
    "layout": {
        "teams_split": 0.5,
        "dashboard_heights": {
            "comp_standings_window": 200,
            "news_window": 120,
            "top_lines_window": 80,
            "stats_window": 120,
            "notif_settings_window": 160,
            "games_list": 120,
            "weekly_games_list": 180
        }
    }
}

settings = default_settings.copy()

def save_settings():
    """Saves the current settings to a JSON file."""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False

def load_settings():
    """Loads settings from a JSON file, merging with defaults."""
    global settings
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                loaded_settings = json.load(f)
                # Deep merge for theme dictionary
                for key, value in loaded_settings.items():
                    if key == "theme" and isinstance(value, dict):
                        settings["theme"].update(value)
                    else:
                        settings[key] = value
                
                # Deep merge for layout dictionary
                if "layout" in loaded_settings and isinstance(loaded_settings["layout"], dict):
                    if "layout" not in settings: settings["layout"] = {}
                    for k, v in loaded_settings["layout"].items():
                        if k == "dashboard_heights" and isinstance(v, dict):
                            if "dashboard_heights" not in settings["layout"]: settings["layout"]["dashboard_heights"] = {}
                            settings["layout"]["dashboard_heights"].update(v)
                        else:
                            settings["layout"][k] = v
        except Exception as e:
            print(f"Error loading settings: {e}")

# Initial load from file
load_settings()

cached_data = {
    "teams": [],
    "coaches": {},
    "selected_team": None,
    "selected_player": None,
    "roster": {},
    "textures": {}, # Store texture tags: url -> tag
    "last_game_states": {} # game_id -> {score, state}
}

def load_image_to_texture(url, is_svg=False):
    """Downloads an image, converts if necessary, and loads it into a DPG texture."""
    if url in cached_data["textures"]:
        return cached_data["textures"][url]
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        img_data = response.content
        
        if is_svg:
            # Convert SVG to PNG using svglib and reportlab
            drawing = svg2rlg(io.BytesIO(img_data))
            out = io.BytesIO()
            renderPM.drawToFile(drawing, out, fmt="PNG")
            img_data = out.getvalue()
            
        img = Image.open(io.BytesIO(img_data)).convert("RGBA")
        width, height = img.size
        
        # Flatten image data for DPG: [R, G, B, A, R, G, B, A, ...]
        # img.getdata() returns a sequence of (R, G, B, A) tuples.
        # We need a flat list of floats from 0.0 to 1.0.
        # Use getdata() and flatten explicitly to avoid Pillow 14 deprecation
        pixels = list(img.getdata())
        data = []
        for p in pixels:
            for c in p:
                data.append(c / 255.0)
            
        texture_tag = f"texture_{url}"
        dpg.add_static_texture(width=width, height=height, default_value=data, tag=texture_tag, parent="main_texture_registry")
            
        cached_data["textures"][url] = texture_tag
        return texture_tag
    except Exception as e:
        print(f"Error loading image {url}: {e}")
        return None

def notify_games_async():
    # Run notification in a separate thread to avoid freezing the GUI
    threading.Thread(target=notify_games, daemon=True).start()

def notify_games():
    toaster = ToastNotifier()
    games = nhl_api.get_todays_games()
    coaches = nhl_api.get_head_coaches()
    if games:
        lines = []
        for g in games[:5]:
            state_abbrev = coaches.get(g['home'], (None, "N/A"))[1]
            lines.append(f"{g['away_name']} @ {g['home_name']} - {g['time']} at {g['venue']}, {state_abbrev}")
        
        msg = "\n".join(lines)
        if len(games) > 5:
            msg += f"\n...and {len(games)-5} more."
        toaster.show_toast("NHL Today's Games", msg, duration=10)
    else:
        toaster.show_toast("NHL Today's Games", "No games today.", duration=10)

def test_toast_notification_async():
    """Runs a test notification in a separate thread."""
    threading.Thread(target=test_toast_notification, daemon=True).start()

def test_toast_notification():
    """Sends a simple test toast to verify the notification system."""
    try:
        toaster = ToastNotifier()
        toaster.show_toast(
            "NHL Notifier - Test",
            "This is a test notification to verify your desktop toast settings are working correctly!",
            duration=5
        )
    except Exception as e:
        print(f"Error sending test notification: {e}")

def notification_loop():
    """Background loop to check for live updates and send notifications."""
    toaster = ToastNotifier()
    coaches = nhl_api.get_head_coaches()
    while True:
        try:
            if settings["notify_starts"] or settings["notify_goals"]:
                games = nhl_api.get_todays_games()
                for g in games:
                    game_id = g['id']
                    prev = cached_data["last_game_states"].get(game_id)
                    
                    if not prev:
                        cached_data["last_game_states"][game_id] = {
                            'state': g['gameState'],
                            'away_score': g['away_score'],
                            'home_score': g['home_score']
                        }
                        continue

                    # Check for game start
                    if settings["notify_starts"] and prev['state'] in ['PRE', 'FUT'] and g['gameState'] in ['LIVE', 'CRIT']:
                        state_abbrev = coaches.get(g['home'], (None, "N/A"))[1]
                        msg = f"{g['away_name']} vs {g['home_name']} is now LIVE!\nTime: {g['time']}\nVenue: {g['venue']}, {state_abbrev}"
                        toaster.show_toast("NHL Game Started", msg, duration=5)
                    
                    # Check for goals
                    if settings["notify_goals"]:
                        if g['away_score'] > prev['away_score']:
                            toaster.show_toast("GOAL! (NHL)", f"{g['away_name']} scored! {g['away_name']} {g['away_score']} - {g['home_name']} {g['home_score']}", duration=5)
                        elif g['home_score'] > prev['home_score']:
                            toaster.show_toast("GOAL! (NHL)", f"{g['home_name']} scored! {g['away_name']} {g['away_score']} - {g['home_name']} {g['home_score']}", duration=5)

                    # Update cache
                    cached_data["last_game_states"][game_id] = {
                        'state': g['gameState'],
                        'away_score': g['away_score'],
                        'home_score': g['home_score']
                    }
            
            # Update frequency to 20 seconds as requested
            time.sleep(20) 
        except Exception as e:
            print(f"Error in notification loop: {e}")
            time.sleep(10)

def update_team_info(sender, app_data):
    """Updates the team tab when a team is selected."""
    print(f"DEBUG: update_team_info called for {app_data}")
    team_name = app_data
    team = next((t for t in cached_data["teams"] if t['name'] == team_name), None)
    if not team:
        print(f"DEBUG: Team '{team_name}' not found in cached_data")
        return
    
    cached_data["selected_team"] = team
    team_abbrev = team['abbrev']
    
    # Update Coach
    coach_info = cached_data["coaches"].get(team_abbrev, ("Unknown", "N/A"))
    coach = coach_info[0]
    dpg.set_value("team_coach_text", f"Head Coach: {coach}")
    dpg.set_value("team_info_text", f"Team: {team['name']} ({team_abbrev}) | {team['conference']} | {team['division']}")

    # Update Logo (Show placeholder while loading)
    dpg.configure_item("team_logo_img", texture_tag="placeholder_tex", show=True)
    if team.get('logo'):
        def _load_logo():
            print(f"DEBUG: Loading team logo from {team['logo']}")
            tex = load_image_to_texture(team['logo'], is_svg=True)
            if tex:
                dpg.configure_item("team_logo_img", texture_tag=tex)
        threading.Thread(target=_load_logo, daemon=True).start()

    # Update Roster
    print(f"DEBUG: Fetching roster for {team_abbrev}")
    roster = nhl_api.get_team_roster(team_abbrev)
    cached_data["roster"] = roster
    
    # Update Player Dropdown for the Player tab
    all_players = []
    for pos in ['forwards', 'defensemen', 'goalies']:
        for p in roster.get(pos, []):
            all_players.append(f"{p['firstName']['default']} {p['lastName']['default']} ({p['id']})")
    
    dpg.configure_item("player_select", items=sorted(all_players))
    
    # Display roster in the team tab
    try:
        # We delete all rows by deleting everything and then re-adding the columns.
        # This is because in DPG, table columns are also children of the table.
        dpg.delete_item("team_roster_table", children_only=True)
        dpg.configure_item("team_roster_table", sortable=True, callback=sort_callback)
        dpg.add_table_column(label="Player", parent="team_roster_table")
        dpg.add_table_column(label="Pos", parent="team_roster_table")
        dpg.add_table_column(label="No", parent="team_roster_table")
        dpg.add_table_column(label="Actions", parent="team_roster_table", no_sort=True)

        for pos in ['forwards', 'defensemen', 'goalies']:
            # Sort players by name within each category for better UX
            players = sorted(roster.get(pos, []), key=lambda x: (x['firstName']['default'], x['lastName']['default']))
            for p in players:
                with dpg.table_row(parent="team_roster_table"):
                    dpg.add_text(f"{p['firstName']['default']} {p['lastName']['default']}")
                    dpg.add_text(p.get('positionCode', 'N/A'))
                    dpg.add_text(str(p.get('sweaterNumber', '??')))
                    dpg.add_button(label="View Stats", user_data=p['id'], callback=lambda s, a, u: select_player_by_id(u))
    except Exception as e:
        print(f"Error updating roster table: {e}")

def select_player_by_id(player_id):
    """Selects a player and switches to the player tab."""
    print(f"DEBUG: select_player_by_id called for {player_id}")
    # Find player in current roster to get name for dropdown
    player_name = None
    if not cached_data["roster"]:
        print("DEBUG: cached_data['roster'] is empty")
    
    for pos in ['forwards', 'defensemen', 'goalies']:
        for p in cached_data["roster"].get(pos, []):
            if p['id'] == player_id:
                player_name = f"{p['firstName']['default']} {p['lastName']['default']} ({p['id']})"
                break
        if player_name: break
    
    if player_name:
        print(f"DEBUG: Selecting player {player_name}")
        dpg.set_value("player_select", player_name)
        update_player_info(None, player_name)
        # Switch to the tab containing players (which is now Teams & Players)
        print("DEBUG: Switching to tab_teams_players")
        dpg.set_value("main_tabs", "tab_teams_players")
        # Ensure the player child window is visible if it was hidden or collapsed
        if dpg.does_item_exist("players_child_window"):
            dpg.show_item("players_child_window")
    else:
        print(f"DEBUG: Player {player_id} not found in cached_data['roster']")

def update_player_info(sender, app_data):
    """Updates the player tab when a player is selected."""
    print(f"DEBUG: update_player_info called for {app_data}")
    if not app_data: return
    # Extract ID from "Name (ID)"
    try:
        player_id = int(app_data.split('(')[-1].split(')')[0])
    except Exception as e:
        print(f"DEBUG: Error extracting player_id from '{app_data}': {e}")
        return
    
    try:
        dpg.set_value("player_stats_text", "Loading stats...")
        print(f"DEBUG: Fetching details for player {player_id}")
        player = nhl_api.get_player_details(player_id)
        if not player:
            print(f"DEBUG: No data returned for player {player_id}")
            dpg.set_value("player_stats_text", "Error fetching player data.")
            return
        
        first_name = player.get('firstName', {}).get('default', '')
        last_name = player.get('lastName', {}).get('default', '')
        print(f"DEBUG: Setting player name to {first_name} {last_name}")
        dpg.set_value("player_name_text", f"{first_name} {last_name}")
        
        bio = (f"Team: {player.get('fullTeamName', 'N/A')} | Position: {player.get('position', 'N/A')} | Number: #{player.get('sweaterNumber', 'N/A')}\n"
               f"Birthplace: {player.get('birthCity', {}).get('default', '')}, {player.get('birthCountry', 'N/A')} | Height: {player.get('heightInInches', 'N/A')}\" | Weight: {player.get('weightInPounds', 'N/A')} lbs")
        print(f"DEBUG: Setting player bio: {bio}")
        dpg.set_value("player_bio_text", bio)
        
        # Update Player Image (Show placeholder while loading)
        dpg.configure_item("player_img", texture_tag="placeholder_tex", show=True)
        headshot_url = player.get('headshot')
        if headshot_url:
            def _load_headshot():
                print(f"DEBUG: Loading headshot from {headshot_url}")
                tex = load_image_to_texture(headshot_url, is_svg=False)
                if tex:
                    print(f"DEBUG: Successfully loaded texture {tex} for headshot")
                    dpg.configure_item("player_img", texture_tag=tex)
                else:
                    print(f"DEBUG: Failed to load texture for headshot")
            threading.Thread(target=_load_headshot, daemon=True).start()
        
        # Stats
        stats = player.get('featuredStats', {}).get('regularSeason', {}).get('subSeason', {})
        if stats:
            if player.get('position') == 'G':
                s_text = f"Season Stats: GAA: {stats.get('gaa', 'N/A')} | SV%: {stats.get('savePctg', 'N/A')} | Wins: {stats.get('wins', 'N/A')}"
            else:
                s_text = f"Season Stats: Goals: {stats.get('goals', 'N/A')} | Assists: {stats.get('assists', 'N/A')} | Points: {stats.get('points', 'N/A')}"
            print(f"DEBUG: Setting player stats: {s_text}")
            dpg.set_value("player_stats_text", s_text)
        else:
            print("DEBUG: No featured stats found in player data")
            dpg.set_value("player_stats_text", "No season stats available.")
    except Exception as e:
        print(f"Error in update_player_info: {e}")
        dpg.set_value("player_stats_text", f"Error: {e}")

def update_schedule_info(sender, app_data):
    """Updates the full schedule tab when a team is selected."""
    print(f"DEBUG: update_schedule_info called for {app_data}")
    team_name = app_data
    team = next((t for t in cached_data["teams"] if t['name'] == team_name), None)
    if not team:
        return
    
    team_abbrev = team['abbrev']
    try:
        schedule = nhl_api.get_team_schedule(team_abbrev)
        
        # Clear and re-init tables
        for table_tag in ["upcoming_schedule_table", "past_schedule_table"]:
            dpg.delete_item(table_tag, children_only=True)
            dpg.add_table_column(label="Date", parent=table_tag)
            dpg.add_table_column(label="Away", parent=table_tag)
            dpg.add_table_column(label="Home", parent=table_tag)
            dpg.add_table_column(label="Result/Time", parent=table_tag)
            dpg.add_table_column(label="Venue", parent=table_tag)

        # Partition games
        # gameStates like 'OFF', 'FINAL' are past. 'LIVE', 'CRIT' are active (putting in upcoming for visibility)
        past_games = []
        upcoming_games = []
        
        for g in schedule:
            if g['gameState'] in ['OFF', 'FINAL']:
                past_games.append(g)
            else:
                upcoming_games.append(g)

        # Populate Upcoming
        for g in upcoming_games:
            with dpg.table_row(parent="upcoming_schedule_table"):
                dpg.add_text(g['date'])
                dpg.add_text(g['away_name'])
                dpg.add_text(g['home_name'])
                res_time = f"LIVE: {g['away_score']} - {g['home_score']}" if g['gameState'] in ['LIVE', 'CRIT'] else f"{g['time']} EST"
                dpg.add_text(res_time)
                dpg.add_text(g['venue'])
        
        # Populate Past (Sorted by date descending so most recent is on top)
        for g in sorted(past_games, key=lambda x: x['date'], reverse=True):
            with dpg.table_row(parent="past_schedule_table"):
                dpg.add_text(g['date'])
                dpg.add_text(g['away_name'])
                dpg.add_text(g['home_name'])
                res_time = f"{g['away_score']} - {g['home_score']}"
                dpg.add_text(res_time)
                dpg.add_text(g['venue'])

    except Exception as e:
        print(f"Error updating schedule tables: {e}")

def show_game_stats(game_id):
    """Fetches and displays boxscore stats for a game."""
    try:
        box = nhl_api.get_game_boxscore(game_id)
        if not box: return
        
        dpg.show_item("game_stats_window")
        dpg.delete_item("game_stats_list", children_only=True)
        
        home = box.get('homeTeam', {}).get('abbrev', 'HOME')
        away = box.get('awayTeam', {}).get('abbrev', 'AWAY')
        h_score = box.get('homeTeam', {}).get('score', 0)
        a_score = box.get('awayTeam', {}).get('score', 0)
        
        dpg.add_text(f"Game Summary: {away} {a_score} - {home} {h_score}", parent="game_stats_list", color=[100, 255, 100])
        
        # Player Stats
        stats = box.get('playerByGameStats', {})
        for side, team_stats in [("Away", stats.get('awayTeam', {})), ("Home", stats.get('homeTeam', {}))]:
            team_abbrev = away if side == "Away" else home
            dpg.add_text(f"\n--- {side} Team: {team_abbrev} ---", parent="game_stats_list", color=[255, 200, 0])
            
            # Skaters
            skaters = team_stats.get('forwards', []) + team_stats.get('defense', [])
            if skaters:
                with dpg.table(header_row=True, parent="game_stats_list", sortable=True, callback=sort_callback):
                    dpg.add_table_column(label="Skater")
                    dpg.add_table_column(label="G")
                    dpg.add_table_column(label="A")
                    dpg.add_table_column(label="PTS")
                    dpg.add_table_column(label="SOG")
                    dpg.add_table_column(label="TOI")
                    
                    for p in sorted(skaters, key=lambda x: x['points'], reverse=True):
                        if p['points'] > 0 or p['sog'] > 0:
                            with dpg.table_row():
                                dpg.add_text(f"{p['name']['default']} (#{p['sweaterNumber']})")
                                dpg.add_text(str(p['goals']))
                                dpg.add_text(str(p['assists']))
                                dpg.add_text(str(p['points']))
                                dpg.add_text(str(p['sog']))
                                dpg.add_text(p['toi'])
                                
            # Goalies
            goalies = team_stats.get('goalies', [])
            if goalies:
                dpg.add_text("Goalies:", parent="game_stats_list")
                with dpg.table(header_row=True, parent="game_stats_list", sortable=True, callback=sort_callback):
                    dpg.add_table_column(label="Goalie")
                    dpg.add_table_column(label="SA")
                    dpg.add_table_column(label="SV")
                    dpg.add_table_column(label="SV%")
                    dpg.add_table_column(label="TOI")
                    
                    for g in goalies:
                        with dpg.table_row():
                            dpg.add_text(f"{g['name']['default']} (#{g['sweaterNumber']})")
                            dpg.add_text(str(g['shotsAgainst']))
                            dpg.add_text(str(g['saves']))
                            dpg.add_text(f"{g['savePctg']:.3f}" if isinstance(g['savePctg'], (int, float)) else str(g['savePctg']))
                            dpg.add_text(g['toi'])

    except Exception as e:
        print(f"Error showing game stats: {e}")

def refresh_data():
    try:
        # Check for daily notification on refresh if enabled and not yet sent today
        if settings.get("notify_daily"):
            today = "2026-03-01" # In a real app, this would be datetime.now().date()
            if cached_data.get("last_daily_notify") != today:
                notify_games_async()
                cached_data["last_daily_notify"] = today

        # Fetch shared data once
        standings = nhl_api.get_standings()
        
        # Cache teams and coaches for dropdowns
        if not cached_data["teams"]:
            cached_data["teams"] = nhl_api.get_teams()
            cached_data["coaches"] = nhl_api.get_head_coaches()
            team_names = [t['name'] for t in cached_data["teams"]]
            dpg.configure_item("team_select", items=team_names)
            dpg.configure_item("schedule_team_select", items=team_names)

        # Today's games
        games = nhl_api.get_todays_games()
        dpg.delete_item("games_list", children_only=True)
        if games:
            for g in games:
                status = ""
                if g['gameState'] in ['LIVE', 'CRIT']:
                    status = f" | {g['away_score']} - {g['home_score']} ({g['period']} {g['periodType']})"
                elif g['gameState'] in ['OFF', 'FINAL']:
                    status = f" | FINAL: {g['away_score']} - {g['home_score']}"
                
                with dpg.group(horizontal=True, parent="games_list"):
                    dpg.add_text(f"{g['away_name']} @ {g['home_name']} ({g['time']} EST){status}")
                    dpg.add_button(label="View Game Stats", user_data=g['id'], callback=lambda s, a, u: show_game_stats(u))
        else:
            dpg.add_text("No games today.", parent="games_list")

        # Weekly games
        weekly_schedule = nhl_api.get_weekly_schedule()
        dpg.delete_item("weekly_games_list", children_only=True)
        today_date = "2026-03-01"
        found_upcoming = False
        if weekly_schedule:
            for day in weekly_schedule:
                if day['date'] <= today_date:
                    continue # Skip past and today (already shown above)
                
                if day['games']:
                    found_upcoming = True
                    # Format date for display: 2026-03-02 -> March 02
                    dt = datetime.strptime(day['date'], "%Y-%m-%d")
                    date_display = dt.strftime("%A, %b %d")
                    dpg.add_text(f"--- {date_display} ---", color=[255, 200, 0], parent="weekly_games_list")
                    for g in day['games']:
                        dpg.add_text(f"  {g['away_name']} @ {g['home_name']} ({g['time']} EST) at {g['venue']}", parent="weekly_games_list")
        
        if not found_upcoming:
            dpg.add_text("No upcoming games this week.", parent="weekly_games_list")

        # Full Standings Tab
        try:
            dpg.delete_item("full_standings_table", children_only=True)
            dpg.configure_item("full_standings_table", sortable=True, callback=sort_callback)
            dpg.add_table_column(label="Team", parent="full_standings_table")
            dpg.add_table_column(label="GP", parent="full_standings_table")
            dpg.add_table_column(label="W", parent="full_standings_table")
            dpg.add_table_column(label="L", parent="full_standings_table")
            dpg.add_table_column(label="OTL", parent="full_standings_table")
            dpg.add_table_column(label="PTS", parent="full_standings_table")
            dpg.add_table_column(label="Conf", parent="full_standings_table")
            dpg.add_table_column(label="Div", parent="full_standings_table")

            # Group by division
            divisions = {}
            for team in standings:
                div = team['divisionName']
                conf = team['conferenceName']
                full_div_title = f"{conf} Conference - {div} Division"
                if full_div_title not in divisions:
                    divisions[full_div_title] = []
                divisions[full_div_title].append(team)

            # Sort divisions alphabetically or use a specific order if desired
            for div_name in sorted(divisions.keys()):
                # Division Header row
                with dpg.table_row(parent="full_standings_table"):
                    # Use a group or just spans for the header
                    dpg.add_text(f"--- {div_name} ---", color=[255, 200, 0])
                    for _ in range(7): dpg.add_text("") # Empty cells for other columns

                # Sort teams in division by points (descending)
                div_teams = sorted(divisions[div_name], key=lambda x: x['points'], reverse=True)
                for team in div_teams:
                    with dpg.table_row(parent="full_standings_table"):
                        dpg.add_text(team['teamName']['default']) # Use full team name
                        dpg.add_text(str(team['gamesPlayed']))
                        dpg.add_text(str(team['wins']))
                        dpg.add_text(str(team['losses']))
                        dpg.add_text(str(team['otLosses']))
                        dpg.add_text(str(team['points']))
                        dpg.add_text(team['conferenceName'])
                        dpg.add_text(team['divisionName'])
        except Exception as e:
            print(f"Error updating full standings table: {e}")

        # Comparative Standings
        if settings["show_comparative"]:
            dpg.show_item("comp_standings_window")
            dpg.show_item("comp_standings_sep")
            # Fetch historical standings (end of previous regular season: 2024-04-18)
            hist_date = "2024-04-18"
            standings_prev = nhl_api.get_standings(date=hist_date)
            
            # Create a map of team abbrev to historical points
            hist_pts = {t['teamAbbrev']['default']: t['points'] for t in standings_prev}
            
            try:
                dpg.delete_item("comp_standings_table", children_only=True)
                dpg.configure_item("comp_standings_table", sortable=True, callback=sort_callback)
                dpg.add_table_column(label="Team", parent="comp_standings_table")
                dpg.add_table_column(label=f"PTS (24-25)", parent="comp_standings_table")
                dpg.add_table_column(label="Current PTS", parent="comp_standings_table")
                dpg.add_table_column(label="+/-", parent="comp_standings_table")

                # Show comparison for all current teams
                for team in sorted(standings, key=lambda x: x['points'], reverse=True):
                    abbrev = team['teamAbbrev']['default']
                    curr_pts = team['points']
                    prev_pts = hist_pts.get(abbrev, 0)
                    diff = curr_pts - prev_pts
                    diff_str = f"+{diff}" if diff > 0 else str(diff)
                    
                    with dpg.table_row(parent="comp_standings_table"):
                        dpg.add_text(team['teamName']['default'])
                        dpg.add_text(str(prev_pts))
                        dpg.add_text(str(curr_pts))
                        
                        # Color code the difference
                        color = [100, 255, 100] if diff > 0 else ([255, 100, 100] if diff < 0 else [200, 200, 200])
                        dpg.add_text(diff_str, color=color)
            except Exception as e:
                print(f"Error updating comparative standings table: {e}")
        else:
            dpg.hide_item("comp_standings_window")
            dpg.hide_item("comp_standings_sep")

        # News
        if settings["show_news"]:
            dpg.show_item("news_window")
            dpg.show_item("news_sep")
            news = nhl_api.get_news()
            dpg.delete_item("news_list", children_only=True)
            for item in news:
                width = dpg.get_viewport_width()
                # Use a specific color for the category tag
                cat_color = [255, 100, 100] if "INJURY" in item.get('category', '') else ([100, 200, 255] if "TRADE" in item.get('category', '') else [200, 255, 100])
                
                with dpg.group(parent="news_list"):
                    dpg.add_text(f"[{item.get('category', 'NEWS')}] {item['title']}", color=cat_color, bullet=True, wrap=width-40)
                    dpg.add_text(item['description'], wrap=width-60)
                    dpg.add_spacer(height=5)
        else:
            dpg.hide_item("news_window")
            dpg.hide_item("news_sep")

        # Top Lines / Players
        if settings["show_top_lines"]:
            dpg.show_item("top_lines_window")
            dpg.show_item("top_lines_sep")
            lines = nhl_api.get_top_lines()
            dpg.set_value("oline_text", f"O-Line: {', '.join(lines['oline'])}")
            dpg.set_value("dline_text", f"D-Line: {', '.join(lines['dline'])}")
            dpg.set_value("goalie_text", f"Goalie: {', '.join(lines['goalie'])}")
        else:
            dpg.hide_item("top_lines_window")
            dpg.hide_item("top_lines_sep")

        # Player Stats
        if settings["show_player_stats"]:
            dpg.show_item("stats_window")
            dpg.show_item("stats_sep")
            stats = nhl_api.get_player_stats()
            dpg.delete_item("stats_list", children_only=True)
            for player in stats:
                dpg.add_text(f"{player['firstName']['default']} {player['lastName']['default']} - {player['value']} goals", parent="stats_list")
        else:
            dpg.hide_item("stats_window")
            dpg.hide_item("stats_sep")
    except Exception as e:
        print(f"Error in refresh_data: {e}")

def toggle_setting(sender, app_data, user_data):
    settings[user_data] = app_data
    save_settings()
    on_viewport_resize()

def update_theme(sender, app_data, user_data):
    """Updates the global theme based on color picker input."""
    settings["theme"][user_data] = app_data
    apply_theme()

def apply_theme():
    """Applies the current theme colors and styles to the application."""
    with dpg.theme() as global_theme:
        with dpg.theme_component(dpg.mvAll):
            # Colors
            dpg.add_theme_color(dpg.mvThemeCol_Text, settings["theme"]["text"], category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, settings["theme"]["background"], category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, settings["theme"]["background"], category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_TabActive, settings["theme"]["active_tab"], category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_Button, settings["theme"]["button"], category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_Header, settings["theme"]["header"], category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, settings["theme"]["header"], category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, settings["theme"]["header"], category=dpg.mvThemeCat_Core)
            
            # Styles
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, settings["theme"]["rounding"], category=dpg.mvThemeCat_Core)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, settings["theme"]["rounding"], category=dpg.mvThemeCat_Core)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, settings["theme"]["padding"], settings["theme"]["padding"], category=dpg.mvThemeCat_Core)
    
    dpg.bind_theme(global_theme)
    # Font scale is applied separately via set_global_font_scale
    dpg.set_global_font_scale(settings["theme"]["font_scale"])

    # Create a specific theme for resize handles to make them more visible
    with dpg.theme(tag="resize_handle_theme"):
        with dpg.theme_component(dpg.mvButton):
            # Slightly lighter/distinct background for the handle
            dpg.add_theme_color(dpg.mvThemeCol_Button, [60, 60, 60], category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, [80, 80, 80], category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, [100, 100, 100], category=dpg.mvThemeCat_Core)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 3, category=dpg.mvThemeCat_Core)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 0, category=dpg.mvThemeCat_Core)

def reset_theme():
    """Resets the theme to default values."""
    settings["theme"] = default_settings["theme"].copy()
    # Update UI pickers
    dpg.set_value("color_picker_text", settings["theme"]["text"])
    dpg.set_value("color_picker_bg", settings["theme"]["background"])
    dpg.set_value("color_picker_active_tab", settings["theme"]["active_tab"])
    dpg.set_value("color_picker_button", settings["theme"]["button"])
    dpg.set_value("color_picker_header", settings["theme"]["header"])
    dpg.set_value("slider_rounding", settings["theme"]["rounding"])
    dpg.set_value("slider_padding", settings["theme"]["padding"])
    dpg.set_value("slider_font_scale", settings["theme"]["font_scale"])
    apply_theme()
    save_settings()

def save_theme_callback():
    """Callback for the 'Save Theme Settings' button."""
    # Check if font scale changed compared to what's in settings.json (if it exists)
    needs_restart = False
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                saved = json.load(f)
                old_font_scale = saved.get("theme", {}).get("font_scale", 1.0)
                if abs(settings["theme"]["font_scale"] - old_font_scale) > 0.01:
                    needs_restart = True
        except:
            pass
    
    if save_settings():
        with dpg.window(label="Settings Saved", modal=True, show=True, tag="save_success_popup", no_title_bar=False, pos=[300, 200], width=250, height=120):
            dpg.add_text("Theme settings have been saved.")
            if needs_restart:
                dpg.add_text("Note: Font scale changes may", color=[255, 200, 0])
                dpg.add_text("require a restart to fully apply.", color=[255, 200, 0])
            dpg.add_spacer(height=10)
            dpg.add_button(label="OK", width=75, callback=lambda: dpg.delete_item("save_success_popup"))
    else:
        with dpg.window(label="Save Error", modal=True, show=True, tag="save_error_popup", pos=[300, 200], width=250, height=100):
            dpg.add_text("Failed to save settings.")
            dpg.add_button(label="OK", width=75, callback=lambda: dpg.delete_item("save_error_popup"))

def sort_callback(sender, sort_specs):
    # sort_specs is a list of lists: [[column_index, direction], ...]
    # direction: 1 is ascending, -1 is descending
    if not sort_specs:
        return

    # In DPG, children of a table include columns AND rows.
    # We need to extract the row data, sort it, and then re-append it.
    rows = dpg.get_item_children(sender, 1)
    if not rows:
        return

    # Get data from each row to sort
    row_data = []
    for row in rows:
        # Each row has cells (texts/buttons) as children
        cells = dpg.get_item_children(row, 1)
        cell_values = []
        for cell in cells:
            # Handle different cell types
            item_type = dpg.get_item_type(cell)
            if item_type == "mvAppItemType::mvText":
                cell_values.append(dpg.get_value(cell))
            elif item_type == "mvAppItemType::mvButton":
                cell_values.append(dpg.get_item_label(cell))
            elif item_type == "mvAppItemType::mvGroup":
                # If cells are wrapped in a group (e.g. news items), try to get first text
                sub_cells = dpg.get_item_children(cell, 1)
                found = False
                for sc in sub_cells:
                    if dpg.get_item_type(sc) == "mvAppItemType::mvText":
                        cell_values.append(dpg.get_value(sc))
                        found = True
                        break
                if not found:
                    cell_values.append("")
            else:
                cell_values.append("")
        row_data.append((row, cell_values))

    # Sort based on specs
    # DPG usually provides a single sort spec unless multi-sort is enabled
    # But let's handle the loop just in case.
    # Note: For multiple specs, we should sort by them in reverse order of priority.
    for i in range(len(sort_specs)):
        col = sort_specs[i][0]
        direction = sort_specs[i][1]
        
        def sort_key(x):
            # Bounds check for cell index
            if col >= len(x[1]):
                return ""
            val = x[1][col]
            if val is None: return ""
            # Try to convert to float/int if possible for numeric sorting
            try:
                # Remove common non-numeric chars for sorting (+/- for standings, etc)
                clean_val = str(val).replace('%', '').replace(':', '').replace('$', '').replace('+', '').replace('-', '')
                if not clean_val.strip(): return 0.0
                return float(clean_val)
            except:
                return str(val).lower()

        row_data.sort(key=sort_key, reverse=(direction < 0))

    # Re-order the items in the UI by re-parenting them in the new order
    for row_info in row_data:
        dpg.move_item(row_info[0], parent=sender)

def on_viewport_resize():
    # Update widths for side-by-side child windows in Teams & Players tab
    viewport_width = dpg.get_viewport_width()
    # 1cm margin = approx 38px (at 96 DPI).
    margin = 38
    
    # We want a 38px margin on the left (via indent) and 38px on the right.
    # Total content width = viewport_width - (2 * margin)
    content_width = viewport_width - (2 * margin)
    if content_width < 100: content_width = 100
    
    if dpg.does_item_exist("main_tabs_group"):
        dpg.configure_item("main_tabs_group", indent=margin)
    if dpg.does_item_exist("main_tabs_container"):
        dpg.set_item_width("main_tabs_container", content_width)

    # Subtract some padding/margins for internal split-screen
    half_width = (content_width / 2) - 10
    if dpg.does_item_exist("teams_child_window"):
        dpg.set_item_width("teams_child_window", half_width)
    if dpg.does_item_exist("players_child_window"):
        dpg.set_item_width("players_child_window", half_width)
    
    # Update wrap widths for text components
    # For tagged items:
    if dpg.does_item_exist("player_bio_text"):
        dpg.configure_item("player_bio_text", wrap=half_width - 20)
    if dpg.does_item_exist("player_name_text"):
        dpg.configure_item("player_name_text", wrap=half_width - 20)
    if dpg.does_item_exist("player_stats_text"):
        dpg.configure_item("player_stats_text", wrap=half_width - 20)
    
    if dpg.does_item_exist("team_info_text"):
        dpg.configure_item("team_info_text", wrap=half_width - 20)
    if dpg.does_item_exist("team_coach_text"):
        dpg.configure_item("team_coach_text", wrap=half_width - 20)
    
    if dpg.does_item_exist("oline_text"):
        dpg.configure_item("oline_text", wrap=content_width - 40)
    if dpg.does_item_exist("dline_text"):
        dpg.configure_item("dline_text", wrap=content_width - 40)
    if dpg.does_item_exist("goalie_text"):
        dpg.configure_item("goalie_text", wrap=content_width - 40)
    
    # Dashboard items:
    # Handle dynamic heights for dashboard windows
    dash_windows = []
    if settings.get("show_comparative"): dash_windows.append("comp_standings_window")
    if settings.get("show_news"): dash_windows.append("news_window")
    if settings.get("show_top_lines"): dash_windows.append("top_lines_window")
    if settings.get("show_player_stats"): dash_windows.append("stats_window")
    
    # Base heights from settings if available, else defaults
    default_heights = {
        "comp_standings_window": 200,
        "news_window": 120,
        "top_lines_window": 80,
        "stats_window": 120,
        "notif_settings_window": 160,
        "games_list": 120,
        "weekly_games_list": 180
    }
    
    # Update from settings layout
    user_heights = settings.get("layout", {}).get("dashboard_heights", {})
    
    # Static dashboard windows (always shown or fixed height based on settings)
    for win in ["notif_settings_window", "games_list", "weekly_games_list"]:
        if dpg.does_item_exist(win):
            h = user_heights.get(win, default_heights.get(win, 100))
            dpg.set_item_height(win, h)

    if len(dash_windows) > 0:
        if len(dash_windows) < 3:
            # Divided height if few are shown - only if user hasn't manually resized them much?
            # Actually, let's respect manual resizing first if it exists, otherwise do auto-scale.
            # For simplicity, if they are auto-scaling, we might override user heights.
            # But the requirement is dragging, so we should probably stick to user heights if they've dragged.
            
            # Estimate available height (Viewport minus approximate overhead)
            available_dash_height = dpg.get_viewport_height() - 500
            if available_dash_height < 150: available_dash_height = 150
            
            shared_height = available_dash_height / len(dash_windows)
            for win in dash_windows:
                if dpg.does_item_exist(win):
                    # Use user height if it's been customized beyond default, else shared
                    custom_h = user_heights.get(win)
                    if custom_h and custom_h != default_heights.get(win):
                        dpg.set_item_height(win, custom_h)
                    else:
                        dpg.set_item_height(win, int(shared_height))
        else:
            # Respect user heights or defaults
            for win in dash_windows:
                if dpg.does_item_exist(win):
                    dpg.set_item_height(win, user_heights.get(win, default_heights.get(win, 100)))

    if dpg.does_item_exist("news_window"):
        # We can't easily iterate children without tags, but refresh_data handles it on load/toggle.
        pass

    # Full Schedule Tab wrap
    if dpg.does_item_exist("schedule_team_select"):
        dpg.configure_item("schedule_team_select", width=content_width - 20)

def exit_app(icon=None, item=None):
    """Clean exit for the application."""
    if icon:
        icon.stop()
    dpg.stop_dearpygui()
    sys.exit(0)

def show_window(icon=None, item=None):
    """Shows the main application window."""
    dpg.show_viewport()

def hide_window(icon=None, item=None):
    """Hides the main application window."""
    dpg.hide_viewport()

def setup_tray_icon():
    """Sets up the system tray icon using pystray."""
    try:
        # Load an icon image
        # Use the first team logo found or a generic one if possible
        # For now, let's create a simple square icon or use an existing one if available.
        # We'll use a blank icon if nothing else is available.
        icon_img = Image.new('RGB', (64, 64), color=(0, 100, 200))
        
        menu = Menu(
            MenuItem('Show', show_window, default=True),
            MenuItem('Refresh Data', lambda: refresh_data()),
            MenuItem('Exit', exit_app)
        )
        
        icon = Icon("NHL Notifier", icon_img, "NHL Notifier", menu)
        icon.run()
    except Exception as e:
        print(f"Error setting up tray icon: {e}")

# Resizing mechanism for dashboard containers
dragging_item = None
last_mouse_pos = [0, 0]

def start_dragging(sender, app_data, user_data):
    global dragging_item, last_mouse_pos
    dragging_item = user_data # This is the tag of the window to resize
    last_mouse_pos = dpg.get_mouse_pos(local=False)

def stop_dragging():
    global dragging_item
    if dragging_item:
        dragging_item = None
        save_settings()

def update_dragging():
    global dragging_item, last_mouse_pos
    if dragging_item and dpg.is_mouse_button_down(dpg.mvMouseButton_Left):
        current_mouse_pos = dpg.get_mouse_pos(local=False)
        delta_y = current_mouse_pos[1] - last_mouse_pos[1]
        
        if abs(delta_y) > 0:
            current_height = dpg.get_item_height(dragging_item)
            new_height = max(50, current_height + delta_y)
            dpg.set_item_height(dragging_item, new_height)
            
            # Save to settings
            settings["layout"]["dashboard_heights"][dragging_item] = new_height
            
            last_mouse_pos = current_mouse_pos
            # Trigger wrap update
            # on_viewport_resize()
    elif dragging_item:
        stop_dragging()

if __name__ == "__main__":
    dpg.create_context()
    dpg.create_viewport(title=APP_TITLE, width=800, height=600)
    dpg.set_viewport_resize_callback(on_viewport_resize)
    
    # Add a handler for global mouse release to stop dragging
    with dpg.handler_registry():
        dpg.add_mouse_release_handler(callback=stop_dragging)
        dpg.add_mouse_move_handler(callback=update_dragging)

    with dpg.texture_registry(tag="main_texture_registry"):
        # Placeholder 1x1 transparent texture to avoid "Texture not found" errors on initial load
        dpg.add_static_texture(width=1, height=1, default_value=[0.0, 0.0, 0.0, 0.0], tag="placeholder_tex")

    with dpg.window(label="Main Window", tag="primary_window", width=800, height=600):
        dpg.add_text("Double click to adjust window", color=[150, 150, 150])
        with dpg.group(tag="main_tabs_group"):
            with dpg.group(tag="main_tabs_container"):
                with dpg.tab_bar(tag="main_tabs"):
                    with dpg.tab(label="Dashboard"):
                        with dpg.child_window(label="Notification Settings", tag="notif_settings_window", height=160):
                            dpg.add_text("NHL Notification Settings")
                            with dpg.group(horizontal=True):
                                dpg.add_checkbox(label="Comparative Standings", callback=toggle_setting, user_data="show_comparative")
                                dpg.add_checkbox(label="Show News", callback=toggle_setting, user_data="show_news")
                                dpg.add_checkbox(label="Show Top Lines", callback=toggle_setting, user_data="show_top_lines")
                                dpg.add_checkbox(label="Show Player Stats", callback=toggle_setting, user_data="show_player_stats")
                        
                            with dpg.group(horizontal=True):
                                dpg.add_checkbox(label="Notify Daily Games", callback=toggle_setting, user_data="notify_daily")
                                dpg.add_checkbox(label="Notify Game Starts", callback=toggle_setting, user_data="notify_starts")
                                dpg.add_checkbox(label="Notify Goals", callback=toggle_setting, user_data="notify_goals")
                        
                            dpg.add_button(label="Refresh Dashboard Data", callback=refresh_data)
                            with dpg.group(horizontal=True):
                                dpg.add_button(label="Send Manual Desktop Notification", callback=notify_games_async)
                                dpg.add_button(label="Test Toast Notification", callback=test_toast_notification_async)

                        dpg.add_spacer(height=3)
                        dpg.add_button(label="---", width=-1, height=8, callback=start_dragging, user_data="notif_settings_window", tag="handle_notif")
                        dpg.bind_item_theme("handle_notif", "resize_handle_theme")
                        dpg.add_spacer(height=3)
                        
                        dpg.add_separator()
                        dpg.add_text("Today's Games:")
                        with dpg.child_window(tag="games_list", height=120):
                            pass
                        dpg.add_spacer(height=3)
                        dpg.add_button(label="---", width=-1, height=8, callback=start_dragging, user_data="games_list", tag="handle_games")
                        dpg.bind_item_theme("handle_games", "resize_handle_theme")
                        dpg.add_spacer(height=3)

                        dpg.add_text("Upcoming This Week:")
                        with dpg.child_window(tag="weekly_games_list", height=180):
                            pass
                        dpg.add_spacer(height=3)
                        dpg.add_button(label="---", width=-1, height=8, callback=start_dragging, user_data="weekly_games_list", tag="handle_weekly")
                        dpg.bind_item_theme("handle_weekly", "resize_handle_theme")
                        dpg.add_spacer(height=3)

                        with dpg.child_window(tag="game_stats_window", height=300, show=False):
                            with dpg.group(horizontal=True):
                                dpg.add_text("Game Boxscore/Stats")
                                dpg.add_button(label="Close Boxscore", callback=lambda: dpg.hide_item("game_stats_window"))
                            with dpg.group(tag="game_stats_list"):
                                pass

                        # Windows for optional data (now inside Dashboard tab as child windows)

                        with dpg.child_window(tag="comp_standings_window", height=200, show=False):
                            dpg.add_text("Comparative Standings (vs Previous Season 24-25)")
                            with dpg.table(tag="comp_standings_table", header_row=True, scrollY=True, sortable=True, callback=sort_callback):
                                dpg.add_table_column(label="Team")
                                dpg.add_table_column(label="Prev PTS")
                                dpg.add_table_column(label="Curr PTS")
                                dpg.add_table_column(label="+/-")
                            dpg.add_spacer(height=3)
                            dpg.add_button(label="---", width=-1, height=8, callback=start_dragging, user_data="comp_standings_window", tag="handle_comp")
                            dpg.bind_item_theme("handle_comp", "resize_handle_theme")
                            dpg.add_spacer(height=3)
                        
                        dpg.add_separator(tag="comp_standings_sep", show=False)

                        with dpg.child_window(tag="news_window", height=120, show=False):
                            dpg.add_text("NHL News")
                            with dpg.group(tag="news_list"):
                                pass
                            dpg.add_spacer(height=3)
                            dpg.add_button(label="---", width=-1, height=8, callback=start_dragging, user_data="news_window", tag="handle_news")
                            dpg.bind_item_theme("handle_news", "resize_handle_theme")
                            dpg.add_spacer(height=3)

                        dpg.add_separator(tag="news_sep", show=False)

                        with dpg.child_window(tag="top_lines_window", height=80, show=False):
                            dpg.add_text("Top Players/Lines")
                            dpg.add_text("", tag="oline_text", wrap=0)
                            dpg.add_text("", tag="dline_text", wrap=0)
                            dpg.add_text("", tag="goalie_text", wrap=0)
                            dpg.add_spacer(height=3)
                            dpg.add_button(label="---", width=-1, height=8, callback=start_dragging, user_data="top_lines_window", tag="handle_top")
                            dpg.bind_item_theme("handle_top", "resize_handle_theme")
                            dpg.add_spacer(height=3)

                        dpg.add_separator(tag="top_lines_sep", show=False)

                        with dpg.child_window(tag="stats_window", height=120, show=False):
                            dpg.add_text("Player Goal Leaders")
                            with dpg.group(tag="stats_list"):
                                pass
                            dpg.add_spacer(height=3)
                            dpg.add_button(label="---", width=-1, height=8, callback=start_dragging, user_data="stats_window", tag="handle_stats")
                            dpg.bind_item_theme("handle_stats", "resize_handle_theme")
                            dpg.add_spacer(height=3)

                        dpg.add_separator(tag="stats_sep", show=False)

                    with dpg.tab(label="Teams & Players", tag="tab_teams_players"):
                        with dpg.group(horizontal=True):
                            # Left side: Teams
                            with dpg.child_window(width=0, height=-1, tag="teams_child_window"):
                                dpg.add_text("Filter by Team")
                                dpg.add_combo(label="Select Team", tag="team_select", callback=update_team_info, width=-1)
                                dpg.add_separator()
                                dpg.add_image("placeholder_tex", tag="team_logo_img", width=80, height=80, show=False)
                                dpg.add_text("Team Information", tag="team_info_text", wrap=0)
                                dpg.add_text("Head Coach: Unknown", tag="team_coach_text", wrap=0)
                                dpg.add_separator()
                                dpg.add_text("Current Roster:")
                                with dpg.child_window(height=-1):
                                    with dpg.table(tag="team_roster_table", header_row=True, scrollY=True, sortable=True, callback=sort_callback):
                                        dpg.add_table_column(label="Player")
                                        dpg.add_table_column(label="Pos")
                                        dpg.add_table_column(label="No")
                                        dpg.add_table_column(label="Actions", no_sort=True)

                            # Right side: Players
                            with dpg.child_window(width=0, height=-1, tag="players_child_window"):
                                dpg.add_text("Search/Filter Players")
                                dpg.add_combo(label="Select Player", tag="player_select", callback=update_player_info, width=-1)
                                dpg.add_separator()
                                with dpg.child_window(height=300):
                                    dpg.add_image("placeholder_tex", tag="player_img", width=150, height=150, show=False)
                                    dpg.add_text("Player Bio", tag="player_name_text", color=[100, 200, 255], wrap=0)
                                    dpg.add_text("", tag="player_bio_text", wrap=0)
                                    dpg.add_separator()
                                    dpg.add_text("", tag="player_stats_text", wrap=0)

                    with dpg.tab(label="Full Standings"):
                        dpg.add_text("NHL League Standings")
                        with dpg.table(tag="full_standings_table", header_row=True, scrollY=True, height=-1, sortable=True, callback=sort_callback):
                            dpg.add_table_column(label="Team")
                            dpg.add_table_column(label="GP")
                            dpg.add_table_column(label="W")
                            dpg.add_table_column(label="L")
                            dpg.add_table_column(label="OTL")
                            dpg.add_table_column(label="PTS")
                            dpg.add_table_column(label="Conf")
                            dpg.add_table_column(label="Div")

                    with dpg.tab(label="Full Schedule"):
                        dpg.add_text("Full Season Schedule")
                        dpg.add_combo(label="Select Team", tag="schedule_team_select", callback=update_schedule_info, width=-1)
                        dpg.add_separator()
                        
                        with dpg.child_window(height=-1):
                            dpg.add_text("Upcoming Games:", color=[100, 255, 100])
                            with dpg.table(tag="upcoming_schedule_table", header_row=True, scrollY=True, height=250, sortable=True, callback=sort_callback):
                                dpg.add_table_column(label="Date")
                                dpg.add_table_column(label="Away")
                                dpg.add_table_column(label="Home")
                                dpg.add_table_column(label="Result/Time")
                                dpg.add_table_column(label="Venue")
                                
                            dpg.add_spacer(height=10)
                            dpg.add_separator()
                            dpg.add_spacer(height=10)
                            
                            dpg.add_text("Past Games:", color=[255, 150, 100])
                            with dpg.table(tag="past_schedule_table", header_row=True, scrollY=True, height=-1, sortable=True, callback=sort_callback):
                                dpg.add_table_column(label="Date")
                                dpg.add_table_column(label="Away")
                                dpg.add_table_column(label="Home")
                                dpg.add_table_column(label="Result/Time")
                                dpg.add_table_column(label="Venue")

                    with dpg.tab(label="Customize UI"):
                        with dpg.child_window(label="Theme Settings", height=-1):
                            dpg.add_text("Customize Application Colors")
                            dpg.add_spacer(height=10)
                            
                            dpg.add_color_edit(label="Text Color", tag="color_picker_text", default_value=settings["theme"]["text"], callback=update_theme, user_data="text")
                            dpg.add_color_edit(label="Background Color", tag="color_picker_bg", default_value=settings["theme"]["background"], callback=update_theme, user_data="background")
                            dpg.add_color_edit(label="Active Tab Color", tag="color_picker_active_tab", default_value=settings["theme"]["active_tab"], callback=update_theme, user_data="active_tab")
                            dpg.add_color_edit(label="Button Color", tag="color_picker_button", default_value=settings["theme"]["button"], callback=update_theme, user_data="button")
                            dpg.add_color_edit(label="Header/Frame Color", tag="color_picker_header", default_value=settings["theme"]["header"], callback=update_theme, user_data="header")
                            
                            dpg.add_spacer(height=15)
                            dpg.add_text("Customize Application Styles")
                            dpg.add_spacer(height=10)
                            
                            dpg.add_slider_float(label="Global Font Scale", tag="slider_font_scale", default_value=settings["theme"]["font_scale"], min_value=0.5, max_value=2.0, callback=update_theme, user_data="font_scale")
                            dpg.add_slider_float(label="Item Rounding", tag="slider_rounding", default_value=settings["theme"]["rounding"], min_value=0.0, max_value=20.0, callback=update_theme, user_data="rounding")
                            dpg.add_slider_float(label="Frame Padding", tag="slider_padding", default_value=settings["theme"]["padding"], min_value=0.0, max_value=20.0, callback=update_theme, user_data="padding")
                            
                            dpg.add_spacer(height=20)
                            with dpg.group(horizontal=True):
                                dpg.add_button(label="Save Theme Settings", callback=save_theme_callback)
                                dpg.add_button(label="Reset to Default", callback=reset_theme)

    # Initial resize to set child window widths
    on_viewport_resize()

    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("primary_window", True)
    
    # Initial load
    refresh_data()
    
    # Start background notification thread
    threading.Thread(target=notification_loop, daemon=True).start()
    
    # Apply initial theme
    apply_theme()
    
    # Start system tray icon in a separate thread
    threading.Thread(target=setup_tray_icon, daemon=True).start()
    
    dpg.start_dearpygui()
    dpg.destroy_context()
