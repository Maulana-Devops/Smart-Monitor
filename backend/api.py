from flask import Flask, jsonify, render_template, request
import docker
import psutil
import json
import threading
import time
from datetime import datetime
from pathlib import Path


app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static",
)


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = Path("/root/smart-monitor")

INCIDENT_FILE = BASE_DIR / "logs" / "incident_log.json"
STATUS_FILE = BASE_DIR / "current_status.json"
TELEMETRY_FILE = BASE_DIR / "telemetry_history.json"


# ============================================================
# GLOBAL STATE
# ============================================================

docker_client = docker.from_env()

INCIDENT_LOGS = []

TELEMETRY_HISTORY = []
MAX_TELEMETRY_HISTORY = 60

TELEMETRY_INTERVAL = 5

telemetry_lock = threading.Lock()
telemetry_thread = None
telemetry_running = False


# ============================================================
# TIME
# ============================================================

def get_current_time_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
# INCIDENT STORAGE
# ============================================================

def load_incidents():
    global INCIDENT_LOGS

    try:
        if INCIDENT_FILE.exists():
            with open(
                INCIDENT_FILE,
                "r",
                encoding="utf-8",
            ) as f:
                data = json.load(f)

            if isinstance(data, list):
                INCIDENT_LOGS = data
                return INCIDENT_LOGS

    except (
        json.JSONDecodeError,
        OSError,
    ) as exc:
        print(
            f"[Incident] Load error: {exc}"
        )

    INCIDENT_LOGS = []
    return INCIDENT_LOGS


def save_incidents():
    try:
        INCIDENT_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with open(
            INCIDENT_FILE,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                INCIDENT_LOGS,
                f,
                indent=2,
                ensure_ascii=False,
            )

    except OSError as exc:
        print(f"[Incident] Save error: {exc}")


def log_incident(
    metric_type,
    severity,
    current_val,
    baseline,
    message,
):
    incident = {
        "timestamp": get_current_time_str(),
        "metric_type": metric_type,
        "severity": severity,
        "current_value": current_val,
        "baseline": baseline,
        "analytical_message": message,
    }

    INCIDENT_LOGS.append(incident)

    if len(INCIDENT_LOGS) > 500:
        del INCIDENT_LOGS[:-500]

    save_incidents()

    return incident


# ============================================================
# SYSTEM METRICS
# ============================================================

def get_system_metrics():
    cpu = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()

    return {
        "cpu": round(cpu, 1),
        "ram": round(
            memory.used / (1024 * 1024),
            1,
        ),
        "ram_percent": round(
            memory.percent,
            1,
        ),
    }


# ============================================================
# HEALTH SCORE
# ============================================================

def calculate_health_score(
    cpu,
    ram_percent,
    container_data,
):
    score = 100

    if cpu >= 90:
        score -= 35
    elif cpu >= 75:
        score -= 20
    elif cpu >= 60:
        score -= 10

    if ram_percent >= 90:
        score -= 35
    elif ram_percent >= 80:
        score -= 20
    elif ram_percent >= 70:
        score -= 10

    running = sum(
        1
        for container in container_data
        if container["status"] == "running"
    )

    total = len(container_data)

    if total > 0:
        stopped = total - running

        if stopped >= 3:
            score -= 20
        elif stopped >= 1:
            score -= 5

    return max(
        0,
        min(100, score),
    )


# ============================================================
# DOCKER
# ============================================================

def get_container_data():
    containers = []

    try:
        all_containers = docker_client.containers.list(
            all=True
        )

        for container in all_containers:
            containers.append({
                "id": container.short_id,
                "name": container.name,
                "image": (
                    container.image.tags[0]
                    if container.image.tags
                    else container.image.short_id
                ),
                "status": container.status,
            })

    except Exception as exc:
        print(f"[Docker] Error: {exc}")

    return containers


# ============================================================
# TELEMETRY STORAGE
# ============================================================

def load_telemetry_history():
    global TELEMETRY_HISTORY

    try:
        if not TELEMETRY_FILE.exists():
            TELEMETRY_HISTORY = []
            return TELEMETRY_HISTORY

        with open(
            TELEMETRY_FILE,
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)

        if isinstance(data, list):
            TELEMETRY_HISTORY = data[-MAX_TELEMETRY_HISTORY:]
        else:
            TELEMETRY_HISTORY = []

    except (
        json.JSONDecodeError,
        OSError,
    ) as exc:
        print(
            f"[Telemetry] Load error: {exc}"
        )
        TELEMETRY_HISTORY = []

    return TELEMETRY_HISTORY


def save_telemetry_history():
    try:
        TELEMETRY_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with open(
            TELEMETRY_FILE,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                TELEMETRY_HISTORY,
                f,
                indent=2,
                ensure_ascii=False,
            )

    except OSError as exc:
        print(
            f"[Telemetry] Save error: {exc}"
        )


# ============================================================
# TELEMETRY COLLECTION
# ============================================================

def collect_telemetry():
    metrics = get_system_metrics()

    containers = get_container_data()

    health_score = calculate_health_score(
        metrics["cpu"],
        metrics["ram_percent"],
        containers,
    )

    running_containers = sum(
        1
        for container in containers
        if container["status"] == "running"
    )

    sample = {
        "timestamp": get_current_time_str(),
        "cpu": metrics["cpu"],
        "ram": metrics["ram"],
        "ram_percent": metrics["ram_percent"],
        "containers": running_containers,
        "total_containers": len(containers),
        "health_score": health_score,
    }

    with telemetry_lock:
        TELEMETRY_HISTORY.append(sample)

        if len(TELEMETRY_HISTORY) > MAX_TELEMETRY_HISTORY:
            del TELEMETRY_HISTORY[
                :-MAX_TELEMETRY_HISTORY
            ]

        save_telemetry_history()

    return sample


# ============================================================
# BACKGROUND TELEMETRY COLLECTOR
# ============================================================

def telemetry_worker():
    global telemetry_running

    print(
        "[Telemetry] Background collector started"
    )

    while telemetry_running:
        try:
            sample = collect_telemetry()

            print(
                "[Telemetry] "
                f"{sample['timestamp']} | "
                f"CPU={sample['cpu']}% | "
                f"RAM={sample['ram_percent']}% | "
                f"Containers="
                f"{sample['containers']}/"
                f"{sample['total_containers']} | "
                f"Health="
                f"{sample['health_score']}"
            )

        except Exception as exc:
            print(
                f"[Telemetry] Collector error: {exc}"
            )

        time.sleep(TELEMETRY_INTERVAL)

    print(
        "[Telemetry] Background collector stopped"
    )


def start_telemetry_collector():
    global telemetry_thread
    global telemetry_running

    if telemetry_thread is not None:
        if telemetry_thread.is_alive():
            return

    telemetry_running = True

    telemetry_thread = threading.Thread(
        target=telemetry_worker,
        name="smart-monitor-telemetry",
        daemon=True,
    )

    telemetry_thread.start()


# ============================================================
# INCIDENT NORMALIZATION
# ============================================================

def normalize_incident(incident):
    """
    Normalize incident data into the frontend contract.

    Canonical backend format:

    {
        "timestamp": "...",
        "type": "CPU_SPIKE",
        "details": {
            "status": "ACTIVE|RESOLVED",
            "severity": "...",
            "anomalies": [...],
            "metrics": {...}
        }
    }
    """

    if not isinstance(incident, dict):
        incident = {}

    # --------------------------------------------------------
    # ROOT FIELDS
    # --------------------------------------------------------

    timestamp = (
        incident.get("timestamp")
        or incident.get("time")
        or get_current_time_str()
    )

    metric_type = (
        incident.get("type")
        or incident.get("event_type")
        or incident.get("metric_type")
        or "UNKNOWN"
    )

    details = incident.get("details")

    if not isinstance(details, dict):
        details = {}

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    status = str(
        details.get("status")
        or incident.get("status")
        or "ACTIVE"
    ).upper()

    # --------------------------------------------------------
    # SEVERITY
    # --------------------------------------------------------

    severity = str(
        details.get("severity")
        or incident.get("severity")
        or ("INFO" if status == "RESOLVED" else "WARNING")
    ).upper()

    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    metrics = details.get("metrics")

    if not isinstance(metrics, dict):
        metrics = {}

    # Copy legacy/root-level metrics if necessary.
    for key in (
        "cpu",
        "cpu_percent",
        "ram",
        "ram_percent",
        "ram_used_mb",
        "containers",
    ):
        if key in incident and key not in metrics:
            metrics[key] = incident[key]

    # --------------------------------------------------------
    # CURRENT VALUE
    # --------------------------------------------------------

    current_value = incident.get("current_value")

    if current_value is None:
        if metric_type == "CPU_SPIKE":
            current_value = metrics.get(
                "cpu_percent",
                metrics.get("cpu")
            )

        elif metric_type in (
            "HIGH_MEMORY",
            "RAM_OVERLOAD",
        ):
            current_value = metrics.get(
                "ram_percent",
                metrics.get("ram")
            )

        else:
            current_value = metrics.get(
                "value"
            )

    # --------------------------------------------------------
    # BASELINE
    # --------------------------------------------------------

    baseline = incident.get("baseline")

    if baseline is None:
        baseline = incident.get("baseline_value")

    # --------------------------------------------------------
    # ANOMALIES
    # --------------------------------------------------------

    anomalies = details.get("anomalies")

    if not isinstance(anomalies, list):
        anomalies = incident.get("anomalies")

    if not isinstance(anomalies, list):
        anomalies = []

    # IMPORTANT:
    # RESOLVED incidents must never be reported
    # as currently anomalous.
    if status == "RESOLVED":
        anomalies = []

    elif not anomalies and metric_type in (
        "CPU_SPIKE",
        "HIGH_MEMORY",
        "RAM_OVERLOAD",
    ):
        anomalies = [metric_type]

    # --------------------------------------------------------
    # MESSAGE
    # --------------------------------------------------------

    message = (
        details.get("message")
        or incident.get("message")
        or incident.get("analytical_message")
    )

    if not message:
        if metric_type == "CPU_SPIKE":
            if status == "RESOLVED":
                message = (
                    "CPU usage has returned to normal."
                )
            else:
                message = (
                    "CPU usage exceeded the configured threshold."
                )

        elif metric_type in (
            "HIGH_MEMORY",
            "RAM_OVERLOAD",
        ):
            if status == "RESOLVED":
                message = (
                    "RAM usage has returned to normal."
                )
            else:
                message = (
                    "RAM usage exceeded the configured threshold."
                )

        elif metric_type == "CONTAINER_DOWN":
            message = "Container stopped."

        elif metric_type == "CONTAINER_UP":
            message = "Container started."

        elif metric_type == "CONTAINER_RESTART":
            message = "Container restarted."

        elif metric_type == "ANOMALY_DETECTED":
            message = "Infrastructure anomaly detected."

        else:
            message = "Infrastructure event detected."

    # --------------------------------------------------------
    # NORMALIZED METRIC ALIASES
    # --------------------------------------------------------

    if metric_type == "CPU_SPIKE":
        if "cpu_percent" in metrics:
            metrics.setdefault(
                "cpu",
                metrics["cpu_percent"],
            )

    if metric_type in (
        "HIGH_MEMORY",
        "RAM_OVERLOAD",
    ):
        if "ram_percent" in metrics:
            metrics.setdefault(
                "ram",
                metrics["ram_percent"],
            )

    # --------------------------------------------------------
    # FINAL FRONTEND CONTRACT
    # --------------------------------------------------------

    return {
        "timestamp": timestamp,
        "event_type": metric_type,
        "severity": severity,
        "current_value": current_value,
        "baseline": baseline,
        "message": message,
        "metrics": metrics,
        "anomalies": anomalies,
    }


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def index():
    return render_template(
        "dashboard.html"
    )


@app.route(
    "/api/status",
    methods=["GET"],
)
def get_status():
    metrics = get_system_metrics()

    containers = get_container_data()

    health_score = calculate_health_score(
        metrics["cpu"],
        metrics["ram_percent"],
        containers,
    )

    running_containers = sum(
        1
        for container in containers
        if container["status"] == "running"
    )

    response = {
        "timestamp": get_current_time_str(),
        "cpu": metrics["cpu"],
        "ram": metrics["ram"],
        "ram_percent": metrics["ram_percent"],
        "containers": running_containers,
        "total_containers": len(containers),
        "health_score": health_score,
    }

    try:
        with open(
            STATUS_FILE,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                response,
                f,
                indent=2,
                ensure_ascii=False,
            )

    except OSError as exc:
        print(
            f"[Status] Save error: {exc}"
        )

    return jsonify(response)


@app.route(
    "/api/containers",
    methods=["GET"],
)
def get_containers():
    return jsonify(
        get_container_data()
    )


@app.route(
    "/api/telemetry",
    methods=["GET"],
)
def get_telemetry():
    with telemetry_lock:
        history = list(
            TELEMETRY_HISTORY
        )

    current = (
        history[-1]
        if history
        else collect_telemetry()
    )

    return jsonify({
        "current": current,
        "history": history,
    })


@app.route(
    "/api/incidents",
    methods=["GET"],
)
def get_incidents():
    load_incidents()

    normalized = [
        normalize_incident(incident)
        for incident in INCIDENT_LOGS
    ]

    return jsonify(normalized)


@app.route(
    "/api/container/action",
    methods=["POST"],
)
def container_action():
    data = request.get_json(
        silent=True
    ) or {}

    container_name = data.get("name")
    action = data.get("action")

    if not container_name:
        return jsonify({
            "status": "error",
            "message": "Container name is required",
        }), 400

    if action not in (
        "start",
        "stop",
        "restart",
    ):
        return jsonify({
            "status": "error",
            "message": "Invalid action",
        }), 400

    try:
        container = (
            docker_client.containers.get(
                container_name
            )
        )

        if action == "start":
            container.start()

            log_incident(
                "CONTAINER_UP",
                "INFO",
                "RUNNING",
                "State: STARTED",
                f"Container {container.name} started",
            )

        elif action == "stop":
            container.stop()

            log_incident(
                "CONTAINER_DOWN",
                "HIGH",
                "EXITED",
                "State: STOPPED",
                f"Container {container.name} stopped by Admin",
            )

        elif action == "restart":
            container.restart()

            log_incident(
                "CONTAINER_RESTART",
                "INFO",
                "RUNNING",
                "State: RESTARTED",
                f"Container {container.name} restarted",
            )

        return jsonify({
            "status": "success",
            "message": (
                f"Container {container.name} "
                f"({action}) successful"
            ),
        })

    except docker.errors.NotFound:
        return jsonify({
            "status": "error",
            "message": "Container not found",
        }), 404

    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": str(exc),
        }), 500


# ============================================================
# INITIALIZATION
# ============================================================

load_incidents()

load_telemetry_history()

start_telemetry_collector()


# ============================================================
# APPLICATION ENTRYPOINT
# ============================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5050,
        debug=False,
    )
