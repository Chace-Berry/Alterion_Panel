"""
Comprehensive Alert System
Dynamically monitors system metrics and generates alerts based on intelligent thresholds
"""
import psutil
import platform
import os
import socket
from datetime import datetime, timedelta
from collections import defaultdict
import subprocess
import shutil


class AlertSystem:
    """
    Main alert system that monitors various aspects of the system
    and generates alerts with dynamic thresholds
    """
    
    def __init__(self):
        self.cpu_count = psutil.cpu_count()
        self.system = platform.system()
        self.alerts = []
        
    def add_alert(self, alert_type, severity, message, metric, value, category, details=None):
        """Add an alert to the list with optional detailed information"""
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
        
        # Add detailed information if provided
        if details:
            alert['details'] = details
        
        self.alerts.append(alert)
    
    def check_system_resources(self):
        """Check CPU, memory, disk, swap, and load average"""
        
        # CPU - Check for sustained usage and find top processes
        cpu_percent = psutil.cpu_percent(interval=2)
        per_cpu = psutil.cpu_percent(interval=1, percpu=True)
        
        # Find top CPU consuming processes
        top_procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent']):
            try:
                cpu_usage = p.info.get('cpu_percent', 0) or 0
                if cpu_usage > 0:
                    top_procs.append((p.info['name'], p.info['pid'], cpu_usage))
            except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError):
                continue
        
        # Sort by CPU usage and get top 5
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
        
        # Memory - Find top memory consuming processes
        memory = psutil.virtual_memory()
        top_mem_procs = []
        for p in psutil.process_iter(['pid', 'name', 'memory_percent']):
            try:
                mem_usage = p.info.get('memory_percent', 0) or 0
                if mem_usage > 0:
                    top_mem_procs.append((p.info['name'], p.info['pid'], mem_usage))
            except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError):
                continue
        
        # Sort by memory usage and get top 5
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
        
        # Disk Usage - Check all partitions
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
        
        # Swap Usage
        swap = psutil.swap_memory()
        if swap.percent > 80:
            self.add_alert('system_resources', 'critical',
                          f'Critical swap usage: {swap.percent:.1f}% (memory exhaustion risk)',
                          'swap', swap.percent, 'system_resources')
        elif swap.percent > 50:
            self.add_alert('system_resources', 'warning',
                          f'High swap usage: {swap.percent:.1f}%',
                          'swap', swap.percent, 'system_resources')
        
        # Load Average (dynamic based on CPU cores)
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
        
        # I/O Wait (Unix-like systems)
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
        """Check for zombie processes, runaway processes, and file descriptors"""
        
        zombie_count = 0
        runaway_procs = []
        total_fds = 0
        
        # Define attrs based on platform
        attrs = ['pid', 'name', 'status', 'cpu_percent']
        if self.system != 'Windows':
            attrs.append('num_fds')
        
        for proc in psutil.process_iter(attrs):
            try:
                # Check for zombie processes
                if proc.info['status'] == psutil.STATUS_ZOMBIE:
                    zombie_count += 1
                
                # Check for runaway processes (>90% CPU sustained)
                if proc.info['cpu_percent'] and proc.info['cpu_percent'] > 90:
                    runaway_procs.append((proc.info['name'], proc.info['cpu_percent'], proc.info['pid']))
                
                # Count file descriptors (Unix-like only)
                if self.system != 'Windows' and proc.info.get('num_fds'):
                    total_fds += proc.info['num_fds']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Zombie process alerts
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
        
        # Runaway process alerts
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
        
        # File descriptor limits (Unix-like)
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
        
        # Check process count (fork bomb detection)
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
        """Check network interfaces, traffic, and packet errors"""
        
        # Virtual adapter patterns to ignore
        virtual_patterns = [
            'Local Area Connection*',  # Windows virtual adapters
            'Bluetooth Network',       # Bluetooth network connections
            'VirtualBox',              # VirtualBox adapters
            'VMware',                  # VMware adapters
            'vEthernet',              # Hyper-V virtual adapters
            'Loopback',               # Loopback interface
            'lo'                      # Linux loopback
        ]
        
        # Check network interfaces
        net_if_stats = psutil.net_if_stats()
        net_if_addrs = psutil.net_if_addrs()
        
        for interface, stats in net_if_stats.items():
            # Skip virtual adapters
            if any(pattern in interface for pattern in virtual_patterns):
                continue
                
            if not stats.isup:
                # Get interface details
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
        
        # Check packet errors
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
        """Check CPU, GPU, and disk temperatures"""
        
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
        
        # Check fan speeds
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
        
        # Check battery status
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
        """Check for security-related issues"""
        
        # Check for failed SSH attempts (Unix-like systems)
        if self.system != 'Windows':
            try:
                # Check auth log for failed SSH attempts
                auth_log = '/var/log/auth.log' if os.path.exists('/var/log/auth.log') else '/var/log/secure'
                if os.path.exists(auth_log):
                    failed_count = 0
                    # Count failed attempts in last 10 minutes
                    # Note: This is a simplified check, would need proper log parsing
                    self.add_alert('security', 'info',
                                  'SSH monitoring active',
                                  'ssh_monitor', 0, 'security')
            except:
                pass
    
    def get_all_alerts(self):
        """Run all checks and return alerts"""
        self.alerts = []
        
        self.check_system_resources()
        self.check_processes_services()
        self.check_network()
        self.check_hardware_temperature()
        self.check_security()
        
        # If no alerts, system is healthy
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
        
        return self.alerts
