"""
Node Management API Views
Handles remote server connections, metrics collection, and management
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Q
import subprocess
import json
import os
from authentication.cookie_oauth2 import CookieOAuth2Authentication

    # Removed stray import statement

from .node_models import Node, NodeMetrics, NodeAlert, NodeService
from .node_serializers import (
    NodeSerializer, NodeMetricsSerializer, 
    NodeAlertSerializer, NodeServiceSerializer
)


class NodeViewSet(viewsets.ModelViewSet):

    def destroy(self, request, *args, **kwargs):
        """Delete a node and cleanup SSH credentials from Secret Manager"""
        from .credential_manager import delete_node_ssh_credentials
        import logging
        
        logger = logging.getLogger(__name__)
        node = self.get_object()
        node_id = node.id
        
        try:
            # Delete SSH credentials from Secret Manager
            logger.info(f"Deleting SSH credentials for node {node_id}")
            delete_node_ssh_credentials(node_id, user=request.user)
            logger.info(f"Successfully deleted credentials for node {node_id}")
        except Exception as e:
            logger.warning(f"Failed to delete credentials for node {node_id}: {e}")
            # Continue with node deletion even if credential cleanup fails
        
        # Delete the node
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['get'])
    def verification_code(self, request, pk=None):
        """Fetch the verification code for this node (for onboarding UI)"""
        node = self.get_object()
        # For demo: code is stored in node.notes
        return Response({"code": node.notes.strip() if node.notes else ""})
    authentication_classes = [CookieOAuth2Authentication]
    @action(detail=True, methods=['post'])
    def verify_code(self, request, pk=None):
        """Verify the code sent by the node agent and entered by the user"""
        node = self.get_object()
        code = request.data.get('code')
        if not code:
            return Response({'error': 'Verification code required'}, status=status.HTTP_400_BAD_REQUEST)
        # For demo: assume code is stored in node.notes (in production, use a secure field)
        if code == node.notes.strip():
            node.status = 'online'
            node.save()
            return Response({'verified': True})
        else:
            return Response({'verified': False, 'error': 'Invalid code'}, status=status.HTTP_400_BAD_REQUEST)
    @action(detail=True, methods=['get'])
    def install_progress(self, request, pk=None):
        """Check installation progress/status for SSH onboarding (stub)"""
        # In a real implementation, this would check a progress file, DB field, or agent status
        # For now, return a stub response
        return Response({
            'status': 'installing',
            'progress': 50,  # percent
            'message': 'Installation in progress...'
        })
    @action(detail=False, methods=['post'])
    def verify_ssh(self, request):
        """Verify SSH credentials before onboarding"""
        data = request.data
        required_fields = ['ip_address', 'port', 'username', 'auth_key']
        for field in required_fields:
            if not data.get(field):
                return Response({'error': f'Missing required field: {field}'}, status=status.HTTP_400_BAD_REQUEST)

        import tempfile
        try:
            with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.pem') as keyfile:
                keyfile.write(data['auth_key'])
                keyfile.flush()
                keyfile_path = keyfile.name
            ssh_cmd = [
                'ssh',
                '-i', keyfile_path,
                '-o', 'StrictHostKeyChecking=no',
                '-p', str(data['port']),
                f"{data['username']}@{data['ip_address']}",
                'echo verify-success'
            ]
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=10)
            os.unlink(keyfile_path)
            if result.returncode != 0 or 'verify-success' not in result.stdout:
                return Response({'verified': False, 'error': result.stderr}, status=status.HTTP_200_OK)
            return Response({'verified': True})
        except Exception as e:
            return Response({'verified': False, 'error': str(e)}, status=status.HTTP_200_OK)
    @action(detail=False, methods=['post'])
    def ssh_onboard(self, request):
        """Onboard a node via SSH (create and verify connection)"""
        data = request.data
        required_fields = ['hostname', 'ip_address', 'port', 'username', 'auth_key']
        for field in required_fields:
            if not data.get(field):
                return Response({'error': f'Missing required field: {field}'}, status=status.HTTP_400_BAD_REQUEST)

        # Try SSH connection
        import tempfile
        try:
            with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.pem') as keyfile:
                keyfile.write(data['auth_key'])
                keyfile.flush()
                keyfile_path = keyfile.name
            # Build SSH command to test connection (simple 'echo' command)
            ssh_cmd = [
                'ssh',
                '-i', keyfile_path,
                '-o', 'StrictHostKeyChecking=no',
                '-p', str(data['port']),
                f"{data['username']}@{data['ip_address']}",
                'echo onboard-success'
            ]
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0 or 'onboard-success' not in result.stdout:
                os.unlink(keyfile_path)
                return Response({'error': f'SSH connection failed: {result.stderr}'}, status=status.HTTP_400_BAD_REQUEST)

            # Use serverid as string id
            serverid = data.get('serverid') or data.get('hostname') or data.get('ip_address')
            # Ensure id is a string and tags is a valid JSON list
            # Do not create the Node here. Node will be created on websocket connect.
            node = None

            # Copy node_agent.py and required files to remote server
            import shutil

            agent_files = [
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../node_agent.py')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend/node_crypto_utils.py')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend/requirements.txt')),
            ]
            # Optionally add agent_private.pem, agent_public.pem if present
            for fname in ['agent_private.pem', 'agent_public.pem']:
                fpath = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend', fname))
                if os.path.exists(fpath):
                    agent_files.append(fpath)

            # Create agent directory on remote
            agent_dir = '~/alterion_agent'
            mkdir_cmd = [
                'ssh',
                '-i', keyfile_path,
                '-o', 'StrictHostKeyChecking=no',
                '-p', str(data['port']),
                f"{data['username']}@{data['ip_address']}",
                f'mkdir -p {agent_dir}'
            ]
            subprocess.run(mkdir_cmd, capture_output=True, text=True, timeout=15)

            # Copy files
            for f in agent_files:
                scp_cmd = [
                    'scp',
                    '-i', keyfile_path,
                    '-P', str(data['port']),
                    '-o', 'StrictHostKeyChecking=no',
                    f,
                    f"{data['username']}@{data['ip_address']}:{agent_dir}/"
                ]
                subprocess.run(scp_cmd, capture_output=True, text=True, timeout=30)





            # Detect remote OS (simple check)
            detect_os_cmd = [
                'ssh',
                '-i', keyfile_path,
                '-o', 'StrictHostKeyChecking=no',
                '-p', str(data['port']),
                f"{data['username']}@{data['ip_address']}",
                'uname || ver'
            ]
            os_result = subprocess.run(detect_os_cmd, capture_output=True, text=True, timeout=15)
            remote_os = os_result.stdout.lower()

            # Choose install script name and copy it as a fixed name on remote
            if 'windows' in remote_os or 'microsoft' in remote_os or 'win' in remote_os:
                install_script = 'install.bat'
                remote_script = f'{agent_dir}/install.bat'
                run_cmd = f'cd {agent_dir.replace("~", "%USERPROFILE%") } && call install.bat'
            else:
                install_script = 'install.sh'
                remote_script = f'{agent_dir}/install.sh'
                run_cmd = f'cd {agent_dir} && bash install.sh'

            # Copy install script as fixed name
            script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), f'../../backend/{install_script}'))
            scp_cmd = [
                'scp',
                '-i', keyfile_path,
                '-P', str(data['port']),
                '-o', 'StrictHostKeyChecking=no',
                script_path,
                f"{data['username']}@{data['ip_address']}:{remote_script}"
            ]
            subprocess.run(scp_cmd, capture_output=True, text=True, timeout=30)

            # Ensure script is executable (for Linux/macOS)
            if not ('windows' in remote_os or 'microsoft' in remote_os or 'win' in remote_os):
                chmod_cmd = [
                    'ssh',
                    '-i', keyfile_path,
                    '-o', 'StrictHostKeyChecking=no',
                    '-p', str(data['port']),
                    f"{data['username']}@{data['ip_address']}",
                    f'chmod +x {remote_script}'
                ]
                subprocess.run(chmod_cmd, capture_output=True, text=True, timeout=10)

            # Start install and stream output to a progress file, with progress markers
            progress_file = f'/tmp/alterion_install_{serverid}.log'
            # Compose a wrapper script to echo progress markers
            progress_steps = [
                ('10', 'Creating venv'),
                ('30', 'Upgrading pip/setuptools'),
                ('60', 'Installing requirements.txt'),
                ('90', 'Launching node agent'),
                ('100', 'Installation complete!'),
            ]
            if 'windows' in remote_os or 'microsoft' in remote_os or 'win' in remote_os:
                # Windows: use a .bat wrapper
                wrapper_script = f"%TEMP%\\alterion_install_{serverid}.bat"
                wrapper_lines = [
                    f'@echo off',
                    f'echo __PROGRESS__:10:Creating venv > {progress_file}',
                    f'python -m venv venv >> {progress_file} 2>&1',
                    f'echo __PROGRESS__:30:Upgrading pip/setuptools >> {progress_file}',
                    f'call venv\\Scripts\\activate.bat >> {progress_file} 2>&1',
                    f'python -m pip install --upgrade pip setuptools wheel >> {progress_file} 2>&1',
                    f'echo __PROGRESS__:60:Installing requirements.txt >> {progress_file}',
                    f'pip install -r requirements.txt >> {progress_file} 2>&1',
                    f'echo __PROGRESS__:90:Launching node agent >> {progress_file}',
                    f'python node_agent.py >> {progress_file} 2>&1',
                    f'echo __PROGRESS__:100:Installation complete! >> {progress_file}',
                    f'echo __INSTALL_DONE__ >> {progress_file}'
                ]
                with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.bat') as batf:
                    batf.write('\n'.join(wrapper_lines))
                    batf.flush()
                    wrapper_path = batf.name
                # Copy wrapper to remote
                scp_cmd = [
                    'scp',
                    '-i', keyfile_path,
                    '-P', str(data['port']),
                    '-o', 'StrictHostKeyChecking=no',
                    wrapper_path,
                    f"{data['username']}@{data['ip_address']}:{agent_dir}/alterion_install_{serverid}.bat"
                ]
                subprocess.run(scp_cmd, capture_output=True, text=True, timeout=30)
                # Run wrapper in background
                install_cmd = [
                    'ssh',
                    '-i', keyfile_path,
                    '-o', 'StrictHostKeyChecking=no',
                    '-p', str(data['port']),
                    f"{data['username']}@{data['ip_address']}",
                    f'cd {agent_dir.replace("~", "%USERPROFILE%") } && start /b alterion_install_{serverid}.bat'
                ]
                subprocess.run(install_cmd, capture_output=True, text=True, timeout=10)
                os.unlink(wrapper_path)
            else:
                # Linux/macOS: use a .sh wrapper
                wrapper_script = f"/tmp/alterion_install_{serverid}.sh"
                wrapper_lines = [
                    '#!/bin/bash',
                    f'echo __PROGRESS__:10:Creating venv > {progress_file}',
                    'python3 -m venv venv >> {progress_file} 2>&1',
                    f'echo __PROGRESS__:30:Upgrading pip/setuptools >> {progress_file}',
                    'source venv/bin/activate >> {progress_file} 2>&1',
                    'python -m pip install --upgrade pip setuptools wheel >> {progress_file} 2>&1',
                    f'echo __PROGRESS__:60:Installing requirements.txt >> {progress_file}',
                    'pip install -r requirements.txt >> {progress_file} 2>&1',
                    f'echo __PROGRESS__:90:Launching node agent >> {progress_file}',
                    'python node_agent.py >> {progress_file} 2>&1',
                    f'echo __PROGRESS__:100:Installation complete! >> {progress_file}',
                    'echo __INSTALL_DONE__ >> {progress_file}'
                ]
                with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.sh') as shf:
                    shf.write('\n'.join(wrapper_lines))
                    shf.flush()
                    wrapper_path = shf.name
                # Copy wrapper to remote
                scp_cmd = [
                    'scp',
                    '-i', keyfile_path,
                    '-P', str(data['port']),
                    '-o', 'StrictHostKeyChecking=no',
                    wrapper_path,
                    f"{data['username']}@{data['ip_address']}:{agent_dir}/alterion_install_{serverid}.sh"
                ]
                subprocess.run(scp_cmd, capture_output=True, text=True, timeout=30)
                # Run wrapper in background
                install_cmd = [
                    'ssh',
                    '-i', keyfile_path,
                    '-o', 'StrictHostKeyChecking=no',
                    '-p', str(data['port']),
                    f"{data['username']}@{data['ip_address']}",
                    f'cd {agent_dir} && bash alterion_install_{serverid}.sh &'
                ]
                subprocess.run(install_cmd, capture_output=True, text=True, timeout=10)
                os.unlink(wrapper_path)
            os.unlink(keyfile_path)

            return Response({'success': True, 'message': 'Agent install triggered. Node will be added on websocket connect.', 'progress_file': progress_file, 'serverid': serverid})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    """
    ViewSet for managing remote nodes/servers
    """
    serializer_class = NodeSerializer
    authentication_classes = [CookieOAuth2Authentication]
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Node.objects.filter(owner=self.request.user)
        status_param = self.request.query_params.get('status')
        if status_param:
            if status_param == 'pending':
                # Only return nodes that are not connected via websocket (no active agent)
                # TODO: Integrate with actual websocket connection tracking
                queryset = queryset.filter(status='pending')
            elif status_param == 'online':
                queryset = queryset.filter(status='online')
            else:
                queryset = queryset.filter(status=status_param)
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
    
    @action(detail=True, methods=['post'])
    def collect_metrics(self, request, pk=None):
        """Collect metrics from this node"""
        node = self.get_object()
        
        try:
            # Execute node_agent.py on remote server via SSH
            metrics_data = self._execute_node_command(node, 'collect_metrics')
            
            if 'error' in metrics_data:
                node.update_status(False, metrics_data['error'])
                return Response(
                    {'error': metrics_data['error']},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Update node status
            node.update_status(True)
            
            # Update system info
            if 'system' in metrics_data:
                node.update_system_info(metrics_data['system'])
            
            # Store metrics
            if 'cpu' in metrics_data and 'memory' in metrics_data:
                memory_data = metrics_data['memory']
                
                NodeMetrics.objects.create(
                    node=node,
                    cpu_usage=metrics_data['cpu'].get('usage_percent', 0),
                    cpu_load_avg=metrics_data['cpu'].get('load_avg'),
                    memory_used=memory_data.get('used', 0),
                    memory_total=memory_data.get('total', 0),
                    memory_percent=memory_data.get('percent', 0),
                    swap_used=memory_data.get('swap', {}).get('used'),
                    swap_percent=memory_data.get('swap', {}).get('percent'),
                    disk_usage=metrics_data.get('disk', {}).get('usage', {}),
                    network_bytes_sent=metrics_data.get('network', {}).get('io', {}).get('bytes_sent'),
                    network_bytes_recv=metrics_data.get('network', {}).get('io', {}).get('bytes_recv'),
                    network_connections=metrics_data.get('network', {}).get('connections'),
                    process_count=metrics_data.get('processes', {}).get('count'),
                    full_metrics=metrics_data
                )
            
            # Update services
            if 'services' in metrics_data:
                for service_type, service_data in metrics_data['services'].items():
                    NodeService.objects.update_or_create(
                        node=node,
                        service_type=service_type,
                        defaults={
                            'service_name': service_data.get('name', service_type),
                            'is_running': service_data.get('running', False),
                        }
                    )
            
            return Response(metrics_data)
            
        except Exception as e:
            node.update_status(False, str(e))
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def latest_metrics(self, request, pk=None):
        """Get latest metrics for this node - fetches live via WebSocket proxy"""
        from .node_api_client import call_node_api_sync
        
        node = self.get_object()
        
        # Try to fetch live metrics via WebSocket proxy
        try:
            result = call_node_api_sync(node.id, 'collect_metrics', {})
            if result and not result.get('error'):
                return Response(result)
        except Exception as e:
            logger.error(f"[LATEST_METRICS] Failed to fetch live metrics for {node.id}: {e}")
        
        # Fallback to database metrics if WebSocket fails
        latest = node.metrics.first()
        if not latest:
            return Response({'error': 'No metrics available'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = NodeMetricsSerializer(latest)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def metrics_history(self, request, pk=None):
        """Get metrics history for this node"""
        node = self.get_object()
        hours = int(request.query_params.get('hours', 24))
        
        since = timezone.now() - timezone.timedelta(hours=hours)
        metrics = node.metrics.filter(timestamp__gte=since)
        
        serializer = NodeMetricsSerializer(metrics, many=True)
        return Response(serializer.data)
    
        status='pending',
    def alerts(self, request, pk=None):
        """Get alerts for this node"""
        node = self.get_object()
        show_resolved = request.query_params.get('resolved', 'false').lower() == 'true'
        
        if show_resolved:
            alerts = node.alerts.all()
        else:
            alerts = node.alerts.filter(resolved=False)
        
        serializer = NodeAlertSerializer(alerts, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def services(self, request, pk=None):
        """Get services running on this node"""
        node = self.get_object()
        services = node.services.all()
        
        serializer = NodeServiceSerializer(services, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def list_files(self, request, pk=None):
        """List files on the node"""
        node = self.get_object()
        path = request.data.get('path', '/')
        
        try:
            result = self._execute_node_command(node, 'list_files', [path])
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def read_file(self, request, pk=None):
        """Read a file from the node"""
        node = self.get_object()
        path = request.data.get('path')
        max_lines = request.data.get('max_lines')
        
        if not path:
            return Response({'error': 'path is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            args = ['read_file', path]
            if max_lines:
                args.extend(['--max-lines', str(max_lines)])
            
            result = self._execute_node_command(node, args[0], args[1:])
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def nginx_config(self, request, pk=None):
        """Get Nginx configuration info"""
        node = self.get_object()
        
        try:
            result = self._execute_node_command(node, 'check_nginx')
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def firewall_status(self, request, pk=None):
        """Get firewall status"""
        node = self.get_object()
        
        try:
            result = self._execute_node_command(node, 'check_firewall')
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """Test connection to the node"""
        node = self.get_object()
        
        try:
            result = self._execute_node_command(node, 'system_info')
            node.update_status(True)
            return Response({'status': 'connected', 'system': result})
        except Exception as e:
            node.update_status(False, str(e))
            return Response(
                {'status': 'failed', 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _execute_node_command(self, node, command, args=None):
        """Execute a command on the remote node via SSH"""
        # Path to node_agent.py
        agent_path = os.path.join(os.path.dirname(__file__), '..', '..', 'node_agent.py')
        
        # Build SSH command
        ssh_cmd = [
            'ssh',
            '-i', node.auth_key,  # SSH key path
            '-o', 'StrictHostKeyChecking=no',
            '-p', str(node.port),
            f'{node.username}@{node.ip_address}',
            f'python3 {agent_path} {command}'
        ]
        
        if args:
            ssh_cmd[-1] += ' ' + ' '.join(args)
        
        # Execute command
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            raise Exception(f"Command failed: {result.stderr}")
        
        # Parse JSON output
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {'output': result.stdout}


class NodeAlertViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for node alerts
    """
    serializer_class = NodeAlertSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieOAuth2Authentication]
    
    def get_queryset(self):
        return NodeAlert.objects.filter(node__owner=self.request.user)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve an alert"""
        alert = self.get_object()
        alert.resolved = True
        alert.resolved_at = timezone.now()
        alert.resolved_by = request.user
        alert.save()
        
        serializer = self.get_serializer(alert)
        return Response(serializer.data)
