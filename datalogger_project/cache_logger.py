import os
import json
import time
from datetime import datetime, timedelta
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, 'settings.json')
CACHE_DIR = os.path.join(BASE_DIR, 'cache')
LAST_TIMES_FILE = os.path.join(BASE_DIR, 'last_logged_times.txt')
ASSIGNMENT_FILE = os.path.join(BASE_DIR, "device_assignments.json")  # ← 追加（未定義エラー対策）


def load_settings():
    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def parse_timestamp_from_filename(filename):
    try:
        name_part = filename.replace("device_cache_", "").replace(".json", "")
        return datetime.strptime(name_part, '%Y%m%d%H%M%S')
    except Exception:
        return None

def load_nearest_cache(log_time: datetime):
    nearest_ts = None
    nearest_data = []
    min_diff = timedelta.max

    for fname in sorted(os.listdir(CACHE_DIR), reverse=True):
        if not fname.endswith(".json"):
            continue
        try:
            ts = parse_timestamp_from_filename(fname)
            if ts is None:
                continue
            diff = abs(log_time - ts)
            if diff < min_diff:
                with open(os.path.join(CACHE_DIR, fname), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    nearest_ts = ts
                    nearest_data = data
                    min_diff = diff
        except Exception:
            continue

    return nearest_ts, nearest_data

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

def load_device_assignments():
    if os.path.exists(ASSIGNMENT_FILE):
        with open(ASSIGNMENT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def log_data():
    print(f"[DEBUG] Attempting to load cache from: {CACHE_DIR}")
    settings = load_settings()
    log_dir = os.path.join(BASE_DIR, settings.get('log_directory', 'logs'))
    os.makedirs(log_dir, exist_ok=True)
    print(f"[DEBUG] Logging to directory: {log_dir}")
    assignments = load_device_assignments()

    now = datetime.now()
    ts, data = load_nearest_cache(now)
    if ts is None or not data:
        print("[WARN] No valid cache to log.")
        return

    timestamp_str = ts.strftime('%Y-%m-%d %H:%M:%S')

    for device in data:
        dev_id = device.get('id')
        temperature = device.get('temperature', '')
        humidity = device.get('humidity', '')
        last_seen = device.get('last_seen', '')
        warehouse = assignments.get(dev_id, '')  # ← 倉庫名を取得

        log_file = os.path.join(log_dir, f"{dev_id}.csv")
        write_header = not os.path.exists(log_file)

        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                if write_header:
                    f.write("timestamp,temperature,humidity,last_seen,warehouse\n")  # ← ヘッダ追加
                f.write(f"{timestamp_str},{temperature},{humidity},{last_seen},{warehouse}\n")  # ← 内容追加
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
