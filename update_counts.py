import json
import os
from datetime import datetime, timedelta
import pytz
import requests
from bs4 import BeautifulSoup

SONGS = {
    'firestorm': {
        'json_file': 'firestorm_history.json',
        'url': 'https://www.jiosaavn.com/album/firestorm-from-they-call-him-og/yHG4eDZauLQ_'
    },
    'hungry_cheetah': {
        'json_file': 'hungry_cheetah_history.json',
        'url': 'https://www.jiosaavn.com/song/hungry-cheetah-from-they-call-him-og/OgQvaDxEbwE'
    }
}

IST = pytz.timezone('Asia/Kolkata')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36'
}

PLAY_P_TAG_CLASSES = [
    'u-centi u-deci@lg u-color-js-gray u-ellipsis@lg u-margin-bottom-tiny@sm',
    'u-centi u-deci@lg u-color-js-gray'
]
ALBUM_SPAN_CLASS = 'u-centi u-hidden@lg'

MAX_RETRIES = 2
BACKOFF_SECONDS = 3

# ---------------- Core helpers -----------------

def parse_int_digits(text: str):
    digits = ''.join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else None

def safe_parse_ts(ts: str):
    try:
        return datetime.strptime(ts.replace(' IST','').strip(), '%Y-%m-%d %H:%M:%S')
    except Exception:
        return None

def fetch_play_count(url: str):
    last_err = None
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'html.parser')
            for cls in PLAY_P_TAG_CLASSES:
                tag = soup.find('p', class_=cls)
                if tag and 'Play' in tag.text:
                    val = parse_int_digits(tag.text.split('Play')[0])
                    if val is not None:
                        return val
            album_tag = soup.find('span', class_=ALBUM_SPAN_CLASS)
            if album_tag and 'Play' in album_tag.text:
                val = parse_int_digits(album_tag.text.split('Play')[0])
                if val is not None:
                    return val
            for text in soup.stripped_strings:
                if 'Play' in text:
                    val = parse_int_digits(text.split('Play')[0])
                    if val is not None:
                        return val
            return None
        except Exception as e:
            last_err = e
            if attempt <= MAX_RETRIES:
                import time; time.sleep(BACKOFF_SECONDS * attempt)
    print(f"Fetch error {url}: {last_err}")
    return None

def load_json(path: str):
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return []

def save_json(path: str, data):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

# ---------------- Update logic -----------------

def should_append_hourly(existing, now_dt):
    if not existing:
        return True
    last = existing[-1]
    try:
        last_dt = datetime.strptime(last['timestamp'].replace(' IST','').strip(), '%Y-%m-%d %H:%M:%S')
    except Exception:
        return True
    return (now_dt.year, now_dt.month, now_dt.day, now_dt.hour) != (last_dt.year, last_dt.month, last_dt.day, last_dt.hour)

def update_song(song_id: str, meta: dict):
    data = load_json(meta['json_file'])
    count = fetch_play_count(meta['url'])
    if count is None:
        print(f"No count for {song_id}")
        return False
    if data:
        try:
            if count < int(data[-1]['play_count']):
                print(f"Skip {song_id}: decreasing count")
                return False
        except Exception:
            pass
    now_dt = datetime.now(IST).replace(tzinfo=None)
    if should_append_hourly(data, now_dt):
        entry = {
            'timestamp': now_dt.strftime('%Y-%m-%d %H:%M:%S IST'),
            'play_count': str(count)
        }
        data.append(entry)
        save_json(meta['json_file'], data)
        print(f"Appended {song_id}: {count}")
        return True
    print(f"Skipped {song_id}: same hour")
    return False

# ---------------- Summary -----------------

def find_reference(entries, hours_back):
    target_time = datetime.now(IST) - timedelta(hours=hours_back)
    closest = None; min_diff = float('inf')
    for e in entries:
        t = safe_parse_ts(e.get('timestamp',''))
        if not t: continue
        t = IST.localize(t)
        diff = abs((t - target_time).total_seconds())
        if diff < min_diff:
            min_diff = diff; closest = e
    return closest

def build_summary():
    summary = {
        'generated_at': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST'),
        'granularity': 'hourly',
        'songs': {}
    }
    for sid, meta in SONGS.items():
        data = load_json(meta['json_file'])
        if not data:
            continue
        current = data[-1]; curr_count = int(current['play_count'])
        prev_hour = find_reference(data, 1)
        prev_day = find_reference(data, 24)
        hour_inc = None; day_inc = None
        if prev_hour:
            try: hour_inc = curr_count - int(prev_hour['play_count'])
            except: pass
        if prev_day:
            try: day_inc = curr_count - int(prev_day['play_count'])
            except: pass
        summary['songs'][sid] = {
            'current': curr_count,
            'previous_hour': int(prev_hour['play_count']) if prev_hour else None,
            'hour_increase': hour_inc,
            'previous_24h': int(prev_day['play_count']) if prev_day else None,
            'day_increase': day_inc,
            'entries': len(data)
        }
    with open('stats_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    return True

# ---------------- Main -----------------

def main():
    changed = False
    for sid, meta in SONGS.items():
        if update_song(sid, meta):
            changed = True
    build_summary()
    if not changed:
        print("No updates needed")

if __name__ == '__main__':
    main()
