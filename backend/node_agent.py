"""
Node Agent - Remote Server Monitoring & Management Gateway
Collects metrics, monitors services, and manages server configurations
"""
import argparse
import psutil
import os
import json
import sys
import platform
import socket
import subprocess
from datetime import datetime
from pathlib import Path


def get_system_info():
    """Get basic system information"""
    return {
        "hostname": socket.gethostname(),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "ip_address": socket.gethostbyname(socket.gethostname()),
        "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
    }


def check_service_status(service_name):
    """Check if a service is running"""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["sc", "query", service_name],
                capture_output=True,
                text=True
            )
            return "RUNNING" in result.stdout
        else:
            result = subprocess.run(
                ["systemctl", "is-active", service_name],
                capture_output=True,
                text=True
            )
            return result.stdout.strip() == "active"
    except Exception as e:
        return None


def detect_services():
    """Detect running services (Nginx, MySQL, Docker, etc.)"""
    services = {}
    
    # Common service names
    service_checks = {
        "nginx": ["nginx", "nginx.service"],
        "mysql": ["mysql", "mysqld", "mariadb"],
        "docker": ["docker", "docker.service"],
        "postgresql": ["postgresql", "postgres"],
        "redis": ["redis", "redis-server"],
        "mongodb": ["mongodb", "mongod"],
    }
    
    for service_type, service_names in service_checks.items():
        for service_name in service_names:
            status = check_service_status(service_name)
            if status is not None:
                services[service_type] = {
                    "name": service_name,
                    "running": status,
                    "detected": True
                }
                break
        if service_type not in services:
            services[service_type] = {
                "name": service_type,
                "running": False,
                "detected": False
            }
    
    return services


def collect_metrics():
    """Collect comprehensive system metrics"""
    try:
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "system": get_system_info(),
            "cpu": {
                "usage_percent": psutil.cpu_percent(interval=1),
                "per_cpu": psutil.cpu_percent(interval=1, percpu=True),
                "count": psutil.cpu_count(),
                "count_logical": psutil.cpu_count(logical=True),
                "load_avg": list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else None,
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
                "io": psutil.disk_io_counters()._asdict() if psutil.disk_io_counters() else None,
            },
            "network": {
                "io": psutil.net_io_counters()._asdict(),
                "io_per_nic": {
                    k: v._asdict() for k, v in psutil.net_io_counters(pernic=True).items()
                },
                "connections": len(psutil.net_connections()),
            },
            "services": detect_services(),
            "processes": {
                "count": len(psutil.pids()),
                "top_cpu": [
                    p.info for p in sorted(
                        psutil.process_iter(['pid', 'name', 'cpu_percent']),
                        key=lambda p: p.info.get('cpu_percent', 0) or 0,
                        reverse=True
                    )[:10]
                ],
                "top_memory": [
                    p.info for p in sorted(
                        psutil.process_iter(['pid', 'name', 'memory_percent']),
                        key=lambda p: p.info.get('memory_percent', 0) or 0,
                        reverse=True
                    )[:10]
                ],
            },
        }
        print(json.dumps(metrics, default=str))
    except Exception as e:
        print(json.dumps({"error": str(e), "type": "metrics_error"}), file=sys.stderr)
        sys.exit(1)


def list_files(path):
    """List files in a directory"""
    try:
        path_obj = Path(path).resolve()
        if not path_obj.exists():
            print(json.dumps({"error": "Path does not exist"}))
            sys.exit(1)
        
        files = []
        for item in path_obj.iterdir():
            stat = item.stat()
            files.append({
                "name": item.name,
                "path": str(item),
                "type": "directory" if item.is_dir() else "file",
                "size": stat.st_size if item.is_file() else None,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "permissions": oct(stat.st_mode)[-3:],
            })
        
        print(json.dumps({"path": str(path_obj), "files": files}))
    except PermissionError:
        print(json.dumps({"error": "Permission denied"}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


def read_file(path, max_lines=None):
    """Read file contents"""
    try:
        path_obj = Path(path).resolve()
        if not path_obj.is_file():
            print(json.dumps({"error": "Not a file"}))
            sys.exit(1)
        
        with open(path_obj, 'r') as f:
            if max_lines:
                lines = [f.readline() for _ in range(max_lines)]
            else:
                lines = f.readlines()
        
        print(json.dumps({
            "path": str(path_obj),
            "content": ''.join(lines),
            "size": path_obj.stat().st_size,
        }))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


def check_nginx_config():
    """Check Nginx configuration files"""
    try:
        nginx_paths = [
            "/etc/nginx/nginx.conf",
            "/usr/local/etc/nginx/nginx.conf",
            "C:/nginx/conf/nginx.conf",
        ]
        
        config_path = None
        for path in nginx_paths:
            if os.path.exists(path):
                config_path = path
                break
        
        if not config_path:
            print(json.dumps({"error": "Nginx config not found", "available": False}))
            return
        
        # Test nginx configuration
        test_cmd = ["nginx", "-t"] if platform.system() != "Windows" else ["nginx.exe", "-t"]
        result = subprocess.run(test_cmd, capture_output=True, text=True)
        
        print(json.dumps({
            "config_path": config_path,
            "available": True,
            "valid": result.returncode == 0,
            "output": result.stderr,
        }))
    except Exception as e:
        print(json.dumps({"error": str(e)}))


def get_database_info():
    """Get database connection information"""
    try:
        databases = {}
        
        # Check MySQL/MariaDB
        try:
            result = subprocess.run(
                ["mysql", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                databases["mysql"] = {
                    "available": True,
                    "version": result.stdout.strip(),
                }
        except:
            databases["mysql"] = {"available": False}
        
        # Check PostgreSQL
        try:
            result = subprocess.run(
                ["psql", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                databases["postgresql"] = {
                    "available": True,
                    "version": result.stdout.strip(),
                }
        except:
            databases["postgresql"] = {"available": False}
        
        print(json.dumps({"databases": databases}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))


def check_firewall():
    """Check firewall status"""
    try:
        firewall_info = {"type": None, "enabled": False, "rules": []}
        
        if platform.system() == "Linux":
            # Check UFW
            try:
                result = subprocess.run(
                    ["ufw", "status"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    firewall_info["type"] = "ufw"
                    firewall_info["enabled"] = "Status: active" in result.stdout
                    firewall_info["output"] = result.stdout
            except:
                pass
            
            # Check iptables
            if not firewall_info["type"]:
                try:
                    result = subprocess.run(
                        ["iptables", "-L", "-n"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        firewall_info["type"] = "iptables"
                        firewall_info["enabled"] = True
                        firewall_info["output"] = result.stdout
                except:
                    pass
        
        elif platform.system() == "Windows":
            try:
                result = subprocess.run(
                    ["netsh", "advfirewall", "show", "allprofiles"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    firewall_info["type"] = "windows_firewall"
                    firewall_info["enabled"] = "ON" in result.stdout
                    firewall_info["output"] = result.stdout
            except:
                pass
        
        print(json.dumps(firewall_info))
    except Exception as e:
        print(json.dumps({"error": str(e)}))


def main():
    parser = argparse.ArgumentParser(description="Node Agent - Server Monitoring & Management Gateway")
    subparsers = parser.add_subparsers(dest="command")

    # Metrics collection
    subparsers.add_parser("collect_metrics", help="Collect all system metrics")

    # File operations
    list_parser = subparsers.add_parser("list_files", help="List files in directory")
    list_parser.add_argument("path", nargs="?", default=".")

    read_parser = subparsers.add_parser("read_file", help="Read file contents")
    read_parser.add_argument("path", help="Path to file")
    read_parser.add_argument("--max-lines", type=int, help="Maximum lines to read")

    # Service checks
    subparsers.add_parser("check_nginx", help="Check Nginx configuration")
    subparsers.add_parser("check_databases", help="Check available databases")
    subparsers.add_parser("check_firewall", help="Check firewall status")
    subparsers.add_parser("system_info", help="Get system information")
    subparsers.add_parser("detect_services", help="Detect running services")

    args = parser.parse_args()

    if args.command == "collect_metrics":
        collect_metrics()
    elif args.command == "list_files":
        list_files(args.path)
    elif args.command == "read_file":
        read_file(args.path, args.max_lines)
    elif args.command == "check_nginx":
        check_nginx_config()
    elif args.command == "check_databases":
        get_database_info()
    elif args.command == "check_firewall":
        check_firewall()
    elif args.command == "system_info":
        print(json.dumps(get_system_info()))
    elif args.command == "detect_services":
        print(json.dumps(detect_services()))
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
