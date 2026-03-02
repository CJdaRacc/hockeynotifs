# NHL Hockey Notifier

A real-time NHL dashboard and desktop notification application built with Python and Dear PyGui. This app provides up-to-date game schedules, league standings, player statistics, team rosters, and more, all with a clean, toggleable interface.

## Features

- **Desktop Notifications**: Get instant alerts for today's scheduled NHL games.
- **Interactive Dashboard**:
    - **Live Games**: View today's matchups with times converted to your local time (EST).
    - **Toggleable Widgets**: Show or hide League Standings, Comparative Standings (last season), NHL News, Top Lines, and Player Stats with simple checkboxes.
- **Detailed Team Browser**:
    - Filter and select any of the 32 NHL teams.
    - View team logos, head coaches, and full current rosters.
    - Quick links to view individual player statistics.
- **Player Stats & Bio**:
    - Search for any player on a selected team.
    - View player headshots, biographical info (height, weight, birthplace), and current season stats (Goals, Assists, Points for skaters; GAA, SV%, Wins for goalies).
- **Full League Standings**: A complete, sortable table of all teams with their GP, W, L, OTL, and Points.
- **Full Season Schedule**: A new tab to view the complete regular season schedule for any selected NHL team, including dates, matchups, results, and game times.

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

- Click **"Send Manual Desktop Notification"** to see the current day's games as a Windows toast.
- Click **"Test Toast Notification"** to verify that notifications are working on your system.
- Use the **checkboxes** on the Dashboard tab to customize your view.
- Navigate to the **Teams** or **Players** tabs for in-depth information.
- Click **"Refresh Dashboard Data"** to fetch the latest updates from the NHL API.

## Technical Details

- **API**: Uses the unofficial [NHL Web API](https://api-web.nhle.com/v1/) for real-time data.
- **GUI**: Built entirely using [Dear PyGui](https://github.com/hoffstadt/DearPyGui), a high-performance GPU-accelerated Python GUI framework.
- **Images**: Team logos are fetched as SVGs and converted on-the-fly to PNGs for display within the application. Player headshots are loaded dynamically as you browse.

## Credits

- Data provided by the NHL (National Hockey League).
- Icons and headshots are sourced via the NHL Web API.
- Head coach information is manually curated based on current league standings and Wikipedia data.
