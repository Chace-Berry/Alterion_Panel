from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model

# Import Node models
from .node_models import Node, NodeMetrics, NodeAlert, NodeService

# Import Server model from dashboard for domain linking
from dashboard.models import Server

class FTPAccount(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=255)
    home_directory = models.CharField(max_length=500)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"FTP: {self.username}"

class Database(models.Model):
    DATABASE_TYPES = [
        ('mysql', 'MySQL'),
        ('postgresql', 'PostgreSQL'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, unique=True)
    db_type = models.CharField(max_length=20, choices=DATABASE_TYPES, default='mysql')
    db_user = models.CharField(max_length=100)
    db_password = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"DB: {self.name}"

class EmailAccount(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    quota_mb = models.IntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Email: {self.email}"

class ServiceStatus(models.Model):
    SERVICES = [
        ('ftp', 'FTP Server'),
        ('email', 'Email Server'),
        ('database', 'Database Server'),
        ('web', 'Web Server'),
    ]

    service_name = models.CharField(max_length=50, choices=SERVICES, unique=True)
    is_running = models.BooleanField(default=False)
    port = models.IntegerField(null=True, blank=True)
    last_checked = models.DateTimeField(auto_now=True)
    status_message = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.service_name}: {'Running' if self.is_running else 'Stopped'}"


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
