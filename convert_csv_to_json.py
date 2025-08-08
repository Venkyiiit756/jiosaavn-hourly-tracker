import os
import csv
import json
from datetime import datetime, timedelta

CSV_FILES = {
    'firestorm': 'play_count_history.csv',
    'hungry_cheetah': 'hungry_cheetah_history.csv'
}

OUTPUT_FILES = {
    'firestorm': 'firestorm_history.json',
    'hungry_cheetah': 'hungry_cheetah_history.json'
}

def parse_ts(ts: str) -> datetime:
    ts = ts.replace(' IST', '').strip()
    return datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')

def load_csv(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        for r in reader:
            if not r.get('timestamp') or not r.get('play_count'):
                continue
            rows.append({'timestamp': r['timestamp'].strip(), 'play_count': r['play_count'].strip()})
    return rows

def filter_hour_gaps(entries, gap_minutes=60):
    if not entries:
        return []
    # ensure sorted oldest->newest
    entries_sorted = sorted(entries, key=lambda e: parse_ts(e['timestamp']))
    filtered = []
    last_kept_time = None
    for entry in entries_sorted:
        current_time = parse_ts(entry['timestamp'])
        if last_kept_time is None:
            filtered.append(entry)
            last_kept_time = current_time
        else:
            diff = (current_time - last_kept_time).total_seconds() / 60
            if diff >= gap_minutes - 5:  # allow ~55 min threshold
                filtered.append(entry)
                last_kept_time = current_time
    # Always ensure the newest entry is included
    if filtered and filtered[-1]['timestamp'] != entries_sorted[-1]['timestamp']:
        filtered.append(entries_sorted[-1])
    return filtered

def write_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def convert_all():
    for key, csv_file in CSV_FILES.items():
        rows = load_csv(csv_file)
        if not rows:
            print(f"No data found for {key} ({csv_file}) - skipping")
            continue
        filtered = filter_hour_gaps(rows)
        out_file = OUTPUT_FILES[key]
        write_json(out_file, filtered)
        print(f"Converted {csv_file} -> {out_file} (kept {len(filtered)} of {len(rows)})")

if __name__ == '__main__':
    convert_all()
