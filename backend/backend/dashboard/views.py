
import logging
import psutil
import platform
import time
import threading
import json
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework import status
import subprocess
import os
import winreg
import uuid
import hashlib
from rest_framework.permissions import AllowAny, IsAuthenticated
from authentication.cookie_oauth2 import CookieOAuth2Authentication

def get_stable_server_id():
    
    import pathlib

    server_id_path = (pathlib.Path(__file__).parent / "serverid.dat").resolve()
    if server_id_path.exists():
        try:
            sid = server_id_path.read_text().strip()
            if sid:
                return sid
        except Exception:
            pass

    try:
        mac = uuid.getnode()
        mac_str = f"{mac:012x}"
    except Exception:
        mac_str = "unknownmac"

    try:
        from .views import MetricsAPIView
        hw = MetricsAPIView.get_hardware_info()
        disk = hw.get("disk_model", "unknowndisk")
        mb = hw.get("motherboard", "unknownmb")
    except Exception:
        disk = "unknowndisk"
        mb = "unknownmb"

    import socket
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
    except Exception:
        ip = "unknownip"

    raw = f"{mac_str}-{disk}-{mb}-{ip}"
    server_id = hashlib.sha256(raw.encode()).hexdigest()[:16]
    try:
        server_id_path.write_text(server_id)
    except Exception:
        pass
    return server_id
from rest_framework.views import APIView
from rest_framework.response import Response

try:
    import cpuinfo
except ImportError:
    cpuinfo = None

try:
    import distro
except ImportError:
    distro = None

try:
    import GPUtil
except ImportError:
    GPUtil = None

try:
    import wmi
    import pythoncom
    WMI_AVAILABLE = True
except ImportError:
    WMI_AVAILABLE = False

class MetricsAPIView(APIView):
    authentication_classes = [CookieOAuth2Authentication]
    permission_classes = [IsAuthenticated]
    prev_net = None
    prev_time = None
    hardware_cache = {}
    cache_timestamp = 0
    cache_duration = 30  # Cache hardware info for 30 seconds
    
    @classmethod
    def get_cpu_temperature(cls):
        
        try:

            if hasattr(psutil, 'sensors_temperatures'):
                temps = psutil.sensors_temperatures()
                if temps:

                    for sensor_name in ['coretemp', 'cpu-thermal', 'acpitz', 'k10temp']:
                        if sensor_name in temps and temps[sensor_name]:
                            return temps[sensor_name][0].current

            if platform.system() == "Windows" and WMI_AVAILABLE:
                try:
                    c = wmi.WMI(namespace="root\\wmi")
                    temp_info = c.MSAcpi_ThermalZoneTemperature()
                    if temp_info:
                        return (temp_info[0].CurrentTemperature / 10.0) - 273.15
                except:
                    pass

                try:
                    c = wmi.WMI(namespace="root\\OpenHardwareMonitor")
                    sensors = c.Sensor()
                    for sensor in sensors:
                        if sensor.SensorType == 'Temperature' and 'CPU' in sensor.Name:
                            return sensor.Value
                except:
                    pass

            if platform.system() == "Windows":
                try:

                    result = subprocess.run([
                        'powershell', '-Command', 
                        'Get-WmiObject -Namespace "root/wmi" -Class MSAcpi_ThermalZoneTemperature | Select-Object -First 1 | ForEach-Object { ($_.CurrentTemperature / 10) - 273.15 }'
                    ], capture_output=True, text=True, timeout=2)
                    if result.returncode == 0 and result.stdout.strip():
                        return float(result.stdout.strip())
                except:
                    pass
                    
        except Exception as e:
            logging.warning(f"CPU temperature detection failed: {e}")
        
        return None

    @classmethod
    def get_hardware_info(cls):
        
        current_time = time.time()

        if (current_time - cls.cache_timestamp < cls.cache_duration and 
            cls.hardware_cache):
            return cls.hardware_cache
        
        hardware_info = {
            "disk_model": "Unknown",
            "disk_type": "Unknown", 
            "ram_type": "Unknown",
            "motherboard": "Unknown"
        }
        
        try:
            if platform.system() == "Windows":

                try:

                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                      r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                        cpu_brand = winreg.QueryValueEx(key, "ProcessorNameString")[0]
                        hardware_info["cpu_brand"] = cpu_brand.strip()
                except:
                    pass

                try:

                    result = subprocess.run(['wmic', 'diskdrive', 'get', 'model,mediatype', '/format:csv'], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')
                        for line in lines[1:]:  # Skip header
                            if line.strip() and 'Model' not in line:
                                parts = line.split(',')
                                if len(parts) >= 3:
                                    media_type = parts[1].strip() if len(parts) > 1 else ""
                                    model = parts[2].strip() if len(parts) > 2 else ""
                                    if model:
                                        hardware_info["disk_model"] = model
                                        if "SSD" in model.upper():
                                            hardware_info["disk_type"] = "SSD"
                                        elif media_type and "Fixed" in media_type:
                                            hardware_info["disk_type"] = "SSD" if any(x in model.upper() for x in ["SSD", "NVME", "SOLID"]) else "HDD"
                                        break
                except:
                    pass
                
                try:

                    result = subprocess.run(['wmic', 'memorychip', 'get', 'memorytype,speed', '/format:csv'], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')
                        for line in lines[1:]:
                            if line.strip() and 'MemoryType' not in line:
                                parts = line.split(',')
                                if len(parts) >= 3:
                                    mem_type_num = parts[1].strip()
                                    speed = parts[2].strip()
                                    if mem_type_num.isdigit():
                                        memory_type_map = {
                                            "20": "DDR", "21": "DDR2", "22": "DDR2 FB-DIMM",
                                            "24": "DDR3", "26": "DDR4", "34": "DDR5"
                                        }
                                        ram_type = memory_type_map.get(mem_type_num, f"Type-{mem_type_num}")
                                        if speed and speed.isdigit():
                                            ram_type += f" {speed}MHz"
                                        hardware_info["ram_type"] = ram_type
                                        break
                except:
                    pass
                
                try:

                    result = subprocess.run(['wmic', 'baseboard', 'get', 'manufacturer,product', '/format:csv'], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')
                        for line in lines[1:]:
                            if line.strip() and 'Manufacturer' not in line:
                                parts = line.split(',')
                                if len(parts) >= 3:
                                    manufacturer = parts[1].strip()
                                    product = parts[2].strip()
                                    if manufacturer and product:
                                        hardware_info["motherboard"] = f"{manufacturer} {product}".strip()
                                        break
                except:
                    pass

                if WMI_AVAILABLE and any(v == "Unknown" for v in hardware_info.values()):
                    try:
                        pythoncom.CoInitialize()  # Initialize COM for this thread
                        c = wmi.WMI()

                        if hardware_info["disk_model"] == "Unknown":
                            disks = c.Win32_DiskDrive()
                            if disks:
                                disk = disks[0]
                                hardware_info["disk_model"] = disk.Model or "Unknown"
                                if "SSD" in str(disk.Model).upper():
                                    hardware_info["disk_type"] = "SSD"
                                elif disk.InterfaceType == "SCSI":
                                    hardware_info["disk_type"] = "SSD"
                                else:
                                    hardware_info["disk_type"] = "HDD"
                        
                        if hardware_info["ram_type"] == "Unknown":
                            memory_modules = c.Win32_PhysicalMemory()
                            if memory_modules:
                                memory_type_map = {
                                    20: "DDR", 21: "DDR2", 22: "DDR2 FB-DIMM",
                                    24: "DDR3", 26: "DDR4", 34: "DDR5"
                                }
                                mem_type = memory_modules[0].SMBIOSMemoryType
                                hardware_info["ram_type"] = memory_type_map.get(mem_type, f"Type-{mem_type}")
                                speed = memory_modules[0].Speed
                                if speed:
                                    hardware_info["ram_type"] += f" {speed}MHz"
                        
                        if hardware_info["motherboard"] == "Unknown":
                            motherboards = c.Win32_BaseBoard()
                            if motherboards:
                                mb = motherboards[0]
                                hardware_info["motherboard"] = f"{mb.Manufacturer} {mb.Product}".strip()
                                
                    except Exception as e:
                        logging.warning(f"WMI fallback failed: {e}")
                    finally:
                        try:
                            pythoncom.CoUninitialize()
                        except:
                            pass
                            
        except Exception as e:
            logging.warning(f"Hardware info detection failed: {e}")

        cls.hardware_cache = hardware_info
        cls.cache_timestamp = current_time
        
        return hardware_info

    def get(self, request):
        # Check if this is for a remote node
        node_id = request.query_params.get('node_id')
        if node_id and node_id.startswith('node-'):
            # Proxy to node agent
            from services.node_api_client import call_node_api_sync
            try:
                result = call_node_api_sync(node_id, 'collect_metrics', {})
                if 'error' in result:
                    return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                return Response(result)
            except Exception as e:
                return Response({'error': f'Failed to collect node metrics: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Local metrics collection
        start_time = time.time()

        vm = psutil.virtual_memory()
        du = psutil.disk_usage('/')
        used_ram = vm.total - vm.available

        cpu_info = cpuinfo.get_cpu_info() if cpuinfo else {}
        cpu_brand = cpu_info.get("brand_raw", platform.processor())

        hardware_details = self.get_hardware_info()

        cpu_temp = self.get_cpu_temperature()

        cpu_physical_cores = psutil.cpu_count(logical=False)
        cpu_total_cores = psutil.cpu_count(logical=True)
        cpu_freq = psutil.cpu_freq()

        if platform.system() == "Linux" and distro:
            os_name = distro.name(pretty=True)
            os_release = distro.version()
            os_version = distro.lsb_release_attr("description") or platform.version()
        else:
            os_name = platform.system()
            os_release = platform.release()
            os_version = platform.version()

        gpu_info = []
        if GPUtil:
            try:
                gpus = GPUtil.getGPUs()
                for gpu in gpus:
                    gpu_data = {
                        "id": gpu.id,
                        "name": gpu.name,
                        "load": round(gpu.load * 100, 1),
                        "memory_free": gpu.memoryFree,
                        "memory_used": gpu.memoryUsed,
                        "memory_total": gpu.memoryTotal,
                        "temperature": gpu.temperature,
                        "uuid": gpu.uuid,
                        "memory_util": round((gpu.memoryUsed / gpu.memoryTotal) * 100, 1) if gpu.memoryTotal > 0 else 0
                    }
                    gpu_info.append(gpu_data)
            except Exception as e:
                logging.warning(f"GPU info failed: {e}")

        current_net = psutil.net_io_counters()
        current_time = time.time()
        
        upload_speed = 0
        download_speed = 0
        
        if self.prev_net and self.prev_time:
            time_diff = current_time - self.prev_time
            if time_diff > 0:

                upload_speed = ((current_net.bytes_sent - self.prev_net.bytes_sent) * 8) / (time_diff * 1000000)
                download_speed = ((current_net.bytes_recv - self.prev_net.bytes_recv) * 8) / (time_diff * 1000000)
        
        self.prev_net = current_net
        self.prev_time = current_time

        network_interfaces = []
        try:
            for interface, stats in psutil.net_if_stats().items():
                if stats.isup and interface != 'lo':  # Skip loopback
                    network_interfaces.append({
                        "name": interface,
                        "speed": stats.speed,  # Mbps
                        "mtu": stats.mtu,
                        "is_up": stats.isup
                    })
        except:
            pass

        processing_time = round((time.time() - start_time) * 1000, 2)
        
        metrics = {
            "cpu_percent": psutil.cpu_percent(interval=0.1),  # Faster interval
            "cpu_model": cpu_brand,
            "cpu_physical_cores": cpu_physical_cores,
            "cpu_total_cores": cpu_total_cores,
            "cpu_freq_max": cpu_freq.max if cpu_freq else None,
            "cpu_freq_min": cpu_freq.min if cpu_freq else None,
            "cpu_freq_current": cpu_freq.current if cpu_freq else None,
            "cpu_temp": round(cpu_temp, 1) if cpu_temp else None,
            
            "memory_gb": round(used_ram / (1024 ** 3), 2),
            "memory_total_gb": round(vm.total / (1024 ** 3), 2),
            "memory_percent": round((used_ram / vm.total) * 100, 1),
            "memory_available_gb": round(vm.available / (1024 ** 3), 2),
            
            "disk_gb": round(du.used / (1024 ** 3), 2),
            "disk_total_gb": round(du.total / (1024 ** 3), 2),
            "disk_percent": round((du.used / du.total) * 100, 1),
            "disk_free_gb": round(du.free / (1024 ** 3), 2),
            "disk_model": hardware_details["disk_model"],
            "disk_type": hardware_details["disk_type"],
            
            "ram_type": hardware_details["ram_type"],
            "motherboard": hardware_details["motherboard"],
            
            "network": {
                "bytes_sent": current_net.bytes_sent,
                "bytes_recv": current_net.bytes_recv,
                "upload_speed_mbps": round(upload_speed, 2),
                "download_speed_mbps": round(download_speed, 2),
                "interfaces": network_interfaces
            },
            
            "gpu": gpu_info,
            
            "os_name": os_name,
            "os_release": os_release,
            "os_version": os_version,
            
            "system_uptime": round(time.time() - psutil.boot_time()),
            "process_count": len(psutil.pids()),
            "response_time_ms": processing_time,
            "timestamp": current_time
        }
        
        return Response(metrics)

class InternetSpeedTestView(APIView):
    authentication_classes = [CookieOAuth2Authentication]
    permission_classes = [IsAuthenticated]
    speed_test_cache = {}
    test_running = False
    
    def get(self, request):

        if (self.speed_test_cache and 
            time.time() - self.speed_test_cache.get('timestamp', 0) < 3600 and self.speed_test_cache.get('complete', False) and not self.speed_test_cache.get('error')):
            return Response({
                "status": "cached",
                "data": {k: v for k, v in self.speed_test_cache.items() if k not in ['timestamp', 'complete', 'progress']},
                "age_seconds": int(time.time() - self.speed_test_cache['timestamp'])
            })

        if self.test_running:
            progress = self.speed_test_cache.get('progress', None)
            return Response({
                "status": "testing",
                "progress": progress,
                "data": self.speed_test_cache.get('partial_results', None)
            })

        self.test_running = True
        self.speed_test_cache = {"progress": "Initializing...", "timestamp": time.time(), "complete": False}
        threading.Thread(target=self._run_speedtest_cli, daemon=True).start()
        return Response({
            "status": "testing",
            "progress": "Initializing...",
            "data": None
        })
    
    def _run_speedtest_cli(self):
        try:
            import speedtest
            import time
            
            self.speed_test_cache["progress"] = "Initializing speed test..."
            time.sleep(0.5)
            
            st = speedtest.Speedtest()
            self.speed_test_cache["progress"] = "Finding best server..."
            
            st.get_best_server()
            self.speed_test_cache["progress"] = "Testing ping..."

            ping = st.results.ping
            partial_results = {"ping": f"Ping: {ping:.2f} ms"}
            self.speed_test_cache["partial_results"] = partial_results.copy()
            self.speed_test_cache["progress"] = f"Ping: {ping:.2f} ms"
            time.sleep(0.5)
            
            self.speed_test_cache["progress"] = "Testing download speed..."
            download = st.download() / 1000000  # Convert to Mbps
            partial_results["download"] = f"Download: {download:.2f} Mbit/s"
            self.speed_test_cache["partial_results"] = partial_results.copy()
            self.speed_test_cache["progress"] = f"Download: {download:.2f} Mbit/s"
            time.sleep(0.5)
            
            self.speed_test_cache["progress"] = "Testing upload speed..."
            upload = st.upload() / 1000000  # Convert to Mbps
            partial_results["upload"] = f"Upload: {upload:.2f} Mbit/s"
            self.speed_test_cache["partial_results"] = partial_results.copy()
            self.speed_test_cache["progress"] = f"Upload: {upload:.2f} Mbit/s"
            time.sleep(0.5)

            self.speed_test_cache = {
                "ping": f"Ping: {ping:.2f} ms",
                "download": f"Download: {download:.2f} Mbit/s",
                "upload": f"Upload: {upload:.2f} Mbit/s",
                "raw_output": f"Ping: {ping:.2f} ms\nDownload: {download:.2f} Mbit/s\nUpload: {upload:.2f} Mbit/s",
                "timestamp": time.time(),
                "complete": True
            }
        except Exception as e:
            self.speed_test_cache = {
                "error": f"Speed test failed: {str(e)}",
                "timestamp": time.time(),
                "complete": True
            }
            logging.error(f"Speedtest failed: {e}")
        finally:
            self.test_running = False

from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response

User = get_user_model()

class InitialDataView(APIView):
    authentication_classes = [CookieOAuth2Authentication]
    def get(self, request):
        user = request.user if request.user.is_authenticated else None
        data = {
            "user": {
                "username": user.username if user else None,
                "is_authenticated": bool(user),
            },
            "settings": {
                "theme": "dark",
                "panel_version": "1.0.0",
            }
        }
        return Response(data)

from rest_framework import viewsets
from .models import Server, Metric, Alert
from .serializers import ServerSerializer, MetricSerializer, AlertSerializer

class ServerViewSet(viewsets.ModelViewSet):
    queryset = Server.objects.all()
    serializer_class = ServerSerializer

class MetricViewSet(viewsets.ModelViewSet):
    queryset = Metric.objects.all()
    serializer_class = MetricSerializer

class AlertViewSet(viewsets.ModelViewSet):
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer

@api_view(["GET"])
@authentication_classes([CookieOAuth2Authentication])
@permission_classes([IsAuthenticated])
def simple_speed_test(request):

    import speedtest
    result = {}
    try:
        st = speedtest.Speedtest()
        st.get_best_server()
        download = st.download() / 1000000  
        upload = st.upload() / 1000000      
        ping = st.results.ping
        
        result["ping"] = f"Ping: {ping:.3f} ms"
        result["download"] = f"Download: {download:.2f} Mbit/s"
        result["upload"] = f"Upload: {upload:.2f} Mbit/s"
        result["raw_output"] = f"Ping: {ping:.3f} ms\nDownload: {download:.2f} Mbit/s\nUpload: {upload:.2f} Mbit/s"

        print("[DEBUG] Internet speed test response:", result)
    except Exception as e:
        result["error"] = str(e)
        print("[DEBUG] Internet speed test error:", str(e))
    return Response(result, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([CookieOAuth2Authentication])
@permission_classes([IsAuthenticated])
def activity_logs(request):
    
    from .models import ActivityLog
    from django.utils import timezone
    from datetime import timedelta

    limit = int(request.GET.get('limit', 50))
    log_type = request.GET.get('type', None)
    days = int(request.GET.get('days', 7))

    cutoff_date = timezone.now() - timedelta(days=days)
    logs = ActivityLog.objects.filter(timestamp__gte=cutoff_date)

    if log_type:
        logs = logs.filter(log_type=log_type)

    logs = logs[:limit]

    formatted_logs = []
    for log in logs:

        time_diff = timezone.now() - log.timestamp
        if time_diff.total_seconds() < 60:
            time_str = 'Just now'
        elif time_diff.total_seconds() < 3600:
            minutes = int(time_diff.total_seconds() / 60)
            time_str = f'{minutes}m ago'
        elif time_diff.total_seconds() < 86400:
            hours = int(time_diff.total_seconds() / 3600)
            time_str = f'{hours}h ago'
        elif time_diff.days == 1:
            time_str = 'Yesterday'
        elif time_diff.days < 7:
            time_str = f'{time_diff.days} days ago'
        else:
            time_str = log.timestamp.strftime('%b %d')
        
        formatted_logs.append({
            'id': log.id,
            'type': log.log_type,
            'message': log.message,
            'timestamp': time_str,
            'full_timestamp': log.timestamp.isoformat(),
            'user': log.user.username if log.user else None,
            'details': log.details
        })
    
    return Response(formatted_logs, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([CookieOAuth2Authentication])
@permission_classes([IsAuthenticated])
def available_servers(request):
    
    import socket
    from services.models import Node
    
    servers = []

    server_id = get_stable_server_id()
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
    except Exception:
        hostname = "localhost"
        ip = "127.0.0.1"
    
    servers.append({
        'id': f'local-{server_id}',
        'name': f'Server {server_id}',
        'type': 'local',
        'node_type': 'server',
        'hostname': hostname,
        'ip_address': ip,
        'status': 'online',
        'last_seen': None,
        'is_local': True
    })

    try:
        nodes = Node.objects.filter(owner=request.user)
        for node in nodes:
            servers.append({
                'id': node.id,  # node.id already has 'node-' prefix
                'node_id': node.id,
                'name': node.name,
                'type': 'remote',
                'node_type': node.node_type,
                'hostname': node.hostname,
                'ip_address': node.ip_address,
                'status': node.status,
                'last_seen': node.last_seen.isoformat() if node.last_seen else None,
                'is_local': False
            })
    except Exception as e:
        print(f"[DEBUG] Error fetching nodes: {e}")
    
    return Response(servers, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([CookieOAuth2Authentication])
@permission_classes([IsAuthenticated])
def resolve_alert(request, alert_id):
    from rest_framework.response import Response
    from .models import Alert
    from .logging_utils import log_alert_resolved
    from django.utils import timezone
    
    # Try to parse as integer for database alerts
    try:
        alert_id_int = int(alert_id)
        try:
            alert = Alert.objects.get(id=alert_id_int)
            alert.resolved = True
            alert.resolved_at = timezone.now()
            alert.resolved_by = request.user
            alert.ignored = False  # Clear ignored status if it was ignored
            alert.save()

            log_alert_resolved(alert.message, user=request.user, level=alert.level)
            
            return Response({
                'success': True,
                'message': 'Alert resolved successfully'
            }, status=status.HTTP_200_OK)
        except Alert.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Alert not found'
            }, status=status.HTTP_404_NOT_FOUND)
    except ValueError:
        # This is a dynamic alert from AlertSystem
        # Create a database record so it will be filtered out
        try:
            from .models import Server
            
            alert_message = request.data.get('message')
            alert_level = request.data.get('level', 'warning')
            
            if not alert_message:
                return Response({
                    'success': False,
                    'error': 'Alert message is required for dynamic alerts'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            server = Server.objects.first()
            if not server:
                return Response({
                    'success': False,
                    'error': 'No server found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Create or get the alert record
            alert, created = Alert.objects.get_or_create(
                server=server,
                message=alert_message,
                defaults={
                    'level': alert_level,
                    'resolved': True,
                    'resolved_at': timezone.now(),
                    'resolved_by': request.user
                }
            )
            
            # If it already exists, update it
            if not created:
                alert.resolved = True
                alert.resolved_at = timezone.now()
                alert.resolved_by = request.user
                alert.ignored = False
                alert.save()

            log_alert_resolved(alert_message, user=request.user, level=alert_level)
            
            return Response({
                'success': True,
                'message': 'Dynamic alert resolved successfully'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Failed to resolve dynamic alert: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([CookieOAuth2Authentication])
@permission_classes([IsAuthenticated])
def ignore_alert(request, alert_id):
    from rest_framework.response import Response
    from .models import Alert, Server
    from .logging_utils import log_alert_ignored
    from django.utils import timezone
    
    # Try to parse as integer for database alerts
    try:
        alert_id_int = int(alert_id)
        try:
            alert = Alert.objects.get(id=alert_id_int)
            alert.ignored = True
            alert.ignored_at = timezone.now()
            alert.ignored_by = request.user
            alert.save()

            log_alert_ignored(alert.message, user=request.user, level=alert.level)
            
            return Response({
                'success': True,
                'message': 'Alert ignored successfully'
            }, status=status.HTTP_200_OK)
        except Alert.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Alert not found'
            }, status=status.HTTP_404_NOT_FOUND)
    except ValueError:
        # This is a dynamic alert from AlertSystem (string ID like "storage_filesystem_disk_1759428134")
        # Create a database record so it will be filtered out in future requests
        try:
            # Get the alert message from request body
            alert_message = request.data.get('message')
            alert_level = request.data.get('level', 'warning')
            
            if not alert_message:
                return Response({
                    'success': False,
                    'error': 'Alert message is required for dynamic alerts'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get the first server (or create logic to determine which server)
            server = Server.objects.first()
            if not server:
                return Response({
                    'success': False,
                    'error': 'No server found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Create or get the alert record
            alert, created = Alert.objects.get_or_create(
                server=server,
                message=alert_message,
                defaults={
                    'level': alert_level,
                    'ignored': True,
                    'ignored_at': timezone.now(),
                    'ignored_by': request.user
                }
            )
            
            # If it already exists, update it
            if not created:
                alert.ignored = True
                alert.ignored_at = timezone.now()
                alert.ignored_by = request.user
                alert.save()

            log_alert_ignored(alert_message, user=request.user, level=alert_level)
            
            return Response({
                'success': True,
                'message': 'Dynamic alert ignored successfully'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Failed to ignore dynamic alert: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([CookieOAuth2Authentication])
@permission_classes([IsAuthenticated])
def unignore_alert(request, alert_id):
    from rest_framework.response import Response
    from .models import Alert
    from .logging_utils import log_alert_unignored
    
    # Try to parse as integer for database alerts
    try:
        alert_id_int = int(alert_id)
        try:
            alert = Alert.objects.get(id=alert_id_int)
            alert.ignored = False
            alert.ignored_at = None
            alert.ignored_by = None
            alert.save()

            log_alert_unignored(alert.message, user=request.user, level=alert.level)
            
            return Response({
                'success': True,
                'message': 'Alert removed from blacklist'
            }, status=status.HTTP_200_OK)
        except Alert.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Alert not found'
            }, status=status.HTTP_404_NOT_FOUND)
    except ValueError:
        # This is a dynamic alert from AlertSystem
        return Response({
            'success': True,
            'message': 'Dynamic alert unignored'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([CookieOAuth2Authentication])
@permission_classes([IsAuthenticated])
def ignored_alerts(request):
    
    from .models import Alert
    
    try:

        alerts = Alert.objects.filter(ignored=True).order_by('-ignored_at')
        
        result = []
        for alert in alerts:
            result.append({
                'id': alert.id,
                'message': alert.message,
                'level': alert.level,
                'created_at': alert.created_at.isoformat(),
                'ignored_at': alert.ignored_at.isoformat() if alert.ignored_at else None,
                'ignored_by': alert.ignored_by.username if alert.ignored_by else None
            })
        
        return Response({'alerts': result}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)