from flask import Flask, jsonify, render_template
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "frontend", "templates"),
    static_folder=os.path.join(BASE_DIR, "frontend", "static")
)

LOG_FILE = os.path.join(BASE_DIR, "logs", "incident_log.json")
@app.route("/")
def dashboard():
    # Render file HTML statis, JavaScript di dalam berkas tersebut yang akan bekerja melakukan fetching
    return render_template("dashboard.html")

@app.route("/api/incidents")
def get_incidents():
    if not os.path.exists(LOG_FILE):
        return jsonify([])
    try:
        with open(LOG_FILE, "r") as file:
            data = json.load(file)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5060, debug=False)