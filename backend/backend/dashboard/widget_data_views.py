
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from authentication.cookie_oauth2 import CookieOAuth2Authentication
from django.utils import timezone
from datetime import timedelta
import random
import psutil
import platform
from .alert_system import AlertSystem


class AlertsWidgetView(APIView):
    
    authentication_classes = [CookieOAuth2Authentication]
    
    def get(self, request):

        alert_system = AlertSystem()
        alerts = alert_system.get_all_alerts()
        
        return Response({'alerts': alerts})


class TrafficWidgetView(APIView):
    
    authentication_classes = [CookieOAuth2Authentication]
    
    def get(self, request):

        traffic_data = {
            'current_visitors': random.randint(50, 500),
            'today_visitors': random.randint(1000, 5000),
            'today_pageviews': random.randint(5000, 25000),
            'trend': 'up',
            'chart_data': [
                {'time': '00:00', 'visitors': random.randint(10, 50)},
                {'time': '04:00', 'visitors': random.randint(5, 30)},
                {'time': '08:00', 'visitors': random.randint(30, 100)},
                {'time': '12:00', 'visitors': random.randint(50, 150)},
                {'time': '16:00', 'visitors': random.randint(40, 120)},
                {'time': '20:00', 'visitors': random.randint(30, 80)},
            ]
        }
        return Response(traffic_data)


class UptimeWidgetView(APIView):
    
    authentication_classes = [CookieOAuth2Authentication]
    
    def get(self, request):
        from .uptime_monitor import UptimeMonitorService
        
        try:

            monitor = UptimeMonitorService()

            from .models import UptimeCheck
            last_check = UptimeCheck.objects.filter(server=monitor.server).first()
            if not last_check or (timezone.now() - last_check.timestamp).total_seconds() > 600:
                monitor.perform_check()

            stats = monitor.get_uptime_stats(days=30)
            current_status = monitor.get_current_status()
            system_uptime = monitor.get_system_uptime()
            last_incident = monitor.get_last_incident_time()
            daily_history = monitor.get_daily_uptime_history(days=30)
            
            uptime_data = {
                'currentUptime': system_uptime,
                'uptimePercentage': stats['uptime_percentage'],
                'lastIncident': last_incident,
                'responseTime': int(stats['avg_response_time']),
                'status': current_status['status'],
                'totalChecks': stats['total_checks'],
                'successfulChecks': stats['successful_checks'],
                'incidentsCount': stats['incidents_count'],
                'totalDowntimeMinutes': stats['total_downtime_minutes'],
                'dailyHistory': daily_history,
                'lastCheck': current_status['last_check'].isoformat() if current_status['last_check'] else None
            }
            
            return Response(uptime_data)
            
        except Exception as e:

            import time
            
            try:
                boot_time = psutil.boot_time()
                uptime_seconds = time.time() - boot_time
                days = int(uptime_seconds // 86400)
                hours = int((uptime_seconds % 86400) // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                
                fallback_data = {
                    'currentUptime': f"{days}d {hours}h {minutes}m",
                    'uptimePercentage': 99.9,
                    'lastIncident': 'Never',
                    'responseTime': 50,
                    'status': 'operational',
                    'error': str(e)
                }
            except:
                fallback_data = {
                    'currentUptime': '0d 0h 0m',
                    'uptimePercentage': 100.0,
                    'lastIncident': 'Never',
                    'responseTime': 0,
                    'status': 'operational',
                    'error': str(e)
                }
            
            return Response(fallback_data)


class PerformanceWidgetView(APIView):
    
    authentication_classes = [CookieOAuth2Authentication]
    
    def get(self, request):

        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net_io = psutil.net_io_counters()


        network_in_mbps = round((net_io.bytes_recv / 1024 / 1024), 2)
        network_out_mbps = round((net_io.bytes_sent / 1024 / 1024), 2)

        try:
            load_avg = psutil.getloadavg()[0]  # 1-minute load average
        except (AttributeError, OSError):

            load_avg = cpu_percent / 100
        
        performance_data = {
            'cpu_usage': round(cpu_percent, 1),
            'cpu_count': psutil.cpu_count(),
            'memory_usage': round(memory.percent, 1),
            'memory_used_gb': round(memory.used / (1024**3), 2),
            'memory_total_gb': round(memory.total / (1024**3), 2),
            'disk_usage': round(disk.percent, 1),
            'disk_used_gb': round(disk.used / (1024**3), 2),
            'disk_total_gb': round(disk.total / (1024**3), 2),
            'network_in_mb': network_in_mbps,
            'network_out_mb': network_out_mbps,
            'load_average': round(load_avg, 2),
            'system': platform.system(),
            'hostname': platform.node()
        }
        return Response(performance_data)


class QuickActionsWidgetView(APIView):
    
    authentication_classes = [CookieOAuth2Authentication]
    
    def get(self, request):

        actions = [
            {'id': 'restart_server', 'label': 'Restart Server', 'icon': 'power'},
            {'id': 'clear_cache', 'label': 'Clear Cache', 'icon': 'trash'},
            {'id': 'backup_now', 'label': 'Backup Now', 'icon': 'database'},
            {'id': 'update_ssl', 'label': 'Update SSL', 'icon': 'shield'},
        ]
        return Response({'actions': actions})
    
    def post(self, request):

        action_id = request.data.get('action_id')

        return Response({
            'success': True,
            'message': f'Action {action_id} executed successfully'
        })


class ActivityWidgetView(APIView):
    
    authentication_classes = [CookieOAuth2Authentication]
    
    def get(self, request):

        activities = [
            {
                'id': 1,
                'type': 'deployment',
                'description': 'Deployed version 2.1.0 to production',
                'user': 'admin',
                'timestamp': (timezone.now() - timedelta(minutes=15)).isoformat()
            },
            {
                'id': 2,
                'type': 'security',
                'description': 'SSL certificate renewed',
                'user': 'system',
                'timestamp': (timezone.now() - timedelta(hours=3)).isoformat()
            },
            {
                'id': 3,
                'type': 'backup',
                'description': 'Automated backup completed',
                'user': 'system',
                'timestamp': (timezone.now() - timedelta(hours=6)).isoformat()
            },
            {
                'id': 4,
                'type': 'user',
                'description': 'New user registered: john@example.com',
                'user': 'system',
                'timestamp': (timezone.now() - timedelta(hours=12)).isoformat()
            }
        ]
        return Response({'activities': activities})


class DomainExpiryWidgetView(APIView):
    
    authentication_classes = [CookieOAuth2Authentication]
    
    def get(self, request):

        domains = [
            {
                'domain': 'example.com',
                'expiry_date': (timezone.now() + timedelta(days=45)).isoformat(),
                'days_remaining': 45,
                'status': 'ok',
                'registrar': 'GoDaddy'
            },
            {
                'domain': 'mysite.net',
                'expiry_date': (timezone.now() + timedelta(days=7)).isoformat(),
                'days_remaining': 7,
                'status': 'warning',
                'registrar': 'Namecheap'
            },
            {
                'domain': 'oldsite.org',
                'expiry_date': (timezone.now() + timedelta(days=365)).isoformat(),
                'days_remaining': 365,
                'status': 'ok',
                'registrar': 'Google Domains'
            }
        ]
        return Response({'domains': domains})


class NodeWidgetProxyView(APIView):
    
    authentication_classes = [CookieOAuth2Authentication]
    
    def get(self, request, node_id, widget_type):
        from services.models import Node
        import subprocess
        import json
        
        try:
            node = Node.objects.get(id=node_id, owner=request.user)
        except Node.DoesNotExist:
            return Response(
                {'error': 'Node not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )

        if node.status != 'online':
            return Response(
                {'error': f'Node is {node.status}', 'node_status': node.status},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        try:

            cmd = [
                'ssh',
                '-i', node.auth_key,
                '-p', str(node.port),
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'ConnectTimeout=10',
                f'{node.username}@{node.ip_address}',
                'python3', '/usr/local/bin/node_agent.py', 'collect_metrics'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return Response(
                    {'error': 'Failed to collect node data', 'details': result.stderr},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            metrics = json.loads(result.stdout)

            widget_data = self._transform_metrics_for_widget(widget_type, metrics)
            return Response(widget_data)
            
        except subprocess.TimeoutExpired:
            return Response(
                {'error': 'Connection timeout'},
                status=status.HTTP_504_GATEWAY_TIMEOUT
            )
        except json.JSONDecodeError:
            return Response(
                {'error': 'Invalid response from node'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _transform_metrics_for_widget(self, widget_type, metrics):
        
        
        if widget_type == 'alerts':

            alerts = []
            system_info = metrics.get('system_info', {})

            cpu_percent = metrics.get('cpu', {}).get('percent', 0)
            if cpu_percent > 80:
                alerts.append({
                    'type': 'critical' if cpu_percent > 90 else 'warning',
                    'message': f'High CPU usage: {cpu_percent:.1f}%',
                    'timestamp': timezone.now().isoformat()
                })

            memory = metrics.get('memory', {})
            memory_percent = memory.get('percent', 0)
            if memory_percent > 80:
                alerts.append({
                    'type': 'critical' if memory_percent > 90 else 'warning',
                    'message': f'High memory usage: {memory_percent:.1f}%',
                    'timestamp': timezone.now().isoformat()
                })

            for disk in metrics.get('disk', []):
                percent = disk.get('percent', 0)
                if percent > 85:
                    alerts.append({
                        'type': 'critical' if percent > 95 else 'warning',
                        'message': f'High disk usage on {disk.get("mountpoint", "disk")}: {percent:.1f}%',
                        'timestamp': timezone.now().isoformat()
                    })
            
            return {'alerts': alerts}
        
        elif widget_type == 'performance':
            return {
                'cpu_usage': metrics.get('cpu', {}).get('percent', 0),
                'memory_usage': metrics.get('memory', {}).get('percent', 0),
                'disk_usage': max([d.get('percent', 0) for d in metrics.get('disk', [])], default=0) if metrics.get('disk') else 0,
                'uptime': metrics.get('system_info', {}).get('boot_time', '')
            }
        
        elif widget_type == 'uptime':
            boot_time = metrics.get('system_info', {}).get('boot_time', '')
            return {
                'uptime': boot_time,
                'status': 'online'
            }
        
        else:

            return metrics
