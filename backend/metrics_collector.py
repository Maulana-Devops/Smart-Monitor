import requests
import time
from datetime import datetime

# ==================== CONFIGURATION ====================
PROMETHEUS_URL = "http://localhost:9090/api/v1/query"

# 1. Mengelompokkan Query (Future-Proof & Mudah Ditambah)
QUERIES = {
    "total_cpu": 'sum(rate(container_cpu_usage_seconds_total{id=~"/system.slice/docker-.*"}[1m])) * 100',
    "total_ram": 'sum(container_memory_usage_bytes{id=~"/system.slice/docker-.*"}) / 1024 / 1024'  # Satuan MiB
}

# 3. Penyimpanan History Sementara untuk Deteksi Tren
HISTORY_LIMIT = 10
cpu_history = []
ram_history = []
# =======================================================

# 2. Fungsi Universal (Sangat Scalable untuk Metrik Apapun)
def query_prometheus(query_string):
    try:
        response = requests.get(PROMETHEUS_URL, params={'query': query_string}, timeout=5)
        data = response.json()
        
        if data['status'] == 'success':
            results = data['data']['result']
            if results:
                return float(results[0]['value'][1])
            return 0.0
        return None
    except Exception as e:
        print(f"❌ Gagal mengambil metrik dari Prometheus: {e}")
        return None

# 4. Implementasi Delta & Spike Detection Awal
def analisa_lonjakan_instant(current_val, history_list, metric_name, threshold_delta=30.0):
    if not history_list:
        return
    
    nilai_sebelumnya = history_list[-1]
    selisih = current_val - nilai_sebelumnya
    
    # Deteksi jika ada kenaikan mendadak melebihi threshold delta
    if selisih > threshold_delta:
        print(f"⚠️ [SMART ALERT] Terdeteksi Spike Mendadak pada {metric_name}!")
        print(f"   -> Dari: {nilai_sebelumnya:.2f} -> {current_val:.2f} (Naik {selisih:.2f} poin)")

if __name__ == "__main__":
    print("🚀 Memulai Smart Infrastructure Collector (Engine v1.1 Active) ...")
    print("-------------------------------------------------------------------")
    
    try:
        while True:
            waktu_sekarang = datetime.now().strftime('%H:%M:%S')
            
            # Eksekusi fungsi universal untuk CPU dan RAM sekaligus
            current_cpu = query_prometheus(QUERIES["total_cpu"])
            current_ram = query_prometheus(QUERIES["total_ram"])
            
            if current_cpu is not None and current_ram is not None:
                # Lakukan analisis Delta sebelum history diperbarui
                analisa_lonjakan_instant(current_cpu, cpu_history, "CPU Containers", threshold_delta=25.0)
                
                # Cetak metrik riil ke layar terminal
                print(f"⏰ [{waktu_sekarang}] CPU Containers: {current_cpu:.2f}% | RAM Total: {current_ram:.2f} MiB")
                
                # Simpan ke history & batasi agar tidak memakan RAM server
                cpu_history.append(current_cpu)
                ram_history.append(current_ram)
                
                if len(cpu_history) > HISTORY_LIMIT:
                    cpu_history.pop(0)
                if len(ram_history) > HISTORY_LIMIT:
                    ram_history.pop(0)
                    
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n👋 Monitoring dihentikan secara aman.")
