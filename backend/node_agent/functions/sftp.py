

import os
import stat
from pathlib import Path
from datetime import datetime

async def list_files(path):
	import asyncio
	def _list():
		try:
			norm_path = os.path.expandvars(os.path.expanduser(path))
			norm_path = os.path.normpath(norm_path)
			if os.name == 'nt':
				import pathlib
				norm_path = str(pathlib.Path(norm_path).resolve())
			if not os.path.exists(norm_path):
				return {"error": f"Path does not exist: {norm_path}"}
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
			return {'path': norm_path, 'files': files}
		except Exception as e:
			return {'error': f'Failed to list directory: {str(e)}'}
	return await asyncio.to_thread(_list)

async def upload_file(path, file_name, file_bytes):
	import asyncio
	def _upload():
		try:
			dest_path = os.path.join(path, file_name)
			with open(dest_path, 'wb+') as f:
				f.write(file_bytes)
			return {'message': 'File uploaded successfully', 'path': dest_path}
		except Exception as e:
			return {'error': f'Failed to upload file: {str(e)}'}
	return await asyncio.to_thread(_upload)

async def create_directory(path):
	import asyncio
	def _mkdir():
		try:
			os.makedirs(path, exist_ok=True)
			return {'message': 'Directory created successfully'}
		except Exception as e:
			return {'error': f'Failed to create directory: {str(e)}'}
	return await asyncio.to_thread(_mkdir)

async def delete(path):
	import asyncio
	def _delete():
		try:
			if os.path.isdir(path):
				os.rmdir(path)
			else:
				os.remove(path)
			return {'message': 'Deleted successfully'}
		except Exception as e:
			return {'error': f'Failed to delete: {str(e)}'}
	return await asyncio.to_thread(_delete)

async def rename(old_path, new_path):
	import asyncio
	def _rename():
		try:
			os.rename(old_path, new_path)
			return {'message': 'Renamed successfully'}
		except Exception as e:
			return {'error': f'Failed to rename: {str(e)}'}
	return await asyncio.to_thread(_rename)

async def read_file(path):
	import asyncio
	def _read():
		try:
			with open(path, 'r', encoding='utf-8', errors='replace') as f:
				content = f.read()
			return {'path': path, 'content': content}
		except Exception as e:
			return {'error': f'Failed to read file: {str(e)}'}
	return await asyncio.to_thread(_read)

async def write_file(path, content):
	import asyncio
	def _write():
		try:
			with open(path, 'w', encoding='utf-8') as f:
				f.write(content)
			return {'message': 'File saved successfully'}
		except Exception as e:
			return {'error': f'Failed to write file: {str(e)}'}
	return await asyncio.to_thread(_write)
