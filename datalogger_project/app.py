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
SETTINGS_FILE = "settings.json"  # ← 更新間隔など保存

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

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"interval": 10}

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

@app.route("/")
def index():
    settings_data = load_settings()
    interval = settings_data.get("interval", 10)
    return render_template("index.html", interval=interval)

@app.route("/data")
def data():
    try:
        token, user_id = login_and_get_token()
        devices = fetch_all_devices(token, user_id)
        assignments = load_device_assignments()
        for device in devices:
            device["warehouse"] = assignments.get(device["id"], "")
        return jsonify(devices)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/settings", methods=["GET", "POST"])
def settings():
    try:
        token, user_id = login_and_get_token()
        devices = fetch_all_devices(token, user_id)
        device_ids = [d["id"] for d in devices]
        assignments = load_device_assignments()
        settings_data = load_settings()

        if request.method == "POST":
            # 更新間隔
            interval = int(request.form.get("interval", 10))

            # 倉庫割当の保存
            for device_id in device_ids:
                selected = request.form.get(device_id, "")
                if selected:
                    assignments[device_id] = selected
                elif device_id in assignments:
                    del assignments[device_id]

            save_device_assignments(assignments)
            save_settings({"interval": interval})
            return redirect(url_for("index"))

        return render_template(
            "settings.html",
            device_ids=device_ids,
            assignments=assignments,
            interval=settings_data.get("interval", 10)
        )
    except Exception as e:
        return f"エラー: {e}", 500

if __name__ == "__main__":
    app.run(debug=True)
