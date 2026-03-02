# NHL Hockey Notifier

A real-time NHL dashboard and desktop notification application built with Python and Dear PyGui. This app provides up-to-date game schedules, live scores, league standings, player statistics, team rosters, and more, all with a clean, toggleable and customizable interface.

## Features

- **Live Game Scores & Boxscores**:
    - Real-time updates for today's games with scores and game states (Live, Final, Pre-game).
    - Detailed game boxscores: View comprehensive stats (Goals, Assists, Points, SOG, TOI for skaters; Saves, Save % for goalies) for both home and away teams.
- **Desktop Notifications & Background Support**:
    - **Instant Alerts**: Get notified for today's scheduled games, game starts, and goal alerts.
    - **Detailed Toasts**: Notifications include game time, arena, and location (state/province abbreviation).
    - **Background Persistence**: The app can run in the system tray (hidden icons) with a 20-second data polling frequency.
- **Interactive Dashboard**:
    - **Toggleable Widgets**: Show or hide Comparative Standings (vs 24-25 season results), NHL News (Categorized: Injuries, Trades, Training, Major News), Top Lines, and Player Stats.
    - **Upcoming Week's Games**: View a 7-day outlook of the NHL schedule.
- **Combined Teams & Players Browser**:
    - **Split-Screen Layout**: View team information on the left and player details on the right simultaneously.
    - **Filter Teams**: Select any of the 32 NHL teams to see logos, head coaches, and full current rosters.
    - **Detailed Player Stats & Bio**: Search for any player on a selected team to view headshots, biographical info (height, weight, birthplace), and current season stats.
- **Full League Standings & Season Schedule**:
    - **Sortable Tables**: Click on any header (GP, W, L, Points, etc.) to sort data instantly.
    - **Division Grouping**: Full league standings organized by division and conference.
    - **Complete Schedule**: Dedicated tab for any team's full 2025-2026 season schedule, split into Upcoming and Past games.
- **Advanced UI Customization**:
    - Personalize the interface with a built-in theme engine.
    - Adjust Text, Background, Active Tab, and Button colors.
    - Customize font scale, item rounding, and frame padding.
    - **Persistent Settings**: Save your theme and dashboard preferences to `settings.json` so they load automatically on restart.

## Prerequisites

- **Python**: 3.8 or higher (Tested with Python 3.13)
- **Dependencies**:
    - `dearpygui`: For the graphical user interface.
    - `requests`: For fetching data from the NHL Web API.
    - `win10toast-persist`: For Windows desktop notifications.
    - `pystray`: For system tray icon support.
    - `Pillow`: For image processing.
    - `svglib` & `reportlab`: For converting team logos (SVG) to a format compatible with the GUI.
    - `setuptools==69.5.1`: Required for `win10toast-persist` compatibility on newer Python versions.

> **Note on Python 3.12+ (including 3.13) Fix**:  
> If you encounter `TypeError: WPARAM is simple, so must be an int object (got NoneType)`, you must edit the `win10toast_persist\__init__.py` file in your Python site-packages.  
> Locate the `on_destroy` method (around line 146) and change `return None` to `return 0`.

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/cmitc/hockeynotifs.git
   cd hockeynotifs
   ```

2. **Install the required packages**:
   ```bash
   pip install dearpygui requests win10toast-persist pystray Pillow svglib reportlab
   ```

3. **Important Compatibility Fix**:
   Due to recent changes in `setuptools`, you may need to downgrade it to ensure the notification system works correctly:
   ```bash
   pip install setuptools==69.5.1
   ```

## Creating an Executable

You can create a standalone `.exe` file for Windows using PyInstaller:

1. **Install PyInstaller**:
   ```bash
   pip install pyinstaller
   ```

2. **Build the executable**:
   ```bash
   python -m PyInstaller --onefile --noconsole --add-data "settings.json;." main.py
   ```
   The generated `main.exe` will be located in the `dist/` folder.

## Usage

Run the main application:
```bash
python main.py
```

- **Dashboard**: Click **"View Game Stats"** on any game to see a live/final boxscore. Use the checkboxes to toggle sections like News or Standings.
- **Notifications**: Enable "Notify Game Starts" or "Notify Goals" for real-time alerts. Click **"Test Toast Notification"** to verify they work.
- **Teams & Players**: Select a team to load its roster. Click **"View Stats"** next to a player's name to see their details on the right.
- **Customization**: Go to the **"Customize UI"** tab, adjust colors and sliders, then click **"Save Theme Settings"**.
- **System Tray**: When the window is hidden, look for the hockey puck icon in your taskbar to show, refresh, or exit.
- **Sorting**: Click any table header (e.g., "PTS" in standings) to sort the data.

## Technical Details

- **API**: Uses the unofficial [NHL Web API](https://api-web.nhle.com/v1/) for real-time data.
- **GUI**: Built entirely using [Dear PyGui](https://github.com/hoffstadt/DearPyGui), a high-performance GPU-accelerated Python GUI framework.
- **Images**: Team logos are fetched as SVGs and converted on-the-fly to PNGs. Player headshots are loaded dynamically.
- **Persistence**: All settings (including custom colors and toggles) are stored in `settings.json`.

## Credits

- Data provided by the NHL (National Hockey League).
- Icons and headshots are sourced via the NHL Web API.
- Head coach information is manually curated based on league standings and Wikipedia data.
