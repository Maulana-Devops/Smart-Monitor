import requests
import time
import json
import os
from datetime import datetime

# ==================== CONFIGURATION ====================
PROMETHEUS_URL = "http://localhost:9090/api/v1/query"

TELEGRAM_TOKEN = "8713469425:AAGHeheEcj-P3PvLKbkiWY3rIDU8sgDwZKk"
TELEGRAM_CHAT_ID = "7707167170"

QUERIES = {
    "total_cpu": 'sum(rate(container_cpu_usage_seconds_total{id=~"/system.slice/docker-.*"}[1m])) * 100',
    "total_ram": 'sum(container_memory_usage_bytes{id=~"/system.slice/docker-.*"}) / 1024 / 1024'
}

RAM_ALERT_THRESHOLD = 1500.0
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LOG_FILE_PATH = os.path.join(BASE_DIR, "logs", "incident_log.json")
STATUS_FILE_PATH = os.path.join(BASE_DIR, "logs", "current_status.json")

ALERT_COOLDOWN = 60 
last_cpu_alert_time = 0
last_ram_alert_time = 0

CPU_HISTORY_LIMIT = 10
cpu_history = []
# =======================================================

def catat_insiden(tipe_insiden, tingkat_bahaya, nilai_sekarang, nilai_baseline, pesan_teks, skor_saat_ini):
    format_waktu = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    data_insiden_baru = {
        "time": format_waktu,
        "type": tipe_insiden,
        "severity": tingkat_bahaya,
        "current_value": round(nilai_sekarang, 2),
        "baseline_value": round(nilai_baseline, 2) if nilai_baseline is not None else None,
        "message": pesan_teks,
        "current_health_score": skor_saat_ini
    }
    
    isi_log_lama = []
    if os.path.exists(LOG_FILE_PATH):
        try:
            with open(LOG_FILE_PATH, 'r') as file_json:
                isi_log_lama = json.load(file_json)
        except:
            isi_log_lama = []
            
    isi_log_lama.append(data_insiden_baru)
    
    try:
        with open(LOG_FILE_PATH, 'w') as file_json:
            json.dump(isi_log_lama, file_json, indent=2)
        print(f"[LOGGED] [{tingkat_bahaya}] {tipe_insiden} disimpan. Current Health: {skor_saat_ini}%")
    except Exception as e:
        print(f"Gagal menulis berkas incident_log.json: {e}")

def simpan_status(cpu, ram, health_score, status):
    """
    Menyimpan kondisi sistem saat ini.
    File ini akan dibaca oleh dashboard sehingga status
    selalu mengikuti kondisi terbaru, bukan histori incident.
    """

    data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cpu": round(cpu, 2),
        "ram": round(ram, 2),
        "health_score": health_score,
        "status": status
    }

    try:
        with open(STATUS_FILE_PATH, "w") as f:
            json.dump(data, f, indent=4)

    except Exception as e:
        print(f"Gagal menyimpan current_status.json : {e}")

def kirim_telegram(pesan):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": pesan, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Gagal mengirim alert Telegram: {e}")

def query_prometheus(query_string):
    try:
        response = requests.get(PROMETHEUS_URL, params={'query': query_string}, timeout=5)
        data = response.json()
        if data['status'] == 'success' and data['data']['result']:
            return float(data['data']['result'][0]['value'][1])
        return 0.0
    except:
        return None

def kalkulasi_health_score_v2(cpu, ram):
    if cpu < 15.0:
        cpu_score = 50
    elif cpu < 40.0:
        cpu_score = 35
    elif cpu < 70.0:
        cpu_score = 15
    else:
        cpu_score = 5

    if ram < RAM_ALERT_THRESHOLD:
        ram_score = 50
    elif ram < (RAM_ALERT_THRESHOLD + 200):
        ram_score = 25
    else:
        ram_score = 10

    total_score = cpu_score + ram_score
    
    if total_score >= 85:
        status = "STABLE"
    elif total_score >= 60:
        status = "DEGRADED"
    else:
        status = "CRITICAL"
        
    return total_score, status

def tentukan_severity_cpu(cpu_val, baseline_val):
    if cpu_val > 70.0:
        return "CRITICAL", "EMERGENCY: Beban komputasi ekstrim terdeteksi pada kluster kontainer!"
    elif cpu_val > 40.0:
        return "HIGH", "HIGH LOAD: Lonjakan CPU tinggi, performa aplikasi mulai terhambat."
    else:
        return "WARNING", "WARNING: Defonstruksi moving baseline, anomali beban ringan terdeteksi."

if __name__ == "__main__":
    print("Smart Infrastructure Analyzer (v1.4 - Production Intelligence) Active...")
    print("---------------------------------------------------------------------")
    
    try:
        while True:
            waktu_sekarang = datetime.now().strftime('%H:%M:%S')
            current_timestamp = time.time()
            
            cpu_now = query_prometheus(QUERIES["total_cpu"])
            ram_now = query_prometheus(QUERIES["total_ram"])
            
            if cpu_now is not None and ram_now is not None:
                skor_kesehatan, status_sistem = kalkulasi_health_score_v2(cpu_now, ram_now)

		    simpan_status(
    		        cpu_now,
		        ram_now,
    		        skor_kesehatan,
    		        status_sistem
		    )

		    print(
    		        f"[{waktu_sekarang}] CPU: {cpu_now:.2f}% | "
    		        f"RAM: {ram_now:.2f} MiB | "
    		        f"Health Score: {skor_kesehatan}% [{status_sistem}]"
		    )                
		    if len(cpu_history) >= 3:
                    baseline = sum(cpu_history) / len(cpu_history)
                    
                    if cpu_now > (baseline * 2) and cpu_now > 15.0:
                        sev_level, sev_msg = tentukan_severity_cpu(cpu_now, baseline)
                        
                        if current_timestamp - last_cpu_alert_time > ALERT_COOLDOWN:
                            print(f"Menembakkan [{sev_level}] Alert ke Telegram...")
                            pesan_cpu = (
                                f"*SMART MONITOR ALERT: {sev_level} CPU ANOMALY*\n"
                                f"--------------------------------------------------\n"
                                f"*CPU Current:* `{cpu_now:.2f}%` (Baseline: {baseline:.2f}%)\n"
                                f"*System Health:* `{skor_kesehatan}%` [{status_sistem}]\n"
                                f"*RAM usage:* `{ram_now:.2f} MiB`\n"
                                f"*Waktu Kejadian:* `{waktu_sekarang}`\n\n"
                                f"*Analisis:* {sev_msg}"
                            )
                            kirim_telegram(pesan_cpu)
                            last_cpu_alert_time = current_timestamp
                        
                        catat_insiden(
                            tipe_insiden="CPU_SPIKE",
                            tingkat_bahaya=sev_level,
                            nilai_sekarang=cpu_now,
                            nilai_baseline=baseline,
                            pesan_teks=sev_msg,
                            skor_saat_ini=skor_kesehatan
                        )
                    
                    if ram_now > RAM_ALERT_THRESHOLD:
                        if current_timestamp - last_ram_alert_time > ALERT_COOLDOWN:
                            print(f"Menembakkan High Memory Alert ke Telegram...")
                            pesan_ram = (
                                f"*SMART MONITOR ALERT: HIGH MEMORY*\n"
                                f"--------------------------------------------------\n"
                                f"*RAM Current:* `{ram_now:.2f} MiB`\n"
                                f"*System Health:* `{skor_kesehatan}%` [{status_sistem}]\n"
                                f"*Waktu Kejadian:* `{waktu_sekarang}`\n"
                            )
                            kirim_telegram(pesan_ram)
                            last_ram_alert_time = current_timestamp
                        
                        catat_insiden(
                            tipe_insiden="RAM_OVERLOAD",
                            tingkat_bahaya="HIGH" if skor_kesehatan >= 60 else "CRITICAL",
                            nilai_sekarang=ram_now,
                            nilai_baseline=RAM_ALERT_THRESHOLD,
                            pesan_teks="Penggunaan memori RAM kontainer melampaui ambang batas aman.",
                            skor_saat_ini=skor_kesehatan
                        )
                        
                else:
                    print(f"Mengumpulkan data awal untuk baseline... ({len(cpu_history)}/3)")

                cpu_history.append(cpu_now)
                if len(cpu_history) > CPU_HISTORY_LIMIT:
                    cpu_history.pop(0)
                    
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\nSmart Analyzer dinonaktifkan secara aman.")