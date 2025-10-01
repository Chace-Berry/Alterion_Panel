
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
