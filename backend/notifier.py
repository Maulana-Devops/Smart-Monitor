# backend/notifier.py
import os
import requests
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8760647789:AAHHfMTjpWsECNgXj38Tv3e6XLk90l-We5A")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7707167170")


def kirim_telegram_alert(tipe_alert, pesan_detail, metrics=None):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[SKIP TELEGRAM] Token atau Chat ID belum diset.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    waktu_sekarang = datetime.now().strftime("%H:%M:%S")
    waktu_lengkap = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    metrics = metrics or {}
    cpu_val = metrics.get("cpu", "0.00")
    baseline_val = metrics.get("baseline", "0.00")
    ram_val = metrics.get("ram", "0.00")
    health_val = metrics.get("health", "75%")
    status_val = metrics.get("status", "DEGRADED")
    container_name = metrics.get("container_name", "Unknown Container")

    # Format Pesan Berdasarkan Tipe Alert
    if tipe_alert == "CPU_SPIKE":
        text = (
            f"SMART MONITOR ALERT: HIGH CPU ANOMALY\n"
            f"--------------------------------------------------\n"
            f"CPU Current: {cpu_val:.2f}% (Baseline: {baseline_val:.2f}%)\n"
            f"System Health: {health_val}% {status_val}\n"
            f"RAM Usage: {ram_val:.2f} MiB\n"
            f"Waktu Kejadian: {waktu_sekarang}\n\n"
            f"Analisis: HIGH LOAD: Lonjakan CPU tinggi, performa aplikasi mulai terhambat."
        )

    elif tipe_alert == "RAM_OVERLOAD":
        text = (
            f"SMART MONITOR ALERT: HIGH MEMORY\n"
            f"--------------------------------------------------\n"
            f"RAM Current: {ram_val:.2f} MiB\n"
            f"System Health: {health_val}% {status_val}\n"
            f"Waktu Kejadian: {waktu_sekarang}"
        )

    elif tipe_alert == "CONTAINER_DOWN":
        text = (
            f"?? ALERT DEVOPS\n\n"
            f"Container '{container_name}' DOWN!\n"
            f"Waktu: {waktu_lengkap}"
        )

    elif tipe_alert == "CONTAINER_UP":
        text = (
            f"? RESOLVED DEVOPS\n\n"
            f"Container '{container_name}' sudah UP kembali.\n"
            f"Waktu: {waktu_lengkap}"
        )

    else:
        text = (
            f"SMART MONITOR ALERT: {tipe_alert}\n"
            f"--------------------------------------------------\n"
            f"Detail: {pesan_detail}\n"
            f"Waktu Kejadian: {waktu_sekarang}"
        )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }

    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            print(f"[TELEGRAM SENT] {tipe_alert}")
            return True
        else:
            print(f"[ERROR TELEGRAM] {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"[ERROR TELEGRAM] {e}")
        return False