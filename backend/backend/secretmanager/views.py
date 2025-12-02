from rest_framework import serializers, viewsets
from .models import SecretProject, SecretEnvironment, Secret, SecretVersion


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
    client_id = serializers.SerializerMethodField()
    client_secret = serializers.SerializerMethodField()
    access_token = serializers.SerializerMethodField()

    class Meta:
        model = SecretProject
        fields = ['id', 'name', 'description', 'created_by', 'created_by_name',
                  'created_at', 'updated_at', 'environments', 'secret_count', 'client_id', 'client_secret', 'access_token']
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def get_access_token(self, obj):
        # Generate a permanent access token for the linked Application
        try:
            app = obj.application
            if not app:
                return None
            from oauth2_provider.models import AccessToken
            from django.utils import timezone
            from django.contrib.auth import get_user_model
            import datetime
            User = get_user_model()
            user = app.user if app.user else User.objects.first()
            # Check for existing valid token (permanent)
            token_obj = AccessToken.objects.filter(application=app, user=user, expires__gt=timezone.now() + datetime.timedelta(days=365*9)).first()
            if token_obj:
                return token_obj.token
            # Otherwise, create a new permanent token
            from oauthlib.common import generate_token
            token = generate_token()
            # Set expiry to 10 years from now
            expires = timezone.now() + datetime.timedelta(days=365*10)
            scope = app.scope if hasattr(app, 'scope') else ''
            token_obj = AccessToken.objects.create(
                user=user,
                application=app,
                token=token,
                expires=expires,
                scope=scope
            )
            return token_obj.token
        except Exception:
            return None

    def get_secret_count(self, obj):
        return Secret.objects.filter(environment__project=obj).count()

    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else None

    def get_client_id(self, obj):
        # Use the linked Application model
        try:
            app = obj.application
            return app.client_id if app else None
        except Exception:
            return None

    def get_client_secret(self, obj):
        try:
            app = obj.application
            return app.client_secret if app else None
        except Exception:
            return None


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


class SecretProjectViewSet(viewsets.ModelViewSet):
    queryset = SecretProject.objects.all()
    serializer_class = SecretProjectSerializer

class SecretEnvironmentViewSet(viewsets.ModelViewSet):
    queryset = SecretEnvironment.objects.all()
    serializer_class = SecretEnvironmentSerializer

class SecretViewSet(viewsets.ModelViewSet):
    queryset = Secret.objects.all()
    serializer_class = SecretSerializer
