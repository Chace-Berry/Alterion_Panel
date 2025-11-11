"""
File Manager and FTP views for remote server file management
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from authentication.cookie_oauth2 import CookieOAuth2Authentication
from django.shortcuts import get_object_or_404
from dashboard.models import Server
import paramiko
import os
import stat
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class FileManagerViewSet(viewsets.ViewSet):
    """
    ViewSet for managing files on remote servers via SFTP
    """
    authentication_classes = [CookieOAuth2Authentication]
    permission_classes = [IsAuthenticated]

    def _get_sftp_client(self, server):
        """Establish SFTP connection to server"""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        ssh.connect(
            hostname=server.ip_address,
            username=getattr(server, 'ssh_user', 'root'),
            password=getattr(server, 'ssh_password', None),
            key_filename=getattr(server, 'ssh_key', None),
            port=getattr(server, 'ssh_port', 22),
            timeout=10
        )
        
        sftp = ssh.open_sftp()
        return ssh, sftp

    def _format_file_info(self, sftp, path, filename):
        """Format file information for response"""
        # Use forward slashes for remote paths (works on both Windows and Linux)
        filepath = path.rstrip('/') + '/' + filename if path != '/' else '/' + filename
        try:
            attrs = sftp.stat(filepath)
            is_dir = stat.S_ISDIR(attrs.st_mode)
            
            return {
                'name': filename,
                'path': filepath,
                'size': attrs.st_size if not is_dir else 0,
                'modified': datetime.fromtimestamp(attrs.st_mtime).isoformat(),
                'permissions': oct(stat.S_IMODE(attrs.st_mode)),
                'type': 'directory' if is_dir else 'file',
                'is_directory': is_dir,
                'is_file': stat.S_ISREG(attrs.st_mode),
                'is_link': stat.S_ISLNK(attrs.st_mode),
            }
        except Exception as e:
            return {
                'name': filename,
                'path': filepath,
                'error': str(e)
            }

    @action(detail=True, methods=['get'], url_path='list')
    def list_files(self, request, pk=None):
        """List files in a directory (supports local, node, and remote servers)"""
        path = request.query_params.get('path', '/')
        home_directory = None
        logger.info(f"[FILE_MANAGER] list_files called - pk: {pk}, path: {path}")
        # Handle node agent requests via direct SFTP
        if pk and pk.startswith('node-'):
            from .node_sftp_client import get_node_sftp_connection, close_sftp_connection
            from .credential_manager import get_node_ssh_username
            from .node_models import Node
            
            node_id = pk  # pk already includes 'node-' prefix
            logger.info(f"[FILE_MANAGER] Routing to node via SFTP: {node_id}")
            
            ssh = None
            sftp = None
            try:
                # Get node info for home directory calculation
                node = Node.objects.get(id=node_id)
                ssh_user = get_node_ssh_username(node_id) or 'root'
                platform = (getattr(node, 'platform', None) or 'Linux').lower()
                
                # Determine home directory based on platform
                if 'windows' in platform:
                    home_directory = f"C:/Users/{ssh_user}"
                elif 'darwin' in platform or 'mac' in platform:
                    home_directory = f"/Users/{ssh_user}"
                else:  # Linux and others
                    home_directory = f"/home/{ssh_user}" if ssh_user != 'root' else '/root'
                
                # If path is '/', redirect to home directory
                if path == '/':
                    path = home_directory
                
                # Establish SFTP connection
                ssh, sftp = get_node_sftp_connection(node_id)
                
                # List directory contents
                items = []
                for filename in sftp.listdir(path):
                    file_info = self._format_file_info(sftp, path, filename)
                    items.append(file_info)
                
                logger.info(f"[FILE_MANAGER] Successfully retrieved {len(items)} files via SFTP")
                return Response({'files': items, 'path': path, 'home_directory': home_directory})
                
            except Exception as e:
                logger.error(f"[FILE_MANAGER] SFTP error: {e}", exc_info=True)
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            finally:
                close_sftp_connection(ssh, sftp)
        # Handle local server requests
        elif pk and pk.startswith('local-'):
            import pathlib
            home_directory = str(pathlib.Path.home())
            try:
                norm_path = os.path.expandvars(os.path.expanduser(path))
                norm_path = os.path.normpath(norm_path)
                if os.name == 'nt':
                    norm_path = str(pathlib.Path(norm_path).resolve())
                if not os.path.exists(norm_path):
                    return Response({'error': f'Path does not exist: {norm_path}'}, status=status.HTTP_400_BAD_REQUEST)
                files = []
                for filename in os.listdir(norm_path):
                    filepath = os.path.join(norm_path, filename)
                    try:
                        attrs = os.stat(filepath)
                        is_dir = stat.S_ISDIR(attrs.st_mode)
                        files.append({
                            'name': filename,
                            'path': filepath,
                            'size': attrs.st_size if not is_dir else 0,
                            'modified': datetime.fromtimestamp(attrs.st_mtime).isoformat(),
                            'permissions': oct(stat.S_IMODE(attrs.st_mode)),
                            'type': 'directory' if is_dir else 'file',
                            'is_directory': is_dir,
                            'is_file': stat.S_ISREG(attrs.st_mode),
                            'is_link': stat.S_ISLNK(attrs.st_mode),
                        })
                    except Exception as e:
                        files.append({
                            'name': filename,
                            'path': filepath,
                            'error': str(e)
                        })
                files.sort(key=lambda x: (not x.get('is_directory', False), x['name'].lower()))
                return Response({'path': norm_path, 'files': files, 'home_directory': home_directory})
            except Exception as e:
                return Response({'error': f'Failed to list local directory: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            server = get_object_or_404(Server, pk=pk)
            ssh_user = getattr(server, 'ssh_user', 'root')
            os_type = getattr(server, 'os_type', 'linux')
            if os_type == 'windows':
                home_directory = f"C:/Users/{ssh_user}"
            elif os_type == 'mac':
                home_directory = f"/Users/{ssh_user}"
            else:
                home_directory = f"/home/{ssh_user}"
            try:
                ssh, sftp = self._get_sftp_client(server)
                try:
                    files = []
                    for filename in sftp.listdir(path):
                        file_info = self._format_file_info(sftp, path, filename)
                        files.append(file_info)
                    files.sort(key=lambda x: (not x.get('is_directory', False), x['name'].lower()))
                    return Response({'path': path, 'files': files, 'home_directory': home_directory})
                finally:
                    sftp.close()
                    ssh.close()
            except Exception as e:
                return Response(
                    {'error': f'Failed to list directory: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

    @action(detail=True, methods=['post'], url_path='prepare-download')
    def prepare_download(self, request, pk=None):
        """Prepare a download (create archive) and return task ID for progress tracking"""
        from django.core.cache import cache
        import uuid
        import threading
        
        remote_path = request.data.get('path')
        
        if not remote_path:
            return Response(
                {'error': 'File path is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Initialize progress in cache
        cache.set(f'download_progress_{task_id}', {
            'status': 'preparing',
            'progress': 0,
            'message': 'Starting download preparation...'
        }, timeout=3600)
        
        # Start background thread to create archive
        def create_archive():
            import tempfile
            import zipfile
            import subprocess
            import shutil
            import os
            import pathlib
            
            try:
                # Handle local server
                if pk and pk.startswith('local-'):
                    norm_path = os.path.expandvars(os.path.expanduser(remote_path))
                    norm_path = os.path.normpath(norm_path)
                    if os.name == 'nt':
                        norm_path = str(pathlib.Path(norm_path).resolve())
                    
                    if not os.path.exists(norm_path):
                        cache.set(f'download_progress_{task_id}', {
                            'status': 'error',
                            'progress': 0,
                            'message': f'Path does not exist: {norm_path}'
                        }, timeout=3600)
                        return
                    
                    is_dir = os.path.isdir(norm_path)
                    
                    if is_dir:
                        cache.set(f'download_progress_{task_id}', {
                            'status': 'preparing',
                            'progress': 10,
                            'message': 'Creating archive...'
                        }, timeout=3600)
                        
                        temp_dir = tempfile.mkdtemp()
                        archive_file = None
                        filename = None
                        
                        # Count total files for progress
                        total_files = sum([len(files) for _, _, files in os.walk(norm_path)])
                        processed_files = 0
                        
                        cache.set(f'download_progress_{task_id}', {
                            'status': 'preparing',
                            'progress': 20,
                            'message': f'Archiving {total_files} files...'
                        }, timeout=3600)
                        
                        # Try RAR first
                        rar_command = None
                        if os.name == 'nt':
                            possible_paths = [
                                r"C:\Program Files\WinRAR\Rar.exe",
                                r"C:\Program Files (x86)\WinRAR\Rar.exe",
                                "rar.exe"
                            ]
                        else:
                            possible_paths = [
                                "/usr/bin/rar",
                                "/usr/local/bin/rar",
                                "rar"
                            ]
                        
                        for rar_path in possible_paths:
                            if shutil.which(rar_path) or os.path.exists(rar_path):
                                rar_command = rar_path
                                break
                        
                        if rar_command:
                            try:
                                archive_file = os.path.join(temp_dir, os.path.basename(norm_path) + '.rar')
                                subprocess.run(
                                    [rar_command, 'a', '-m0', '-r', archive_file, norm_path],
                                    check=True,
                                    capture_output=True,
                                    cwd=temp_dir
                                )
                                filename = os.path.basename(norm_path) + '.rar'
                            except:
                                rar_command = None
                        
                        if not rar_command:
                            # ZIP with progress tracking
                            archive_file = os.path.join(temp_dir, os.path.basename(norm_path) + '.zip')
                            with zipfile.ZipFile(archive_file, 'w', zipfile.ZIP_STORED) as zipf:
                                for root, dirs, files in os.walk(norm_path):
                                    for file in files:
                                        file_path = os.path.join(root, file)
                                        arcname = os.path.relpath(file_path, os.path.dirname(norm_path))
                                        zipf.write(file_path, arcname)
                                        processed_files += 1
                                        progress = 20 + int((processed_files / total_files) * 70)
                                        cache.set(f'download_progress_{task_id}', {
                                            'status': 'preparing',
                                            'progress': progress,
                                            'message': f'Archiving... {processed_files}/{total_files} files'
                                        }, timeout=3600)
                            filename = os.path.basename(norm_path) + '.zip'
                        
                        # Store archive info
                        cache.set(f'download_file_{task_id}', {
                            'path': archive_file,
                            'filename': filename,
                            'temp_dir': temp_dir
                        }, timeout=3600)
                        
                        cache.set(f'download_progress_{task_id}', {
                            'status': 'ready',
                            'progress': 100,
                            'message': 'Archive ready for download'
                        }, timeout=3600)
                    else:
                        # Single file - no archiving needed
                        cache.set(f'download_file_{task_id}', {
                            'path': norm_path,
                            'filename': os.path.basename(norm_path),
                            'temp_dir': None
                        }, timeout=3600)
                        
                        cache.set(f'download_progress_{task_id}', {
                            'status': 'ready',
                            'progress': 100,
                            'message': 'File ready for download'
                        }, timeout=3600)
                        
            except Exception as e:
                cache.set(f'download_progress_{task_id}', {
                    'status': 'error',
                    'progress': 0,
                    'message': f'Failed to prepare download: {str(e)}'
                }, timeout=3600)
        
        thread = threading.Thread(target=create_archive)
        thread.daemon = True
        thread.start()
        
        return Response({'task_id': task_id})
    
    @action(detail=True, methods=['get'], url_path='download-progress')
    def download_progress(self, request, pk=None):
        """Get download preparation progress"""
        from django.core.cache import cache
        
        task_id = request.query_params.get('task_id')
        if not task_id:
            return Response({'error': 'task_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        progress_data = cache.get(f'download_progress_{task_id}')
        if not progress_data:
            return Response({'error': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(progress_data)
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download a prepared file"""
        from django.http import FileResponse
        from django.core.cache import cache
        import shutil
        
        task_id = request.query_params.get('task_id')
        
        if not task_id:
            return Response({'error': 'task_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get file info from cache
        file_info = cache.get(f'download_file_{task_id}')
        if not file_info:
            return Response({'error': 'Download not ready or expired'}, status=status.HTTP_404_NOT_FOUND)
        
        file_path = file_info['path']
        filename = file_info['filename']
        temp_dir = file_info.get('temp_dir')
        
        if not os.path.exists(file_path):
            return Response({'error': 'File not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Clean up temp directory after download if exists
        def cleanup_temp():
            try:
                if temp_dir and os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                cache.delete(f'download_progress_{task_id}')
                cache.delete(f'download_file_{task_id}')
            except:
                pass
        
        response = FileResponse(
            open(file_path, 'rb'),
            content_type='application/octet-stream'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Schedule cleanup
        import threading
        threading.Timer(60, cleanup_temp).start()
        
        return response

    @action(detail=True, methods=['post'])
    def upload(self, request, pk=None):
        """Upload a file to server or local/node"""
        remote_path = request.data.get('path')
        file_obj = request.FILES.get('file')
        if not remote_path or not file_obj:
            return Response({'error': 'Path and file are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Handle node agent requests via direct SFTP
        if pk and pk.startswith('node-'):
            from .node_sftp_client import get_node_sftp_connection, close_sftp_connection
            node_id = pk
            
            ssh = None
            sftp = None
            try:
                ssh, sftp = get_node_sftp_connection(node_id)
                remote_filepath = os.path.join(remote_path, file_obj.name)
                sftp.putfo(file_obj, remote_filepath)
                return Response({'message': 'File uploaded successfully', 'path': remote_filepath})
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            finally:
                close_sftp_connection(ssh, sftp)
        
        # Handle local server requests
        elif pk and pk.startswith('local-'):
            try:
                dest_path = os.path.join(remote_path, file_obj.name)
                with open(dest_path, 'wb+') as f:
                    for chunk in file_obj.chunks():
                        f.write(chunk)
                return Response({'message': 'File uploaded successfully', 'path': dest_path})
            except Exception as e:
                return Response({'error': f'Failed to upload file: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            server = get_object_or_404(Server, pk=pk)
            try:
                ssh, sftp = self._get_sftp_client(server)
                try:
                    remote_filepath = os.path.join(remote_path, file_obj.name)
                    sftp.putfo(file_obj, remote_filepath)
                    return Response({'message': 'File uploaded successfully', 'path': remote_filepath})
                finally:
                    sftp.close()
                    ssh.close()
            except Exception as e:
                return Response({'error': f'Failed to upload file: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def create_directory(self, request, pk=None):
        """Create a new directory (local/node/server)"""
        path = request.data.get('path')
        if not path:
            return Response({'error': 'Directory path is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Handle node agent requests via direct SFTP
        if pk and pk.startswith('node-'):
            from .node_sftp_client import get_node_sftp_connection, close_sftp_connection
            node_id = pk
            
            ssh = None
            sftp = None
            try:
                ssh, sftp = get_node_sftp_connection(node_id)
                sftp.mkdir(path)
                return Response({'message': 'Directory created successfully'})
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            finally:
                close_sftp_connection(ssh, sftp)
        
        # Handle local server requests
        elif pk and pk.startswith('local-'):
            try:
                os.makedirs(path, exist_ok=True)
                return Response({'message': 'Directory created successfully'})
            except Exception as e:
                return Response({'error': f'Failed to create directory: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            server = get_object_or_404(Server, pk=pk)
            try:
                ssh, sftp = self._get_sftp_client(server)
                try:
                    sftp.mkdir(path)
                    return Response({'message': 'Directory created successfully'})
                finally:
                    sftp.close()
                    ssh.close()
            except Exception as e:
                return Response({'error': f'Failed to create directory: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['delete'])
    def delete(self, request, pk=None):
        """Delete a file or directory (local/node/server)"""
        path = request.query_params.get('path')
        if not path:
            return Response({'error': 'Path is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Handle node agent requests via direct SFTP
        if pk and pk.startswith('node-'):
            from .node_sftp_client import get_node_sftp_connection, close_sftp_connection
            import stat
            node_id = pk
            
            ssh = None
            sftp = None
            try:
                ssh, sftp = get_node_sftp_connection(node_id)
                attrs = sftp.stat(path)
                if stat.S_ISDIR(attrs.st_mode):
                    sftp.rmdir(path)
                else:
                    sftp.remove(path)
                return Response({'message': 'Deleted successfully'})
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            finally:
                close_sftp_connection(ssh, sftp)
        
        # Handle local server requests
        elif pk and pk.startswith('local-'):
            try:
                if os.path.isdir(path):
                    os.rmdir(path)
                else:
                    os.remove(path)
                return Response({'message': 'Deleted successfully'})
            except Exception as e:
                return Response({'error': f'Failed to delete: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            server = get_object_or_404(Server, pk=pk)
            try:
                ssh, sftp = self._get_sftp_client(server)
                try:
                    attrs = sftp.stat(path)
                    if stat.S_ISDIR(attrs.st_mode):
                        sftp.rmdir(path)
                    else:
                        sftp.remove(path)
                    return Response({'message': 'Deleted successfully'})
                finally:
                    sftp.close()
                    ssh.close()
            except Exception as e:
                return Response({'error': f'Failed to delete: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def rename(self, request, pk=None):
        """Rename a file or directory (local/node/server)"""
        old_path = request.data.get('old_path')
        new_path = request.data.get('new_path')
        if not old_path or not new_path:
            return Response({'error': 'Both old_path and new_path are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Handle node agent requests via direct SFTP
        if pk and pk.startswith('node-'):
            from .node_sftp_client import get_node_sftp_connection, close_sftp_connection
            node_id = pk
            
            ssh = None
            sftp = None
            try:
                ssh, sftp = get_node_sftp_connection(node_id)
                sftp.rename(old_path, new_path)
                return Response({'message': 'Renamed successfully'})
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            finally:
                close_sftp_connection(ssh, sftp)
        
        # Handle local server requests
        elif pk and pk.startswith('local-'):
            try:
                os.rename(old_path, new_path)
                return Response({'message': 'Renamed successfully'})
            except Exception as e:
                return Response({'error': f'Failed to rename: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            server = get_object_or_404(Server, pk=pk)
            try:
                ssh, sftp = self._get_sftp_client(server)
                try:
                    sftp.rename(old_path, new_path)
                    return Response({'message': 'Renamed successfully'})
                finally:
                    sftp.close()
                    ssh.close()
            except Exception as e:
                return Response({'error': f'Failed to rename: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def read_file(self, request, pk=None):
        """Read file contents (for text files, local/node/server)"""
        path = request.query_params.get('path')
        if not path:
            return Response({'error': 'File path is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Handle node agent requests via direct SFTP
        if pk and pk.startswith('node-'):
            from .node_sftp_client import get_node_sftp_connection, close_sftp_connection
            node_id = pk
            
            ssh = None
            sftp = None
            try:
                ssh, sftp = get_node_sftp_connection(node_id)
                with sftp.file(path, 'r') as f:
                    content = f.read().decode('utf-8', errors='replace')
                return Response({'path': path, 'content': content})
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            finally:
                close_sftp_connection(ssh, sftp)
        
        # Handle local server requests
        elif pk and pk.startswith('local-'):
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                return Response({'path': path, 'content': content})
            except Exception as e:
                return Response({'error': f'Failed to read file: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            server = get_object_or_404(Server, pk=pk)
            try:
                ssh, sftp = self._get_sftp_client(server)
                try:
                    with sftp.file(path, 'r') as f:
                        content = f.read().decode('utf-8', errors='replace')
                    return Response({'path': path, 'content': content})
                finally:
                    sftp.close()
                    ssh.close()
            except Exception as e:
                return Response({'error': f'Failed to read file: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def write_file(self, request, pk=None):
        """Write content to a file (local/node/server)"""
        path = request.data.get('path')
        content = request.data.get('content')
        if not path or content is None:
            return Response({'error': 'Path and content are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Handle node agent requests via direct SFTP
        if pk and pk.startswith('node-'):
            from .node_sftp_client import get_node_sftp_connection, close_sftp_connection
            node_id = pk
            
            ssh = None
            sftp = None
            try:
                ssh, sftp = get_node_sftp_connection(node_id)
                with sftp.file(path, 'w') as f:
                    f.write(content.encode('utf-8'))
                return Response({'message': 'File saved successfully'})
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            finally:
                close_sftp_connection(ssh, sftp)
        
        # Handle local server requests
        elif pk and pk.startswith('local-'):
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return Response({'message': 'File saved successfully'})
            except Exception as e:
                return Response({'error': f'Failed to write file: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            server = get_object_or_404(Server, pk=pk)
            try:
                ssh, sftp = self._get_sftp_client(server)
                try:
                    with sftp.file(path, 'w') as f:
                        f.write(content.encode('utf-8'))
                    return Response({'message': 'File saved successfully'})
                finally:
                    sftp.close()
                    ssh.close()
            except Exception as e:
                return Response({'error': f'Failed to write file: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
