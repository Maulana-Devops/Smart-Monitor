import psutil

class MetricsCollector:
    def __init__(self):
        # Warm-up call agar bacaan pertama tidak 0.0
        psutil.cpu_percent(interval=None)

    def get_system_metrics(self):
        # Mengambil persentase CPU dengan interval penundaan 1 detik
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        
        return {
            "cpu_percent": cpu,
            "ram_percent": ram.percent,
            "ram_used_mb": round(ram.used / (1024 * 1024), 2),
            "ram_total_mb": round(ram.total / (1024 * 1024), 2)
        }