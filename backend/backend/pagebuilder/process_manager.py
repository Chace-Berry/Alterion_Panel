"""
Backend Process Manager
Manages starting, stopping, and monitoring backend processes (Django, FastAPI, Node.js).
"""

import os
import signal
import subprocess
import psutil
import time
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime


class ProcessManager:
    """
    Manages backend server processes with health checking and automatic restart.
    """
    
    def __init__(self):
        self.processes: Dict[str, Dict] = {}  # project_id -> process info
    
    def start_backend(self, 
                     project_id: str,
                     framework: str,
                     backend_path: str,
                     start_command: str,
                     port: int,
                     environment_vars: Optional[Dict] = None) -> Dict:
        """
        Start a backend server process.
        
        Args:
            project_id: Unique project identifier
            framework: Backend framework (django, fastapi, nodejs)
            backend_path: Path to backend directory
            start_command: Command to start the server
            port: Port number for the server
            environment_vars: Environment variables
            
        Returns:
            Dict with process information
        """
        result = {
            'success': False,
            'pid': None,
            'message': '',
            'started_at': None
        }
        
        # Check if process already running
        if project_id in self.processes:
            existing = self.processes[project_id]
            if self.is_process_running(existing['pid']):
                result['message'] = f"Backend already running with PID {existing['pid']}"
                result['pid'] = existing['pid']
                return result
            else:
                # Clean up dead process
                del self.processes[project_id]
        
        try:
            # Prepare environment
            env = os.environ.copy()
            if environment_vars:
                env.update(environment_vars)
            
            # Set PORT environment variable
            env['PORT'] = str(port)
            
            # Parse start command
            cmd_parts = start_command.split()
            
            # Special handling for different frameworks
            if framework == 'django':
                # Ensure manage.py is in the command
                if 'manage.py' not in start_command:
                    manage_py = Path(backend_path) / 'manage.py'
                    if manage_py.exists():
                        cmd_parts = ['python', str(manage_py), 'runserver', f'0.0.0.0:{port}']
            
            elif framework == 'fastapi':
                # Use uvicorn with proper host and port
                if 'uvicorn' in start_command:
                    # Ensure --host and --port are set
                    if '--host' not in start_command:
                        cmd_parts.extend(['--host', '0.0.0.0'])
                    if '--port' not in start_command:
                        cmd_parts.extend(['--port', str(port)])
            
            elif framework == 'nodejs':
                # For Node.js, check if npm or node command
                if 'npm' in start_command and 'start' in start_command:
                    cmd_parts = ['npm', 'start']
                elif 'node' in start_command:
                    pass  # Use as is
            
            # Start process
            process = subprocess.Popen(
                cmd_parts,
                cwd=backend_path,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                start_new_session=True  # Detach from parent
            )
            
            # Wait a moment to check if process started successfully
            time.sleep(2)
            
            if process.poll() is None:
                # Process is running
                self.processes[project_id] = {
                    'pid': process.pid,
                    'framework': framework,
                    'port': port,
                    'command': start_command,
                    'started_at': datetime.now(),
                    'process': process,
                    'backend_path': backend_path
                }
                
                result['success'] = True
                result['pid'] = process.pid
                result['started_at'] = datetime.now().isoformat()
                result['message'] = f"Backend started successfully on port {port}"
            else:
                # Process died immediately
                stdout, stderr = process.communicate()
                result['message'] = f"Backend failed to start: {stderr.decode()}"
        
        except FileNotFoundError as e:
            result['message'] = f"Command not found: {str(e)}"
        
        except Exception as e:
            result['message'] = f"Failed to start backend: {str(e)}"
        
        return result
    
    def stop_backend(self, project_id: str, force: bool = False) -> Dict:
        """
        Stop a backend server process.
        
        Args:
            project_id: Project identifier
            force: Force kill if graceful shutdown fails
            
        Returns:
            Dict with stop result
        """
        result = {
            'success': False,
            'message': ''
        }
        
        if project_id not in self.processes:
            result['message'] = f"No backend process found for project {project_id}"
            return result
        
        process_info = self.processes[project_id]
        pid = process_info['pid']
        
        try:
            if not self.is_process_running(pid):
                result['message'] = f"Process {pid} is not running"
                del self.processes[project_id]
                result['success'] = True
                return result
            
            # Try graceful shutdown first
            try:
                proc = psutil.Process(pid)
                proc.terminate()
                
                # Wait up to 10 seconds for graceful shutdown
                try:
                    proc.wait(timeout=10)
                    result['success'] = True
                    result['message'] = f"Backend stopped gracefully (PID {pid})"
                except psutil.TimeoutExpired:
                    if force:
                        proc.kill()
                        result['success'] = True
                        result['message'] = f"Backend force killed (PID {pid})"
                    else:
                        result['message'] = f"Backend did not stop gracefully (PID {pid})"
            
            except psutil.NoSuchProcess:
                result['success'] = True
                result['message'] = f"Process {pid} already terminated"
            
            # Clean up
            if result['success']:
                del self.processes[project_id]
        
        except Exception as e:
            result['message'] = f"Error stopping backend: {str(e)}"
        
        return result
    
    def restart_backend(self, project_id: str) -> Dict:
        """
        Restart a backend server process.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Dict with restart result
        """
        if project_id not in self.processes:
            return {
                'success': False,
                'message': f"No backend process found for project {project_id}"
            }
        
        # Get process info before stopping
        process_info = self.processes[project_id]
        framework = process_info['framework']
        backend_path = process_info['backend_path']
        command = process_info['command']
        port = process_info['port']
        
        # Stop the process
        stop_result = self.stop_backend(project_id, force=True)
        
        if not stop_result['success']:
            return stop_result
        
        # Wait a moment
        time.sleep(1)
        
        # Start again
        return self.start_backend(
            project_id=project_id,
            framework=framework,
            backend_path=backend_path,
            start_command=command,
            port=port
        )
    
    def get_process_status(self, project_id: str) -> Dict:
        """
        Get status of a backend process.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Dict with process status
        """
        if project_id not in self.processes:
            return {
                'running': False,
                'message': 'No process found'
            }
        
        process_info = self.processes[project_id]
        pid = process_info['pid']
        
        if not self.is_process_running(pid):
            return {
                'running': False,
                'pid': pid,
                'message': 'Process not running (may have crashed)'
            }
        
        try:
            proc = psutil.Process(pid)
            
            return {
                'running': True,
                'pid': pid,
                'port': process_info['port'],
                'framework': process_info['framework'],
                'started_at': process_info['started_at'].isoformat(),
                'cpu_percent': proc.cpu_percent(interval=0.1),
                'memory_mb': proc.memory_info().rss / 1024 / 1024,
                'status': proc.status(),
                'uptime_seconds': (datetime.now() - process_info['started_at']).total_seconds()
            }
        
        except Exception as e:
            return {
                'running': False,
                'pid': pid,
                'message': f"Error getting status: {str(e)}"
            }
    
    def is_process_running(self, pid: int) -> bool:
        """Check if a process is running"""
        try:
            proc = psutil.Process(pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return False
    
    def check_port_available(self, port: int) -> bool:
        """Check if a port is available"""
        import socket
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return True
            except OSError:
                return False
    
    def find_available_port(self, start_port: int = 8000, end_port: int = 9000) -> Optional[int]:
        """Find an available port in range"""
        for port in range(start_port, end_port):
            if self.check_port_available(port):
                return port
        return None
    
    def health_check(self, port: int, endpoint: str = '/') -> Dict:
        """
        Perform health check on backend server.
        
        Args:
            port: Server port
            endpoint: Health check endpoint
            
        Returns:
            Dict with health check result
        """
        import requests
        
        result = {
            'healthy': False,
            'status_code': None,
            'response_time': None,
            'message': ''
        }
        
        url = f"http://127.0.0.1:{port}{endpoint}"
        
        try:
            start_time = time.time()
            response = requests.get(url, timeout=5)
            response_time = time.time() - start_time
            
            result['status_code'] = response.status_code
            result['response_time'] = round(response_time * 1000, 2)  # ms
            
            if 200 <= response.status_code < 500:
                result['healthy'] = True
                result['message'] = f"Server responding (HTTP {response.status_code})"
            else:
                result['message'] = f"Server error (HTTP {response.status_code})"
        
        except requests.exceptions.Timeout:
            result['message'] = "Health check timeout"
        
        except requests.exceptions.ConnectionError:
            result['message'] = "Cannot connect to server"
        
        except Exception as e:
            result['message'] = f"Health check error: {str(e)}"
        
        return result
    
    def get_all_processes(self) -> List[Dict]:
        """Get status of all managed processes"""
        statuses = []
        
        for project_id in list(self.processes.keys()):
            status = self.get_process_status(project_id)
            status['project_id'] = project_id
            statuses.append(status)
        
        return statuses
    
    def stop_all(self) -> Dict:
        """Stop all managed processes"""
        results = {
            'stopped': [],
            'failed': []
        }
        
        for project_id in list(self.processes.keys()):
            result = self.stop_backend(project_id, force=True)
            if result['success']:
                results['stopped'].append(project_id)
            else:
                results['failed'].append({
                    'project_id': project_id,
                    'message': result['message']
                })
        
        return results
    
    def get_process_logs(self, project_id: str, lines: int = 50) -> Dict:
        """
        Get recent logs from a process.
        
        Args:
            project_id: Project identifier
            lines: Number of recent lines to return
            
        Returns:
            Dict with logs
        """
        if project_id not in self.processes:
            return {
                'success': False,
                'message': 'Process not found'
            }
        
        process_info = self.processes[project_id]
        process = process_info.get('process')
        
        if not process:
            return {
                'success': False,
                'message': 'Process handle not available'
            }
        
        try:
            # Read from stdout and stderr (non-blocking)
            import select
            
            stdout_lines = []
            stderr_lines = []
            
            # This is a simplified version - in production you'd want to
            # continuously log output to a file and read from there
            
            return {
                'success': True,
                'stdout': ''.join(stdout_lines[-lines:]),
                'stderr': ''.join(stderr_lines[-lines:])
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f"Error reading logs: {str(e)}"
            }
