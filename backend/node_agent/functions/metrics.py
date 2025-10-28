
import psutil
import os
from datetime import datetime
import platform

def get_system_info():
	return {
		"hostname": platform.node(),
		"platform": platform.system(),
		"platform_release": platform.release(),
		"platform_version": platform.version(),
		"architecture": platform.machine(),
		"processor": platform.processor(),
	}

async def collect_metrics():
	import asyncio
	def _collect():
		try:
			metrics = {
				"timestamp": datetime.now().isoformat(),
				"system": get_system_info(),
				"cpu": {
					"usage_percent": psutil.cpu_percent(interval=1),
					"per_cpu": psutil.cpu_percent(interval=1, percpu=True),
					"count": psutil.cpu_count(),
					"count_logical": psutil.cpu_count(logical=True),
					"load_avg": list(os.getloadavg()) if hasattr(os, 'getloadavg') else None,
				},
				"memory": {
					**psutil.virtual_memory()._asdict(),
					"swap": psutil.swap_memory()._asdict(),
				},
				"disk": {
					"partitions": [p._asdict() for p in psutil.disk_partitions()],
					"usage": {
						p.mountpoint: psutil.disk_usage(p.mountpoint)._asdict() 
						for p in psutil.disk_partitions() 
						if os.path.exists(p.mountpoint)
					},
				},
				"network": {
					"io": psutil.net_io_counters()._asdict(),
					"io_per_nic": {
						k: v._asdict() for k, v in psutil.net_io_counters(pernic=True).items()
					},
					"connections": len(psutil.net_connections()),
				},
				"services": [],
				"processes": {
					"count": len(psutil.pids()),
				},
			}
			return metrics
		except Exception as e:
			return {"error": str(e)}
	return await asyncio.to_thread(_collect)
