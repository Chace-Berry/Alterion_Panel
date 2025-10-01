from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import FTPAccount, Database, EmailAccount, ServiceStatus
from .serializers import (
    FTPAccountSerializer, DatabaseSerializer,
    EmailAccountSerializer, ServiceStatusSerializer
)
import subprocess
import os
import psutil

class FTPAccountViewSet(viewsets.ModelViewSet):
    queryset = FTPAccount.objects.all()
    serializer_class = FTPAccountSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FTPAccount.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def reset_password(self, request, pk=None):
        ftp_account = self.get_object()
        new_password = request.data.get('password')
        if new_password:
            ftp_account.password = new_password
            ftp_account.save()
            # Here you would implement actual FTP password reset
            # Similar to CyberPanel's FTPUtilities.changeFTPPassword
            return Response({'status': 'Password reset successfully'})
        return Response({'error': 'Password required'}, status=400)

class DatabaseViewSet(viewsets.ModelViewSet):
    queryset = Database.objects.all()
    serializer_class = DatabaseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Database.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class EmailAccountViewSet(viewsets.ModelViewSet):
    queryset = EmailAccount.objects.all()
    serializer_class = EmailAccountSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return EmailAccount.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class ServiceStatusViewSet(viewsets.ModelViewSet):
    queryset = ServiceStatus.objects.all()
    serializer_class = ServiceStatusSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def check_status(self, request):
        """Check status of all services like CyberPanel does"""
        services_status = {}

        # Check FTP (Pure-FTPd)
        try:
            ftp_running = any('pure-ftpd' in proc.name() for proc in psutil.process_iter())
            services_status['ftp'] = {
                'running': ftp_running,
                'port': 21,
                'message': 'FTP server is running' if ftp_running else 'FTP server is stopped'
            }
        except:
            services_status['ftp'] = {'running': False, 'port': 21, 'message': 'Unable to check FTP status'}

        # Check MySQL/MariaDB
        try:
            mysql_running = any('mysqld' in proc.name() or 'mariadbd' in proc.name() for proc in psutil.process_iter())
            services_status['database'] = {
                'running': mysql_running,
                'port': 3306,
                'message': 'Database server is running' if mysql_running else 'Database server is stopped'
            }
        except:
            services_status['database'] = {'running': False, 'port': 3306, 'message': 'Unable to check database status'}

        # Check Postfix (Email)
        try:
            postfix_running = any('postfix' in proc.name() for proc in psutil.process_iter())
            services_status['email'] = {
                'running': postfix_running,
                'port': 25,
                'message': 'Email server is running' if postfix_running else 'Email server is stopped'
            }
        except:
            services_status['email'] = {'running': False, 'port': 25, 'message': 'Unable to check email status'}

        # Update database
        for service_name, status_info in services_status.items():
            ServiceStatus.objects.update_or_create(
                service_name=service_name,
                defaults={
                    'is_running': status_info['running'],
                    'port': status_info['port'],
                    'status_message': status_info['message']
                }
            )

        return Response(services_status)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def manage_service(request):
    """Manage services like CyberPanel does - start/stop/restart"""
    service_name = request.data.get('service')
    action = request.data.get('action')  # start, stop, restart

    if not service_name or not action:
        return Response({'error': 'Service name and action required'}, status=400)

    # Service management commands (similar to CyberPanel's approach)
    service_commands = {
        'ftp': {
            'start': 'systemctl start pure-ftpd',
            'stop': 'systemctl stop pure-ftpd',
            'restart': 'systemctl restart pure-ftpd',
        },
        'database': {
            'start': 'systemctl start mysql',
            'stop': 'systemctl stop mysql',
            'restart': 'systemctl restart mysql',
        },
        'email': {
            'start': 'systemctl start postfix',
            'stop': 'systemctl stop postfix',
            'restart': 'systemctl restart postfix',
        }
    }

    if service_name not in service_commands or action not in ['start', 'stop', 'restart']:
        return Response({'error': 'Invalid service or action'}, status=400)

    try:
        command = service_commands[service_name][action]
        result = subprocess.run(command, shell=True, capture_output=True, text=True)

        if result.returncode == 0:
            return Response({
                'status': 'success',
                'message': f'Service {service_name} {action} successful'
            })
        else:
            return Response({
                'status': 'error',
                'message': f'Failed to {action} {service_name}: {result.stderr}'
            }, status=500)

    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=500)
