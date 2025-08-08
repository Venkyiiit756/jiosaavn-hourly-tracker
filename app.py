from flask import Flask, render_template_string
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import threading
import time
import pytz
import csv
import os
import pandas as pd
import logging
from logging.handlers import RotatingFileHandler

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('app.log', maxBytes=100000, backupCount=3),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
ist_tz = pytz.timezone('Asia/Kolkata')

@app.template_filter('format_number')
def format_number(value):
    """Format a number with commas for thousands"""
    try:
        return "{:,}".format(int(value))
    except (ValueError, TypeError):
        return str(value)

@app.template_filter('format_time')
def format_time(value):
    """Format a timestamp string"""
    try:
        return value.split()[1]  # Return only the time part
    except (AttributeError, IndexError):
        return value

# CSV files to store the data
SONGS = {
    'firestorm': {
        'csv_file': 'play_count_history.csv',
        'url': 'https://www.jiosaavn.com/album/firestorm-from-they-call-him-og/yHG4eDZauLQ_',
        'title': 'Firestorm',
        'entries': []
    },
    'hungry_cheetah': {
        'csv_file': 'hungry_cheetah_history.csv',
        'url': 'https://www.jiosaavn.com/song/hungry-cheetah-from-they-call-him-og/OgQvaDxEbwE',
        'title': 'Hungry Cheetah',
        'entries': []
    }
}

def load_entries_from_csv(csv_file):
    """Load existing entries from CSV file"""
    entries = []
    if os.path.exists(csv_file):
        df = pd.read_csv(csv_file)
        entries = df.to_dict('records')
    return entries

def save_entry_to_csv(csv_file, entry):
    """Save a new entry to CSV file"""
    try:
        is_new_file = not os.path.exists(csv_file)
        with open(csv_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['timestamp', 'play_count'])
            if is_new_file:
                writer.writeheader()
            writer.writerow(entry)
        logger.info(f"Successfully saved entry to CSV: {entry}")
    except IOError as e:
        logger.error(f"IO error saving to CSV: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error saving to CSV: {e}")
        raise

# Load initial data for each song
for song in SONGS.values():
    song['entries'] = load_entries_from_csv(song['csv_file'])

last_update_time = None

def calculate_rate(current, previous, time_diff_minutes):
    """Calculate rate of increase per minute"""
    if time_diff_minutes <= 0:
        return 0
    return (int(current) - int(previous)) / time_diff_minutes

def calculate_changes(entries):
    """Calculate changes between consecutive play counts"""
    if not entries:
        return []
    
    # Convert entries to list if it's reversed
    entries_list = list(entries)
    
    # Initialize the first entry's change as 0
    result = [dict(entries_list[0], change="--")]
    
    # Calculate changes for remaining entries
    for i in range(1, len(entries_list)):
        current = entries_list[i]
        previous = entries_list[i-1]
        change = int(current['play_count']) - int(previous['play_count'])
        change_str = f"+{change}" if change > 0 else str(change) if change < 0 else "0"
        result.append(dict(current, change=change_str))
    
    return reversed(result)  # Reverse back to maintain newest-first order

# HTML template for the webpage
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>JioSaavn Play Count Monitor</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f0f0f0;
        }
        .container {
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            max-width: 1200px;
            margin: 0 auto;
        }
        .song-container {
            margin-bottom: 40px;
            padding: 20px;
            border-radius: 8px;
            background-color: #f8f9fa;
        }
        .stats-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        .stat-card {
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .stat-title {
            color: #666;
            font-size: 0.9em;
            margin-bottom: 5px;
        }
        .stat-value {
            font-size: 1.5em;
            font-weight: bold;
            color: #007bff;
        }
        .chart-container {
            margin: 20px 0;
            height: 300px;
            background: white;
            padding: 20px;
            border-radius: 8px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            background-color: white;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #007bff;
            color: white;
        }
        tr:nth-child(even) {
            background-color: #f2f2f2;
        }
        tr:hover {
            background-color: #e9ecef;
        }
        .header {
            margin-bottom: 20px;
        }
        td:last-child {
            color: #28a745;
            font-weight: bold;
        }
        td:last-child:empty::before {
            content: "--";
            color: #6c757d;
        }
        .refresh-note {
            color: #666;
            font-size: 0.9em;
            margin-top: 10px;
        }
        .song-title {
            color: #007bff;
            margin-bottom: 20px;
        }
    </style>
    <meta http-equiv="refresh" content="900">
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>JioSaavn Play Count Monitor</h1>
            <h2>They Call Him OG</h2>
        </div>
        {% for song_id, song_data in songs.items() %}
        <div class="song-container">
            <h3 class="song-title">{{ song_data.title }}</h3>
            <div class="stats-container">
                <div class="stat-card">
                    <div class="stat-title">Current Play Count</div>
                    <div class="stat-value">{{ song_data.entries[0].play_count | format_number }}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-title">Total Increase</div>
                    <div class="stat-value">+{{ (song_data.entries[0].play_count | int - song_data.entries[-1].play_count | int) | format_number }}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-title">Average Rate</div>
                    <div class="stat-value">{{ song_data.avg_rate | round(1) }}/min</div>
                </div>
                <div class="stat-card">
                    <div class="stat-title">Next Update</div>
                    <div class="stat-value">{{ next_update }}</div>
                </div>
            </div>
            <div class="chart-container">
                <canvas id="{{ song_id }}Chart"></canvas>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Timestamp (IST)</th>
                        <th>Play Count</th>
                        <th>Change</th>
                    </tr>
                </thead>
                <tbody>
                    {% for entry in song_data.entries_with_changes %}
                    <tr>
                        <td>{{ loop.index }}</td>
                        <td>{{ entry.timestamp }}</td>
                        <td>{{ entry.play_count | format_number }}</td>
                        <td>{{ entry.change }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endfor %}
        
        <!-- 24 Hour Stats for Firestorm -->
        {% if songs.get('firestorm', {}).get('plays_24h_ago') %}
        <div class="song-container">
            <h3>Firestorm 24-Hour Stats</h3>
            <table>
                <thead>
                    <tr>
                        <th>24h Ago</th>
                        <th>Current</th>
                        <th>Increase</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>{{ songs['firestorm'].plays_24h_ago | format_number }}</td>
                        <td>{{ songs['firestorm'].entries[0].play_count }}</td>
                        <td style="color: #28a745;">↑ +{{ (songs['firestorm'].entries[0].play_count | int - songs['firestorm'].plays_24h_ago | int) | format_number }}</td>
                    </tr>
                </tbody>
            </table>
        </div>
        {% endif %}
        
        <!-- Summary Table -->
        <div class="song-container">
            <h3>JioSaavn TheyCallHimOG Stats</h3>
            <table>
                <thead>
                    <tr>
                        <th>Song</th>
                        <th>Current Play Count</th>
                        <th>Increase Remarks</th>
                    </tr>
                </thead>
                <tbody>
                    {% for song_id, song_data in songs.items() %}
                    <tr>
                        <td>{{ song_data.title }}</td>
                        <td>{{ song_data.entries[0].play_count }}</td>
                        <td>{{ song_data.increase_remarks }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <p class="refresh-note">Page and data auto-update every 15 minutes.</p>
    </div>
    <script>
        {% for song_id, song_data in songs.items() %}
        const ctx_{{ song_id }} = document.getElementById('{{ song_id }}Chart');
        new Chart(ctx_{{ song_id }}, {
            type: 'line',
            data: {
                labels: {{ song_data.timestamps | tojson }},
                datasets: [{
                    label: '{{ song_data.title }} Play Count',
                    data: {{ song_data.play_counts | tojson }},
                    borderColor: '{{ "#007bff" if song_id == "firestorm" else "#28a745" }}',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: false
                    }
                }
            }
        });
        {% endfor %}
    </script>
</body>
</html>'''

def fetch_play_count(url):
    """Fetch the play count from JioSaavn"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        logger.info(f"Fetching play count from JioSaavn for {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise exception for non-200 status codes
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try to find the play count in song/album info
        # First check for the song page format (new format)
        play_info = soup.find('p', class_=['u-centi u-deci@lg u-color-js-gray u-ellipsis@lg u-margin-bottom-tiny@sm', 'u-centi u-deci@lg u-color-js-gray'])
        if play_info and 'Play' in play_info.text:
            text = play_info.text
            # Extract number before the word "Play" and remove commas
            number_part = text.split('Play')[0].strip()
            play_count = ''.join(filter(str.isdigit, number_part))
            if play_count:
                logger.info(f"Found play count in song info (new format): {play_count}")
                return play_count
        
        # Then try the album format
        album_info = soup.find('span', class_='u-centi u-hidden@lg')
        if album_info and 'Plays' in album_info.text:
            text = album_info.text
            parts = text.split('Plays')[0].strip()
            play_count = ''.join(filter(str.isdigit, parts))
            if play_count:
                logger.info(f"Found play count in album info: {play_count}")
                return play_count
        
        # If not found, try searching all text
        logger.debug("Searching all text for play count")
        for text in soup.stripped_strings:
            if 'Plays' in text:
                logger.debug(f"Found text with plays: {text}")
                parts = text.split('Plays')[0].strip()
                play_count = ''.join(filter(str.isdigit, parts))
                if play_count:
                    logger.info(f"Extracted play count from text: {play_count}")
                    return play_count
                break
                
        logger.warning("No play count found in page content")
        return None
        
    except requests.RequestException as e:
        logger.error(f"Network error fetching play count: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching play count: {e}")
        return None

def update_play_count():
    """Update the play count every 15 minutes"""
    global last_update_time
    while True:
        current_time = datetime.now(ist_tz)
        
        # Only check for updates if no previous update or 15 minutes have passed
        if last_update_time is None or (current_time - last_update_time).total_seconds() >= 900:
            logger.info("Starting update check for all songs...")
            for song_id, song in SONGS.items():
                logger.info(f"Checking {song['title']}...")
                play_count = fetch_play_count(song['url'])
                if play_count:
                    # Only add if this is the first entry or count has changed
                    is_new_entry = True
                    if song['entries']:
                        last_entry = song['entries'][-1]
                        is_new_entry = last_entry['play_count'] != play_count
                        logger.info(f"{song['title']}: Current count: {play_count}, Last count: {last_entry['play_count']}, Need update: {is_new_entry}")
                    
                    if is_new_entry:
                        entry = {
                            'play_count': play_count,
                            'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S IST')
                        }
                        song['entries'].append(entry)
                        save_entry_to_csv(song['csv_file'], entry)
                        print(f"Added new entry for {song['title']}: {entry}")
            
            last_update_time = current_time
        
        # Sleep for 60 seconds before checking again
        time.sleep(60)

def calculate_next_update():
    """Calculate time until next update"""
    if last_update_time is None:
        return "Soon"
    next_time = last_update_time + timedelta(minutes=15)
    now = datetime.now(ist_tz)
    if next_time <= now:
        return "Soon"
    diff = (next_time - now).total_seconds() / 60
    return f"in {diff:.0f} min"

@app.route('/')
def home():
    song_data = {}
    next_update = calculate_next_update()
    
    try:
        # Process each song
        for song_id, song in SONGS.items():
            entries = load_entries_from_csv(song['csv_file'])
            if entries:
                # Calculate changes
                entries_with_changes = list(calculate_changes(entries))
                
                # Calculate rate
                avg_rate = 0
                if len(entries) >= 2:
                    first = entries[-1]  # Oldest entry
                    last = entries[0]    # Newest entry
                    try:
                        first_time = datetime.strptime(first['timestamp'].replace(' IST', ''), '%Y-%m-%d %H:%M:%S').replace(tzinfo=ist_tz)
                        last_time = datetime.strptime(last['timestamp'].replace(' IST', ''), '%Y-%m-%d %H:%M:%S').replace(tzinfo=ist_tz)
                        time_diff = (last_time - first_time).total_seconds() / 60
                        total_increase = int(last['play_count']) - int(first['play_count'])
                        avg_rate = total_increase / time_diff if time_diff > 0 else 0
                        logger.info(f"Calculated rate for {song['title']}: {avg_rate:.2f} plays/minute over {time_diff:.1f} minutes")
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error calculating average rate for {song['title']}: {e}")
                
                # Prepare chart data
                try:
                    timestamps = [entry['timestamp'].split()[1] for entry in reversed(entries)]
                    # Format play counts with commas and convert to integers for calculations
                    play_counts = []
                    formatted_entries = []
                    for entry in reversed(entries):
                        count = int(entry['play_count'])
                        play_counts.append(count)
                        formatted_entry = entry.copy()
                        formatted_entry['play_count'] = "{:,}".format(count)
                        formatted_entries.append(formatted_entry)
                    logger.debug(f"Prepared chart data for {song['title']} with {len(timestamps)} points")
                except (ValueError, TypeError) as e:
                    logger.error(f"Error preparing chart data for {song['title']}: {e}")
                
                # Find play count from 24 hours ago
                current_time = datetime.now(ist_tz)
                target_time = current_time - timedelta(hours=24)
                plays_24h_ago = None
                
                # Find the closest entry to 24 hours ago
                closest_entry = None
                min_diff = float('inf')
                for entry in entries:
                    entry_time = datetime.strptime(entry['timestamp'].replace(' IST', ''), '%Y-%m-%d %H:%M:%S').replace(tzinfo=ist_tz)
                    diff = abs((entry_time - target_time).total_seconds())
                    if diff < min_diff:
                        min_diff = diff
                        closest_entry = entry
                        plays_24h_ago = int(entry['play_count'])
                
                # Calculate increase remarks
                first_time = datetime.strptime(entries[-1]['timestamp'].replace(' IST', ''), '%Y-%m-%d %H:%M:%S')
                last_time = datetime.strptime(entries[0]['timestamp'].replace(' IST', ''), '%Y-%m-%d %H:%M:%S')
                hours_diff = (last_time - first_time).total_seconds() / 3600
                total_increase = int(entries[0]['play_count']) - int(entries[-1]['play_count'])
                
                # Format time in hours with one decimal place
                time_text = f"{hours_diff:.1f} hours"
                
                increase_remarks = f"↑ +{format_number(total_increase)} in {time_text}"
                
                # Store processed data
                data = {
                    'title': song['title'],
                    'entries': formatted_entries,  # Use formatted entries
                    'entries_with_changes': entries_with_changes,
                    'avg_rate': avg_rate,
                    'timestamps': timestamps,
                    'play_counts': play_counts,
                    'increase_remarks': increase_remarks
                }
                
                # Add 24h stats for Firestorm
                if song_id == 'firestorm' and plays_24h_ago is not None:
                    data['plays_24h_ago'] = plays_24h_ago
                
                song_data[song_id] = data
            
    except Exception as e:
        logger.error(f"Error in home route: {e}")
        
    return render_template_string(
        HTML_TEMPLATE,
        songs=song_data,
        next_update=next_update
    )

if __name__ == '__main__':
    # Get initial play count for each song if there's no existing data
    for song_id, song in SONGS.items():
        if not song['entries']:
            initial_count = fetch_play_count(song['url'])
            if initial_count:
                # Add initial entry
                entry = {
                    'play_count': initial_count,
                    'timestamp': datetime.now(ist_tz).strftime('%Y-%m-%d %H:%M:%S IST')
                }
                save_entry_to_csv(song['csv_file'], entry)
                song['entries'].append(entry)
                print(f"Added initial entry for {song['title']}: {entry}")
            else:
                print(f"Failed to fetch initial play count for {song['title']}")
        else:
            print(f"Loaded {len(song['entries'])} existing entries for {song['title']}")
    
    # Start the background thread for updating play count
    update_thread = threading.Thread(target=update_play_count, daemon=True)
    update_thread.start()
    
    # Start the Flask application
    app.run(host='0.0.0.0', port=5000, debug=True)
