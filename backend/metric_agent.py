import argparse
import psutil
import os
import json
import sys


def collect_metrics():
    metrics = {
        "cpu": {
            "usage_percent": psutil.cpu_percent(interval=1, percpu=True),
            "count": psutil.cpu_count(),
            "load_avg": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None,
        },
        "memory": psutil.virtual_memory()._asdict(),
        "disk": {
            "partitions": [p._asdict() for p in psutil.disk_partitions()],
            "usage": {p.mountpoint: psutil.disk_usage(p.mountpoint)._asdict() for p in psutil.disk_partitions()},
        },
        "network": {
            "interfaces": psutil.net_if_addrs(),
            "stats": psutil.net_if_stats(),
            "io": psutil.net_io_counters(pernic=True),
        },
        "processes": [p.info for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent'])],
    }
    print(json.dumps(metrics))


def list_files(path):
    try:
        files = os.listdir(path)
        print(json.dumps({"files": files}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Metric/File Agent")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("collect_metrics")

    list_parser = subparsers.add_parser("list_files")
    list_parser.add_argument("path", nargs="?", default=".")

    args = parser.parse_args()

    if args.command == "collect_metrics":
        collect_metrics()
    elif args.command == "list_files":
        list_files(args.path)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
