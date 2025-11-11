from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from accounts.models import User, DeviceLogin
import hashlib
import json


def get_device_fingerprint(request):
    """Generate a unique device fingerprint based on request metadata"""
    # Combine various request attributes to create a unique device ID
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
    accept_encoding = request.META.get('HTTP_ACCEPT_ENCODING', '')
    
    # Create a fingerprint hash
    fingerprint_string = f"{user_agent}|{accept_language}|{accept_encoding}"
    device_id = hashlib.sha256(fingerprint_string.encode()).hexdigest()
    
    return device_id


def get_device_name(request):
    """Extract a human-readable device name from user agent"""
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    # Simple parsing for common browsers and OS
    if 'Windows' in user_agent:
        os = 'Windows'
    elif 'Macintosh' in user_agent or 'Mac OS' in user_agent:
        os = 'macOS'
    elif 'Linux' in user_agent:
        os = 'Linux'
    elif 'Android' in user_agent:
        os = 'Android'
    elif 'iPhone' in user_agent or 'iPad' in user_agent:
        os = 'iOS'
    else:
        os = 'Unknown OS'
    
    if 'Chrome' in user_agent and 'Edg' not in user_agent:
        browser = 'Chrome'
    elif 'Firefox' in user_agent:
        browser = 'Firefox'
    elif 'Safari' in user_agent and 'Chrome' not in user_agent:
        browser = 'Safari'
    elif 'Edg' in user_agent:
        browser = 'Edge'
    else:
        browser = 'Unknown Browser'
    
    return f"{browser} on {os}"


def get_client_ip(request):
    """Get the client's IP address from the request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@api_view(['GET'])
@permission_classes([AllowAny])
def get_recent_device_users(request):
    """
    Get list of users who have logged in from this device in the last 10 days.
    Returns users sorted by most recent login first.
    """
    device_id = get_device_fingerprint(request)
    ten_days_ago = timezone.now() - timedelta(days=10)
    
    # Get all device logins for this device in the last 10 days
    recent_logins = DeviceLogin.objects.filter(
        device_id=device_id,
        last_login__gte=ten_days_ago
    ).select_related('user').order_by('-last_login')
    
    # Build user list with login info
    users_data = []
    for login in recent_logins:
        user = login.user
        users_data.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'last_login': login.last_login.isoformat(),
            'device_name': login.device_name,
            'login_count': login.login_count
        })
    
    return Response({
        'device_id': device_id,
        'users': users_data,
        'count': len(users_data)
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def record_device_login(request):
    """
    Record or update a device login after successful authentication.
    Should be called after successful OAuth token generation.
    """
    user_id = request.data.get('user_id')
    
    if not user_id:
        return Response({'error': 'user_id is required'}, status=400)
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)
    
    device_id = get_device_fingerprint(request)
    ip_address = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    device_name = get_device_name(request)
    
    # Get or create device login record
    device_login, created = DeviceLogin.objects.get_or_create(
        user=user,
        device_id=device_id,
        defaults={
            'ip_address': ip_address,
            'user_agent': user_agent,
            'device_name': device_name,
            'login_count': 1
        }
    )
    
    if not created:
        # Update existing record
        device_login.ip_address = ip_address
        device_login.user_agent = user_agent
        device_login.device_name = device_name
        device_login.login_count += 1
        device_login.save()
    
    return Response({
        'success': True,
        'device_id': device_id,
        'device_name': device_name,
        'login_count': device_login.login_count
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def get_all_users(request):
    """
    Fallback endpoint to get all active users.
    Used if no device-specific users are found.
    """
    users = User.objects.filter(is_active=True).order_by('username')
    
    users_data = [{
        'id': user.id,
        'username': user.username,
        'email': user.email,
    } for user in users]
    
    return Response({
        'users': users_data,
        'count': len(users_data)
    })
