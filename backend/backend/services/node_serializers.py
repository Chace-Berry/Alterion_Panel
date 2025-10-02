"""
Node Management Serializers
"""
from rest_framework import serializers
from .node_models import Node, NodeMetrics, NodeAlert, NodeService


class NodeSerializer(serializers.ModelSerializer):
    """Serializer for Node model"""
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_node_type_display', read_only=True)
    uptime = serializers.SerializerMethodField()
    
    class Meta:
        model = Node
        fields = [
            'id', 'name', 'hostname', 'ip_address', 'port', 'node_type', 'type_display',
            'username', 'status', 'status_display', 'last_seen', 'last_error',
            'platform', 'platform_version', 'cpu_cores', 'total_memory',
            'tags', 'notes', 'created_at', 'updated_at', 'uptime'
        ]
        read_only_fields = [
            'status', 'last_seen', 'last_error', 'platform', 
            'platform_version', 'cpu_cores', 'total_memory'
        ]
        extra_kwargs = {
            'auth_key': {'write_only': True}
        }
    
    def get_uptime(self, obj):
        """Calculate uptime if node is online"""
        if obj.status == 'online' and obj.last_seen:
            from django.utils import timezone
            delta = timezone.now() - obj.last_seen
            return delta.total_seconds()
        return None


class NodeMetricsSerializer(serializers.ModelSerializer):
    """Serializer for NodeMetrics model"""
    
    node_name = serializers.CharField(source='node.name', read_only=True)
    
    class Meta:
        model = NodeMetrics
        fields = [
            'id', 'node', 'node_name', 'timestamp',
            'cpu_usage', 'cpu_load_avg',
            'memory_used', 'memory_total', 'memory_percent',
            'swap_used', 'swap_percent',
            'disk_usage',
            'network_bytes_sent', 'network_bytes_recv', 'network_connections',
            'process_count',
            'full_metrics'
        ]
        read_only_fields = ['timestamp']


class NodeAlertSerializer(serializers.ModelSerializer):
    """Serializer for NodeAlert model"""
    
    node_name = serializers.CharField(source='node.name', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    resolved_by_username = serializers.CharField(source='resolved_by.username', read_only=True)
    
    class Meta:
        model = NodeAlert
        fields = [
            'id', 'node', 'node_name', 'severity', 'severity_display',
            'category', 'message', 'details',
            'resolved', 'resolved_at', 'resolved_by', 'resolved_by_username',
            'created_at'
        ]
        read_only_fields = ['created_at', 'resolved_at', 'resolved_by']


class NodeServiceSerializer(serializers.ModelSerializer):
    """Serializer for NodeService model"""
    
    node_name = serializers.CharField(source='node.name', read_only=True)
    
    class Meta:
        model = NodeService
        fields = [
            'id', 'node', 'node_name', 'service_type', 'service_name',
            'is_running', 'version', 'config_path', 'last_checked'
        ]
        read_only_fields = ['last_checked']


class NodeListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing nodes (for dropdown)"""
    
    class Meta:
        model = Node
        fields = ['id', 'name', 'hostname', 'ip_address', 'status', 'node_type', 'last_seen']
