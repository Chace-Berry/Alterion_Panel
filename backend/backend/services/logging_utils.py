
from django.utils import timezone
from dashboard.models import ActivityLog, Server
import socket

def get_server_id():
    
    hostname = socket.gethostname()
    try:
        ip_address = socket.gethostbyname(hostname)
    except:
        ip_address = '127.0.0.1'
    
    server, _ = Server.objects.get_or_create(
        ip_address=ip_address,
        defaults={'name': hostname, 'status': 'online', 'last_seen': timezone.now()}
    )
    server.last_seen = timezone.now()
    server.status = 'online'
    server.save()
    return server

def log_activity(log_type, message, user=None, details=None, request=None, server=None):
    
    ip_address = None
    user_agent = None
    
    if request:
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if not user and hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user
    
    if not server:
        server = get_server_id()
    
    ActivityLog.objects.create(
        user=user,
        server=server,
        log_type=log_type,
        message=message,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent
    )

def get_client_ip(request):
    
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def log_login(user, request):
    
    log_activity('login', f'User {user.username} logged in', user=user, request=request)

def log_logout(user, request):
    
    log_activity('logout', f'User {user.username} logged out', user=user, request=request)

def log_database_operation(operation, details=None, user=None):
    
    log_activity('database', operation, user=user, details=details)

def log_security_event(event, details=None, user=None, request=None):
    
    log_activity('security', event, user=user, details=details, request=request)

def log_deployment(app_name, version, user=None, details=None):
    
    message = f'{app_name} deployed v{version}' if version else f'{app_name} deployed'
    log_activity('deployment', message, user=user, details=details)

def log_alert_resolved(alert_message, user=None, level=None):
    
    details = {'level': level} if level else None
    log_activity('alert_resolved', f'Alert resolved: {alert_message}', user=user, details=details)

def log_alert_ignored(alert_message, user=None, level=None):
    
    details = {'level': level} if level else None
    log_activity('alert_ignored', f'Alert ignored: {alert_message}', user=user, details=details)

def log_alert_unignored(alert_message, user=None, level=None):
    
    details = {'level': level} if level else None
    log_activity('alert_ignored', f'Alert unignored: {alert_message}', user=user, details=details)

def log_alert_created(alert_message, level):
    
    log_activity('alert_created', f'{level.upper()} alert: {alert_message}', details={'level': level})

def log_backup(backup_type, status, details=None):
    
    message = f'{backup_type} backup {status}'
    log_activity('backup', message, details=details)

def log_service_change(service_name, action, details=None):
    
    message = f'Service {service_name} {action}'
    log_activity('service', message, details=details)

def log_config_change(config_type, change_description, user=None, details=None):
    
    message = f'{config_type} configuration: {change_description}'
    log_activity('config', message, user=user, details=details)

def log_domain_added(domain_name, user=None, details=None):
    
    log_activity('domain', f'Domain added: {domain_name}', user=user, details=details)

def log_domain_removed(domain_name, user=None, details=None):
    
    log_activity('domain', f'Domain removed: {domain_name}', user=user, details=details)

def log_domain_updated(domain_name, user=None, details=None):
    
    log_activity('domain', f'Domain updated: {domain_name}', user=user, details=details)

def log_domain_verified(domain_name, verification_method=None, user=None):
    
    details = {'verification_method': verification_method} if verification_method else None
    log_activity('domain', f'Domain verified: {domain_name}', user=user, details=details)

def log_domain_linked(domain_name, server_name, user=None):
    
    details = {'server': server_name}
    log_activity('domain', f'Domain linked to server: {domain_name} → {server_name}', user=user, details=details)

def log_domain_unlinked(domain_name, server_name, user=None):
    
    details = {'server': server_name}
    log_activity('domain', f'Domain unlinked from server: {domain_name} ← {server_name}', user=user, details=details)
