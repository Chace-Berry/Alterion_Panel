"""
File manager operations for node agent
Handles local file operations on the node
"""
import os
import stat
import shutil
import base64
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


async def list_files(path="."):
    """List files in a directory"""
    import asyncio
    
    def _list():
        try:
            logger.info(f"[SFTP] list_files called with path: {path}")
            # Normalize and expand path
            norm_path = os.path.expandvars(os.path.expanduser(path))
            norm_path = os.path.normpath(norm_path)
            logger.info(f"[SFTP] Normalized path: {norm_path}")
            
            if not os.path.exists(norm_path):
                logger.error(f"[SFTP] Path does not exist: {norm_path}")
                return {"error": f"Path does not exist: {norm_path}"}
            
            logger.info(f"[SFTP] Path exists, listing contents...")
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
            
            # Sort: directories first, then by name
            files.sort(key=lambda x: (not x.get('is_directory', False), x['name'].lower()))
            
            home_directory = str(Path.home())
            logger.info(f"[SFTP] Successfully listed {len(files)} items in {norm_path}")
            return {'path': norm_path, 'files': files, 'home_directory': home_directory}
            
        except Exception as e:
            logger.error(f"[SFTP] Error in list_files: {e}", exc_info=True)
            return {"error": str(e)}
    
    return await asyncio.to_thread(_list)


async def read_file(path):
    """Read file contents"""
    import asyncio
    
    def _read():
        try:
            logger.info(f"[SFTP] read_file called with path: {path}")
            norm_path = os.path.expandvars(os.path.expanduser(path))
            norm_path = os.path.normpath(norm_path)
            logger.info(f"[SFTP] Reading file: {norm_path}")
            
            if not os.path.exists(norm_path):
                return {"error": f"File does not exist: {norm_path}"}
            
            if not os.path.isfile(norm_path):
                return {"error": f"Path is not a file: {norm_path}"}
            
            with open(norm_path, 'rb') as f:
                content = f.read()
            
            # Try to decode as UTF-8, fallback to base64 for binary files
            try:
                content_str = content.decode('utf-8')
                return {'path': norm_path, 'content': content_str}
            except UnicodeDecodeError:
                # Binary file - return base64 encoded
                content_b64 = base64.b64encode(content).decode('ascii')
                return {'path': norm_path, 'content': content_b64, 'encoding': 'base64'}
                
        except Exception as e:
            return {"error": str(e)}
    
    return await asyncio.to_thread(_read)


async def write_file(path, content):
    """Write content to a file"""
    import asyncio
    
    def _write():
        try:
            norm_path = os.path.expandvars(os.path.expanduser(path))
            norm_path = os.path.normpath(norm_path)
            
            # Create parent directory if it doesn't exist
            parent_dir = os.path.dirname(norm_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            
            # Write content (handle both string and bytes)
            if isinstance(content, bytes):
                mode = 'wb'
            else:
                mode = 'w'
                
            with open(norm_path, mode) as f:
                f.write(content)
            
            return {'message': 'File written successfully', 'path': norm_path}
            
        except Exception as e:
            return {"error": str(e)}
    
    return await asyncio.to_thread(_write)


async def upload_file(path, file_name, file_bytes):
    """Upload a file to the specified directory"""
    import asyncio
    
    def _upload():
        try:
            norm_path = os.path.expandvars(os.path.expanduser(path))
            norm_path = os.path.normpath(norm_path)
            
            if not os.path.exists(norm_path):
                return {"error": f"Directory does not exist: {norm_path}"}
            
            if not os.path.isdir(norm_path):
                return {"error": f"Path is not a directory: {norm_path}"}
            
            dest_path = os.path.join(norm_path, file_name)
            
            with open(dest_path, 'wb') as f:
                f.write(file_bytes)
            
            return {'message': 'File uploaded successfully', 'path': dest_path}
            
        except Exception as e:
            return {"error": str(e)}
    
    return await asyncio.to_thread(_upload)


async def create_directory(path):
    """Create a new directory"""
    import asyncio
    
    def _create():
        try:
            norm_path = os.path.expandvars(os.path.expanduser(path))
            norm_path = os.path.normpath(norm_path)
            
            os.makedirs(norm_path, exist_ok=True)
            
            return {'message': 'Directory created successfully', 'path': norm_path}
            
        except Exception as e:
            return {"error": str(e)}
    
    return await asyncio.to_thread(_create)


async def delete(path):
    """Delete a file or directory"""
    import asyncio
    
    def _delete():
        try:
            norm_path = os.path.expandvars(os.path.expanduser(path))
            norm_path = os.path.normpath(norm_path)
            
            if not os.path.exists(norm_path):
                return {"error": f"Path does not exist: {norm_path}"}
            
            if os.path.isdir(norm_path):
                shutil.rmtree(norm_path)
            else:
                os.remove(norm_path)
            
            return {'message': 'Deleted successfully', 'path': norm_path}
            
        except Exception as e:
            return {"error": str(e)}
    
    return await asyncio.to_thread(_delete)


async def rename(old_path, new_path):
    """Rename/move a file or directory"""
    import asyncio
    
    def _rename():
        try:
            old_norm = os.path.expandvars(os.path.expanduser(old_path))
            old_norm = os.path.normpath(old_norm)
            
            new_norm = os.path.expandvars(os.path.expanduser(new_path))
            new_norm = os.path.normpath(new_norm)
            
            if not os.path.exists(old_norm):
                return {"error": f"Source path does not exist: {old_norm}"}
            
            os.rename(old_norm, new_norm)
            
            return {'message': 'Renamed successfully', 'old_path': old_norm, 'new_path': new_norm}
            
        except Exception as e:
            return {"error": str(e)}
    
    return await asyncio.to_thread(_rename)
