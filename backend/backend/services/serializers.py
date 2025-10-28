from rest_framework import serializers
from .models import FTPAccount, Database, EmailAccount, ServiceStatus, Domain, DomainCheck

class FTPAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = FTPAccount
        fields = ['id', 'username', 'home_directory', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {
            'password': {'write_only': True}
        }

class DatabaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Database
        fields = ['id', 'name', 'db_type', 'db_user', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {
            'db_password': {'write_only': True}
        }

class EmailAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailAccount
        fields = ['id', 'email', 'quota_mb', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {
            'password': {'write_only': True}
        }

class ServiceStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceStatus
        fields = '__all__'


class DomainSerializer(serializers.ModelSerializer):
    days_until_expiry = serializers.ReadOnlyField()
    linked_server_name = serializers.CharField(source='linked_server.name', read_only=True)
    linked_server_identifier = serializers.CharField(source='linked_server.identifier', read_only=True)
    
    class Meta:
        model = Domain
        fields = [
            'id', 'domain_name', 'registrar', 'linked_server', 'linked_server_name',
            'linked_server_identifier', 'expiry_date', 'last_checked', 'status',
            'is_active', 'check_interval_hours', 'notification_days', 'web_root',
            'ssl_enabled', 'ssl_expiry', 'dns_records', 'days_until_expiry',
            'is_verified', 'verification_token', 'verification_status',
            'verified_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['status', 'last_checked', 'is_verified', 'verified_at', 'created_at', 'updated_at']


class DomainCheckSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)
    
    class Meta:
        model = DomainCheck
        fields = '__all__'
        read_only_fields = ['timestamp']
