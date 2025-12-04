from prometheus_client import start_http_server, Gauge
import psutil
import time
import platform

try:
    import GPUtil
except ImportError:
    GPUtil = None

# Gauges for system metrics
cpu_percent_gauge = Gauge('cpu_percent', 'CPU usage percent')
mem_percent_gauge = Gauge('memory_percent', 'Memory usage percent')
disk_percent_gauge = Gauge('disk_percent', 'Disk usage percent')
network_sent_gauge = Gauge('network_bytes_sent', 'Bytes sent over network')
network_recv_gauge = Gauge('network_bytes_recv', 'Bytes received over network')

# GPU metrics
gpu_load_gauge = Gauge('gpu_load_percent', 'GPU load percent', ['gpu_name'])
gpu_mem_free_gauge = Gauge('gpu_memory_free_mb', 'GPU free memory in MB', ['gpu_name'])
gpu_mem_used_gauge = Gauge('gpu_memory_used_mb', 'GPU used memory in MB', ['gpu_name'])
gpu_mem_total_gauge = Gauge('gpu_memory_total_mb', 'GPU total memory in MB', ['gpu_name'])
gpu_temp_gauge = Gauge('gpu_temperature_c', 'GPU temperature in Celsius', ['gpu_name'])
gpu_mem_util_gauge = Gauge('gpu_memory_util_percent', 'GPU memory utilization percent', ['gpu_name'])

def collect_metrics():
    # CPU
    cpu_percent_gauge.set(psutil.cpu_percent(interval=0.1))
    # Memory
    vm = psutil.virtual_memory()
    mem_percent_gauge.set(vm.percent)
    # Disk
    du = psutil.disk_usage('/')
    disk_percent_gauge.set(du.percent)
    # Network
    net = psutil.net_io_counters()
    network_sent_gauge.set(net.bytes_sent)
    network_recv_gauge.set(net.bytes_recv)
    # GPU
    if GPUtil:
        gpus = GPUtil.getGPUs()
        for gpu in gpus:
            gpu_load_gauge.labels(gpu_name=gpu.name).set(round(gpu.load * 100, 1))
            gpu_mem_free_gauge.labels(gpu_name=gpu.name).set(gpu.memoryFree)
            gpu_mem_used_gauge.labels(gpu_name=gpu.name).set(gpu.memoryUsed)
            gpu_mem_total_gauge.labels(gpu_name=gpu.name).set(gpu.memoryTotal)
            gpu_temp_gauge.labels(gpu_name=gpu.name).set(gpu.temperature)
            mem_util = round((gpu.memoryUsed / gpu.memoryTotal) * 100, 1) if gpu.memoryTotal > 0 else 0
            gpu_mem_util_gauge.labels(gpu_name=gpu.name).set(mem_util)

if __name__ == '__main__':
    start_http_server(8000)  # Exposes /metrics
    print("Exporter running on port 8000...")
    while True:
        collect_metrics()
        time.sleep(15)  # scrape interval
