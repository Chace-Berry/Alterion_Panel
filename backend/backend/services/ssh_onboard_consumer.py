import json
import paramiko
import io
import os
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async



@sync_to_async
def get_node_by_ip_sync(ip_address):
    from .node_models import Node
    node = Node.objects.filter(ip_address=ip_address).order_by('-created_at').first()
    if node:
        # Force evaluation of all fields including related ones to prevent lazy loading
        return {
            'id': node.id,
            'hostname': node.hostname,
            'ip_address': node.ip_address,
            'port': node.port,
            'node_type': node.node_type,
            'auth_key': node.auth_key,
            'username': node.username,
            'status': node.status,
            'last_seen': node.last_seen.isoformat() if node.last_seen else None,
            'owner': str(node.owner) if node.owner else None,
            'notes': node.notes
        }
    return None

class SSHOnboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Extract ip from URL route
        self.ip = self.scope['url_route']['kwargs'].get('ip')
        self.ssh = None
        self.sftp = None
        self.ssh_remote_ip = None
        await self.accept()
        await self.send(json.dumps({"status": "connected", "ip": self.ip}))

    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection. Clean up SSH and SFTP sessions if open.
        """
        await self.send(json.dumps({"status": "debug", "step": f"WebSocket disconnecting with code: {close_code}"}))
        if hasattr(self, 'sftp') and self.sftp:
            try:
                await sync_to_async(self.sftp.close)()
            except Exception:
                pass
        if hasattr(self, 'ssh') and self.ssh:
            try:
                await sync_to_async(self.ssh.close)()
            except Exception:
                pass

    async def receive(self, text_data=None):
        if not text_data:
            return
        try:
            msg = json.loads(text_data)
        except Exception as e:
            await self.send(json.dumps({"error": f"Invalid JSON: {e}"}))
            return
        
        if msg.get("type") == "ssh_onboard":
            try:
                await self.handle_ssh_onboard(msg)
            except Exception as e:
                await self.send(json.dumps({"error": f"Unexpected error in handle_ssh_onboard: {type(e).__name__}: {e}"}))
                import traceback
                await self.send(json.dumps({"error": f"Traceback: {traceback.format_exc()}"}))
                await self.cleanup_connections()

    async def handle_ssh_onboard(self, msg):
        host = self.ip
        port = int(msg.get("port", 22))
        username = msg.get("username")
        private_key = msg.get("private_key")
        
        await self.send(json.dumps({
            "status": "debug",
            "step": "Entered handle_ssh_onboard",
            "received": msg,
            "host": host,
            "port": port,
            "username": username
        }))
        
        # Required fields: port, username, private_key (PEM string)
        if not (host and port and username and private_key):
            await self.send(json.dumps({"error": "Missing SSH details"}))
            return
            
        await self.send(json.dumps({"status": "connecting", "step": f"Connecting via SSH to {host}..."}))
        
        # Run SSH connection in thread pool to avoid blocking
        try:
            await self.send(json.dumps({"status": "debug", "step": "Parsing private key..."}))
            await asyncio.sleep(0.1)  # Give client time to receive message

            print("[DEBUG] About to call connect_ssh")
            result = await self.connect_ssh(host, port, username, private_key)
            print(f"[DEBUG] connect_ssh returned: {result}")

            # After SSH connect, get the real remote IP
            try:
                if self.ssh and self.ssh.get_transport():
                    self.ssh_remote_ip = self.ssh.get_transport().getpeername()[0]
                    await self.send(json.dumps({"status": "debug", "step": f"SSH remote IP detected: {self.ssh_remote_ip}"}))
            except Exception as e:
                await self.send(json.dumps({"status": "warning", "step": f"Could not get SSH remote IP: {e}"}))

            await asyncio.sleep(0.1)  # Give client time before next message
            await self.send(json.dumps({"status": "debug", "step": "SSH connection succeeded!"}))
            await asyncio.sleep(0.1)

            await self.send(json.dumps({"status": "debug", "step": "SFTP session opened"}))
            await asyncio.sleep(0.1)

            await self.send(json.dumps({"status": "connected", "step": "SSH connection established."}))
            await asyncio.sleep(0.1)

            print("[DEBUG] All connection messages sent")
        except paramiko.AuthenticationException as e:
            print(f"[DEBUG] Auth exception: {e}")
            await self.send(json.dumps({"error": f"SSH authentication failed - check private key: {e}"}))
            return
        except paramiko.SSHException as e:
            print(f"[DEBUG] SSH exception: {e}")
            await self.send(json.dumps({"error": f"SSH protocol error: {e}"}))
            return
        except Exception as e:
            print(f"[DEBUG] General exception: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            await self.send(json.dumps({"error": f"SSH connection failed: {type(e).__name__}: {e}"}))
            return

        print("[DEBUG] Starting agent directory creation...")
        # 1. Create agent directory (try SFTP first, fallback to SSH exec)
        agent_dir = "alterion_agent"
        remote_home = f"/home/{username}"
        remote_agent_dir = f"{remote_home}/{agent_dir}"
        
        try:
            await self.sftp_mkdir(remote_agent_dir)
            await self.send(json.dumps({"status": "debug", "step": "Agent directory created via SFTP."}))
        except IOError:
            await self.send(json.dumps({"status": "debug", "step": "SFTP mkdir failed (may already exist), trying SSH exec..."}))
            exit_status, err = await self.ssh_exec_command_with_exit(f"mkdir -p {remote_agent_dir}")
            if exit_status == 0:
                await self.send(json.dumps({"status": "debug", "step": "Agent directory created via SSH exec."}))
            else:
                await self.send(json.dumps({"error": f"Failed to create agent directory: {err}"}))
                await self.cleanup_connections()
                return

                
        print("[DEBUG] Starting file copy section...")
        # 2. Copy files with debug
        await self.send(json.dumps({"status": "debug", "step": "Starting file copy loop..."}))
        
        # Copy requirements.txt from backend/backend/
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
        req_path = os.path.join(backend_dir, 'requirements.txt')
        
        await self.send(json.dumps({"status": "debug", "step": f"Backend dir: {backend_dir}"}))
        await self.send(json.dumps({"status": "debug", "step": f"Requirements path: {req_path}"}))
        
        files_to_copy = []
        
        # Check if requirements.txt exists
        if os.path.exists(req_path):
            files_to_copy.append((req_path, f'{agent_dir}/requirements.txt'))
            await self.send(json.dumps({"status": "debug", "step": "Found requirements.txt"}))
        else:
            await self.send(json.dumps({"status": "warning", "step": f"requirements.txt not found at {req_path}"}))
        
        # Copy all files from backend/node_agent/ to remote agent_dir, including functions folder recursively
        node_agent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../node_agent/'))
        await self.send(json.dumps({"status": "debug", "step": f"Node agent dir: {node_agent_dir}"}))
        if os.path.isdir(node_agent_dir):
            files = os.listdir(node_agent_dir)
            await self.send(json.dumps({"status": "debug", "step": f"Found {len(files)} files in node_agent dir"}))
            for fname in files:
                local_path = os.path.join(node_agent_dir, fname)
                remote_path = f'{agent_dir}/{fname}'
                if os.path.isfile(local_path):
                    files_to_copy.append((local_path, remote_path))
                elif os.path.isdir(local_path) and fname == 'functions':
                    # Recursively add all files in functions/
                    for root, dirs, subfiles in os.walk(local_path):
                        for subfile in subfiles:
                            sub_local = os.path.join(root, subfile)
                            rel_path = os.path.relpath(sub_local, node_agent_dir)
                            sub_remote = f'{agent_dir}/{rel_path.replace(os.sep, "/")}'
                            files_to_copy.append((sub_local, sub_remote))
        else:
            await self.send(json.dumps({"error": f"Local node_agent dir missing: {node_agent_dir}"}))
            await self.cleanup_connections()
            return
            
        try:
            for fname in ['agent_private.pem', 'agent_public.pem']:
                fpath = os.path.join(backend_dir, fname)
                if os.path.exists(fpath):
                    files_to_copy.append((fpath, f'{agent_dir}/{fname}'))
                    await self.send(json.dumps({"status": "debug", "step": f"Found {fname}"}))
                else:
                    await self.send(json.dumps({"status": "warning", "step": f"{fname} not found at {fpath}"}))
        except Exception as e:
            await self.send(json.dumps({"error": f"Error while preparing files to copy: {e}"}))
            await self.cleanup_connections()
            return
        
        await self.send(json.dumps({"status": "debug", "step": f"Total files to copy: {len(files_to_copy)}"}))
            
        # Copy files
        import posixpath
        async def ensure_remote_dir(sftp, remote_dir):
            # Recursively create remote_dir on the server
            dirs = []
            while remote_dir not in ('', '/', None):
                dirs.append(remote_dir)
                remote_dir = posixpath.dirname(remote_dir)
            for d in reversed(dirs):
                try:
                    await self.sftp_mkdir(f'/home/{username}/{d}')
                except Exception:
                    pass  # Ignore if already exists

        for local_path, remote_path in files_to_copy:
            if not os.path.exists(local_path):
                await self.send(json.dumps({"error": f"Local file missing: {local_path}"}))
                await self.cleanup_connections()
                return

            await self.send(json.dumps({"status": "installing", "step": f"Copying {os.path.basename(local_path)} to {remote_path}..."}))
            try:
                # Ensure parent directory exists on remote
                remote_full_path = f'/home/{username}/{remote_path}'
                remote_parent = posixpath.dirname(remote_path)
                if remote_parent and remote_parent != '.':
                    await ensure_remote_dir(self.sftp, remote_parent)
                await self.sftp_put(local_path, remote_full_path)
            except Exception as e:
                await self.send(json.dumps({"error": f"Failed to copy {local_path} to {remote_path}: {e}"}))
                await self.cleanup_connections()
                return
        
        await self.send(json.dumps({"status": "debug", "step": "All files copied successfully"}))
                
        try:
            await self.send(json.dumps({"status": "debug", "step": "Listing remote directory after copy..."}))
            dirlist = await self.sftp_listdir(f'/home/{username}/{agent_dir}')
            await self.send(json.dumps({"status": "debug", "step": f"Remote dir contents: {dirlist}"}))
        except Exception as e:
            await self.send(json.dumps({"error": f"Failed to list remote dir: {e}"}))
            
        print("[DEBUG] Detecting remote OS for install script...")
        # Detect remote OS
        try:
            exit_status, uname_out = await self.ssh_exec_command_with_exit("uname")
            is_windows = False
            if exit_status != 0 or "not found" in uname_out.lower():
                # Try 'ver' for Windows
                exit_status, ver_out = await self.ssh_exec_command_with_exit("ver")
                if exit_status == 0 and ("windows" in ver_out.lower() or "microsoft" in ver_out.lower()):
                    is_windows = True
            await self.send(json.dumps({"status": "debug", "step": f"Remote OS detected: {'Windows' if is_windows else 'Unix-like'}"}))
        except Exception as e:
            await self.send(json.dumps({"status": "warning", "step": f"Could not detect remote OS, defaulting to install.sh: {e}"}))
            is_windows = False

        # Choose install script
        if is_windows:
            cmd = f"cd C:/Users/{username}/alterion_agent && install.bat"
            script_name = "install.bat"
        else:
            cmd = f"cd /home/{username}/{agent_dir} && bash install.sh"
            script_name = "install.sh"

        try:
            await self.send(json.dumps({"status": "installing", "step": f"Running {script_name}..."}))
            # Run install and stream output line by line for progress
            async for progress_msg in self.run_install_script_with_progress(cmd):
                await self.send(json.dumps(progress_msg))
            await self.send(json.dumps({"status": "done", "step": "Install complete."}))

  # --- Add as pending node in DB ---
            try:
                from django.utils import timezone
                from .node_models import Node
                from asgiref.sync import sync_to_async
                import time
                user = getattr(self.scope, 'user', None)
                ip_address = self.ssh_remote_ip or self.ip
                node_data = None
                # Wait up to 40 seconds for the node to appear in DB
                for i in range(40):
                    node_data = await get_node_by_ip_sync(ip_address)
                    if node_data:
                        break
                    await asyncio.sleep(1)
                if node_data:
                    node_id = node_data['id']
                    hostname = node_data['hostname']
                    username = node_data['username']
                    await self.send(json.dumps({"status": "node_info", "node": node_data}))
            except Exception as e:
                import traceback
                await self.send(json.dumps({"status": "error", "step": f"Failed to find node by IP: {e}", "traceback": traceback.format_exc()}))
        except Exception as e:
            await self.send(json.dumps({"error": f"Install failed: {e}"}))
            print(f"[DEBUG] Install failed with exception: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("[DEBUG] Cleaning up connections...")
            await self.cleanup_connections()
            print("[DEBUG] handle_ssh_onboard completed!")
            await self.send(json.dumps({"status": "workflow_complete", "step": "All operations finished"}))

    async def run_install_script_with_progress(self, command):
        """Run install script, yield progress and log messages as dicts"""
        # Use a thread to run the blocking SSH command and stream output
        loop = asyncio.get_event_loop()
        def run_and_yield():
            stdin, stdout, stderr = self.ssh.exec_command(command)
            while True:
                line = stdout.readline()
                if not line:
                    break
                line = line.strip()
                if line.startswith("PROGRESS:"):
                    # Format: PROGRESS:step:total:desc
                    try:
                        _, step, total, desc = line.split(":", 3)
                        yield {"progress": int(int(step)/int(total)*100), "step": int(step), "total": int(total), "desc": desc, "status": "installing"}
                    except Exception:
                        yield {"log": line}
                else:
                    yield {"log": line}
            # Also yield stderr lines as errors
            for err_line in stderr.readlines():
                yield {"error": err_line.strip()}
        for msg in await loop.run_in_executor(None, lambda: list(run_and_yield())):
            yield msg

            
    @sync_to_async        
    def cleanup_connections(self):
        """Helper method to close SSH and SFTP connections"""
        if self.sftp:
            try:
                self.sftp.close()
            except Exception:
                pass
            self.sftp = None
        if self.ssh:
            try:
                self.ssh.close()
            except Exception:
                pass
            self.ssh = None
            
    @sync_to_async
    def connect_ssh(self, host, port, username, private_key):
        """Run SSH connection in thread pool to avoid blocking"""
        print(f"[DEBUG] Starting SSH connection to {host}:{port}")
        key = paramiko.RSAKey.from_private_key(io.StringIO(private_key))
        print("[DEBUG] Private key parsed")
        
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print("[DEBUG] SSHClient created, attempting connection...")
        self.ssh.connect(host, port=port, username=username, pkey=key, timeout=30, banner_timeout=30)
        print("[DEBUG] SSH connected successfully")
        
        self.sftp = self.ssh.open_sftp()
        print("[DEBUG] SFTP session opened")
        return True        
    @sync_to_async
    def ssh_exec_command_with_exit(self, command):
        """Run SSH command and wait for exit status"""
        stdin, stdout, stderr = self.ssh.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        err_bytes = stderr.read()
        err = err_bytes.decode() if hasattr(err_bytes, 'decode') else str(err_bytes)
        return exit_status, err
    
    @sync_to_async
    def sftp_mkdir(self, path):
        """Create directory via SFTP in thread pool"""
        self.sftp.mkdir(path)
    
    @sync_to_async
    def sftp_put(self, local_path, remote_path):
        """Upload file via SFTP in thread pool"""
        self.sftp.put(local_path, remote_path)
    
    @sync_to_async
    def sftp_listdir(self, path):
        """List directory via SFTP in thread pool"""
        return self.sftp.listdir(path)
    
    @sync_to_async
    def run_install_script(self, command):
        """Run install script and return output"""
        stdin, stdout, stderr = self.ssh.exec_command(command)
        
        all_stdout = ""
        all_stderr = ""
        
        # Read output in real-time
        while True:
            if stdout.channel.recv_ready():
                line = stdout.readline()
                if line:
                    all_stdout += line
            if stdout.channel.recv_stderr_ready():
                err_line = stderr.readline()
                if err_line:
                    all_stderr += err_line
            if stdout.channel.exit_status_ready():
                break
        
        # Get any remaining output
        remaining_stdout = stdout.read().decode()
        remaining_stderr = stderr.read().decode()
        all_stdout += remaining_stdout
        all_stderr += remaining_stderr
        
        exit_status = stdout.channel.recv_exit_status()
        
        return all_stdout, all_stderr, exit_status