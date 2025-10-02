
from django.db import models

from django.conf import settings

class Device(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    device_cookie = models.CharField(max_length=255, unique=True)
    ip = models.GenericIPAddressField()
    user_agent = models.TextField()
    last_login = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} - {self.device_cookie}"

class Server(models.Model):
    name = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField()
    status = models.CharField(max_length=20, default='offline')
    last_seen = models.DateTimeField(null=True, blank=True)

class Metric(models.Model):
    server = models.ForeignKey(Server, on_delete=models.CASCADE)
    metric_type = models.CharField(max_length=50)
    value = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

class Alert(models.Model):
    server = models.ForeignKey(Server, on_delete=models.CASCADE)
    message = models.CharField(max_length=255)
    level = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_alerts')
    ignored = models.BooleanField(default=False)
    ignored_at = models.DateTimeField(null=True, blank=True)
    ignored_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='ignored_alerts')

class ActivityLog(models.Model):
    LOG_TYPES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('database', 'Database'),
        ('security', 'Security'),
        ('deployment', 'Deployment'),
        ('alert_resolved', 'Alert Resolved'),
        ('alert_ignored', 'Alert Ignored'),
        ('alert_created', 'Alert Created'),
        ('system', 'System'),
        ('file', 'File'),
        ('config', 'Configuration'),
        ('backup', 'Backup'),
        ('service', 'Service'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    server = models.ForeignKey(Server, on_delete=models.CASCADE, null=True, blank=True)
    log_type = models.CharField(max_length=20, choices=LOG_TYPES)
    message = models.TextField()
    details = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['log_type', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.log_type}: {self.message} ({self.timestamp})"


class UptimeMonitor(models.Model):
    
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name='uptime_monitors')
    start_time = models.DateTimeField(auto_now_add=True)
    last_check = models.DateTimeField(auto_now=True)
    is_up = models.BooleanField(default=True)
    response_time_ms = models.IntegerField(null=True, blank=True)
    check_interval = models.IntegerField(default=300)  # seconds
    
    def __str__(self):
        return f"{self.server.name} - {'UP' if self.is_up else 'DOWN'}"


class UptimeIncident(models.Model):
    
    INCIDENT_TYPES = [
        ('downtime', 'Downtime'),
        ('degraded', 'Performance Degraded'),
        ('maintenance', 'Planned Maintenance'),
    ]
    
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name='uptime_incidents')
    incident_type = models.CharField(max_length=20, choices=INCIDENT_TYPES, default='downtime')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-start_time']
    
    def save(self, *args, **kwargs):
        if self.end_time and self.start_time:
            self.duration_seconds = int((self.end_time - self.start_time).total_seconds())
        super().save(*args, **kwargs)
    
    def __str__(self):
        status = "Ongoing" if not self.end_time else f"{self.duration_seconds}s"
        return f"{self.server.name} - {self.incident_type} ({status})"


class UptimeCheck(models.Model):
    
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name='uptime_checks')
    timestamp = models.DateTimeField(auto_now_add=True)
    is_up = models.BooleanField()
    response_time_ms = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['server', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.server.name} - {'UP' if self.is_up else 'DOWN'} ({self.timestamp})"
