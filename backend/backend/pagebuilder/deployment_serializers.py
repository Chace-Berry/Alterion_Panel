from rest_framework import serializers
from .deployment_models import (
    Project, BackendConfig, DomainConfig, 
    Deployment, ComponentLibrary, APIEndpoint, Animation
)


class APIEndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = APIEndpoint
        fields = ['id', 'path', 'method', 'description', 'request_schema', 
                  'response_schema', 'requires_auth', 'created_at']


class BackendConfigSerializer(serializers.ModelSerializer):
    api_endpoints = APIEndpointSerializer(many=True, read_only=True)
    
    class Meta:
        model = BackendConfig
        fields = ['id', 'framework', 'detected_apis', 'detected_models',
                  'start_command', 'port', 'environment_vars', 'process_id',
                  'is_running', 'last_started', 'last_stopped', 'api_endpoints',
                  'created_at', 'updated_at']
        read_only_fields = ['detected_apis', 'detected_models', 'process_id', 
                           'is_running', 'last_started', 'last_stopped']


class DomainConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = DomainConfig
        fields = ['id', 'domain_name', 'dns_verified', 'expected_ip', 'actual_ip',
                  'last_verified', 'ssl_enabled', 'ssl_auto', 'ssl_cert_path',
                  'ssl_key_path', 'nginx_config_path', 'nginx_enabled',
                  'created_at', 'updated_at']
        read_only_fields = ['dns_verified', 'actual_ip', 'last_verified', 
                           'nginx_config_path', 'nginx_enabled']


class ProjectSerializer(serializers.ModelSerializer):
    backend_config = BackendConfigSerializer(read_only=True)
    domain_config = DomainConfigSerializer(read_only=True)
    deployment_count = serializers.SerializerMethodField()
    latest_deployment = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = ['id', 'name', 'slug', 'description', 'build_type', 
                  'frontend_framework', 'frontend_dist_path', 'frontend_dev_path',
                  'backend_path', 'is_active', 'backend_config', 'domain_config',
                  'deployment_count', 'latest_deployment', 'created_at', 'updated_at']
        read_only_fields = ['user']
    
    def get_deployment_count(self, obj):
        return obj.deployments.count()
    
    def get_latest_deployment(self, obj):
        latest = obj.deployments.first()
        if latest:
            return {
                'id': latest.id,
                'status': latest.status,
                'started_at': latest.started_at,
                'completed_at': latest.completed_at
            }
        return None


class DeploymentSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = Deployment
        fields = ['id', 'project', 'project_name', 'user', 'user_username',
                  'status', 'logs', 'frontend_hash', 'backend_hash',
                  'started_at', 'completed_at']
        read_only_fields = ['user', 'logs', 'frontend_hash', 'backend_hash',
                           'started_at', 'completed_at']


class ComponentLibrarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ComponentLibrary
        fields = ['id', 'name', 'description', 'component_json', 'preview_image',
                  'category', 'tags', 'is_public', 'usage_count',
                  'created_at', 'updated_at']
        read_only_fields = ['user', 'usage_count']


class AnimationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Animation
        fields = ['id', 'name', 'duration', 'keyframes_json', 'easing',
                  'created_at', 'updated_at']
        read_only_fields = ['user']


class ProjectCreateSerializer(serializers.Serializer):
    """Serializer for creating a new project with initial configuration"""
    name = serializers.CharField(max_length=255)
    slug = serializers.SlugField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    build_type = serializers.ChoiceField(choices=['nocode', 'import'])
    frontend_framework = serializers.ChoiceField(
        choices=['react', 'vue', 'angular', 'static'],
        default='react'
    )
    
    # Backend configuration (optional)
    has_backend = serializers.BooleanField(default=False)
    backend_framework = serializers.ChoiceField(
        choices=['django', 'fastapi', 'nodejs', 'other'],
        required=False
    )
    backend_port = serializers.IntegerField(default=8000, required=False)
    
    # Domain configuration (optional)
    has_domain = serializers.BooleanField(default=False)
    domain_name = serializers.CharField(required=False)
    expected_ip = serializers.IPAddressField(required=False)
    ssl_enabled = serializers.BooleanField(default=False)


class BackendDetectionResultSerializer(serializers.Serializer):
    """Serializer for backend framework detection results"""
    framework = serializers.CharField()
    confidence = serializers.FloatField()
    detected_files = serializers.ListField(child=serializers.CharField())
    suggested_start_command = serializers.CharField()
    detected_apis = serializers.ListField(child=serializers.DictField())
    detected_models = serializers.ListField(child=serializers.DictField())
    port = serializers.IntegerField()


class DNSVerificationSerializer(serializers.Serializer):
    """Serializer for DNS verification results"""
    domain = serializers.CharField()
    verified = serializers.BooleanField()
    expected_ip = serializers.IPAddressField()
    actual_ip = serializers.IPAddressField(allow_null=True)
    message = serializers.CharField()


class DeploymentTriggerSerializer(serializers.Serializer):
    """Serializer for triggering a new deployment"""
    project_id = serializers.IntegerField()
    deploy_frontend = serializers.BooleanField(default=True)
    deploy_backend = serializers.BooleanField(default=True)
    restart_backend = serializers.BooleanField(default=True)
    apply_nginx = serializers.BooleanField(default=True)
    verify_dns = serializers.BooleanField(default=True)
