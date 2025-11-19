from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import URLValidator
import json

User = get_user_model()


class Project(models.Model):
    """
    Main project model representing a full-stack web application.
    Can be created via no-code builder or imported from existing files.
    """
    BUILD_TYPE_CHOICES = [
        ('nocode', 'No-Code Builder'),
        ('import', 'Import Existing'),
    ]
    
    FRAMEWORK_CHOICES = [
        ('react', 'React'),
        ('vue', 'Vue'),
        ('angular', 'Angular'),
        ('static', 'Static HTML/CSS'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects')
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    build_type = models.CharField(max_length=10, choices=BUILD_TYPE_CHOICES, default='nocode')
    frontend_framework = models.CharField(max_length=20, choices=FRAMEWORK_CHOICES, default='react')
    
    # File paths
    frontend_dist_path = models.CharField(max_length=500, blank=True, help_text="Path to built frontend files")
    frontend_dev_path = models.CharField(max_length=500, blank=True, help_text="Path to source/editable files")
    backend_path = models.CharField(max_length=500, blank=True, help_text="Path to backend folder")
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        unique_together = ['user', 'slug']
    
    def __str__(self):
        return f"{self.name} ({self.build_type})"


class BackendConfig(models.Model):
    """
    Configuration for backend services attached to a project.
    Stores framework detection results, API endpoints, and startup commands.
    """
    FRAMEWORK_CHOICES = [
        ('django', 'Django'),
        ('fastapi', 'FastAPI'),
        ('nodejs', 'Node.js'),
        ('other', 'Other'),
    ]
    
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='backend_config')
    framework = models.CharField(max_length=20, choices=FRAMEWORK_CHOICES)
    detected_apis = models.JSONField(default=list, help_text="List of detected API endpoints")
    detected_models = models.JSONField(default=list, help_text="List of detected data models/schemas")
    
    # Startup configuration
    start_command = models.CharField(max_length=500, help_text="Command to start backend server")
    port = models.IntegerField(default=8000, help_text="Backend server port")
    environment_vars = models.JSONField(default=dict, help_text="Environment variables for backend")
    
    # Process management
    process_id = models.IntegerField(null=True, blank=True, help_text="PID of running backend process")
    is_running = models.BooleanField(default=False)
    last_started = models.DateTimeField(null=True, blank=True)
    last_stopped = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.project.name} - {self.framework}"


class DomainConfig(models.Model):
    """
    Domain and DNS configuration for a project.
    Handles domain verification and NGINX configuration.
    """
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='domain_config')
    domain_name = models.CharField(max_length=255)
    
    # DNS verification
    dns_verified = models.BooleanField(default=False)
    expected_ip = models.GenericIPAddressField(help_text="Server IP that domain should point to")
    actual_ip = models.GenericIPAddressField(null=True, blank=True, help_text="Current A-record IP")
    last_verified = models.DateTimeField(null=True, blank=True)
    
    # SSL configuration
    ssl_enabled = models.BooleanField(default=False)
    ssl_auto = models.BooleanField(default=True, help_text="Use Let's Encrypt for SSL")
    ssl_cert_path = models.CharField(max_length=500, blank=True)
    ssl_key_path = models.CharField(max_length=500, blank=True)
    
    # NGINX configuration
    nginx_config_path = models.CharField(max_length=500, blank=True, help_text="Path to generated NGINX config")
    nginx_enabled = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.domain_name} -> {self.project.name}"


class Deployment(models.Model):
    """
    Tracks deployment history and status for projects.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('validating', 'Validating Files'),
        ('configuring', 'Configuring Services'),
        ('starting_backend', 'Starting Backend'),
        ('deploying_frontend', 'Deploying Frontend'),
        ('applying_nginx', 'Applying NGINX Config'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('rollback', 'Rolled Back'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='deployments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deployments')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    logs = models.TextField(blank=True, help_text="Deployment logs and output")
    
    # Deployment metadata
    frontend_hash = models.CharField(max_length=64, blank=True, help_text="Git hash or checksum of frontend")
    backend_hash = models.CharField(max_length=64, blank=True, help_text="Git hash or checksum of backend")
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.project.name} - {self.status} ({self.started_at.strftime('%Y-%m-%d %H:%M')})"
    
    def add_log(self, message):
        """Helper method to append log messages"""
        timestamp = models.DateTimeField(auto_now_add=True)
        self.logs += f"[{timestamp}] {message}\n"
        self.save(update_fields=['logs'])


class ComponentLibrary(models.Model):
    """
    Reusable components created in the page builder.
    Can be shared across pages and projects.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='components')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Component definition
    component_json = models.JSONField(help_text="JSON representation of component structure")
    preview_image = models.CharField(max_length=500, blank=True, help_text="Path to preview thumbnail")
    
    # Categorization
    category = models.CharField(max_length=100, default='custom')
    tags = models.JSONField(default=list, help_text="Tags for component search")
    
    is_public = models.BooleanField(default=False, help_text="Share with other users")
    usage_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-usage_count', '-created_at']
    
    def __str__(self):
        return self.name


class APIEndpoint(models.Model):
    """
    Represents a backend API endpoint detected from the backend configuration.
    Used for mapping data to frontend components.
    """
    HTTP_METHODS = [
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH'),
        ('DELETE', 'DELETE'),
    ]
    
    backend_config = models.ForeignKey(BackendConfig, on_delete=models.CASCADE, related_name='api_endpoints')
    path = models.CharField(max_length=500, help_text="API endpoint path (e.g., /api/users)")
    method = models.CharField(max_length=10, choices=HTTP_METHODS)
    description = models.TextField(blank=True)
    
    # Schema information
    request_schema = models.JSONField(default=dict, help_text="Expected request body schema")
    response_schema = models.JSONField(default=dict, help_text="Expected response schema")
    
    # Authentication
    requires_auth = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['backend_config', 'path', 'method']
    
    def __str__(self):
        return f"{self.method} {self.path}"


class Animation(models.Model):
    """
    Keyframe animations created in the page builder timeline editor.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='animations')
    name = models.CharField(max_length=255)
    duration = models.FloatField(default=1.0, help_text="Animation duration in seconds")
    
    # Keyframes definition
    keyframes_json = models.JSONField(help_text="Keyframe definitions with CSS properties")
    easing = models.CharField(max_length=100, default='ease', help_text="CSS easing function")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.duration}s)"
