import docker
import datetime
import os
import json
import requests
import time

# ==============================
# KONFIGURASI TELEGRAM
# ==============================

BOT_TOKEN = "8713469425:AAGHeheEcj-P3PvLKbkiWY3rIDU8sgDwZKk"
CHAT_ID = "7707167170"


# ==============================
# FUNGSI KIRIM TELEGRAM
# ==============================

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message
    }

    try:
        requests.post(url, data=data, timeout=5)
    except Exception as e:
        print(f"Gagal mengirim Telegram: {e}")


# ==============================
# FUNGSI MONITORING CONTAINER
# ==============================

def cek_dan_log_container():
    client = docker.from_env()

    container_target = [
        "cms_vulner",
        "db_perpus",
        "pma_perpus"
    ]

    waktu_sekarang = datetime.datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    # ==============================
    # FOLDER LOG & STATE
    # ==============================

    folder_log = os.path.expanduser("~/logs")
    os.makedirs(folder_log, exist_ok=True)

    file_log = os.path.join(
        folder_log,
        "container_monitor.log"
    )

    file_state = os.path.expanduser(
        "~/scripts/monitor/alert_state.json"
    )
    # Memastikan folder untuk file_state dibuat agar tidak error saat json.dump
    os.makedirs(os.path.dirname(file_state), exist_ok=True)

    # ==============================
    # LOAD STATUS LAMA
    # ==============================

    status_lama = {}

    if os.path.exists(file_state):
        try:
            with open(file_state, "r") as f:
                status_lama = json.load(f)
        except Exception:
            status_lama = {}

    # ==============================
    # STATUS BARU
    # ==============================

    status_baru = {}

    print(
        f"\n=== MONITORING & TELEGRAM ALERT ({waktu_sekarang}) ==="
    )

    # ==============================
    # LOGGING
    # ==============================

    with open(file_log, "a") as log:

        log.write(
            f"\n--- MONITOR ENTRY: {waktu_sekarang} ---\n"
        )

        # ==============================
        # LOOP CONTAINER
        # ==============================

        for nama in container_target:

            try:

                container = client.containers.get(nama)

                # Refresh realtime status
                container.reload()

                status_sekarang = container.status

                # Ambil status sebelumnya (default 'running' agar tidak firing palsu saat awal start)
                status_terakhir = status_lama.get(
                    nama,
                    "running"
                )

                # ==============================
                # ALERT JIKA DOWN
                # ==============================

                if (
                    status_sekarang != "running"
                    and status_terakhir == "running"
                ):

                    send_telegram(
                        f"🚨 ALERT DEVOPS\n\n"
                        f"Container '{nama}' DOWN!\n"
                        f"Waktu: {waktu_sekarang}"
                    )

                # ==============================
                # ALERT JIKA RECOVERY
                # ==============================

                elif (
                    status_sekarang == "running"
                    and status_terakhir != "running"
                ):

                    send_telegram(
                        f"✅ RESOLVED DEVOPS\n\n"
                        f"Container '{nama}' sudah UP kembali.\n"
                        f"Waktu: {waktu_sekarang}"
                    )

                # ==============================
                # SIMPAN STATUS
                # ==============================

                status_baru[nama] = status_sekarang

                # ==============================
                # PRINT TERMINAL
                # ==============================

                print(
                    f"Container: {nama:<15} | "
                    f"Status: {status_sekarang.upper()}"
                )

                # ==============================
                # TULIS LOG
                # ==============================

                log.write(
                    f"Container: {nama:<15} | "
                    f"Status: {status_sekarang.upper()}\n"
                )

            # ==============================
            # JIKA CONTAINER TIDAK ADA
            # ==============================

            except docker.errors.NotFound:

                status_baru[nama] = "not_found"

                print(
                    f"Container: {nama:<15} | "
                    f"Status: NOT FOUND"
                )

                log.write(
                    f"Container: {nama:<15} | "
                    f"Status: NOT FOUND\n"
                )

                # Kirim alert sekali
                if status_lama.get(nama) != "not_found":

                    send_telegram(
                        f"⚠️ CRITICAL DEVOPS\n\n"
                        f"Container '{nama}' TIDAK DITEMUKAN!\n"
                        f"Waktu: {waktu_sekarang}"
                    )

            # ==============================
            # ERROR UMUM
            # ==============================

            except Exception as e:

                print(
                    f"ERROR saat cek container "
                    f"{nama}: {e}"
                )

                log.write(
                    f"ERROR saat cek container "
                    f"{nama}: {e}\n"
                )

    # ==============================
    # SIMPAN STATUS TERBARU
    # ==============================

    with open(file_state, "w") as f:

        json.dump(status_baru, f)


# ==============================
# MAIN PROGRAM
# ==============================

if __name__ == "__main__":

    print("🚀 DevOps Monitor Started...")

    while True:

        cek_dan_log_container()

        # Interval monitoring (setiap 10 detik)
        time.sleep(10)
