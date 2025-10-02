"""
Django signals to automatically log important events
"""
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from .models import ActivityLog, Alert, Server
from django.utils import timezone


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Log when a user logs in"""
    try:
        from .logging_utils import log_login
        log_login(user, request)
    except Exception as e:
        print(f"Error logging user login: {e}")


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Log when a user logs out"""
    try:
        from .logging_utils import log_logout
        log_logout(user, request)
    except Exception as e:
        print(f"Error logging user logout: {e}")


@receiver(post_save, sender=Alert)
def log_alert_changes(sender, instance, created, **kwargs):
    """
    Signal handler for alert changes.
    Note: Logging is handled in views.py to avoid duplicates and ensure proper severity tracking.
    This signal is kept for potential future use.
    """
    pass
