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
        print(f"[DEBUG] WebSocket disconnecting with code: {close_code}")
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
        auth_credential = msg.get("private_key")  # Can be private key or password
        
        # Store username and password for later use (credential saving)
        self.ssh_username = username
        self.user_password = None
        if auth_credential and not auth_credential.strip().startswith('-----BEGIN'):
            self.user_password = auth_credential
        
        await self.send(json.dumps({
            "status": "debug",
            "step": "Entered handle_ssh_onboard",
            "received": msg,
            "host": host,
            "port": port,
            "username": username
        }))
        
        # Required fields: port, username, auth_credential (password or PEM string)
        if not (host and port and username and auth_credential):
            await self.send(json.dumps({"error": "Missing SSH details (host, port, username, and password or private key required)"}))
            return
            
        await self.send(json.dumps({"status": "connecting", "step": f"Connecting via SSH to {host}..."}))
        
        # Run SSH connection in thread pool to avoid blocking
        try:
            auth_type = "private key" if auth_credential.strip().startswith('-----BEGIN') else "password"
            await self.send(json.dumps({"status": "debug", "step": f"Authenticating with {auth_type}..."}))
            await asyncio.sleep(0.1)  # Give client time to receive message

            print("[DEBUG] About to call connect_ssh")
            result = await self.connect_ssh(host, port, username, auth_credential)
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
        
        # Create server config file with the correct WebSocket URL
        await self.send(json.dumps({"status": "installing", "step": "Creating server configuration...", "progress": 4}))
        try:
            from django.conf import settings
            import re
            
            # Get the host from the WebSocket connection headers
            # Check for forwarded headers first (ngrok, reverse proxies)
            headers = dict(self.scope.get('headers', []))
            
            # Try multiple headers in order of preference
            host = None
            for header_name in [b'x-forwarded-host', b'x-original-host', b'x-forwarded-server', b'host']:
                if header_name in headers:
                    potential_host = headers[header_name].decode('utf-8')
                    # Skip localhost/127.0.0.1, these aren't useful for remote agents
                    if potential_host not in ['localhost', '127.0.0.1', 'localhost:13527']:
                        host = potential_host
                        await self.send(json.dumps({"status": "debug", "step": f"Found host from {header_name.decode()}: {host}"}))
                        break
            
            # If still no valid host, try to get from Django settings or environment
            if not host:
                # Check for PUBLIC_URL in settings or environment
                public_url = getattr(settings, 'PUBLIC_URL', os.environ.get('PUBLIC_URL', ''))
                if public_url:
                    # Extract host from URL
                    match = re.search(r'(?:https?://)?([^/]+)', public_url)
                    if match:
                        host = match.group(1)
                        await self.send(json.dumps({"status": "debug", "step": f"Found host from PUBLIC_URL: {host}"}))
            
            if not host:
                # Last resort: use ngrok URL from the error message
                host = 'massive-easy-tetra.ngrok-free.app'
                await self.send(json.dumps({"status": "warning", "step": f"Using fallback ngrok host: {host}"}))
            
            # Determine protocol (wss for https/ngrok, ws otherwise)
            # Check X-Forwarded-Proto header first
            forwarded_proto = headers.get(b'x-forwarded-proto', b'').decode('utf-8')
            if forwarded_proto == 'https' or host.endswith('.ngrok-free.app') or self.scope.get('scheme') == 'https':
                scheme = 'wss'
            else:
                scheme = 'ws'
            
            # Build the server URL
            server_url = f"{scheme}://{host}/alterion/panel/agent/{{serverid}}/"
            
            # Create config content
            config_content = json.dumps({
                "server_url": server_url,
                "reconnect_delay": 5,
                "connection_timeout": 30
            }, indent=2)
            
            await self.send(json.dumps({"status": "debug", "step": f"Server URL: {server_url}"}))
            
            # Write config file to remote
            config_path = f'/home/{username}/{agent_dir}/server_config.json'
            import io
            config_bytes = io.BytesIO(config_content.encode('utf-8'))
            await self.sftp_put_bytes(config_bytes, config_path)
            
            await self.send(json.dumps({"status": "debug", "step": "✓ Server configuration created"}))
        except Exception as e:
            await self.send(json.dumps({"status": "warning", "step": f"Failed to create server config: {e}"}))
                
        try:
            await self.send(json.dumps({"status": "debug", "step": "Listing remote directory after copy..."}))
            dirlist = await self.sftp_listdir(f'/home/{username}/{agent_dir}')
            await self.send(json.dumps({"status": "debug", "step": f"Remote dir contents: {dirlist}"}))
        except Exception as e:
            await self.send(json.dumps({"error": f"Failed to list remote dir: {e}"}))
        
        # Stop any existing Alterion agent services before starting installation
        await self.send(json.dumps({"status": "installing", "step": "Stopping existing agent services...", "progress": 5}))
        print("[DEBUG] Checking for and stopping existing agent services...")
        
        # Try to stop systemd service if it exists
        exit_status, _ = await self.ssh_exec_command_with_exit("systemctl is-active alterion-node-agent.service 2>/dev/null")
        if exit_status == 0:  # Service exists and is active
            await self.send(json.dumps({"status": "installing", "step": "Stopping alterion-node-agent service...", "progress": 6}))
            stop_cmd = "sudo systemctl stop alterion-node-agent.service"
            if self.user_password:
                await self.run_install_script(stop_cmd, provide_password=True)
            else:
                await self.run_install_script(stop_cmd, provide_password=False)
            await self.send(json.dumps({"status": "debug", "step": "✓ Systemd service stopped"}))
        
        # Kill any running node_agent.py processes
        exit_status, pids = await self.ssh_exec_command_with_exit("pgrep -f 'node_agent.py'")
        if exit_status == 0 and pids.strip():
            await self.send(json.dumps({"status": "installing", "step": "Stopping running agent processes...", "progress": 7}))
            kill_cmd = "pkill -f 'node_agent.py' || true"
            await self.run_install_script(kill_cmd)
            await asyncio.sleep(1)  # Give processes time to terminate
            await self.send(json.dumps({"status": "debug", "step": "✓ Agent processes stopped"}))
        else:
            await self.send(json.dumps({"status": "debug", "step": "No running agent processes found"}))
            
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

        print(f"[DEBUG] About to check Python installation, is_windows={is_windows}")
        # Check for Python installation
        await self.send(json.dumps({"status": "installing", "step": "Checking for Python installation...", "progress": 10}))
        print("[DEBUG] Sent Python installation check message")
        
        if not is_windows:
            python_cmd = None
            try:
                for py in ['python3', 'python']:
                    print(f"[DEBUG] Checking for {py}...")
                    exit_status, _ = await self.ssh_exec_command_with_exit(f"which {py}")
                    if exit_status == 0:
                        python_cmd = py
                        await self.send(json.dumps({"status": "installing", "step": f"Found {py}", "progress": 15}))
                        print(f"[DEBUG] Found {py}")
                        break
            except Exception as e:
                print(f"[DEBUG] Exception while checking Python: {e}")
                import traceback
                traceback.print_exc()
                raise
            
            # Detect package manager (needed for both Python and venv installation)
            pkg_mgr = None
            print("[DEBUG] Detecting package manager...")
            for mgr, check_cmd in [('apt', 'which apt-get'), ('yum', 'which yum'), ('dnf', 'which dnf'), ('apk', 'which apk')]:
                exit_status, _ = await self.ssh_exec_command_with_exit(check_cmd)
                if exit_status == 0:
                    pkg_mgr = mgr
                    print(f"[DEBUG] Found package manager: {pkg_mgr}")
                    break
            print(f"[DEBUG] Package manager detection complete: {pkg_mgr}")
            
            if not python_cmd:
                await self.send(json.dumps({"status": "installing", "step": "Python not found. Installing Python 3...", "progress": 20}))
                
                if pkg_mgr:
                    if pkg_mgr == 'apt':
                        # Include python3-venv for Debian/Ubuntu systems
                        install_cmd = "sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv"
                    elif pkg_mgr in ['yum', 'dnf']:
                        install_cmd = f"sudo {pkg_mgr} install -y python3 python3-pip"
                    elif pkg_mgr == 'apk':
                        install_cmd = "sudo apk add --no-cache python3 py3-pip"
                    
                    await self.send(json.dumps({"status": "installing", "step": f"Installing Python via {pkg_mgr}...", "progress": 25}))
                    stdout, stderr, exit_status = await self.run_install_script(install_cmd)
                    
                    if exit_status != 0:
                        await self.send(json.dumps({"error": f"Failed to install Python: {stderr}"}))
                        await self.cleanup_connections()
                        return
                    
                    await self.send(json.dumps({"status": "installing", "step": "Python installed successfully", "progress": 35}))
                    python_cmd = 'python3'
                else:
                    await self.send(json.dumps({"error": "Could not detect package manager to install Python"}))
                    await self.cleanup_connections()
                    return
            else:
                # Python found, but check if venv module is actually functional by testing creation
                print(f"[DEBUG] Python found as {python_cmd}, checking for venv module...")
                await self.send(json.dumps({"status": "installing", "step": "Checking for venv module...", "progress": 20}))
                
                # Test creating a temporary venv to see if it actually works (not just --help)
                test_venv_cmd = f"cd /tmp && {python_cmd} -m venv test_venv_check && rm -rf test_venv_check"
                exit_status, venv_check = await self.ssh_exec_command_with_exit(test_venv_cmd)
                print(f"[DEBUG] venv test creation exit status: {exit_status}")
                if exit_status != 0:
                    await self.send(json.dumps({"status": "installing", "step": "venv module not found. Installing...", "progress": 22}))
                    print(f"[DEBUG] pkg_mgr = {pkg_mgr}")
                    
                    if pkg_mgr == 'apt':
                        print("[DEBUG] Entering apt installation block")
                        try:
                            # Get Python version for specific venv package
                            print("[DEBUG] Getting Python version...")
                            _, py_version = await self.ssh_exec_command_with_exit(f"{python_cmd} -c 'import sys; print(f\"{{sys.version_info.major}}.{{sys.version_info.minor}}\")'")
                            py_version = py_version.strip()
                            print(f"[DEBUG] Python version: {py_version}")
                        
                            # Check if user is root
                            print("[DEBUG] Checking user...")
                            whoami_exit, whoami_out = await self.ssh_exec_command_with_exit("whoami")
                            is_root = (whoami_out.strip() == "root")
                            print(f"[DEBUG] User is: {whoami_out.strip()}, is_root: {is_root}")
                        
                            await self.send(json.dumps({"status": "debug", "step": f"User: {whoami_out.strip()}, is_root: {is_root}"}))
                            
                            # Try multiple strategies to get venv working
                            venv_installed = False
                            strategies = [
                                {
                                    "name": f"python{py_version}-venv package",
                                    "cmd": f"apt-get update && apt-get install -y python{py_version}-venv"
                                },
                                {
                                    "name": "python3-venv generic package",
                                    "cmd": "apt-get install -y python3-venv"
                                },
                                {
                                    "name": "python3-virtualenv",
                                    "cmd": "apt-get install -y python3-virtualenv"
                                },
                                {
                                    "name": "ensurepip + pip install virtualenv",
                                    "cmd": f"{python_cmd} -m ensurepip --default-pip && {python_cmd} -m pip install --user virtualenv"
                                }
                            ]
                            
                            for idx, strategy in enumerate(strategies):
                                await self.send(json.dumps({"status": "installing", "step": f"Trying strategy {idx+1}/{len(strategies)}: {strategy['name']}...", "progress": 23 + idx}))
                                
                                if is_root:
                                    install_cmd = strategy['cmd']
                                    stdout, stderr, exit_status = await self.run_install_script(install_cmd, provide_password=False)
                                else:
                                    # Prefix each command with sudo -S
                                    install_cmd = ' && '.join([f"sudo -S {cmd}" for cmd in strategy['cmd'].split(' && ')])
                                    stdout, stderr, exit_status = await self.run_install_script(install_cmd, provide_password=True)
                                
                                if exit_status == 0:
                                    # Test if venv actually works now
                                    test_cmd = f"cd /tmp && {python_cmd} -m venv test_venv_verify && rm -rf test_venv_verify"
                                    test_exit, test_out = await self.ssh_exec_command_with_exit(test_cmd)
                                    if test_exit == 0:
                                        await self.send(json.dumps({"status": "installing", "step": f"✓ Strategy succeeded: {strategy['name']}", "progress": 28}))
                                        venv_installed = True
                                        break
                                    else:
                                        await self.send(json.dumps({"status": "warning", "step": f"Strategy installed but venv still not functional, trying next..."}))
                                else:
                                    await self.send(json.dumps({"status": "warning", "step": f"Strategy failed (exit {exit_status}), trying next..."}))
                            
                            if not venv_installed:
                                # Last resort: try to use virtualenv directly or create venv manually
                                await self.send(json.dumps({"status": "installing", "step": "All standard methods failed. Attempting manual venv creation...", "progress": 28}))
                                
                                # Try using virtualenv command if it exists
                                check_virtualenv_exit, _ = await self.ssh_exec_command_with_exit("which virtualenv")
                                if check_virtualenv_exit == 0:
                                    await self.send(json.dumps({"status": "installing", "step": "Found virtualenv command, will use that instead", "progress": 29}))
                                    venv_installed = True
                                else:
                                    await self.send(json.dumps({"error": "Unable to install venv or virtualenv. System may have restricted packages or network issues."}))
                                    await asyncio.sleep(0.5)
                                    await self.cleanup_connections()
                                    return
                            
                            await self.send(json.dumps({"status": "installing", "step": "venv/virtualenv ready", "progress": 30}))
                        except Exception as e:
                            print(f"[DEBUG] Exception in venv installation: {e}")
                            import traceback
                            traceback.print_exc()
                            await self.send(json.dumps({"error": f"Error during venv installation: {e}"}))
                            await self.cleanup_connections()
                            return
                    elif pkg_mgr in ['yum', 'dnf']:
                        # For RHEL-based systems, python3-venv might be separate
                        install_cmd = f"sudo {pkg_mgr} install -y python3-virtualenv"
                        await self.send(json.dumps({"status": "installing", "step": "Installing virtualenv...", "progress": 25}))
                        stdout, stderr, exit_status = await self.run_install_script(install_cmd)
                        if exit_status != 0:
                            await self.send(json.dumps({"error": f"Failed to install virtualenv: {stderr}"}))
                            await self.cleanup_connections()
                            return
                        await self.send(json.dumps({"status": "installing", "step": "virtualenv installed successfully", "progress": 30}))
                else:
                    await self.send(json.dumps({"status": "installing", "step": "venv module available", "progress": 25}))
            
            # Verify pip is available
            await self.send(json.dumps({"status": "installing", "step": "Verifying pip installation...", "progress": 40}))
            pip_cmd = f"{python_cmd} -m pip"
            exit_status, _ = await self.ssh_exec_command_with_exit(f"{pip_cmd} --version")
            if exit_status != 0:
                await self.send(json.dumps({"status": "installing", "step": "pip not found. Installing...", "progress": 45}))
                
                # Try to install pip via package manager first
                if pkg_mgr == 'apt':
                    # Get Python version for specific pip package
                    _, py_version = await self.ssh_exec_command_with_exit(f"{python_cmd} -c 'import sys; print(f\"{{sys.version_info.major}}.{{sys.version_info.minor}}\")'")
                    py_version = py_version.strip()
                    
                    # First try to install the version-specific pip package
                    install_pip_cmd = f"sudo apt-get install -y python{py_version}-pip"
                    await self.send(json.dumps({"status": "installing", "step": f"Installing python{py_version}-pip...", "progress": 47}))
                    stdout, stderr, exit_status = await self.run_install_script(install_pip_cmd)
                    
                    if exit_status != 0:
                        # Try generic python3-pip
                        await self.send(json.dumps({"status": "warning", "step": f"Trying python3-pip..."}))
                        install_pip_cmd = f"sudo apt-get install -y python3-pip"
                        stdout, stderr, exit_status = await self.run_install_script(install_pip_cmd)
                    
                    if exit_status != 0:
                        # Try ensurepip
                        await self.send(json.dumps({"status": "warning", "step": f"Trying ensurepip..."}))
                        stdout, stderr, exit_status = await self.run_install_script(f"{python_cmd} -m ensurepip --default-pip")
                    
                    if exit_status != 0:
                        # Last resort: download get-pip.py with wget
                        await self.send(json.dumps({"status": "warning", "step": f"Downloading get-pip.py..."}))
                        download_cmd = f"cd /tmp && wget -q https://bootstrap.pypa.io/get-pip.py && {python_cmd} get-pip.py && rm get-pip.py"
                        stdout, stderr, exit_status = await self.run_install_script(download_cmd)
                        
                        if exit_status != 0:
                            await self.send(json.dumps({"error": f"Failed to install pip. Last error: {stderr}"}))
                            await self.cleanup_connections()
                            return
                elif pkg_mgr in ['yum', 'dnf']:
                    install_pip_cmd = f"sudo {pkg_mgr} install -y python3-pip"
                    await self.send(json.dumps({"status": "installing", "step": f"Installing pip via {pkg_mgr}...", "progress": 47}))
                    stdout, stderr, exit_status = await self.run_install_script(install_pip_cmd)
                    if exit_status != 0:
                        await self.send(json.dumps({"error": f"Failed to install pip via {pkg_mgr}"}))
                        await self.cleanup_connections()
                        return
                elif pkg_mgr == 'apk':
                    install_pip_cmd = "sudo apk add --no-cache py3-pip"
                    await self.send(json.dumps({"status": "installing", "step": "Installing pip via apk...", "progress": 47}))
                    stdout, stderr, exit_status = await self.run_install_script(install_pip_cmd)
                    if exit_status != 0:
                        await self.send(json.dumps({"error": "Failed to install pip via apk"}))
                        await self.cleanup_connections()
                        return
                else:
                    # No package manager, try ensurepip or bootstrap
                    await self.send(json.dumps({"status": "installing", "step": "Trying ensurepip...", "progress": 47}))
                    _, _, exit_status = await self.run_install_script(f"{python_cmd} -m ensurepip --default-pip")
                    if exit_status != 0:
                        await self.send(json.dumps({"error": "Failed to install pip"}))
                        await self.cleanup_connections()
                        return
                
                await self.send(json.dumps({"status": "installing", "step": "pip installed successfully", "progress": 50}))

        # Choose install script
        if is_windows:
            cmd = f"cd C:/Users/{username}/alterion_agent && install.bat"
            script_name = "install.bat"
        else:
            # Make install.sh executable and run with sh for maximum compatibility
            cmd = f"cd /home/{username}/{agent_dir} && chmod +x install.sh && sh install.sh"
            script_name = "install.sh"

        # Run install script
        try:
            await self.send(json.dumps({"status": "installing", "step": f"Running {script_name}...", "progress": 55}))
            print(f"[DEBUG] Running command: {cmd}")
            
            # Run install and stream output line by line for progress
            stdout, stderr, exit_status = await self.run_install_script(cmd)
            
            print(f"[DEBUG] Install script exit status: {exit_status}")
            print(f"[DEBUG] Install script stdout: {stdout[:500] if stdout else 'None'}")
            print(f"[DEBUG] Install script stderr: {stderr[:500] if stderr else 'None'}")
            
            # Send stdout as log
            if stdout:
                for line in stdout.split('\n'):
                    if line.strip():
                        await self.send(json.dumps({"log": line + '\n', "status": "installing", "progress": 70}))
            
            # Send stderr as error if there was a failure
            if exit_status != 0:
                # Combine stderr and stdout for error message since errors can be in either
                error_output = []
                if stderr and stderr.strip():
                    error_output.append(f"STDERR: {stderr.strip()}")
                if stdout and stdout.strip():
                    # Get last 500 chars of stdout for context
                    error_output.append(f"STDOUT: {stdout.strip()[-500:]}")
                
                error_msg = "\n".join(error_output) if error_output else "Install script failed with no output"
                await self.send(json.dumps({"error": f"Install script failed (exit code {exit_status}):\n{error_msg}"}))
                await self.cleanup_connections()
                return
            
            await self.send(json.dumps({"status": "installing", "step": "Install script completed", "progress": 90}))
            await self.send(json.dumps({"status": "done", "step": "Install complete.", "progress": 100}))
        except Exception as e:
            await self.send(json.dumps({"error": f"Failed to run install script: {e}"}))
            print(f"[DEBUG] Install script exception: {e}")
            import traceback
            traceback.print_exc()
            await self.cleanup_connections()
            return

        # --- Wait for node to connect to DB ---
        try:
            print("[DEBUG] Waiting for node to appear in DB...")
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
                    print(f"[DEBUG] Found node in DB: {node_data}")
                    break
                await asyncio.sleep(1)
            
            if node_data:
                node_id = node_data['id']
                hostname = node_data['hostname']
                await self.send(json.dumps({"status": "node_info", "node": node_data}))
                
                # Save SSH credentials to Secret Manager (production environment)
                if self.user_password and self.ssh_username:
                    try:
                        await self.send(json.dumps({"status": "debug", "step": "Saving SSH credentials to Secret Manager..."}))
                        await self.save_node_credentials(
                            node_id=node_id,
                            username=self.ssh_username,  # Use actual SSH username from connection
                            password=self.user_password,
                            ssh_port=port
                        )
                        await self.send(json.dumps({"status": "debug", "step": "✓ SSH credentials saved to Secret Manager"}))
                    except Exception as e:
                        await self.send(json.dumps({"status": "warning", "step": f"Failed to save SSH credentials: {e}"}))
                        print(f"[DEBUG] Failed to save credentials: {e}")
            else:
                print("[DEBUG] Node not found in DB after 40 seconds")
                await self.send(json.dumps({"status": "warning", "step": "Node agent installed but not yet connected to panel"}))
        except Exception as e:
            import traceback
            await self.send(json.dumps({"status": "error", "step": f"Failed to find node by IP: {e}", "traceback": traceback.format_exc()}))
            print(f"[DEBUG] Error waiting for node: {e}")
            traceback.print_exc()
        
        # Cleanup
        print("[DEBUG] Cleaning up connections...")
        await self.cleanup_connections()
        print("[DEBUG] handle_ssh_onboard completed!")
        await self.send(json.dumps({"status": "workflow_complete", "step": "All operations finished"}))
    
    async def save_node_credentials(self, node_id, username, password, ssh_port):
        """Save node SSH credentials to Secret Manager after successful installation"""
        from .credential_manager import save_node_ssh_credentials
        from .node_models import Node
        from asgiref.sync import sync_to_async
        
        try:
            print(f"[DEBUG] Saving credentials for node {node_id}")
            
            # Save credentials to Secret Manager (runs in thread pool)
            await sync_to_async(save_node_ssh_credentials)(
                node_id=node_id,
                username=username,
                password=password,
                user=getattr(self.scope, 'user', None)
            )
            
            # Update Node record with ssh_port and key_id
            def update_node():
                node = Node.objects.get(id=node_id)
                node.ssh_port = ssh_port
                node.ssh_key_id = f"node_{node_id}_ssh"  # Reference to credentials in Secret Manager
                node.username = username
                node.save()
                return node
            
            await sync_to_async(update_node)()
            
            print(f"[DEBUG] Successfully saved SSH credentials for node {node_id}")
            
        except Exception as e:
            print(f"[DEBUG] Error saving credentials for node {node_id}: {e}")
            import traceback
            traceback.print_exc()
            raise
            
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
    def connect_ssh(self, host, port, username, auth_credential):
        """Run SSH connection in thread pool to avoid blocking
        auth_credential can be either a private key (PEM string) or a password
        """
        print(f"[DEBUG] Starting SSH connection to {host}:{port}")
        
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print("[DEBUG] SSHClient created, attempting connection...")
        
        # Try to determine if auth_credential is a private key or password
        # If it looks like a PEM key (starts with -----BEGIN), use key auth
        # Otherwise, use password auth
        if auth_credential and auth_credential.strip().startswith('-----BEGIN'):
            print("[DEBUG] Using private key authentication")
            try:
                key = paramiko.RSAKey.from_private_key(io.StringIO(auth_credential))
                print("[DEBUG] Private key parsed")
                self.ssh.connect(host, port=port, username=username, pkey=key, timeout=30, banner_timeout=30)
            except Exception as e:
                print(f"[DEBUG] RSA key failed, trying DSA/ECDSA/Ed25519: {e}")
                # Try other key types
                for key_class in [paramiko.DSSKey, paramiko.ECDSAKey, paramiko.Ed25519Key]:
                    try:
                        key = key_class.from_private_key(io.StringIO(auth_credential))
                        print(f"[DEBUG] {key_class.__name__} parsed")
                        self.ssh.connect(host, port=port, username=username, pkey=key, timeout=30, banner_timeout=30)
                        break
                    except Exception:
                        continue
                else:
                    raise Exception("Failed to parse private key with any supported key type")
        else:
            print("[DEBUG] Using password authentication")
            self.ssh.connect(host, port=port, username=username, password=auth_credential, timeout=30, banner_timeout=30)
        
        print("[DEBUG] SSH connected successfully")
        
        self.sftp = self.ssh.open_sftp()
        print("[DEBUG] SFTP session opened")
        return True        
    @sync_to_async
    def ssh_exec_command_with_exit(self, command):
        """Run SSH command and wait for exit status
        Returns (exit_status, stdout_output)
        """
        stdin, stdout, stderr = self.ssh.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        out_bytes = stdout.read()
        out = out_bytes.decode().strip() if hasattr(out_bytes, 'decode') else str(out_bytes).strip()
        return exit_status, out
    
    @sync_to_async
    def sftp_mkdir(self, path):
        """Create directory via SFTP in thread pool"""
        self.sftp.mkdir(path)
    
    @sync_to_async
    def sftp_put(self, local_path, remote_path):
        """Upload file via SFTP in thread pool"""
        self.sftp.put(local_path, remote_path)
    
    @sync_to_async
    def sftp_put_bytes(self, bytes_io, remote_path):
        """Upload bytes from BytesIO object via SFTP in thread pool"""
        with self.sftp.open(remote_path, 'wb') as remote_file:
            remote_file.write(bytes_io.getvalue())
    
    @sync_to_async
    def sftp_listdir(self, path):
        """List directory via SFTP in thread pool"""
        return self.sftp.listdir(path)
    
    @sync_to_async
    def run_install_script(self, command, provide_password=False):
        """Run install script and return output
        If provide_password=True and we have a password, send it to stdin for sudo -S
        """
        import time
        print(f"[DEBUG] run_install_script called with provide_password={provide_password}")
        print(f"[DEBUG] Command: {command[:100]}...")
        
        stdin, stdout, stderr = self.ssh.exec_command(command, get_pty=True)
        
        # If command uses sudo -S and we have a password, send it
        if provide_password and self.user_password and 'sudo' in command:
            print("[DEBUG] Sending password to sudo...")
            stdin.write(self.user_password + '\n')
            stdin.flush()
            print("[DEBUG] Password sent")
        
        all_stdout = ""
        all_stderr = ""
        
        # Read output in real-time with timeout
        print("[DEBUG] Starting to read output...")
        timeout = 300  # 5 minutes timeout for apt commands
        start_time = time.time()
        
        while True:
            if time.time() - start_time > timeout:
                print("[DEBUG] Command timeout!")
                raise Exception(f"Command timed out after {timeout} seconds")
            
            if stdout.channel.recv_ready():
                line = stdout.readline()
                if line:
                    all_stdout += line
                    if len(all_stdout) % 1000 == 0:  # Log progress every 1000 chars
                        print(f"[DEBUG] Read {len(all_stdout)} chars so far...")
            
            if stdout.channel.recv_stderr_ready():
                err_line = stderr.readline()
                if err_line:
                    all_stderr += err_line
            
            if stdout.channel.exit_status_ready():
                print("[DEBUG] Command finished, exit status ready")
                break
            
            time.sleep(0.1)  # Small delay to avoid busy waiting
        
        # Get any remaining output
        remaining_stdout = stdout.read().decode()
        remaining_stderr = stderr.read().decode()
        all_stdout += remaining_stdout
        all_stderr += remaining_stderr
        
        exit_status = stdout.channel.recv_exit_status()
        print(f"[DEBUG] Command exit status: {exit_status}")
        print(f"[DEBUG] Output length: stdout={len(all_stdout)}, stderr={len(all_stderr)}")
        
        return all_stdout, all_stderr, exit_status