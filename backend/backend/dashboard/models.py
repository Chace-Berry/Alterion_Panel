
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
    SERVER_TYPE_CHOICES = [
        ('server', 'Server'),
        ('webserver', 'Web Server'),
        ('database', 'Database Server'),
        ('cache', 'Cache Server'),
        ('storage', 'Storage Server'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='servers', null=True, blank=True)
    name = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField()
    server_type = models.CharField(max_length=20, choices=SERVER_TYPE_CHOICES, default='server')
    status = models.CharField(max_length=20, default='offline')
    last_seen = models.DateTimeField(null=True, blank=True)
    hostname = models.CharField(max_length=255, blank=True)  # For server identification
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    
    # Web server specific fields
    web_stats_enabled = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.name} ({self.ip_address}) - {self.get_server_type_display()}"
    
    @property
    def is_web_server(self):
        """Check if this server is a web server"""
        return self.server_type == 'webserver'
    
    @property
    def identifier(self):
        """Generate a unique identifier for the server"""
        # Format: server{id}-{ip_without_dots}
        # Example: server1-192168001 for 192.168.0.1
        ip_clean = self.ip_address.replace('.', '').replace(':', '')
        return f"server{self.id}-{ip_clean}"

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


class Domain(models.Model):
    """Domain model for tracking domain expiry dates and web hosting"""
    
    STATUS_CHOICES = [
        ('pending_verification', 'Pending Verification'),
        ('active', 'Active'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('expired', 'Expired'),
        ('unknown', 'Unknown'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='domains')
    domain_name = models.CharField(max_length=255, unique=True)
    registrar = models.CharField(max_length=100, blank=True)
    
    # Server linking - when a domain is linked to a server, that server becomes a web server
    linked_server = models.ForeignKey(
        Server, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='domains',
        help_text='Server hosting this domain (automatically converts server to webserver type)'
    )
    
    # Domain expiry tracking
    expiry_date = models.DateTimeField(null=True, blank=True)
    last_checked = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unknown')
    is_active = models.BooleanField(default=True)
    check_interval_hours = models.IntegerField(default=24)  # Check every 24 hours by default
    notification_days = models.IntegerField(default=30)  # Notify 30 days before expiry
    
    # Domain verification
    is_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=255, blank=True, help_text='TXT record verification token')
    verification_status = models.CharField(max_length=50, blank=True, help_text='Current verification status')
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Web hosting configuration
    web_root = models.CharField(max_length=500, blank=True, help_text='Web root directory on the server')
    ssl_enabled = models.BooleanField(default=False)
    ssl_expiry = models.DateTimeField(null=True, blank=True)
    
    # DNS records for reference
    dns_records = models.JSONField(null=True, blank=True, help_text='Store DNS records for reference')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['expiry_date']
        indexes = [
            models.Index(fields=['expiry_date']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['status']),
            models.Index(fields=['linked_server']),
        ]
    
    def __str__(self):
        server_info = f" → {self.linked_server.name}" if self.linked_server else ""
        return f"{self.domain_name}{server_info}"
    
    def save(self, *args, **kwargs):
        """Override save to automatically convert linked server to webserver type"""
        if self.linked_server and self.linked_server.server_type != 'webserver':
            self.linked_server.server_type = 'webserver'
            self.linked_server.web_stats_enabled = True
            self.linked_server.save()
        
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['expiry_date']
        indexes = [
            models.Index(fields=['expiry_date']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.domain_name} ({'expires' if self.expiry_date else 'unknown expiry'})"
    
    @property
    def days_until_expiry(self):
        """Calculate days until domain expires"""
        if not self.expiry_date:
            return None
        
        from django.utils import timezone
        delta = self.expiry_date - timezone.now()
        return delta.days if delta.days >= 0 else 0
    
    def update_status(self):
        """Update domain status based on days until expiry - only if verified"""
        # If not verified, status should be pending verification
        if not self.is_verified:
            self.status = 'pending_verification'
            self.save()
            return
        
        # Only check expiry status if domain is verified
        days = self.days_until_expiry
        
        if days is None:
            self.status = 'unknown'
        elif days <= 0:
            self.status = 'expired'
        elif days <= 7:
            self.status = 'critical'
        elif days <= 30:
            self.status = 'warning'
        else:
            self.status = 'active'
        
        self.save()


class DomainCheck(models.Model):
    """Records of domain expiry checks"""
    
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name='checks')
    timestamp = models.DateTimeField(auto_now_add=True)
    expiry_date_found = models.DateTimeField(null=True, blank=True)
    registrar_found = models.CharField(max_length=100, blank=True)
    check_successful = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    whois_data = models.JSONField(null=True, blank=True)  # Store raw WHOIS data
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['domain', '-timestamp']),
            models.Index(fields=['-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.domain.domain_name} check at {self.timestamp}"
