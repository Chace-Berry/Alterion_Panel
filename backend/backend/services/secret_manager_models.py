from django.db import models
from accounts.models import User
from django.utils import timezone
import uuid
from oauth2_provider.models import Application


class SecretProject(models.Model):
    """A project to organize secrets (similar to Infisical)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='secret_projects')
    # Link to OAuth Toolkit Application
    application = models.OneToOneField('oauth2_provider.Application', on_delete=models.SET_NULL, null=True, blank=True, related_name='secret_project')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'secret_projects'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


class SecretEnvironment(models.Model):
    """Environment within a project (dev, staging, prod, etc.)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(SecretProject, on_delete=models.CASCADE, related_name='environments')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    position = models.IntegerField(default=0)
    is_hidden = models.BooleanField(default=False, help_text="Hide from UI (for system-managed secrets)")
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'secret_environments'
        ordering = ['position', 'name']
        unique_together = ['project', 'slug']
    
    def __str__(self):
        return f"{self.project.name} - {self.name}"


class Secret(models.Model):
    """Individual secret key-value pair"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    environment = models.ForeignKey(SecretEnvironment, on_delete=models.CASCADE, related_name='secrets')
    key = models.CharField(max_length=255)
    value = models.TextField()  # Encrypted value
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_secrets')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_secrets')
    
    class Meta:
        db_table = 'secrets'
        ordering = ['key']
        unique_together = ['environment', 'key']
    
    def __str__(self):
        return f"{self.environment.project.name}/{self.environment.name}/{self.key}"


class SecretVersion(models.Model):
    """Version history for secrets"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    secret = models.ForeignKey(Secret, on_delete=models.CASCADE, related_name='versions')
    value = models.TextField()  # Encrypted value
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(default=timezone.now)
    change_type = models.CharField(max_length=20, choices=[
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('deleted', 'Deleted'),
    ])
    
    class Meta:
        db_table = 'secret_versions'
        ordering = ['-changed_at']
    
    def __str__(self):
        return f"{self.secret.key} - {self.changed_at}"
