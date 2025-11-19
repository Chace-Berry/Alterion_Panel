"""
Deployment API Views
REST API endpoints for project management, deployment, and monitoring.
"""

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .deployment_models import (
    Project, BackendConfig, DomainConfig, 
    Deployment, ComponentLibrary, APIEndpoint, Animation
)
from .deployment_serializers import (
    ProjectSerializer, BackendConfigSerializer, DomainConfigSerializer,
    DeploymentSerializer, ComponentLibrarySerializer, APIEndpointSerializer,
    AnimationSerializer, ProjectCreateSerializer, BackendDetectionResultSerializer,
    DNSVerificationSerializer, DeploymentTriggerSerializer
)
from .backend_detector import BackendDetector
from .dns_verifier import DNSVerifier
from .deployment_orchestrator import DeploymentOrchestrator

import os
import shutil
from pathlib import Path


class ProjectViewSet(viewsets.ModelViewSet):
    """
    ViewSet for CRUD operations on Projects.
    """
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Project.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def create_full_project(self, request):
        """
        Create a new project with backend and domain configuration.
        """
        serializer = ProjectCreateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Create project
        project = Project.objects.create(
            user=request.user,
            name=data['name'],
            slug=data['slug'],
            description=data.get('description', ''),
            build_type=data['build_type'],
            frontend_framework=data.get('frontend_framework', 'react')
        )
        
        # Create backend config if requested
        if data.get('has_backend'):
            BackendConfig.objects.create(
                project=project,
                framework=data.get('backend_framework', 'other'),
                port=data.get('backend_port', 8000)
            )
        
        # Create domain config if requested
        if data.get('has_domain'):
            DomainConfig.objects.create(
                project=project,
                domain_name=data.get('domain_name'),
                expected_ip=data.get('expected_ip', ''),
                ssl_enabled=data.get('ssl_enabled', False)
            )
        
        return Response(
            ProjectSerializer(project).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_frontend(self, request, pk=None):
        """
        Upload frontend dist files (ZIP or individual files).
        """
        project = self.get_object()
        
        # Handle file upload
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        uploaded_file = request.FILES['file']
        
        # Create project directory
        project_dir = Path('/var/alterion/projects') / project.slug
        frontend_dist = project_dir / 'frontend' / 'dist'
        frontend_dist.mkdir(parents=True, exist_ok=True)
        
        # Handle ZIP file
        if uploaded_file.name.endswith('.zip'):
            import zipfile
            import tempfile
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
                for chunk in uploaded_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name
            
            try:
                with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
                    zip_ref.extractall(frontend_dist)
                
                project.frontend_dist_path = str(frontend_dist)
                project.save()
                
                return Response({
                    'message': 'Frontend uploaded successfully',
                    'path': str(frontend_dist),
                    'files_count': len(list(frontend_dist.rglob('*')))
                })
            finally:
                os.unlink(tmp_path)
        
        return Response(
            {'error': 'Only ZIP files are supported'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_backend(self, request, pk=None):
        """
        Upload backend folder and detect framework.
        """
        project = self.get_object()
        
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        uploaded_file = request.FILES['file']
        
        # Create project directory
        project_dir = Path('/var/alterion/projects') / project.slug
        backend_dir = project_dir / 'backend'
        backend_dir.mkdir(parents=True, exist_ok=True)
        
        # Handle ZIP file
        if uploaded_file.name.endswith('.zip'):
            import zipfile
            import tempfile
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
                for chunk in uploaded_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name
            
            try:
                with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
                    zip_ref.extractall(backend_dir)
                
                project.backend_path = str(backend_dir)
                project.save()
                
                # Detect backend framework
                try:
                    detector = BackendDetector(str(backend_dir))
                    detection_result = detector.detect_framework()
                    
                    # Create or update backend config
                    backend_config, created = BackendConfig.objects.get_or_create(
                        project=project,
                        defaults={
                            'framework': detection_result['framework'],
                            'detected_apis': detection_result['detected_apis'],
                            'detected_models': detection_result['detected_models'],
                            'start_command': detection_result['suggested_start_command'],
                            'port': detection_result['port']
                        }
                    )
                    
                    if not created:
                        backend_config.framework = detection_result['framework']
                        backend_config.detected_apis = detection_result['detected_apis']
                        backend_config.detected_models = detection_result['detected_models']
                        backend_config.start_command = detection_result['suggested_start_command']
                        backend_config.port = detection_result['port']
                        backend_config.save()
                    
                    # Create API endpoint entries
                    for api_data in detection_result['detected_apis']:
                        APIEndpoint.objects.get_or_create(
                            backend_config=backend_config,
                            path=api_data.get('path', api_data.get('name', '')),
                            method=api_data.get('method', 'GET'),
                            defaults={
                                'description': f"Auto-detected from {api_data.get('file', 'unknown')}"
                            }
                        )
                    
                    return Response({
                        'message': 'Backend uploaded and detected successfully',
                        'path': str(backend_dir),
                        'detection': BackendDetectionResultSerializer(detection_result).data
                    })
                
                except Exception as e:
                    return Response({
                        'message': 'Backend uploaded but detection failed',
                        'path': str(backend_dir),
                        'error': str(e)
                    }, status=status.HTTP_207_MULTI_STATUS)
            
            finally:
                os.unlink(tmp_path)
        
        return Response(
            {'error': 'Only ZIP files are supported'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=True, methods=['get'])
    def deployment_history(self, request, pk=None):
        """Get deployment history for a project."""
        project = self.get_object()
        deployments = project.deployments.all()[:20]  # Last 20 deployments
        serializer = DeploymentSerializer(deployments, many=True)
        return Response(serializer.data)


class DomainConfigViewSet(viewsets.ModelViewSet):
    """
    ViewSet for domain configuration and DNS verification.
    """
    serializer_class = DomainConfigSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return DomainConfig.objects.filter(project__user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def verify_dns(self, request, pk=None):
        """
        Verify DNS configuration for a domain.
        """
        domain_config = self.get_object()
        
        verifier = DNSVerifier()
        
        # Get server IP if not set
        if not domain_config.expected_ip:
            server_ip = verifier.get_server_public_ip()
            if server_ip:
                domain_config.expected_ip = server_ip
                domain_config.save()
        
        # Verify DNS
        result = verifier.verify_domain(
            domain_config.domain_name,
            domain_config.expected_ip
        )
        
        # Update domain config
        domain_config.dns_verified = result['verified']
        domain_config.actual_ip = result.get('actual_ip')
        domain_config.last_verified = timezone.now()
        domain_config.save()
        
        serializer = DNSVerificationSerializer(result)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def dns_suggestions(self, request, pk=None):
        """
        Get DNS configuration suggestions.
        """
        domain_config = self.get_object()
        
        verifier = DNSVerifier()
        
        # Get server IP
        server_ip = domain_config.expected_ip
        if not server_ip:
            server_ip = verifier.get_server_public_ip()
        
        suggestions = verifier.suggest_dns_configuration(
            domain_config.domain_name,
            server_ip
        )
        
        return Response(suggestions)


class DeploymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing deployments.
    """
    serializer_class = DeploymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Deployment.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def trigger_deployment(self, request):
        """
        Trigger a new deployment for a project.
        """
        serializer = DeploymentTriggerSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        project_id = data['project_id']
        
        # Get project
        project = get_object_or_404(
            Project.objects.filter(user=request.user),
            id=project_id
        )
        
        # Create deployment record
        deployment = Deployment.objects.create(
            project=project,
            user=request.user,
            status='pending'
        )
        
        # Start deployment orchestration
        orchestrator = DeploymentOrchestrator()
        
        try:
            deployment.status = 'validating'
            deployment.save()
            
            # Get domain config if exists
            domain = None
            expected_ip = None
            ssl_enabled = False
            ssl_cert = ""
            ssl_key = ""
            
            if hasattr(project, 'domain_config'):
                domain = project.domain_config.domain_name
                expected_ip = project.domain_config.expected_ip
                ssl_enabled = project.domain_config.ssl_enabled
                ssl_cert = project.domain_config.ssl_cert_path
                ssl_key = project.domain_config.ssl_key_path
            
            # Execute deployment
            result = orchestrator.deploy_project(
                project_id=str(project.id),
                project_name=project.slug,
                frontend_dist_path=project.frontend_dist_path,
                backend_path=project.backend_path if data['deploy_backend'] else None,
                domain=domain if data['apply_nginx'] else None,
                expected_ip=expected_ip,
                ssl_enabled=ssl_enabled,
                ssl_cert_path=ssl_cert,
                ssl_key_path=ssl_key,
                verify_dns=data['verify_dns'],
                restart_backend=data['restart_backend']
            )
            
            # Update deployment record
            deployment.logs = '\n'.join(result['logs'])
            
            if result['success']:
                deployment.status = 'success'
                
                # Update backend config if backend was started
                if result.get('backend_pid') and hasattr(project, 'backend_config'):
                    backend_config = project.backend_config
                    backend_config.process_id = result['backend_pid']
                    backend_config.is_running = True
                    backend_config.last_started = timezone.now()
                    backend_config.save()
                
                # Update domain config if NGINX was applied
                if result.get('nginx_config') and hasattr(project, 'domain_config'):
                    domain_config = project.domain_config
                    domain_config.nginx_config_path = result['nginx_config']
                    domain_config.nginx_enabled = True
                    domain_config.save()
            else:
                deployment.status = 'failed'
            
            deployment.completed_at = timezone.now()
            deployment.save()
            
            return Response({
                'deployment_id': deployment.id,
                'status': deployment.status,
                'logs': result['logs'],
                'errors': result.get('errors', [])
            })
        
        except Exception as e:
            deployment.status = 'failed'
            deployment.logs += f"\n\nDeployment error: {str(e)}"
            deployment.completed_at = timezone.now()
            deployment.save()
            
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def rollback(self, request, pk=None):
        """
        Rollback a deployment.
        """
        deployment = self.get_object()
        project = deployment.project
        
        orchestrator = DeploymentOrchestrator()
        
        domain = None
        if hasattr(project, 'domain_config'):
            domain = project.domain_config.domain_name
        
        result = orchestrator.rollback_deployment(
            project_id=str(project.id),
            project_name=project.slug,
            domain=domain
        )
        
        if result['success']:
            # Create rollback deployment record
            rollback_deployment = Deployment.objects.create(
                project=project,
                user=request.user,
                status='rollback',
                logs=f"Rolled back deployment {deployment.id}\n{result['message']}"
            )
            rollback_deployment.completed_at = timezone.now()
            rollback_deployment.save()
            
            return Response({
                'message': 'Rollback successful',
                'deployment_id': rollback_deployment.id
            })
        
        return Response(
            {'error': result['message']},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class ComponentLibraryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for reusable component library.
    """
    serializer_class = ComponentLibrarySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Show user's components and public components
        return ComponentLibrary.objects.filter(
            user=self.request.user
        ) | ComponentLibrary.objects.filter(is_public=True)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def increment_usage(self, request, pk=None):
        """Increment usage count when component is used."""
        component = self.get_object()
        component.usage_count += 1
        component.save()
        return Response({'usage_count': component.usage_count})


class AnimationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for keyframe animations.
    """
    serializer_class = AnimationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Animation.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
