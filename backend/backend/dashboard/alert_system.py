
import psutil
import platform
import os
import socket
from datetime import datetime, timedelta
from collections import defaultdict
import subprocess
import shutil


class AlertSystem:
    
    
    def __init__(self):
        self.cpu_count = psutil.cpu_count()
        self.system = platform.system()
        self.alerts = []
        
    def add_alert(self, alert_type, severity, message, metric, value, category, details=None):
        
        alert = {
            'id': f'{category}_{metric}_{int(datetime.now().timestamp())}',
            'type': severity,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'resolved': False,
            'metric': metric,
            'value': value,
            'category': category
        }

        if details:
            alert['details'] = details
        
        self.alerts.append(alert)
    
    def check_system_resources(self):
        

        cpu_percent = psutil.cpu_percent(interval=2)
        per_cpu = psutil.cpu_percent(interval=1, percpu=True)

        top_procs = []

        ignore_processes = {'System Idle Process', 'System', 'Idle'}
        
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent']):
            try:
                process_name = p.info.get('name', '')

                if process_name in ignore_processes:
                    continue
                    
                cpu_usage = p.info.get('cpu_percent', 0) or 0

                cpu_usage_normalized = cpu_usage / self.cpu_count

                cpu_usage_normalized = min(cpu_usage_normalized, 100.0)
                
                if cpu_usage_normalized > 0.1:  # Only include processes using more than 0.1% CPU
                    top_procs.append((process_name, p.info['pid'], cpu_usage_normalized))
            except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError):
                continue

        top_procs = sorted(top_procs, key=lambda x: x[2], reverse=True)[:5]
        
        top_cpu_info = [
            {'name': name, 'pid': pid, 'cpu': cpu}
            for name, pid, cpu in top_procs
        ]
        
        if cpu_percent > 90:
            details = {
                'total_cores': self.cpu_count,
                'per_cpu_usage': [f'{cpu:.1f}%' for cpu in per_cpu],
                'top_processes': top_cpu_info,
                'cause': f"Top process: {top_cpu_info[0]['name']} using {top_cpu_info[0]['cpu']:.1f}%" if top_cpu_info else "Multiple processes consuming CPU"
            }
            self.add_alert('system_resources', 'critical', 
                          f'Critical CPU usage: {cpu_percent:.1f}%', 
                          'cpu', cpu_percent, 'system_resources', details)
        elif cpu_percent > 80:
            details = {
                'total_cores': self.cpu_count,
                'per_cpu_usage': [f'{cpu:.1f}%' for cpu in per_cpu],
                'top_processes': top_cpu_info,
                'cause': f"Top process: {top_cpu_info[0]['name']} using {top_cpu_info[0]['cpu']:.1f}%" if top_cpu_info else "Multiple processes consuming CPU"
            }
            self.add_alert('system_resources', 'warning',
                          f'High CPU usage: {cpu_percent:.1f}%',
                          'cpu', cpu_percent, 'system_resources', details)

        memory = psutil.virtual_memory()
        top_mem_procs = []
        for p in psutil.process_iter(['pid', 'name', 'memory_percent']):
            try:
                mem_usage = p.info.get('memory_percent', 0) or 0
                if mem_usage > 0:
                    top_mem_procs.append((p.info['name'], p.info['pid'], mem_usage))
            except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError):
                continue

        top_mem_procs = sorted(top_mem_procs, key=lambda x: x[2], reverse=True)[:5]
        
        top_mem_info = [
            {'name': name, 'pid': pid, 'memory': f"{mem:.1f}%"}
            for name, pid, mem in top_mem_procs
        ]
        
        if memory.percent > 90:
            details = {
                'total_gb': f"{memory.total / (1024**3):.1f}GB",
                'used_gb': f"{memory.used / (1024**3):.1f}GB",
                'available_gb': f"{memory.available / (1024**3):.1f}GB",
                'top_processes': top_mem_info,
                'cause': f"Top process: {top_mem_info[0]['name']} using {top_mem_info[0]['memory']}" if top_mem_info else "Memory exhaustion imminent"
            }
            self.add_alert('system_resources', 'critical',
                          f'Critical memory usage: {memory.percent:.1f}% (OOM risk)',
                          'memory', memory.percent, 'system_resources', details)
        elif memory.percent > 80:
            details = {
                'total_gb': f"{memory.total / (1024**3):.1f}GB",
                'used_gb': f"{memory.used / (1024**3):.1f}GB",
                'available_gb': f"{memory.available / (1024**3):.1f}GB",
                'top_processes': top_mem_info,
                'cause': f"Top process: {top_mem_info[0]['name']} using {top_mem_info[0]['memory']}" if top_mem_info else "Multiple processes consuming memory"
            }
            self.add_alert('system_resources', 'warning',
                          f'High memory usage: {memory.percent:.1f}%',
                          'memory', memory.percent, 'system_resources', details)

        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                if usage.percent > 90:
                    self.add_alert('storage_filesystem', 'critical',
                                  f'Critical disk space on {partition.mountpoint}: {usage.percent:.1f}% used',
                                  'disk', usage.percent, 'storage_filesystem')
                elif usage.percent > 80:
                    self.add_alert('storage_filesystem', 'warning',
                                  f'Low disk space on {partition.mountpoint}: {usage.percent:.1f}% used',
                                  'disk', usage.percent, 'storage_filesystem')
            except (PermissionError, OSError):
                continue

        swap = psutil.swap_memory()
        if swap.percent > 80:
            self.add_alert('system_resources', 'critical',
                          f'Critical swap usage: {swap.percent:.1f}% (memory exhaustion risk)',
                          'swap', swap.percent, 'system_resources')
        elif swap.percent > 50:
            self.add_alert('system_resources', 'warning',
                          f'High swap usage: {swap.percent:.1f}%',
                          'swap', swap.percent, 'system_resources')

        try:
            load_avg = psutil.getloadavg()[0]
            critical_threshold = self.cpu_count * 2
            warning_threshold = self.cpu_count * 1
            
            if load_avg > critical_threshold:
                self.add_alert('system_resources', 'critical',
                              f'Critical load average: {load_avg:.2f} (>{critical_threshold} on {self.cpu_count} cores)',
                              'load', load_avg, 'system_resources')
            elif load_avg > warning_threshold:
                self.add_alert('system_resources', 'warning',
                              f'High load average: {load_avg:.2f} (>{warning_threshold} on {self.cpu_count} cores)',
                              'load', load_avg, 'system_resources')
        except (AttributeError, OSError):
            pass

        if self.system != 'Windows':
            try:
                cpu_times = psutil.cpu_times_percent(interval=1)
                if hasattr(cpu_times, 'iowait'):
                    if cpu_times.iowait > 20:
                        self.add_alert('system_resources', 'critical',
                                      f'Critical I/O wait: {cpu_times.iowait:.1f}% (disk bottleneck)',
                                      'iowait', cpu_times.iowait, 'system_resources')
                    elif cpu_times.iowait > 10:
                        self.add_alert('system_resources', 'warning',
                                      f'High I/O wait: {cpu_times.iowait:.1f}%',
                                      'iowait', cpu_times.iowait, 'system_resources')
            except:
                pass
    
    def check_processes_services(self):
        
        
        zombie_count = 0
        runaway_procs = []
        total_fds = 0

        attrs = ['pid', 'name', 'status', 'cpu_percent']
        if self.system != 'Windows':
            attrs.append('num_fds')

        ignore_processes = {'System Idle Process', 'System', 'Idle'}
        
        for proc in psutil.process_iter(attrs):
            try:
                process_name = proc.info.get('name', '')

                if proc.info['status'] == psutil.STATUS_ZOMBIE:
                    zombie_count += 1

                if proc.info['cpu_percent']:

                    cpu_normalized = proc.info['cpu_percent'] / self.cpu_count

                    cpu_normalized = min(cpu_normalized, 100.0)

                    if cpu_normalized > 90 and process_name not in ignore_processes:
                        runaway_procs.append((process_name, cpu_normalized, proc.info['pid']))

                if self.system != 'Windows' and proc.info.get('num_fds'):
                    total_fds += proc.info['num_fds']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if zombie_count > 20:
            details = {
                'zombie_count': zombie_count,
                'cause': 'Parent processes not reaping child processes. Check for hung or malfunctioning parent processes.',
                'recommendation': 'Kill parent processes or restart affected services'
            }
            self.add_alert('process_service', 'critical',
                          f'Critical: {zombie_count} zombie processes detected',
                          'zombies', zombie_count, 'process_service', details)
        elif zombie_count > 5:
            details = {
                'zombie_count': zombie_count,
                'cause': 'Some parent processes not properly cleaning up child processes',
                'recommendation': 'Monitor parent processes for issues'
            }
            self.add_alert('process_service', 'warning',
                          f'{zombie_count} zombie processes detected',
                          'zombies', zombie_count, 'process_service', details)

        for proc_name, cpu, pid in runaway_procs:
            details = {
                'process_name': proc_name,
                'process_id': pid,
                'cpu_usage': f'{cpu:.1f}%',
                'cause': f'{proc_name} (PID: {pid}) is consuming excessive CPU resources',
                'recommendation': 'Consider restarting this process or investigating why it\'s using so much CPU'
            }
            self.add_alert('process_service', 'critical',
                          f'Runaway process: {proc_name} using {cpu:.1f}% CPU',
                          'runaway_process', cpu, 'process_service', details)

        if self.system != 'Windows':
            try:
                import resource
                soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
                fd_percent = (total_fds / soft) * 100
                
                if fd_percent > 90:
                    self.add_alert('process_service', 'critical',
                                  f'Critical: {fd_percent:.1f}% of file descriptors used',
                                  'file_descriptors', fd_percent, 'process_service')
                elif fd_percent > 70:
                    self.add_alert('process_service', 'warning',
                                  f'High file descriptor usage: {fd_percent:.1f}%',
                                  'file_descriptors', fd_percent, 'process_service')
            except:
                pass

        proc_count = len(psutil.pids())
        if proc_count > 1000:
            details = {
                'total_processes': proc_count,
                'cause': 'Possible fork bomb attack or runaway process spawning',
                'recommendation': 'Immediately check for malicious processes or stuck scripts creating infinite child processes'
            }
            self.add_alert('security', 'critical',
                          f'Critical process count: {proc_count} (possible fork bomb)',
                          'process_count', proc_count, 'security', details)
        elif proc_count > 300:
            details = {
                'total_processes': proc_count,
                'cause': 'Higher than normal process count',
                'recommendation': 'Monitor for unusual process creation patterns'
            }
            self.add_alert('security', 'warning',
                          f'High process count: {proc_count}',
                          'process_count', proc_count, 'security', details)
    
    def check_network(self):
        

        virtual_patterns = [
            'Local Area Connection*',  # Windows virtual adapters
            'Bluetooth Network',       # Bluetooth network connections
            'VirtualBox',              # VirtualBox adapters
            'VMware',                  # VMware adapters
            'vEthernet',              # Hyper-V virtual adapters
            'Loopback',               # Loopback interface
            'lo'                      # Linux loopback
        ]

        net_if_stats = psutil.net_if_stats()
        net_if_addrs = psutil.net_if_addrs()
        
        for interface, stats in net_if_stats.items():

            if any(pattern in interface for pattern in virtual_patterns):
                continue
                
            if not stats.isup:

                addrs = net_if_addrs.get(interface, [])
                ip_info = ', '.join([addr.address for addr in addrs if addr.family == 2])  # AF_INET
                
                severity = 'critical' if 'eth0' in interface.lower() or 'en0' in interface.lower() or 'Wi-Fi' in interface else 'warning'
                
                details = {
                    'interface': interface,
                    'status': 'down',
                    'ip_addresses': ip_info if ip_info else 'No IP assigned',
                    'cause': 'Cable unplugged or adapter disabled' if 'eth' in interface.lower() else 'Connection not active'
                }
                
                self.add_alert('network', severity,
                              f'Network interface {interface} is down',
                              'interface_down', 0, 'network', details)

        net_io = psutil.net_io_counters()
        total_packets = net_io.packets_sent + net_io.packets_recv
        if total_packets > 0:
            error_percent = ((net_io.errin + net_io.errout) / total_packets) * 100
            
            if error_percent > 5:
                details = {
                    'total_packets': total_packets,
                    'errors_in': net_io.errin,
                    'errors_out': net_io.errout,
                    'drops_in': net_io.dropin,
                    'drops_out': net_io.dropout,
                    'cause': 'Network congestion, faulty hardware, or driver issues'
                }
                self.add_alert('network', 'critical',
                              f'Critical packet error rate: {error_percent:.2f}%',
                              'packet_errors', error_percent, 'network', details)
            elif error_percent > 1:
                details = {
                    'total_packets': total_packets,
                    'errors_in': net_io.errin,
                    'errors_out': net_io.errout,
                    'drops_in': net_io.dropin,
                    'drops_out': net_io.dropout,
                    'cause': 'Possible network congestion or intermittent connection issues'
                }
                self.add_alert('network', 'warning',
                              f'High packet error rate: {error_percent:.2f}%',
                              'packet_errors', error_percent, 'network', details)
    
    def check_hardware_temperature(self):
        
        
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    for entry in entries:
                        if entry.current > 85:
                            self.add_alert('hardware_environment', 'critical',
                                          f'Critical temperature on {name}: {entry.current:.1f}°C',
                                          'temperature', entry.current, 'hardware_environment')
                        elif entry.current > 75:
                            self.add_alert('hardware_environment', 'warning',
                                          f'High temperature on {name}: {entry.current:.1f}°C',
                                          'temperature', entry.current, 'hardware_environment')
        except (AttributeError, OSError):
            pass

        try:
            fans = psutil.sensors_fans()
            if fans:
                for name, entries in fans.items():
                    failed_fans = sum(1 for fan in entries if fan.current == 0)
                    if failed_fans > 1:
                        self.add_alert('hardware_environment', 'critical',
                                      f'Multiple fans failed on {name}',
                                      'fan_failure', failed_fans, 'hardware_environment')
                    elif failed_fans > 0:
                        self.add_alert('hardware_environment', 'warning',
                                      f'Fan failure detected on {name}',
                                      'fan_failure', failed_fans, 'hardware_environment')
        except (AttributeError, OSError):
            pass

        try:
            battery = psutil.sensors_battery()
            if battery:
                if battery.percent < 20 and not battery.power_plugged:
                    self.add_alert('hardware_environment', 'critical',
                                  f'Critical battery level: {battery.percent:.0f}%',
                                  'battery', battery.percent, 'hardware_environment')
                elif battery.percent < 50 and not battery.power_plugged:
                    self.add_alert('hardware_environment', 'warning',
                                  f'Low battery level: {battery.percent:.0f}%',
                                  'battery', battery.percent, 'hardware_environment')
        except (AttributeError, OSError):
            pass
    
    def check_security(self):
        

        if self.system != 'Windows':
            try:

                auth_log = '/var/log/auth.log' if os.path.exists('/var/log/auth.log') else '/var/log/secure'
                if os.path.exists(auth_log):
                    failed_count = 0


                    self.add_alert('security', 'info',
                                  'SSH monitoring active',
                                  'ssh_monitor', 0, 'security')
            except:
                pass
    
    def get_all_alerts(self):
        
        self.alerts = []
        
        self.check_system_resources()
        self.check_processes_services()
        self.check_network()
        self.check_hardware_temperature()
        self.check_security()

        if not self.alerts:
            self.alerts.append({
                'id': 'all_ok',
                'type': 'info',
                'message': 'All systems operating normally',
                'timestamp': datetime.now().isoformat(),
                'resolved': True,
                'metric': 'system',
                'value': 0,
                'category': 'system'
            })

        filtered_alerts = self._filter_ignored_resolved_alerts(self.alerts)
        
        return filtered_alerts
    
    def _filter_ignored_resolved_alerts(self, alerts):
        
        try:
            from .models import Alert, Server
            from django.db import models

            server = Server.objects.first()
            if not server:
                return alerts

            db_alerts = Alert.objects.filter(
                server=server
            ).filter(
                models.Q(ignored=True) | models.Q(resolved=True)
            ).values_list('message', flat=True)
            
            ignored_messages = set(db_alerts)

            filtered = [
                alert for alert in alerts 
                if alert['message'] not in ignored_messages
            ]
            
            return filtered if filtered else alerts
        except Exception as e:

            print(f"[DEBUG] Error filtering ignored/resolved alerts: {e}")
            return alerts
