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
        filepath = os.path.join(path, filename)
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
        if pk and (pk.startswith('local-') or pk.startswith('node-')):
            # Local or node file listing (Windows path normalization)
            import pathlib
            try:
                # Normalize and expand user/vars
                norm_path = os.path.expandvars(os.path.expanduser(path))
                norm_path = os.path.normpath(norm_path)
                # On Windows, ensure drive letter is uppercase and slashes are correct
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
                return Response({'path': norm_path, 'files': files})
            except Exception as e:
                return Response({'error': f'Failed to list local/node directory: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            # Remote server (SFTP)
            server = get_object_or_404(Server, pk=pk)
            try:
                ssh, sftp = self._get_sftp_client(server)
                try:
                    files = []
                    for filename in sftp.listdir(path):
                        file_info = self._format_file_info(sftp, path, filename)
                        files.append(file_info)
                    files.sort(key=lambda x: (not x.get('is_directory', False), x['name'].lower()))
                    return Response({'path': path, 'files': files})
                finally:
                    sftp.close()
                    ssh.close()
            except Exception as e:
                return Response(
                    {'error': f'Failed to list directory: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download a file or directory (as ZIP) from server"""
        from django.http import FileResponse
        import tempfile
        import zipfile
        import os
        
        server = get_object_or_404(Server, pk=pk)
        remote_path = request.query_params.get('path')
        
        if not remote_path:
            return Response(
                {'error': 'File path is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            ssh, sftp = self._get_sftp_client(server)
            
            try:
                # Check if it's a directory
                try:
                    attrs = sftp.stat(remote_path)
                    is_dir = stat.S_ISDIR(attrs.st_mode)
                except:
                    is_dir = False
                
                if is_dir:
                    # Create ZIP file for directory
                    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
                    with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        # Walk through directory and add files
                        def add_to_zip(sftp_client, path, zip_file, base_path):
                            try:
                                for item in sftp_client.listdir(path):
                                    item_path = os.path.join(path, item)
                                    try:
                                        item_attrs = sftp_client.stat(item_path)
                                        if stat.S_ISDIR(item_attrs.st_mode):
                                            # Recursively add directory
                                            add_to_zip(sftp_client, item_path, zip_file, base_path)
                                        else:
                                            # Add file
                                            with sftp_client.file(item_path, 'rb') as f:
                                                zip_file.writestr(os.path.relpath(item_path, base_path), f.read())
                                    except Exception as e:
                                        # Skip files that can't be read
                                        continue
                            except:
                                pass
                        
                        add_to_zip(sftp, remote_path, zipf, os.path.dirname(remote_path))
                    
                    temp_zip.close()
                    
                    # Return ZIP file response
                    filename = os.path.basename(remote_path) + '.zip'
                    response = FileResponse(
                        open(temp_zip.name, 'rb'),
                        as_attachment=True,
                        filename=filename
                    )
                    
                    # Clean up temp file after response
                    os.unlink(temp_zip.name)
                    
                    return response
                else:
                    # Download single file
                    temp_file = tempfile.NamedTemporaryFile(delete=False)
                    sftp.get(remote_path, temp_file.name)
                    temp_file.close()
                    
                    # Return file response
                    filename = os.path.basename(remote_path)
                    response = FileResponse(
                        open(temp_file.name, 'rb'),
                        as_attachment=True,
                        filename=filename
                    )
                    
                    # Clean up temp file after response
                    os.unlink(temp_file.name)
                    
                    return response
            finally:
                sftp.close()
                ssh.close()
                
        except Exception as e:
            return Response(
                {'error': f'Failed to download: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def upload(self, request, pk=None):
        """Upload a file to server or local/node"""
        remote_path = request.data.get('path')
        file_obj = request.FILES.get('file')
        if not remote_path or not file_obj:
            return Response({'error': 'Path and file are required'}, status=status.HTTP_400_BAD_REQUEST)
        if pk and (pk.startswith('local-') or pk.startswith('node-')):
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
        if pk and (pk.startswith('local-') or pk.startswith('node-')):
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
        if pk and (pk.startswith('local-') or pk.startswith('node-')):
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
        if pk and (pk.startswith('local-') or pk.startswith('node-')):
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
        if pk and (pk.startswith('local-') or pk.startswith('node-')):
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
        if pk and (pk.startswith('local-') or pk.startswith('node-')):
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
