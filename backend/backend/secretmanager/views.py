from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from .models import SecretProject, SecretEnvironment, Secret, SecretVersion
from oauth2_provider.models import Application
from .serializers import (
    SecretProjectSerializer, SecretEnvironmentSerializer, 
    SecretSerializer, SecretVersionSerializer
)
from crypto_utils import encrypt_value, decrypt_value
import logging

logger = logging.getLogger(__name__)


class SecretProjectViewSet(viewsets.ModelViewSet):
    """ViewSet for managing secret projects"""
    queryset = SecretProject.objects.all()
    serializer_class = SecretProjectSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Exclude Node SSH Credentials project from UI (identified by internal marker)"""
        return SecretProject.objects.exclude(
            description__contains="_ssh_node_creds_internal_"
        ).filter(created_by=self.request.user)
    
    @transaction.atomic
    def perform_create(self, serializer):
        """Create project with default environments and OAuth2 app"""
        project = serializer.save(created_by=self.request.user)
        
        # Create default environments
        default_envs = [
            {'name': 'Development', 'slug': 'dev', 'position': 0},
            {'name': 'Staging', 'slug': 'staging', 'position': 1},
            {'name': 'Production', 'slug': 'prod', 'position': 2},
        ]
        
        for env_data in default_envs:
            SecretEnvironment.objects.create(project=project, **env_data)
        
        # Create OAuth2 app/client for this project
        try:
            app = Application.objects.create(
                name=f"{project.name} Client",
                user=self.request.user,
                client_type=Application.CLIENT_CONFIDENTIAL,
                authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS
            )
            project.application = app
            project.save()
        except Exception as e:
            logger.error(f"Failed to create OAuth2 app for project {project.id}: {e}")
            # Don't fail the whole transaction, just log it
    
    @transaction.atomic
    def perform_destroy(self, instance):
        """Delete project and associated OAuth2 app"""
        # Delete associated OAuth2 app if exists
        if instance.application:
            try:
                instance.application.delete()
            except Exception as e:
                logger.error(f"Failed to delete OAuth2 app: {e}")
        
        super().perform_destroy(instance)
    
    @action(detail=True, methods=['get'])
    def environments(self, request, pk=None):
        """Get all environments for a project"""
        project = self.get_object()
        # Exclude hidden environments (like SSH)
        environments = project.environments.filter(is_hidden=False)
        serializer = SecretEnvironmentSerializer(environments, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_environment(self, request, pk=None):
        """Add a new environment to a project"""
        project = self.get_object()
        serializer = SecretEnvironmentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(project=project)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SecretEnvironmentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing environments"""
    queryset = SecretEnvironment.objects.all()
    serializer_class = SecretEnvironmentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Exclude hidden environments from UI and filter by user's projects"""
        return SecretEnvironment.objects.filter(
            is_hidden=False,
            project__created_by=self.request.user
        )
    
    @action(detail=True, methods=['get'])
    def secrets(self, request, pk=None):
        """Get all secrets in an environment"""
        environment = self.get_object()
        secrets = environment.secrets.all()
        serializer = SecretSerializer(secrets, many=True)
        
        # Decrypt secrets
        decrypted_data = []
        for secret_data in serializer.data:
              decrypted_secret = self._decrypt_secret_data(secret_data)
              # Add raw_key field with encrypted key value for API copy
              decrypted_secret['raw_key'] = secret_data.get('key', '')
              decrypted_data.append(decrypted_secret)
        
        return Response(decrypted_data)
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def add_secret(self, request, pk=None):
        """Add a new secret to an environment"""
        environment = self.get_object()
        
        key = request.data.get('key', '').strip()
        value = request.data.get('value', '')
        description = request.data.get('description', '').strip()
        
        # Validation
        if not key or not value:
            return Response(
                {'error': 'Key and value are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(key) > 255:
            return Response(
                {'error': 'Key must be 255 characters or less'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Encrypt data
        try:
            encrypted_key = encrypt_value(key)
            encrypted_value = encrypt_value(value)
            encrypted_description = encrypt_value(description) if description else ''
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return Response(
                {'error': 'Failed to encrypt data'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Check if secret already exists
        if Secret.objects.filter(environment=environment, key=encrypted_key).exists():
            return Response(
                {'error': f'Secret with key "{key}" already exists in this environment'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create secret
        secret = Secret.objects.create(
            environment=environment,
            key=encrypted_key,
            value=encrypted_value,
            description=encrypted_description,
            created_by=request.user
        )
        
        # Create version history
        SecretVersion.objects.create(
            secret=secret,
            value=encrypted_value,
            changed_by=request.user,
            change_type='created'
        )
        
        # Return decrypted data
        serializer = SecretSerializer(secret)
        response_data = serializer.data
        response_data.update({
            'key': key,
            'value': value,
            'description': description
        })
        
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def bulk_update(self, request, pk=None):
        """Bulk update/create secrets in an environment"""
        environment = self.get_object()
        secrets_data = request.data.get('secrets', [])
        
        if not isinstance(secrets_data, list):
            return Response(
                {'error': 'secrets must be a list'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(secrets_data) > 100:  # Rate limiting
            return Response(
                {'error': 'Maximum 100 secrets per bulk operation'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        results = {'created': 0, 'updated': 0, 'errors': []}
        
        for secret_data in secrets_data:
            key = secret_data.get('key', '').strip()
            value = secret_data.get('value', '')
            description = secret_data.get('description', '').strip()
            
            if not key or value is None:
                results['errors'].append({
                    'key': key or '[missing]',
                    'error': 'Key and value are required'
                })
                continue
            
            try:
                encrypted_key = encrypt_value(key)
                encrypted_value = encrypt_value(value)
                encrypted_description = encrypt_value(description) if description else ''
                
                secret, created = Secret.objects.update_or_create(
                    environment=environment,
                    key=encrypted_key,
                    defaults={
                        'value': encrypted_value,
                        'description': encrypted_description,
                        'updated_by': request.user
                    }
                )
                
                if created:
                    secret.created_by = request.user
                    secret.save()
                    results['created'] += 1
                    change_type = 'created'
                else:
                    results['updated'] += 1
                    change_type = 'updated'
                
                # Create version history
                SecretVersion.objects.create(
                    secret=secret,
                    value=encrypted_value,
                    changed_by=request.user,
                    change_type=change_type
                )
                
            except Exception as e:
                logger.error(f"Failed to process secret {key}: {e}")
                results['errors'].append({'key': key, 'error': 'Processing failed'})
        
        return Response(results)
    
    def _decrypt_secret_data(self, secret_data):
        """Helper method to decrypt secret data"""
        result = secret_data.copy()
        
        for field in ['key', 'value', 'description']:
            if field in result and result[field]:
                try:
                    result[field] = decrypt_value(result[field])
                except Exception as e:
                    logger.error(f"Failed to decrypt {field}: {e}")
                    result[field] = '[Decryption Failed]'
            else:
                result[field] = ''
        
        return result


class SecretViewSet(viewsets.ModelViewSet):
    """ViewSet for managing individual secrets"""
    queryset = Secret.objects.all()
    serializer_class = SecretSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter secrets by user's projects"""
        return Secret.objects.filter(
            environment__project__created_by=self.request.user
        )
    
    @action(detail=False, methods=['get'], permission_classes=[])
    def get_by_key(self, request):
        """Fetch latest decrypted value for a specific encrypted key in an environment"""
        # Custom authentication for api_key
        api_key = request.query_params.get('api_key')
        user = None
        if api_key:
            from oauth2_provider.models import AccessToken
            from django.utils import timezone
            try:
                token_obj = AccessToken.objects.get(token=api_key)
                if token_obj.expires > timezone.now():
                    user = token_obj.user
            except AccessToken.DoesNotExist:
                pass
        if user:
            request.user = user
        environment_id = request.query_params.get('environment_id')
        encrypted_key = request.query_params.get('key')
        if not environment_id or not encrypted_key:
            return Response(
                {'error': 'environment_id and key required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            environment = SecretEnvironment.objects.get(
                id=environment_id,
                project__created_by=request.user
            )
        except SecretEnvironment.DoesNotExist:
            return Response(
                {'error': 'Environment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        try:
            secret = Secret.objects.get(environment=environment, key=encrypted_key)
            value = decrypt_value(secret.value)
            # Only return the decrypted value
            return Response({'value': value})
        except Secret.DoesNotExist:
            return Response(
                {'error': 'Secret not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to retrieve secret: {e}")
            return Response(
                {'error': 'Failed to retrieve secret'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def retrieve(self, request, *args, **kwargs):
        """Get a single secret with decrypted data"""
        secret = self.get_object()
        serializer = self.get_serializer(secret)
        data = serializer.data
        
        # Decrypt all fields
        for field in ['key', 'value', 'description']:
            if field in data and data[field]:
                try:
                    data[field] = decrypt_value(data[field])
                except Exception as e:
                    logger.error(f"Failed to decrypt {field}: {e}")
                    data[field] = '[Decryption Failed]'
        
        return Response(data)
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update a secret"""
        secret = self.get_object()
        key = request.data.get('key')
        value = request.data.get('value')
        description = request.data.get('description')
        
        try:
            # Encrypt and update fields
            if value is not None:
                secret.value = encrypt_value(value)
            
            if key is not None:
                encrypted_key = encrypt_value(key)
                # Check for duplicates
                if Secret.objects.filter(
                    environment=secret.environment,
                    key=encrypted_key
                ).exclude(id=secret.id).exists():
                    return Response(
                        {'error': 'A secret with this key already exists'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                secret.key = encrypted_key
            
            if description is not None:
                secret.description = encrypt_value(description) if description else ''
            
            secret.updated_by = request.user
            secret.save()
            
            # Create version history
            SecretVersion.objects.create(
                secret=secret,
                value=secret.value,
                changed_by=request.user,
                change_type='updated'
            )
            
        except Exception as e:
            logger.error(f"Failed to update secret: {e}")
            return Response(
                {'error': 'Failed to update secret'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Return decrypted values
        serializer = self.get_serializer(secret)
        response_data = serializer.data
        
        if key is not None:
            response_data['key'] = key
        else:
            try:
                response_data['key'] = decrypt_value(secret.key)
            except:
                response_data['key'] = '[Decryption Failed]'
        
        if value is not None:
            response_data['value'] = value
        else:
            try:
                response_data['value'] = decrypt_value(secret.value)
            except:
                response_data['value'] = '[Decryption Failed]'
        
        if description is not None:
            response_data['description'] = description
        else:
            try:
                response_data['description'] = decrypt_value(secret.description) if secret.description else ''
            except:
                response_data['description'] = ''
        
        return Response(response_data)
    
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """Delete a secret"""
        secret = self.get_object()
        
        # Create version history before deleting
        SecretVersion.objects.create(
            secret=secret,
            value=secret.value,
            changed_by=request.user,
            change_type='deleted'
        )
        
        return super().destroy(request, *args, **kwargs)
    
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Get version history for a secret"""
        secret = self.get_object()
        versions = secret.versions.all()[:20]  # Last 20 versions
        serializer = SecretVersionSerializer(versions, many=True)
        
        # Decrypt values
        for version_data in serializer.data:
            if version_data.get('value'):
                try:
                    version_data['value'] = decrypt_value(version_data['value'])
                except Exception as e:
                    logger.error(f"Failed to decrypt version value: {e}")
                    version_data['value'] = '[Decryption Failed]'
        
        return Response(serializer.data)