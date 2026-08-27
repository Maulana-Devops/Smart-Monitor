import datetime
import sys
import time

import pytz

from collector import MetricsCollector
from telegram import kirim_telegram
from incident_manager import IncidentManager


# ==========================================================
# KONFIGURASI
# ==========================================================

# Zona waktu dikunci ke Asia/Jakarta (WIB)
LOCAL_TZ = pytz.timezone("Asia/Jakarta")

# Threshold anomaly
CPU_ALERT_THRESHOLD = 80.0
RAM_ALERT_THRESHOLD = 85.0

# Jumlah sample berturut-turut sebelum incident
# dianggap benar-benar aktif.
CPU_ALERT_CONSECUTIVE = 3
RAM_ALERT_CONSECUTIVE = 3

# Jumlah sample normal berturut-turut sebelum
# incident dianggap benar-benar resolved.
CPU_RECOVERY_CONSECUTIVE = 3
RAM_RECOVERY_CONSECUTIVE = 3


# ==========================================================
# TIME
# ==========================================================

def get_current_time():
    """Mengembalikan timestamp saat ini dalam zona waktu WIB."""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    return now_utc.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")


# ==========================================================
# TELEGRAM MESSAGE
# ==========================================================

def buat_pesan_cpu_alert(metrics, timestamp):
    """Membuat pesan ketika CPU melewati threshold."""

    return (
        "?? <b>SIOD ALERT: HIGH CPU USAGE</b>\n\n"
        f"CPU Usage: <code>{metrics['cpu']:.1f}%</code>\n"
        f"RAM Usage: <code>{metrics['ram_percent']:.1f}%</code>\n"
        f"RAM Used: <code>{metrics['ram']:.1f} MiB</code>\n"
        f"Running Containers: <code>{metrics['containers']}</code>\n\n"
        f"<b>Threshold:</b> {CPU_ALERT_THRESHOLD:.1f}%\n"
        f"<b>Waktu:</b> {timestamp} WIB\n\n"
        "Status: CPU usage melewati threshold secara persisten."
    )


def buat_pesan_cpu_resolved(metrics, timestamp):
    """Membuat pesan ketika CPU kembali normal."""

    return (
        "?? <b>SIOD RESOLVED: CPU NORMAL</b>\n\n"
        f"CPU Usage: <code>{metrics['cpu']:.1f}%</code>\n"
        f"RAM Usage: <code>{metrics['ram_percent']:.1f}%</code>\n"
        f"RAM Used: <code>{metrics['ram']:.1f} MiB</code>\n"
        f"Running Containers: <code>{metrics['containers']}</code>\n\n"
        f"<b>Threshold:</b> {CPU_ALERT_THRESHOLD:.1f}%\n"
        f"<b>Waktu:</b> {timestamp} WIB\n\n"
        "Status: CPU usage telah kembali normal secara persisten."
    )


def buat_pesan_ram_alert(metrics, timestamp):
    """Membuat pesan ketika RAM melewati threshold."""

    return (
        "?? <b>SIOD ALERT: HIGH RAM USAGE</b>\n\n"
        f"RAM Usage: <code>{metrics['ram_percent']:.1f}%</code>\n"
        f"RAM Used: <code>{metrics['ram']:.1f} MiB</code>\n"
        f"CPU Usage: <code>{metrics['cpu']:.1f}%</code>\n"
        f"Running Containers: <code>{metrics['containers']}</code>\n\n"
        f"<b>Threshold:</b> {RAM_ALERT_THRESHOLD:.1f}%\n"
        f"<b>Waktu:</b> {timestamp} WIB\n\n"
        "Status: RAM usage melewati threshold secara persisten."
    )


def buat_pesan_ram_resolved(metrics, timestamp):
    """Membuat pesan ketika RAM kembali normal."""

    return (
        "?? <b>SIOD RESOLVED: RAM NORMAL</b>\n\n"
        f"RAM Usage: <code>{metrics['ram_percent']:.1f}%</code>\n"
        f"RAM Used: <code>{metrics['ram']:.1f} MiB</code>\n"
        f"CPU Usage: <code>{metrics['cpu']:.1f}%</code>\n"
        f"Running Containers: <code>{metrics['containers']}</code>\n\n"
        f"<b>Threshold:</b> {RAM_ALERT_THRESHOLD:.1f}%\n"
        f"<b>Waktu:</b> {timestamp} WIB\n\n"
        "Status: RAM usage telah kembali normal secara persisten."
    )


# ==========================================================
# ENGINE
# ==========================================================

def run_engine():
    print("==========================================================")
    print("  SIOD Engine v2.2 - Persistent Anomaly Detection")
    print("==========================================================")

    print(
        f"[Config] CPU Alert Threshold     : "
        f"{CPU_ALERT_THRESHOLD:.1f}%"
    )
    print(
        f"[Config] CPU Alert Consecutive   : "
        f"{CPU_ALERT_CONSECUTIVE} samples"
    )
    print(
        f"[Config] CPU Recovery Consecutive: "
        f"{CPU_RECOVERY_CONSECUTIVE} samples"
    )
    print(
        f"[Config] RAM Alert Threshold     : "
        f"{RAM_ALERT_THRESHOLD:.1f}%"
    )
    print(
        f"[Config] RAM Alert Consecutive   : "
        f"{RAM_ALERT_CONSECUTIVE} samples"
    )
    print(
        f"[Config] RAM Recovery Consecutive: "
        f"{RAM_RECOVERY_CONSECUTIVE} samples"
    )
    print("[Config] Telegram notifier       : ENABLED")
    print("----------------------------------------------------------")

    # ======================================================
    # INITIALIZE COLLECTOR
    # ======================================================

    try:
        collector = MetricsCollector()
        incident_manager = IncidentManager()

    except Exception as e:
        print(
            f"[Engine Error] Gagal inisialisasi "
            f"MetricsCollector: {e}"
        )
        sys.exit(1)

    # ======================================================
    # ALERT STATE
    # ======================================================

    # False = kondisi normal
    # True  = alert sedang aktif
    cpu_alert_active = False
    ram_alert_active = False

    # Counter untuk persistence detection
    cpu_high_count = 0
    cpu_normal_count = 0

    ram_high_count = 0
    ram_normal_count = 0

    # ======================================================
    # MAIN LOOP
    # ======================================================

    while True:

        try:
            # ------------------------------------------------
            # Ambil metrik sistem
            # ------------------------------------------------

            metrics = collector.get_system_metrics()

            timestamp = get_current_time()

            cpu = float(metrics["cpu"])
            ram = float(metrics["ram"])
            ram_percent = float(metrics["ram_percent"])
            containers = int(metrics["containers"])

            # ------------------------------------------------
            # Print telemetry
            # ------------------------------------------------

            print(
                f"[{timestamp} WIB] "
                f"CPU: {cpu:.1f}% | "
                f"RAM: {ram:.1f} MiB ({ram_percent:.1f}%) | "
                f"Active Containers: {containers}"
            )

            # =================================================
            # CPU MONITORING
            # =================================================

            if cpu > CPU_ALERT_THRESHOLD:

                cpu_high_count += 1
                cpu_normal_count = 0

                print(
                    f"[CPU] Above threshold "
                    f"({cpu_high_count}/{CPU_ALERT_CONSECUTIVE})"
                )

                # Incident hanya dibuat setelah CPU
                # melewati threshold secara berturut-turut.
                if (
                    not cpu_alert_active
                    and cpu_high_count >= CPU_ALERT_CONSECUTIVE
                ):

                    incident_manager.log_incident(
                        "CPU_SPIKE",
                        {
                            "status": "ACTIVE",
                            "severity": "CRITICAL",
                            "anomalies": ["CPU_SPIKE"],
                            "metrics": {
                                "cpu_percent": cpu,
                                "ram_percent": ram_percent,
                                "ram_used_mb": ram,
                                "containers": containers,
                            },
                        },
                    )

                    cpu_alert_active = True

                    print(
                        "[INCIDENT STATE] "
                        "CPU incident = ACTIVE"
                    )

                    print(
                        "[TELEGRAM] "
                        "Menembakkan CPU alert..."
                    )

                    pesan = buat_pesan_cpu_alert(
                        metrics,
                        timestamp
                    )

                    kirim_telegram(pesan)

            else:

                cpu_high_count = 0

                if cpu_alert_active:

                    cpu_normal_count += 1

                    print(
                        f"[CPU] Recovery progress "
                        f"({cpu_normal_count}/{CPU_RECOVERY_CONSECUTIVE})"
                    )

                    # Incident baru dianggap resolved
                    # setelah CPU normal beberapa sample
                    # berturut-turut.
                    if (
                        cpu_normal_count
                        >= CPU_RECOVERY_CONSECUTIVE
                    ):

                        print(
                            "[RECOVERY] "
                            "CPU kembali ke kondisi normal."
                        )

                        cpu_alert_active = False
                        cpu_normal_count = 0

                        incident_manager.log_incident(
                            "CPU_SPIKE",
                            {
                                "status": "RESOLVED",
                                "severity": "INFO",
                                "anomalies": [],
                                "metrics": {
                                    "cpu_percent": cpu,
                                    "ram_percent": ram_percent,
                                    "ram_used_mb": ram,
                                    "containers": containers,
                                },
                            },
                        )

                        print(
                            "[INCIDENT STATE] "
                            "CPU incident = RESOLVED"
                        )

                        pesan = buat_pesan_cpu_resolved(
                            metrics,
                            timestamp
                        )

                        kirim_telegram(pesan)

                else:
                    cpu_normal_count = 0

            # =================================================
            # RAM MONITORING
            # =================================================

            if ram_percent > RAM_ALERT_THRESHOLD:

                ram_high_count += 1
                ram_normal_count = 0

                print(
                    f"[RAM] Above threshold "
                    f"({ram_high_count}/{RAM_ALERT_CONSECUTIVE})"
                )

                # Incident hanya dibuat setelah RAM
                # melewati threshold secara berturut-turut.
                if (
                    not ram_alert_active
                    and ram_high_count >= RAM_ALERT_CONSECUTIVE
                ):

                    incident_manager.log_incident(
                        "HIGH_MEMORY",
                        {
                            "status": "ACTIVE",
                            "severity": "CRITICAL",
                            "anomalies": ["HIGH_MEMORY"],
                            "metrics": {
                                "cpu_percent": cpu,
                                "ram_percent": ram_percent,
                                "ram_used_mb": ram,
                                "containers": containers,
                            },
                        },
                    )

                    ram_alert_active = True

                    print(
                        "[INCIDENT STATE] "
                        "RAM incident = ACTIVE"
                    )

                    print(
                        "[TELEGRAM] "
                        "Menembakkan RAM alert..."
                    )

                    pesan = buat_pesan_ram_alert(
                        metrics,
                        timestamp
                    )

                    kirim_telegram(pesan)

            else:

                ram_high_count = 0

                if ram_alert_active:

                    ram_normal_count += 1

                    print(
                        f"[RAM] Recovery progress "
                        f"({ram_normal_count}/{RAM_RECOVERY_CONSECUTIVE})"
                    )

                    # Incident baru dianggap resolved
                    # setelah RAM normal beberapa sample
                    # berturut-turut.
                    if (
                        ram_normal_count
                        >= RAM_RECOVERY_CONSECUTIVE
                    ):

                        print(
                            "[RECOVERY] "
                            "RAM kembali ke kondisi normal."
                        )

                        ram_alert_active = False
                        ram_normal_count = 0

                        incident_manager.log_incident(
                            "HIGH_MEMORY",
                            {
                                "status": "RESOLVED",
                                "severity": "INFO",
                                "anomalies": [],
                                "metrics": {
                                    "cpu_percent": cpu,
                                    "ram_percent": ram_percent,
                                    "ram_used_mb": ram,
                                    "containers": containers,
                                },
                            },
                        )

                        print(
                            "[INCIDENT STATE] "
                            "RAM incident = RESOLVED"
                        )

                        pesan = buat_pesan_ram_resolved(
                            metrics,
                            timestamp
                        )

                        kirim_telegram(pesan)

                else:
                    ram_normal_count = 0

            # ------------------------------------------------
            # Interval monitoring
            # ------------------------------------------------

            time.sleep(3)

        # =====================================================
        # KEYBOARD INTERRUPT
        # =====================================================

        except KeyboardInterrupt:

            print(
                "\n[Engine Stopped] "
                "Monitoring dihentikan oleh user."
            )

            break

        # =====================================================
        # UNEXPECTED ERROR
        # =====================================================

        except Exception as e:

            print(
                f"[Engine Error] {type(e).__name__}: {e}"
            )

            time.sleep(3)


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":
    run_engine()
