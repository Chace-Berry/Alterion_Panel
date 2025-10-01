"""
Widget Data API Views
Provides endpoints for fetching widget-specific data
"""
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
    """API endpoint for Alerts widget data - comprehensive dynamic alert system"""
    authentication_classes = [CookieOAuth2Authentication]
    
    def get(self, request):
        # Use the comprehensive alert system
        alert_system = AlertSystem()
        alerts = alert_system.get_all_alerts()
        
        return Response({'alerts': alerts})


class TrafficWidgetView(APIView):
    """API endpoint for Traffic widget data"""
    authentication_classes = [CookieOAuth2Authentication]
    
    def get(self, request):
        # Mock traffic data - replace with actual analytics
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
    """API endpoint for Uptime Monitor widget data"""
    authentication_classes = [CookieOAuth2Authentication]
    
    def get(self, request):
        # Mock uptime data - replace with actual monitoring
        uptime_data = {
            'uptime_percentage': 99.98,
            'current_status': 'online',
            'last_downtime': (timezone.now() - timedelta(days=7)).isoformat(),
            'response_time': random.randint(50, 200),  # ms
            'incidents_30d': random.randint(0, 3)
        }
        return Response(uptime_data)


class PerformanceWidgetView(APIView):
    """API endpoint for Performance Metrics widget data - real system metrics"""
    authentication_classes = [CookieOAuth2Authentication]
    
    def get(self, request):
        # Get real system performance data
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net_io = psutil.net_io_counters()
        
        # Calculate network speed (bytes per second to Mbps)
        # Note: This is cumulative, you'd need to track deltas for real-time speed
        network_in_mbps = round((net_io.bytes_recv / 1024 / 1024), 2)
        network_out_mbps = round((net_io.bytes_sent / 1024 / 1024), 2)
        
        # Get load average (Unix-like systems only)
        try:
            load_avg = psutil.getloadavg()[0]  # 1-minute load average
        except (AttributeError, OSError):
            # Load average not available on Windows
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
    """API endpoint for Quick Actions widget data"""
    authentication_classes = [CookieOAuth2Authentication]
    
    def get(self, request):
        # Available quick actions
        actions = [
            {'id': 'restart_server', 'label': 'Restart Server', 'icon': 'power'},
            {'id': 'clear_cache', 'label': 'Clear Cache', 'icon': 'trash'},
            {'id': 'backup_now', 'label': 'Backup Now', 'icon': 'database'},
            {'id': 'update_ssl', 'label': 'Update SSL', 'icon': 'shield'},
        ]
        return Response({'actions': actions})
    
    def post(self, request):
        # Execute quick action
        action_id = request.data.get('action_id')
        # TODO: Implement actual action execution
        return Response({
            'success': True,
            'message': f'Action {action_id} executed successfully'
        })


class ActivityWidgetView(APIView):
    """API endpoint for Recent Activity widget data"""
    authentication_classes = [CookieOAuth2Authentication]
    
    def get(self, request):
        # Mock activity data - replace with actual activity logs
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
    """API endpoint for Domain Expiry widget data"""
    authentication_classes = [CookieOAuth2Authentication]
    
    def get(self, request):
        # Mock domain data - replace with actual domain monitoring
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
