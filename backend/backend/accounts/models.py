from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='accounts_user_set',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='accounts_user_set_permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions'
    )
    email = models.EmailField(unique=True)
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Optional. Used for 2FA if enabled."
    )
    role = models.CharField(max_length=50, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    is_verified_number = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email or self.username


class WidgetLayout(models.Model):
    """Store user's dashboard widget layout"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='widget_layout')
    layout = models.JSONField(
        default=list,
        help_text="JSON array of widget layout configuration"
    )
    available_widgets = models.JSONField(
        default=list,
        help_text="JSON array of available widgets in library"
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email}'s Widget Layout"

    class Meta:
        verbose_name = "Widget Layout"
        verbose_name_plural = "Widget Layouts"
