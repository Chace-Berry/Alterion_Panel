"""
WebSocket consumer for terminal connections
Handles SSH connections to servers and local terminal sessions
"""
import json
import asyncio
import subprocess
import os
import sys
from channels.generic.websocket import AsyncWebsocketConsumer
from dashboard.models import Server


class TerminalConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for interactive terminal sessions
    Supports:
    - Local terminal (when node_id starts with 'local-')
    - SSH to servers
    """

    async def connect(self):
        """Accept WebSocket connection and initialize terminal"""
        self.node_id = self.scope['url_route']['kwargs'].get('node_id')
        self.server_id = self.scope['url_route']['kwargs'].get('server_id')
        
        self.ssh_client = None
        self.ssh_channel = None
        self.process = None
        self.pty_master = None
        self.pty_slave = None
        self.shell_task = None
        
        await self.accept()
        
        try:
            # Determine connection type and initialize
            if self.node_id and self.node_id.startswith('local-'):
                # Local terminal on the server itself
                await self.init_local_terminal()
            elif self.node_id:
                # Treat node_id as server ID or name for SSH
                server = await self.get_server_by_id_or_name(self.node_id)
                if server:
                    await self.init_ssh_connection(server)
                else:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': f'Server not found: {self.node_id}'
                    }))
                    await self.close()
            elif self.server_id:
                # SSH to server
                try:
                    server = await asyncio.to_thread(
                        Server.objects.get,
                        id=self.server_id
                    )
                    await self.init_ssh_connection(server)
                except Server.DoesNotExist:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': f'Server not found: {self.server_id}'
                    }))
                    await self.close()
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'No node or server specified'
                }))
                await self.close()
                
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Connection failed: {str(e)}'
            }))
            await self.close()

    async def disconnect(self, close_code):
        """Clean up resources on disconnect"""
        # Stop shell reading task
        if self.shell_task:
            self.shell_task.cancel()
            try:
                await self.shell_task
            except asyncio.CancelledError:
                pass
        
        # Close SSH connection
        if self.ssh_channel:
            self.ssh_channel.close()
        if self.ssh_client:
            self.ssh_client.close()
        
        # Close local process
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except:
                self.process.kill()
        
        # Close PTY
        if self.pty_master is not None:
            try:
                os.close(self.pty_master)
            except:
                pass
        if self.pty_slave is not None:
            try:
                os.close(self.pty_slave)
            except:
                pass

    async def receive(self, text_data):
        """Handle incoming messages from WebSocket"""
        try:
            data = json.loads(text_data)
            
            if data['type'] == 'input':
                # Send input to terminal
                user_input = data['data']
                
                if self.ssh_channel:
                    # SSH connection
                    self.ssh_channel.send(user_input)
                elif self.process and sys.platform == 'win32':
                    # Windows subprocess
                    self.process.stdin.write(user_input.encode())
                    self.process.stdin.flush()
                elif self.pty_master is not None:
                    # Unix PTY
                    os.write(self.pty_master, user_input.encode())
                    
            elif data['type'] == 'resize':
                # Handle terminal resize
                cols = data.get('cols', 80)
                rows = data.get('rows', 24)
                
                if self.ssh_channel:
                    self.ssh_channel.resize_pty(width=cols, height=rows)
                elif self.pty_master is not None and hasattr(os, 'set_winsz'):
                    import fcntl
                    import struct
                    import termios
                    winsize = struct.pack('HHHH', rows, cols, 0, 0)
                    fcntl.ioctl(self.pty_master, termios.TIOCSWINSZ, winsize)
                    
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Error processing input: {str(e)}'
            }))

    async def init_local_terminal(self):
        """Initialize a local terminal session on the server"""
        try:
            if sys.platform == 'win32':
                await self.init_local_terminal_windows()
            else:
                await self.init_local_terminal_unix()
                
            await self.send(text_data=json.dumps({
                'type': 'connected',
                'message': f'Connected to local terminal ({sys.platform})'
            }))
            
        except Exception as e:
            raise Exception(f'Failed to start local terminal: {str(e)}')

    async def init_local_terminal_windows(self):
        """Initialize Windows local terminal using subprocess"""
        # Start PowerShell process
        self.process = subprocess.Popen(
            ['powershell.exe', '-NoLogo', '-NoProfile'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=False,
            bufsize=0
        )
        
        # Start reading output
        self.shell_task = asyncio.create_task(self.read_process_output())

    async def init_local_terminal_unix(self):
        """Initialize Unix/Linux local terminal using PTY"""
        import pty
        
        # Create a pseudo-terminal
        self.pty_master, self.pty_slave = pty.openpty()
        
        # Start shell process
        shell = os.environ.get('SHELL', '/bin/bash')
        self.process = subprocess.Popen(
            [shell],
            stdin=self.pty_slave,
            stdout=self.pty_slave,
            stderr=self.pty_slave,
            preexec_fn=os.setsid
        )
        
        # Start reading output
        self.shell_task = asyncio.create_task(self.read_pty_output())

    async def init_ssh_connection(self, server):
        """Initialize SSH connection to a server"""
        import paramiko
        
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Connect to server
        await asyncio.to_thread(
            self.ssh_client.connect,
            hostname=server.ip_address,
            username=getattr(server, 'ssh_user', 'root'),
            password=getattr(server, 'ssh_password', None),
            key_filename=getattr(server, 'ssh_key', None),
            port=getattr(server, 'ssh_port', 22),
            timeout=10
        )
        
        # Open interactive shell
        self.ssh_channel = self.ssh_client.invoke_shell(term='xterm-256color')
        self.ssh_channel.settimeout(0.0)
        
        # Start reading output
        self.shell_task = asyncio.create_task(self.read_shell_output())
        
        await self.send(text_data=json.dumps({
            'type': 'connected',
            'message': f'Connected to server: {server.name}'
        }))

    async def read_process_output(self):
        """Read output from Windows subprocess"""
        try:
            while True:
                # Read from subprocess stdout
                data = await asyncio.to_thread(self.process.stdout.read, 1024)
                if data:
                    await self.send(text_data=json.dumps({
                        'type': 'output',
                        'data': data.decode('utf-8', errors='replace')
                    }))
                else:
                    break
                await asyncio.sleep(0.01)
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Process output error: {str(e)}'
            }))

    async def read_pty_output(self):
        """Read output from Unix PTY"""
        import select
        try:
            while True:
                # Check if data is available
                ready, _, _ = await asyncio.to_thread(
                    select.select, [self.pty_master], [], [], 0.1
                )
                
                if ready:
                    data = await asyncio.to_thread(os.read, self.pty_master, 1024)
                    if data:
                        await self.send(text_data=json.dumps({
                            'type': 'output',
                            'data': data.decode('utf-8', errors='replace')
                        }))
                else:
                    await asyncio.sleep(0.01)
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'PTY output error: {str(e)}'
            }))

    async def read_shell_output(self):
        """Read output from SSH channel"""
        try:
            while True:
                if self.ssh_channel.recv_ready():
                    data = self.ssh_channel.recv(1024)
                    if data:
                        await self.send(text_data=json.dumps({
                            'type': 'output',
                            'data': data.decode('utf-8', errors='replace')
                        }))
                else:
                    await asyncio.sleep(0.01)
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'SSH output error: {str(e)}'
            }))

    async def get_server_by_id_or_name(self, identifier):
        """Get server by ID or name"""
        try:
            # Try to get by ID (if numeric)
            if identifier.isdigit():
                return await asyncio.to_thread(
                    Server.objects.get,
                    id=int(identifier)
                )
            else:
                # Try to get by name
                return await asyncio.to_thread(
                    Server.objects.get,
                    name=identifier
                )
        except:
            return None
