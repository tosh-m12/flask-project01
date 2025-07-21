from flask import Flask, render_template, jsonify, request, redirect, url_for
import requests
import json
import os
import subprocess
import sys
from datetime import datetime

app = Flask(__name__)

LOGIN_URL = "http://1weilian.com/user/login"
DATA_URL = "http://1weilian.com/public/realTimeData"
ACCOUNT = "nglswhs47"
PASSWORD = "ngls1234"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSIGNMENT_FILE = os.path.join(BASE_DIR, "device_assignments.json")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
WAREHOUSE_FILE = os.path.join(BASE_DIR, "warehouses.json")
LOCATION_FILE = os.path.join(BASE_DIR, "locations.json")
ASSIGNMENT_HISTORY_FILE = os.path.join(BASE_DIR, "assignment_history.json")
CACHE_DIR = os.path.join(BASE_DIR, "cache")

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
            if "data" not in result or "dataList" not in result["data"]:
                print(f"[WARN] No dataList found in response: {result}")
                break
            data_list = result["data"]["dataList"]
        except Exception as e:
            print(f"[ERROR] Failed to parse device data: {e}")
            break

        if not data_list:
            break

        for dev in data_list:
            all_devices.append({
                "id": dev["sn"],
                "name": dev["deviceName"],
                "temperature": dev["temperature"] if dev["status"] == 0 else "-",
                "humidity": dev["humidity"] if dev["status"] == 0 else "-",
                "last_seen": dev["date"],
                "online": dev["status"] == 0
            })

        page += 1
    return all_devices

def start_background_tasks():
    try:
        subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "cache_worker.py")],
                         stdout=sys.stdout, stderr=sys.stderr)
        subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "cache_logger.py")],
                         stdout=sys.stdout, stderr=sys.stderr)
    except Exception as e:
        print(f"[ERROR] Failed to start background tasks: {e}")

def load_json(filename, default):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_latest_cache():
    latest_file = os.path.join(CACHE_DIR, 'device_cache_latest.json')
    if not os.path.exists(latest_file):
        return None, []
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        timestamp = os.path.getmtime(latest_file)
        dt = datetime.fromtimestamp(timestamp)
        return dt, data
    except Exception as e:
        print(f"[ERROR] Failed to load latest cache: {e}")
        return None, []

def record_assignment_history(device_id, location_id):
    history = load_json(ASSIGNMENT_HISTORY_FILE, {})
    if device_id not in history:
        history[device_id] = []
    history[device_id].append({
        "location_id": location_id,
        "timestamp": datetime.now().isoformat()
    })
    save_json(ASSIGNMENT_HISTORY_FILE, history)

@app.route("/")
def index():
    dt, devices = load_latest_cache()
    assignments = load_json(ASSIGNMENT_FILE, {})
    locations = load_json(LOCATION_FILE, {})
    settings = load_json(SETTINGS_FILE, {})

    warehouse_devices = {}
    for device in devices:
        device_id = str(device.get("id"))
        loc_id = assignments.get(device_id)

        if not loc_id or not isinstance(loc_id, str) or loc_id.strip() == "":
            continue

        warehouse = locations.get(loc_id)
        if not warehouse or warehouse == "未割当":
            continue  # 表示除外条件を追加

        warehouse_devices.setdefault(warehouse, []).append(device)

    return render_template("index.html", warehouse_devices=warehouse_devices,
                           interval=settings.get("interval", 10),
                           last_updated=dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "N/A")

@app.route("/data")
def data():
    try:
        token, user_id = login_and_get_token()
        devices = fetch_all_devices(token, user_id)
        assignments = load_json(ASSIGNMENT_FILE, {})
        locations = load_json(LOCATION_FILE, {})  # ← 追加

        for device in devices:
            loc_id = assignments.get(device["id"], "")
            device["location_id"] = loc_id
            device["warehouse"] = locations.get(loc_id, "未割当") if loc_id else "未割当"  # ← 追加

        return jsonify(devices)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/save_assignment", methods=["POST"])
def save_assignment():
    data = request.get_json()
    save_json(ASSIGNMENT_FILE, data)
    for dev_id, loc_id in data.items():
        record_assignment_history(dev_id, loc_id)
    return jsonify({"status": "ok"})

@app.route("/settings", methods=["GET", "POST"])
def settings():
    settings = load_json(SETTINGS_FILE, {
        "interval": 10,
        "cache_interval": 10,
        "cache_expire_hours": 72,
        "log_times": ["03:00", "09:00"],
        "log_directory": "logs"
    })

    if request.method == "POST":
        settings["interval"] = int(request.form.get("interval", settings["interval"]))
        settings["cache_interval"] = int(request.form.get("cache_interval", settings["cache_interval"]))
        settings["cache_expire_hours"] = int(request.form.get("cache_expire_hours", settings["cache_expire_hours"]))
        settings["log_directory"] = request.form.get("log_directory", settings["log_directory"]).strip()
        settings["log_times"] = request.form.getlist("log_times")
        save_json(SETTINGS_FILE, settings)
        return redirect(url_for("index"))

    return render_template("settings.html", **settings)

@app.route("/locations", methods=["GET", "POST"])
def edit_locations():
    locations = load_json(LOCATION_FILE, {})
    if request.method == "POST":
        new_locations = {}
        for key in request.form:
            if key.startswith("loc_"):
                loc_id = key[4:]
                name = request.form[key].strip()
                if name:
                    new_locations[loc_id] = name
        save_json(LOCATION_FILE, new_locations)
        return redirect(url_for("edit_locations"))
    return render_template("locations.html", locations=locations)

@app.route("/warehouse_assign", methods=["GET", "POST"])
def warehouse_assign():
    token, user_id = login_and_get_token()
    devices = fetch_all_devices(token, user_id)
    assignments = load_json(ASSIGNMENT_FILE, {})
    locations = load_json(LOCATION_FILE, {})
    device_names = {d["id"]: d["name"] for d in devices}

    if request.method == "POST":
        assignments_json = request.form.get("assignments_json")
        if assignments_json:
            new_assignments = json.loads(assignments_json)
            save_json(ASSIGNMENT_FILE, new_assignments)
            for device_id, loc_id in new_assignments.items():
                record_assignment_history(device_id, loc_id)
        return redirect(url_for("settings"))

    # 表示用データの構築
    warehouse_to_devices = {}
    unassigned_devices = []

    for d in devices:
        device_id = d["id"]
        loc_id = assignments.get(device_id)
        if loc_id and loc_id in locations:
            warehouse_to_devices.setdefault(loc_id, []).append({
                "id": device_id,
                "name": device_names.get(device_id, "")
            })
        else:
            unassigned_devices.append({
                "id": device_id,
                "name": device_names.get(device_id, "")
            })

    return render_template(
        "warehouse_assign.html",
        assignments=assignments,
        locations=locations,  # location_id → 倉庫名の辞書
        warehouse_to_devices=warehouse_to_devices,  # location_id → device list
        unassigned_devices=unassigned_devices,  # ← 正しい名前で渡す
        assignments_json=json.dumps(assignments, ensure_ascii=False)
    )



@app.route("/warehouse_names")
def warehouse_names():
    return redirect(url_for("edit_locations"))

@app.route("/all_devices")
def all_devices():
    dt, devices = load_latest_cache()
    assignments = load_json(ASSIGNMENT_FILE, {})
    locations = load_json(LOCATION_FILE, {})

    # location_id → 倉庫名の辞書を参照してデバイス情報に追加
    for dev in devices:
        loc_id = assignments.get(dev["id"])
        dev["location_id"] = loc_id
        dev["location_name"] = locations.get(loc_id, "未割当")

    return render_template("all_devices.html", devices=devices,
                           last_updated=dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "N/A")

if __name__ == "__main__":
    start_background_tasks()
    app.run(debug=True)
