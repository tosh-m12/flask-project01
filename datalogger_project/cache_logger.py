import os 
import json
import time
from datetime import datetime
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, 'settings.json')
CACHE_DIR = os.path.join(BASE_DIR, 'cache')
LAST_LOGGED_FILE = os.path.join(BASE_DIR, 'last_logged.txt')
LAST_TIMES_FILE = os.path.join(BASE_DIR, 'last_logged_times.txt')  # 複数時刻用

def load_settings():
    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def parse_timestamp_from_filename(filename):
    try:
        name_part = filename.replace("device_cache_", "").replace(".json", "")
        return datetime.strptime(name_part, '%Y%m%d%H%M%S')
    except Exception:
        return None

def load_latest_cache():
    try:
        files = sorted(
            [f for f in os.listdir(CACHE_DIR) if f.endswith('.json')],
            reverse=True
        )
        for fname in files:
            path = os.path.join(CACHE_DIR, fname)
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            ts = parse_timestamp_from_filename(fname)
            if ts and isinstance(data, list):
                return fname, ts, data
    except Exception as e:
        print(f"[ERROR] Failed to load cache: {e}")
    return None, None, []

def load_last_logged_times():
    if os.path.exists(LAST_TIMES_FILE):
        with open(LAST_TIMES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_last_logged_times(data):
    with open(LAST_TIMES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f)

def should_log_now(log_times):
    now = datetime.now()
    now_str = now.strftime("%H:%M")
    today = now.strftime("%Y-%m-%d")

    last_logged_times = load_last_logged_times()
    last_logged_date = last_logged_times.get(now_str)

    if now_str in log_times and last_logged_date != today:
        last_logged_times[now_str] = today
        save_last_logged_times(last_logged_times)
        return True
    return False

def log_data():
    print(f"[DEBUG] Attempting to load cache from: {CACHE_DIR}")
    settings = load_settings()
    log_dir = os.path.join(BASE_DIR, settings.get('log_directory', 'logs'))
    os.makedirs(log_dir, exist_ok=True)
    print(f"[DEBUG] Logging to directory: {log_dir}")

    fname, ts, data = load_latest_cache()
    if fname is None or not data:
        print("[WARN] No valid cache to log.")
        return

    timestamp_str = ts.strftime('%Y-%m-%d %H:%M:%S')

    for device in data:
        dev_id = device.get('id')
        temperature = device.get('temperature', '')
        humidity = device.get('humidity', '')
        last_seen = device.get('last_seen', '')

        log_file = os.path.join(log_dir, f"{dev_id}.csv")
        write_header = not os.path.exists(log_file)

        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                if write_header:
                    f.write("timestamp,temperature,humidity,last_seen\n")
                f.write(f"{timestamp_str},{temperature},{humidity},{last_seen}\n")
            print(f"[INFO] Logged: {dev_id} at {timestamp_str}")
        except Exception as e:
            print(f"[ERROR] Writing log for {dev_id} failed: {e}")

def main():
    print("[DEBUG] cache_logger started")
    while True:
        try:
            settings = load_settings()
            log_times = settings.get("log_times", ["03:00", "09:00"])

            if should_log_now(log_times):
                print(f"[DEBUG] Matched log time, logging now...")
                log_data()
            else:
                print(f"[DEBUG] Not time to log yet.")
        except Exception:
            print("[ERROR] Unexpected error:")
            traceback.print_exc()

        time.sleep(60)  # 毎分チェック

if __name__ == '__main__':
    main()
