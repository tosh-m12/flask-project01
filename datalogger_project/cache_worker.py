import os
import json
import time
from datetime import datetime, timedelta
import requests

LOGIN_URL = "http://1weilian.com/user/login"
DATA_URL = "http://1weilian.com/public/realTimeData"
ACCOUNT = "nglswhs47"
PASSWORD = "ngls1234"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
ASSIGNMENT_FILE = os.path.join(BASE_DIR, "device_assignments.json")
CACHE_DIR = os.path.join(BASE_DIR, "cache")
LOCATION_FILE = os.path.join(BASE_DIR, "locations.json")

os.makedirs(CACHE_DIR, exist_ok=True)
print(f"[INFO] Cache directory ensured at: {os.path.abspath(CACHE_DIR)}")

def load_json(filename, default=None):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default if default is not None else {}

def load_settings():
    return load_json(SETTINGS_FILE, {})

def load_device_assignments():
    return load_json(ASSIGNMENT_FILE, {})

def login_and_get_token():
    payload = {
        "account": ACCOUNT,
        "pwd": PASSWORD,
        "systemVersion": "PC",
        "loginType": 2
    }
    headers = {"Content-Type": "application/json;charset=UTF-8"}
    response = requests.post(LOGIN_URL, json=payload, headers=headers)
    result = response.json()
    return result["data"]["accessToken"], result["data"]["userId"]

def load_locations():
    return load_json(LOCATION_FILE, {})

def fetch_all_devices(token, user_id):
    all_devices = []
    page = 0
    while True:
        payload = {
            "userId": user_id,
            "loginType": 2,
            "accessToken": token,
            "permissions": 2,
            "language": 1,
            "page": page,
            "rows": 20,
            "sortingType": 0
        }
        headers = {"Content-Type": "application/json;charset=UTF-8"}
        response = requests.post(DATA_URL, json=payload, headers=headers)
        try:
            result = response.json()
            data_list = result["data"]["dataList"]
        except (KeyError, ValueError) as e:
            print(f"[ERROR] Failed to parse response: {e}")
            break
        if not data_list:
            break
        for dev in data_list:
            all_devices.append({
                "id": dev["sn"],
                "name": dev["deviceName"],
                "temperature": dev["temperature"] if dev["status"] == 0 else "",
                "humidity": dev["humidity"] if dev["status"] == 0 else "",
                "last_seen": dev["date"],
                "online": dev["status"] == 0
            })
        page += 1
    return all_devices

def cleanup_cache(expire_hours):
    now = datetime.now()
    for fname in os.listdir(CACHE_DIR):
        if fname.endswith(".json") and "device_cache_" in fname:
            try:
                ts = datetime.strptime(fname.replace("device_cache_", "").replace(".json", ""), "%Y%m%d%H%M%S")
                if now - ts > timedelta(hours=expire_hours):
                    path = os.path.join(CACHE_DIR, fname)
                    os.remove(path)
                    print(f"[INFO] Deleted expired cache: {path}")
            except:
                continue

def main():
    print("[DEBUG] cache_worker main loop starting")
    while True:
        settings = load_settings()
        interval = settings.get("cache_interval", 300)
        expire_hours = settings.get("cache_expire_hours", 168)

        try:
            try:
                token, user_id = login_and_get_token()
            except Exception as e:
                print(f"[ERROR] Login failed: {e}")
                time.sleep(interval)
                continue

            try:
                devices = fetch_all_devices(token, user_id)
            except Exception as e:
                print(f"[ERROR] Fetching devices failed: {e}")
                devices = []

            assignments = load_device_assignments()
            locations = load_json(LOCATION_FILE, {})

            for d in devices:
                d["location_id"] = assignments.get(d["id"], None)
                d["warehouse"] = locations.get(d["location_id"], "未割当") if d["location_id"] else "未割当"  # ← 追加

            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            cache_file = os.path.join(CACHE_DIR, f"device_cache_{timestamp}.json")
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(devices, f, ensure_ascii=False, indent=2)
                print(f"[INFO] Cache saved to {cache_file}")

                latest_cache_file = os.path.join(CACHE_DIR, "device_cache_latest.json")
                with open(latest_cache_file, "w", encoding="utf-8") as f:
                    json.dump(devices, f, ensure_ascii=False, indent=2)
                print(f"[INFO] device_cache_latest.json updated")

            except Exception as e:
                print(f"[ERROR] Saving cache failed: {e}")

            try:
                cleanup_cache(expire_hours)
            except Exception as e:
                print(f"[ERROR] Cache cleanup failed: {e}")

        except Exception as e:
            print(f"[FATAL ERROR] Unexpected error in main loop: {e}")
        finally:
            time.sleep(interval)

if __name__ == "__main__":
    main()
