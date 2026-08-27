import json
from datetime import datetime
from pathlib import Path


class IncidentManager:
    """
    Mengelola penyimpanan incident SIOD.

    Format canonical incident:

    {
        "timestamp": "...",
        "type": "CPU_SPIKE",
        "details": {
            "status": "ACTIVE",
            "severity": "CRITICAL",
            "anomalies": ["CPU_SPIKE"],
            "metrics": {...}
        }
    }
    """

    def __init__(self, log_file=None):
        base_dir = Path("/root/smart-monitor")

        self.log_file = (
            Path(log_file)
            if log_file
            else base_dir / "logs" / "incident_log.json"
        )

        self.log_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _load(self):
        try:
            if not self.log_file.exists():
                return []

            with open(
                self.log_file,
                "r",
                encoding="utf-8",
            ) as f:
                data = json.load(f)

            return data if isinstance(data, list) else []

        except (
            OSError,
            json.JSONDecodeError,
        ):
            return []

    def _save(self, incidents):
        with open(
            self.log_file,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                incidents,
                f,
                indent=2,
                ensure_ascii=False,
            )

    def log_incident(self, incident_type, details):
        """
        Simpan satu incident.

        incident_type:
            CPU_SPIKE
            HIGH_MEMORY
            CONTAINER_DOWN
            CONTAINER_UP
            CONTAINER_RESTART
            ANOMALY_DETECTED

        details:
            dictionary berisi status, severity,
            anomalies, dan metrics.
        """

        if not isinstance(details, dict):
            details = {}

        incident = {
            "timestamp": datetime.now().isoformat(),
            "type": str(incident_type),
            "details": {
                "status": details.get(
                    "status",
                    "ACTIVE",
                ),
                "severity": details.get(
                    "severity",
                    "INFO",
                ),
                "anomalies": (
                    details.get("anomalies")
                    if isinstance(
                        details.get("anomalies"),
                        list,
                    )
                    else []
                ),
                "metrics": (
                    details.get("metrics")
                    if isinstance(
                        details.get("metrics"),
                        dict,
                    )
                    else {}
                ),
            },
        }

        incidents = self._load()

        incidents.insert(
            0,
            incident,
        )

        # Simpan maksimum 500 event.
        incidents = incidents[:500]

        self._save(incidents)

        print(
            f"[IncidentManager] "
            f"{incident['type']} "
            f"{incident['details']['status']} "
            f"logged."
        )

        return incident

    def get_incidents(self):
        return self._load()
