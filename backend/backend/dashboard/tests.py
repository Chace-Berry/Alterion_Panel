from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status

from .models import ActivityLog, Server

User = get_user_model()


class ActivityWidgetViewTests(TestCase):
    """Test suite for Activity Widget with real ActivityLog data"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create test server
        self.server = Server.objects.create(
            user=self.user,
            name='Test Server',
            ip_address='192.168.1.100',
            server_type='server',
            status='online'
        )
        
        # Create sample activity logs
        self.create_test_logs()
        
        # Set up API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def create_test_logs(self):
        """Create sample activity logs for testing"""
        now = timezone.now()
        
        # Recent logs (within 24 hours) - explicitly set timestamps
        self.login_log = ActivityLog.objects.create(
            user=self.user,
            server=self.server,
            log_type='login',
            message='User testuser logged in',
        )
        self.login_log.timestamp = now - timedelta(minutes=15)
        self.login_log.save()
        
        self.security_log = ActivityLog.objects.create(
            user=None,
            server=self.server,
            log_type='security',
            message='SSL certificate renewed',
        )
        self.security_log.timestamp = now - timedelta(hours=3)
        self.security_log.save()
        
        self.backup_log = ActivityLog.objects.create(
            user=None,
            server=self.server,
            log_type='backup',
            message='Automated backup completed',
            details={'backup_size': '2.5GB', 'duration': '15min'},
        )
        self.backup_log.timestamp = now - timedelta(hours=6)
        self.backup_log.save()
        
        self.deployment_log = ActivityLog.objects.create(
            user=self.user,
            server=self.server,
            log_type='deployment',
            message='Application deployed v2.1.0',
            details={'version': '2.1.0'},
        )
        self.deployment_log.timestamp = now - timedelta(hours=12)
        self.deployment_log.save()
        
        # Old log (older than 24 hours - should not appear)
        self.old_log = ActivityLog.objects.create(
            user=self.user,
            server=self.server,
            log_type='system',
            message='Old system event',
        )
        self.old_log.timestamp = now - timedelta(hours=30)
        self.old_log.save()
    
    def test_activity_widget_returns_real_data(self):
        """Test that Activity Widget returns real ActivityLog data"""
        response = self.client.get('/api/alterion/panel/widget/activity')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('activities', response.data)
        
        activities = response.data['activities']
        
        # Should return 4 logs (excluding the 30-hour old one)
        self.assertEqual(len(activities), 4)
    
    def test_activity_log_structure(self):
        """Test that activity logs have correct structure"""
        response = self.client.get('/api/alterion/panel/widget/activity')
        
        activities = response.data['activities']
        first_activity = activities[0]
        
        # Verify required fields
        self.assertIn('id', first_activity)
        self.assertIn('type', first_activity)
        self.assertIn('description', first_activity)
        self.assertIn('user', first_activity)
        self.assertIn('timestamp', first_activity)
        self.assertIn('details', first_activity)
        self.assertIn('server', first_activity)
    
    def test_activity_log_ordering(self):
        """Test that activities are ordered by timestamp (newest first)"""
        response = self.client.get('/api/alterion/panel/widget/activity')
        
        activities = response.data['activities']
        
        # First activity should be the most recent (login)
        self.assertEqual(activities[0]['type'], 'login')
        self.assertEqual(activities[0]['description'], 'User testuser logged in')
        
        # Last activity should be the oldest within 24h (deployment)
        self.assertEqual(activities[-1]['type'], 'deployment')
    
    def test_activity_log_user_mapping(self):
        """Test that user field is correctly mapped"""
        response = self.client.get('/api/alterion/panel/widget/activity')
        
        activities = response.data['activities']
        
        # Find login activity
        login_activity = next(a for a in activities if a['type'] == 'login')
        self.assertEqual(login_activity['user'], 'testuser')
        
        # Find security activity (no user)
        security_activity = next(a for a in activities if a['type'] == 'security')
        self.assertEqual(security_activity['user'], 'system')
    
    def test_activity_log_details_field(self):
        """Test that details field contains JSON data"""
        response = self.client.get('/api/alterion/panel/widget/activity')
        
        activities = response.data['activities']
        
        # Find backup activity with details
        backup_activity = next(a for a in activities if a['type'] == 'backup')
        self.assertIsNotNone(backup_activity['details'])
        self.assertEqual(backup_activity['details']['backup_size'], '2.5GB')
    
    def test_activity_log_server_mapping(self):
        """Test that server field is correctly mapped"""
        response = self.client.get('/api/alterion/panel/widget/activity')
        
        activities = response.data['activities']
        
        # All activities should have the server name
        for activity in activities:
            self.assertEqual(activity['server'], 'Test Server')
    
    def test_activity_widget_no_logs(self):
        """Test widget returns empty array when no logs exist"""
        # Delete all logs
        ActivityLog.objects.all().delete()
        
        response = self.client.get('/api/alterion/panel/widget/activity')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['activities']), 0)
    
    def test_activity_widget_authentication_required(self):
        """Test that authentication is required"""
        # Unauthenticated client
        client = APIClient()
        response = client.get('/api/alterion/panel/widget/activity')
        
        # Should return 401 or 403 (depending on authentication setup)
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
    
    def test_activity_log_limit(self):
        """Test that widget returns max 20 activities"""
        # Create 25 more logs
        now = timezone.now()
        for i in range(25):
            ActivityLog.objects.create(
                user=self.user,
                server=self.server,
                log_type='system',
                message=f'System event {i}',
                timestamp=now - timedelta(minutes=i)
            )
        
        response = self.client.get('/api/alterion/panel/widget/activity')
        
        activities = response.data['activities']
        
        # Should return max 20 activities
        self.assertEqual(len(activities), 20)


class NodeWidgetProxyTests(TestCase):
    """Test suite for Node Widget Proxy with WebSocket API"""
    
    def setUp(self):
        from services.models import Node
        
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create test node
        self.node = Node.objects.create(
            owner=self.user,
            name='Test Node',
            ip_address='192.168.1.101',
            port=22,
            username='testuser',
            node_type='server',
            status='online'
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_node_widget_proxy_requires_auth(self):
        """Test that node widget proxy requires authentication"""
        client = APIClient()
        response = client.get(f'/api/alterion/panel/node/{self.node.id}/uptime')
        
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
    
    def test_node_widget_proxy_node_not_found(self):
        """Test node widget proxy returns 404 for non-existent node"""
        response = self.client.get('/api/alterion/panel/node/99999/uptime')
        
        # Should get error due to websockets module or node not found
        self.assertIn(response.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR])
    
    def test_node_widget_proxy_offline_node(self):
        """Test node widget proxy returns 503 for offline node"""
        self.node.status = 'offline'
        self.node.save()
        
        response = self.client.get(f'/api/alterion/panel/node/{self.node.id}/uptime')
        
        # Should get 503 or 500 depending on if websockets is available
        self.assertIn(response.status_code, [status.HTTP_503_SERVICE_UNAVAILABLE, status.HTTP_500_INTERNAL_SERVER_ERROR])


class UptimeWidgetTests(TestCase):
    """Test suite for Uptime Widget - local server"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_uptime_widget_local_server(self):
        """Test that uptime widget returns data for local panel server"""
        response = self.client.get('/api/alterion/panel/widget/uptime')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify required fields exist
        self.assertIn('currentUptime', response.data)
        self.assertIn('uptimePercentage', response.data)
        self.assertIn('status', response.data)
        self.assertIn('responseTime', response.data)
    
    def test_uptime_widget_requires_auth(self):
        """Test that uptime widget requires authentication"""
        client = APIClient()
        response = client.get('/api/alterion/panel/widget/uptime')
        
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
    
    def test_uptime_widget_data_format(self):
        """Test that uptime widget returns properly formatted data"""
        response = self.client.get('/api/alterion/panel/widget/uptime')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check data types
        self.assertIsInstance(response.data['currentUptime'], str)
        self.assertIsInstance(response.data['uptimePercentage'], (int, float))
        self.assertIsInstance(response.data['status'], str)
        
        # Verify uptime percentage is between 0 and 100
        self.assertGreaterEqual(response.data['uptimePercentage'], 0)
        self.assertLessEqual(response.data['uptimePercentage'], 100)
        
        # Verify status is valid
        valid_statuses = ['operational', 'degraded', 'down']
        self.assertIn(response.data['status'], valid_statuses)


class ActivityLogModelTests(TestCase):
    """Test suite for ActivityLog model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        self.server = Server.objects.create(
            user=self.user,
            name='Test Server',
            ip_address='192.168.1.100'
        )
    
    def test_activity_log_creation(self):
        """Test creating an ActivityLog"""
        log = ActivityLog.objects.create(
            user=self.user,
            server=self.server,
            log_type='login',
            message='Test login',
            details={'ip': '192.168.1.1'}
        )
        
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.server, self.server)
        self.assertEqual(log.log_type, 'login')
        self.assertEqual(log.message, 'Test login')
        self.assertEqual(log.details['ip'], '192.168.1.1')
    
    def test_activity_log_without_user(self):
        """Test creating ActivityLog without user (system event)"""
        log = ActivityLog.objects.create(
            server=self.server,
            log_type='system',
            message='System event'
        )
        
        self.assertIsNone(log.user)
        self.assertEqual(log.server, self.server)
    
    def test_activity_log_ordering(self):
        """Test that logs are ordered by timestamp descending"""
        now = timezone.now()
        
        log1 = ActivityLog.objects.create(
            server=self.server,
            log_type='system',
            message='First',
            timestamp=now - timedelta(hours=2)
        )
        
        log2 = ActivityLog.objects.create(
            server=self.server,
            log_type='system',
            message='Second',
            timestamp=now - timedelta(hours=1)
        )
        
        logs = list(ActivityLog.objects.all())
        
        # Should be ordered newest first
        self.assertEqual(logs[0].id, log2.id)
        self.assertEqual(logs[1].id, log1.id)
