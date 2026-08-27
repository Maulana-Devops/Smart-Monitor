# backend/telegram.py

import os
import requests


# ==========================================================
# KONFIGURASI TELEGRAM
# ==========================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# ==========================================================
# KIRIM TELEGRAM
# ==========================================================

def kirim_telegram(pesan):
    """
    Mengirim pesan teks ke Telegram Bot.
    Credential dibaca dari environment variable.
    """

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[TELEGRAM] Token atau Chat ID belum dikonfigurasi.")
        return False

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": pesan,
    }

    try:
        response = requests.post(
            url,
            data=payload,
            timeout=5,
        )

        response.raise_for_status()

        result = response.json()

        if result.get("ok"):
            print("[TELEGRAM SENT] Pesan berhasil terkirim.")
            return True

        print(f"[TELEGRAM ERROR] Response API: {result}")
        return False

    except requests.RequestException as e:
        print(f"[TELEGRAM ERROR] Request gagal: {e}")
        return False

    except Exception as e:
        print(f"[TELEGRAM ERROR] {e}")
        return False
