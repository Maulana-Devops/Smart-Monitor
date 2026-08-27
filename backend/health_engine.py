class HealthEngine:
    def __init__(self, cpu_threshold=80.0, ram_threshold=85.0):
        self.cpu_threshold = cpu_threshold
        self.ram_threshold = ram_threshold

    def calculate_health(self, cpu, ram, container_issues=0):
        score = 100
        
        if cpu > self.cpu_threshold:
            score -= 30
        elif cpu > 50:
            score -= 10

        if ram > self.ram_threshold:
            score -= 30
        elif ram > 70:
            score -= 10

        score -= (container_issues * 20)
        return max(0, score)

    def evaluate_status(self, cpu, ram):
        anomalies = []
        if cpu > self.cpu_threshold:
            anomalies.append("CPU_SPIKE")
        if ram > self.ram_threshold:
            anomalies.append("HIGH_MEMORY")
        
        status = "CRITICAL" if anomalies else "STABLE"
        return status, anomalies