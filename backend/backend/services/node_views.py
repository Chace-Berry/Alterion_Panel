"""
Node Management API Views
Handles remote server connections, metrics collection, and management
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Q
import subprocess
import json
import os

from .node_models import Node, NodeMetrics, NodeAlert, NodeService
from .node_serializers import (
    NodeSerializer, NodeMetricsSerializer, 
    NodeAlertSerializer, NodeServiceSerializer
)


class NodeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing remote nodes/servers
    """
    serializer_class = NodeSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Node.objects.filter(owner=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
    
    @action(detail=True, methods=['post'])
    def collect_metrics(self, request, pk=None):
        """Collect metrics from this node"""
        node = self.get_object()
        
        try:
            # Execute node_agent.py on remote server via SSH
            metrics_data = self._execute_node_command(node, 'collect_metrics')
            
            if 'error' in metrics_data:
                node.update_status(False, metrics_data['error'])
                return Response(
                    {'error': metrics_data['error']},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Update node status
            node.update_status(True)
            
            # Update system info
            if 'system' in metrics_data:
                node.update_system_info(metrics_data['system'])
            
            # Store metrics
            if 'cpu' in metrics_data and 'memory' in metrics_data:
                memory_data = metrics_data['memory']
                
                NodeMetrics.objects.create(
                    node=node,
                    cpu_usage=metrics_data['cpu'].get('usage_percent', 0),
                    cpu_load_avg=metrics_data['cpu'].get('load_avg'),
                    memory_used=memory_data.get('used', 0),
                    memory_total=memory_data.get('total', 0),
                    memory_percent=memory_data.get('percent', 0),
                    swap_used=memory_data.get('swap', {}).get('used'),
                    swap_percent=memory_data.get('swap', {}).get('percent'),
                    disk_usage=metrics_data.get('disk', {}).get('usage', {}),
                    network_bytes_sent=metrics_data.get('network', {}).get('io', {}).get('bytes_sent'),
                    network_bytes_recv=metrics_data.get('network', {}).get('io', {}).get('bytes_recv'),
                    network_connections=metrics_data.get('network', {}).get('connections'),
                    process_count=metrics_data.get('processes', {}).get('count'),
                    full_metrics=metrics_data
                )
            
            # Update services
            if 'services' in metrics_data:
                for service_type, service_data in metrics_data['services'].items():
                    NodeService.objects.update_or_create(
                        node=node,
                        service_type=service_type,
                        defaults={
                            'service_name': service_data.get('name', service_type),
                            'is_running': service_data.get('running', False),
                        }
                    )
            
            return Response(metrics_data)
            
        except Exception as e:
            node.update_status(False, str(e))
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def latest_metrics(self, request, pk=None):
        """Get latest metrics for this node"""
        node = self.get_object()
        latest = node.metrics.first()
        
        if not latest:
            return Response({'error': 'No metrics available'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = NodeMetricsSerializer(latest)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def metrics_history(self, request, pk=None):
        """Get metrics history for this node"""
        node = self.get_object()
        hours = int(request.query_params.get('hours', 24))
        
        since = timezone.now() - timezone.timedelta(hours=hours)
        metrics = node.metrics.filter(timestamp__gte=since)
        
        serializer = NodeMetricsSerializer(metrics, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def alerts(self, request, pk=None):
        """Get alerts for this node"""
        node = self.get_object()
        show_resolved = request.query_params.get('resolved', 'false').lower() == 'true'
        
        if show_resolved:
            alerts = node.alerts.all()
        else:
            alerts = node.alerts.filter(resolved=False)
        
        serializer = NodeAlertSerializer(alerts, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def services(self, request, pk=None):
        """Get services running on this node"""
        node = self.get_object()
        services = node.services.all()
        
        serializer = NodeServiceSerializer(services, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def list_files(self, request, pk=None):
        """List files on the node"""
        node = self.get_object()
        path = request.data.get('path', '/')
        
        try:
            result = self._execute_node_command(node, 'list_files', [path])
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def read_file(self, request, pk=None):
        """Read a file from the node"""
        node = self.get_object()
        path = request.data.get('path')
        max_lines = request.data.get('max_lines')
        
        if not path:
            return Response({'error': 'path is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            args = ['read_file', path]
            if max_lines:
                args.extend(['--max-lines', str(max_lines)])
            
            result = self._execute_node_command(node, args[0], args[1:])
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def nginx_config(self, request, pk=None):
        """Get Nginx configuration info"""
        node = self.get_object()
        
        try:
            result = self._execute_node_command(node, 'check_nginx')
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def firewall_status(self, request, pk=None):
        """Get firewall status"""
        node = self.get_object()
        
        try:
            result = self._execute_node_command(node, 'check_firewall')
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """Test connection to the node"""
        node = self.get_object()
        
        try:
            result = self._execute_node_command(node, 'system_info')
            node.update_status(True)
            return Response({'status': 'connected', 'system': result})
        except Exception as e:
            node.update_status(False, str(e))
            return Response(
                {'status': 'failed', 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _execute_node_command(self, node, command, args=None):
        """Execute a command on the remote node via SSH"""
        # Path to node_agent.py
        agent_path = os.path.join(os.path.dirname(__file__), '..', '..', 'node_agent.py')
        
        # Build SSH command
        ssh_cmd = [
            'ssh',
            '-i', node.auth_key,  # SSH key path
            '-o', 'StrictHostKeyChecking=no',
            '-p', str(node.port),
            f'{node.username}@{node.ip_address}',
            f'python3 {agent_path} {command}'
        ]
        
        if args:
            ssh_cmd[-1] += ' ' + ' '.join(args)
        
        # Execute command
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            raise Exception(f"Command failed: {result.stderr}")
        
        # Parse JSON output
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {'output': result.stdout}


class NodeAlertViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for node alerts
    """
    serializer_class = NodeAlertSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return NodeAlert.objects.filter(node__owner=self.request.user)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve an alert"""
        alert = self.get_object()
        alert.resolved = True
        alert.resolved_at = timezone.now()
        alert.resolved_by = request.user
        alert.save()
        
        serializer = self.get_serializer(alert)
        return Response(serializer.data)
