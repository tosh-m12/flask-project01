from flask import Flask, render_template, jsonify, request, redirect, url_for
import requests
import json
import os

app = Flask(__name__)

LOGIN_URL = "http://1weilian.com/user/login"
DATA_URL = "http://1weilian.com/public/realTimeData"

ACCOUNT = "nglswhs47"
PASSWORD = "ngls1234"

ASSIGNMENT_FILE = "device_assignments.json"
SETTINGS_FILE = "settings.json"
WAREHOUSE_FILE = "warehouse_names.json"


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
        result = response.json()
        data_list = result["data"]["dataList"]
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

def load_device_assignments():
    if os.path.exists(ASSIGNMENT_FILE):
        with open(ASSIGNMENT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_device_assignments(assignments):
    with open(ASSIGNMENT_FILE, "w", encoding="utf-8") as f:
        json.dump(assignments, f, ensure_ascii=False, indent=2)

def load_json(filename, default):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

WAREHOUSE_FILE = "warehouses.json"

def load_warehouse_names():
    if os.path.exists(WAREHOUSE_FILE):
        with open(WAREHOUSE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return ["倉庫A", "倉庫B", "倉庫C"]

@app.route("/")
def index():
    settings = load_json(SETTINGS_FILE, {"interval": 10})
    return render_template("index.html", interval=settings.get("interval", 10))


@app.route("/data")
def data():
    try:
        token, user_id = login_and_get_token()
        devices = fetch_all_devices(token, user_id)
        assignments = load_json(ASSIGNMENT_FILE, {})
        for device in devices:
            device["warehouse"] = assignments.get(device["id"], "")
        return jsonify(devices)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/settings", methods=["GET", "POST"])
def settings():
    settings = load_json(SETTINGS_FILE, {"interval": 10})
    if request.method == "POST":
        interval = int(request.form.get("interval", 10))
        settings["interval"] = interval
        save_json(SETTINGS_FILE, settings)
        return redirect(url_for("index"))
    return render_template("settings.html", interval=settings.get("interval", 10))


@app.route("/warehouse_assign", methods=["GET", "POST"])
def warehouse_assign():
    try:
        token, user_id = login_and_get_token()
        devices = fetch_all_devices(token, user_id)
        all_device_ids = [d["id"] for d in devices]
        device_names = {d["id"]: d["name"] for d in devices}

        warehouse_names = load_warehouse_names()
        assignments = load_device_assignments()

        if request.method == "POST":
            assignments_json = request.form.get("assignments_json")
            if assignments_json:
                new_assignments = json.loads(assignments_json)
                save_device_assignments(new_assignments)
            return redirect(url_for("settings"))

        # 表示用データの構成（GET時）
        warehouse_to_devices = {wh: [] for wh in warehouse_names}
        unassigned_devices = []

        for device_id in all_device_ids:
            warehouse = assignments.get(device_id)
            if warehouse in warehouse_to_devices:
                warehouse_to_devices[warehouse].append({
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
            warehouses=warehouse_names,               # 倉庫名のリスト
            assignments=assignments,                  # デバイスID → 倉庫名 の dict
            unassigned=[d["id"] for d in unassigned_devices],  # 割り当てなしIDリスト
            assignments_json=json.dumps(assignments, ensure_ascii=False)
        )
    except Exception as e:
        return f"エラー: {e}", 500


@app.route("/warehouse_names", methods=["GET", "POST"])
def warehouse_names():
    warehouses = load_json(WAREHOUSE_FILE, ["A", "B", "C"])

    if request.method == "POST":
        new_warehouses = []
        for key in request.form:
            if key.startswith("warehouse_"):
                name = request.form.get(key, "").strip()
                if name:
                    new_warehouses.append(name)
        save_json(WAREHOUSE_FILE, new_warehouses)
        return redirect(url_for("settings"))

    return render_template("warehouse_names.html", warehouses=warehouses)



if __name__ == "__main__":
    app.run(debug=True)
