import docker
import psutil


class MetricsCollector:

  def __init__(self):
    """Inisialisasi Docker client."""
    try:
      self.docker_client = docker.from_env()
    except Exception as e:
      print(
          f'[Collector Warning] Gagal terhubung ke /var/run/docker.sock: {e}'
      )
      self.docker_client = None

  def get_system_metrics(self):
    """Mengambil metrik sistem (CPU %, RAM MiB & %, Running Containers) secara real-time."""
    # Ambil persentase penggunaan CPU
    cpu_percent = psutil.cpu_percent(interval=0.5)

    # Ambil statistik RAM
    memory_info = psutil.virtual_memory()
    ram_used_mib = round(memory_info.used / (1024 * 1024), 1)
    ram_percent = memory_info.percent

    # Ambil jumlah kontainer yang sedang RUNNING
    running_containers = 0
    if self.docker_client:
      try:
        running_containers = len(self.docker_client.containers.list())
      except Exception as e:
        print(f'[Collector Error] Gagal mengambil daftar kontainer: {e}')
        running_containers = 0

    return {
        'cpu': cpu_percent,
        'ram': ram_used_mib,
        'ram_percent': ram_percent,
        'containers': running_containers,
    }