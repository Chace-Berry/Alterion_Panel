from rest_framework import serializers
from .secret_manager_models import SecretProject, SecretEnvironment, Secret, SecretVersion


class SecretEnvironmentSerializer(serializers.ModelSerializer):
    secret_count = serializers.SerializerMethodField()
    
    class Meta:
        model = SecretEnvironment
        fields = ['id', 'name', 'slug', 'position', 'created_at', 'secret_count']
    
    def get_secret_count(self, obj):
        return obj.secrets.count()


class SecretProjectSerializer(serializers.ModelSerializer):
    environments = SecretEnvironmentSerializer(many=True, read_only=True)
    secret_count = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = SecretProject
        fields = ['id', 'name', 'description', 'created_by', 'created_by_name', 
                  'created_at', 'updated_at', 'environments', 'secret_count']
        read_only_fields = ['created_by', 'created_at', 'updated_at']
    
    def get_secret_count(self, obj):
        return Secret.objects.filter(environment__project=obj).count()
    
    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else None


class SecretSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Secret
        fields = ['id', 'key', 'value', 'description', 'created_by', 'created_by_name',
                  'updated_by', 'updated_by_name', 'created_at', 'updated_at']
        read_only_fields = ['created_by', 'updated_by', 'created_at', 'updated_at']
    
    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else None
    
    def get_updated_by_name(self, obj):
        return obj.updated_by.username if obj.updated_by else None


class SecretVersionSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = SecretVersion
        fields = ['id', 'value', 'changed_by', 'changed_by_name', 'changed_at', 'change_type']
    
    def get_changed_by_name(self, obj):
        return obj.changed_by.username if obj.changed_by else None
