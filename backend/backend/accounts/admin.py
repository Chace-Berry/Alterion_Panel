from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, WidgetLayout, DeviceLogin


class CustomUserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_verified')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'is_verified')


@admin.register(DeviceLogin)
class DeviceLoginAdmin(admin.ModelAdmin):
    list_display = ('user', 'device_name', 'ip_address', 'last_login', 'login_count')
    list_filter = ('last_login', 'device_name')
    search_fields = ('user__username', 'user__email', 'device_id', 'ip_address')
    readonly_fields = ('device_id', 'first_seen', 'last_login', 'login_count')
    ordering = ('-last_login',)
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Device Information', {
            'fields': ('device_id', 'device_name', 'ip_address', 'user_agent')
        }),
        ('Login Statistics', {
            'fields': ('first_seen', 'last_login', 'login_count')
        }),
    )


@admin.register(WidgetLayout)
class WidgetLayoutAdmin(admin.ModelAdmin):
    list_display = ('user', 'updated_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')


admin.site.register(User, CustomUserAdmin)
