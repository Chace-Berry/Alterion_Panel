"""
Node Management Models
Stores remote server/node connections and their metrics
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import json

User = get_user_model()


class Node(models.Model):
    """Remote server/node connection"""
    
    STATUS_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('error', 'Error'),
        ('pending', 'Pending'),
    ]
    
    TYPE_CHOICES = [
        ('server', 'Server'),
        ('website', 'Website'),
        ('database', 'Database'),
        ('application', 'Application'),
    ]
    
    # Basic Info
    id = models.CharField(max_length=64, primary_key=True)  # Use serverid as string PK
    name = models.CharField(max_length=255)
    hostname = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField()
    port = models.IntegerField(default=22)
    node_type = models.CharField(max_length=50, choices=TYPE_CHOICES, default='server')
    
    # Authentication
    auth_key = models.TextField(help_text="SSH key or API key for authentication")
    username = models.CharField(max_length=100, default='root')
    
    # SSH/SFTP Authentication (for file operations)
    ssh_port = models.IntegerField(default=22, help_text="SSH port for SFTP file operations")
    ssh_key_id = models.CharField(max_length=255, null=True, blank=True, 
                                  help_text="Key ID for retrieving SSH password from secret manager")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    last_seen = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(null=True, blank=True)
    
    # System Info
    platform = models.CharField(max_length=50, null=True, blank=True)
    platform_version = models.CharField(max_length=100, null=True, blank=True)
    cpu_cores = models.IntegerField(null=True, blank=True)
    total_memory = models.BigIntegerField(null=True, blank=True, help_text="Total RAM in bytes")
    
    # Metadata
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='nodes')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tags = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-last_seen', 'name']
        unique_together = [['hostname', 'ip_address', 'owner']]
    
    def __str__(self):
        return f"{self.name} ({self.ip_address})"
    
    def update_status(self, is_online, error_message=None):
        """Update node online status"""
        if is_online:
            self.status = 'online'
            self.last_seen = timezone.now()
            self.last_error = None
        else:
            self.status = 'offline' if not error_message else 'error'
            self.last_error = error_message
        self.save()
    
    def update_system_info(self, system_info):
        """Update system information from metrics"""
        self.platform = system_info.get('platform')
        self.platform_version = system_info.get('platform_version')
        self.cpu_cores = system_info.get('count')
        self.save()


class NodeMetrics(models.Model):
    """Historical metrics data for nodes"""
    
    node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name='metrics')
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # CPU
    cpu_usage = models.FloatField()
    cpu_load_avg = models.JSONField(null=True, blank=True)
    
    # Memory
    memory_used = models.BigIntegerField()
    memory_total = models.BigIntegerField()
    memory_percent = models.FloatField()
    swap_used = models.BigIntegerField(null=True, blank=True)
    swap_percent = models.FloatField(null=True, blank=True)
    
    # Disk
    disk_usage = models.JSONField(default=dict)
    
    # Network
    network_bytes_sent = models.BigIntegerField(null=True, blank=True)
    network_bytes_recv = models.BigIntegerField(null=True, blank=True)
    network_connections = models.IntegerField(null=True, blank=True)
    
    # Processes
    process_count = models.IntegerField(null=True, blank=True)
    
    # Full metrics JSON
    full_metrics = models.JSONField(default=dict)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['node', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.node.name} metrics at {self.timestamp}"


class NodeAlert(models.Model):
    """Alerts generated from node metrics"""
    
    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('warning', 'Warning'),
        ('info', 'Info'),
    ]
    
    node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name='alerts')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    category = models.CharField(max_length=100)
    message = models.TextField()
    details = models.JSONField(default=dict)
    
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['node', 'resolved', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.severity.upper()}: {self.message}"


class NodeService(models.Model):
    """Services detected on nodes (Nginx, MySQL, Docker, etc.)"""
    
    node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name='services')
    service_type = models.CharField(max_length=100)  # nginx, mysql, docker, etc.
    service_name = models.CharField(max_length=255)
    is_running = models.BooleanField(default=False)
    version = models.CharField(max_length=100, null=True, blank=True)
    config_path = models.CharField(max_length=500, null=True, blank=True)
    
    last_checked = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['node', 'service_type']]
    
    def __str__(self):
        return f"{self.service_type} on {self.node.name}"
