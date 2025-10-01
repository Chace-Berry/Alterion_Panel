from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model

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
