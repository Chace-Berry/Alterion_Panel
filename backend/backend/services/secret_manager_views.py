from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .secret_manager_models import SecretProject, SecretEnvironment, Secret, SecretVersion
from .secret_manager_serializers import (
    SecretProjectSerializer, SecretEnvironmentSerializer, 
    SecretSerializer, SecretVersionSerializer
)
from crypto_utils import encrypt_value, decrypt_value


class SecretProjectViewSet(viewsets.ModelViewSet):
    """ViewSet for managing secret projects"""
    queryset = SecretProject.objects.all()
    serializer_class = SecretProjectSerializer
    
    def get_queryset(self):
        """Exclude Node SSH Credentials project from UI (identified by internal marker)"""
        return SecretProject.objects.exclude(description__contains="_ssh_node_creds_internal_")
    
    def perform_create(self, serializer):
        project = serializer.save(created_by=self.request.user)
        # Create default environments
        default_envs = [
            {'name': 'Development', 'slug': 'dev', 'position': 0},
            {'name': 'Staging', 'slug': 'staging', 'position': 1},
            {'name': 'Production', 'slug': 'prod', 'position': 2},
        ]
        for env_data in default_envs:
            SecretEnvironment.objects.create(project=project, **env_data)
    
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
    
    def get_queryset(self):
        """Exclude hidden environments from UI"""
        return SecretEnvironment.objects.filter(is_hidden=False)
    
    @action(detail=True, methods=['get'])
    def secrets(self, request, pk=None):
        """Get all secrets in an environment"""
        environment = self.get_object()
        secrets = environment.secrets.all()
        serializer = SecretSerializer(secrets, many=True)
        
        # Decrypt keys, values, and descriptions before sending
        for secret_data in serializer.data:
            try:
                secret_data['key'] = decrypt_value(secret_data['key']) if secret_data.get('key') else ''
            except:
                secret_data['key'] = '[Decryption Failed]'
            
            try:
                secret_data['value'] = decrypt_value(secret_data['value']) if secret_data.get('value') else ''
            except:
                secret_data['value'] = '[Decryption Failed]'
            
            try:
                secret_data['description'] = decrypt_value(secret_data['description']) if secret_data.get('description') else ''
            except:
                secret_data['description'] = ''
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_secret(self, request, pk=None):
        """Add a new secret to an environment"""
        environment = self.get_object()
        
        key = request.data.get('key')
        value = request.data.get('value')
        description = request.data.get('description', '')
        
        if not key or not value:
            return Response(
                {'error': 'Key and value are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Encrypt key first to check if it exists
        try:
            encrypted_key = encrypt_value(key)
        except Exception as e:
            return Response(
                {'error': f'Failed to encrypt key: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Check if secret already exists
        if Secret.objects.filter(environment=environment, key=encrypted_key).exists():
            return Response(
                {'error': f'Secret with key "{key}" already exists in this environment'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Encrypt the value and description (key already encrypted above)
        try:
            encrypted_value = encrypt_value(value)
            encrypted_description = encrypt_value(description) if description else ''
        except Exception as e:
            return Response(
                {'error': f'Failed to encrypt data: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
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
        
        serializer = SecretSerializer(secret)
        response_data = serializer.data
        response_data['key'] = key  # Return decrypted key
        response_data['value'] = value  # Return decrypted value
        response_data['description'] = description  # Return decrypted description
        
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def bulk_update(self, request, pk=None):
        """Bulk update/create secrets in an environment"""
        environment = self.get_object()
        secrets_data = request.data.get('secrets', [])
        
        results = {'created': 0, 'updated': 0, 'errors': []}
        
        for secret_data in secrets_data:
            key = secret_data.get('key')
            value = secret_data.get('value')
            description = secret_data.get('description', '')
            
            if not key or value is None:
                results['errors'].append({'key': key, 'error': 'Key and value are required'})
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
                results['errors'].append({'key': key, 'error': str(e)})
        
        return Response(results)


class SecretViewSet(viewsets.ModelViewSet):
    """ViewSet for managing individual secrets"""
    queryset = Secret.objects.all()
    serializer_class = SecretSerializer
    
    def retrieve(self, request, *args, **kwargs):
        """Get a single secret with decrypted key, value, and description"""
        secret = self.get_object()
        serializer = self.get_serializer(secret)
        data = serializer.data
        
        try:
            data['key'] = decrypt_value(data['key']) if data.get('key') else ''
        except:
            data['key'] = '[Decryption Failed]'
        
        try:
            data['value'] = decrypt_value(data['value']) if data.get('value') else ''
        except:
            data['value'] = '[Decryption Failed]'
        
        try:
            data['description'] = decrypt_value(data['description']) if data.get('description') else ''
        except:
            data['description'] = '[Decryption Failed]'
        
        return Response(data)
    
    def update(self, request, *args, **kwargs):
        """Update a secret"""
        secret = self.get_object()
        key = request.data.get('key')
        value = request.data.get('value')
        description = request.data.get('description')
        
        try:
            if value is not None:
                encrypted_value = encrypt_value(value)
                secret.value = encrypted_value
            
            if key is not None:
                encrypted_key = encrypt_value(key)
                secret.key = encrypted_key
            
            if description is not None:
                encrypted_description = encrypt_value(description)
                secret.description = encrypted_description
        except Exception as e:
            return Response(
                {'error': f'Failed to encrypt data: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        secret.updated_by = request.user
        secret.save()
        
        # Create version history
        SecretVersion.objects.create(
            secret=secret,
            value=secret.value,
            changed_by=request.user,
            change_type='updated'
        )
        
        serializer = self.get_serializer(secret)
        response_data = serializer.data
        # Return decrypted values
        if key is not None:
            response_data['key'] = key
        if value is not None:
            response_data['value'] = value
        if description is not None:
            response_data['description'] = description
        
        return Response(response_data)
    
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
        
        # Decrypt values before sending (keys and descriptions are on the secret, not versions)
        for version_data in serializer.data:
            try:
                version_data['value'] = decrypt_value(version_data['value']) if version_data.get('value') else ''
            except:
                version_data['value'] = '[Decryption Failed]'
        
        return Response(serializer.data)
