# Node Agent Consumer for Alterion Panel
from channels.generic.websocket import AsyncWebsocketConsumer
import json
import os
import base64
import logging
import asyncio
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from urllib.parse import parse_qs
from channels.db import database_sync_to_async

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NodeAgentConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pending_verifications = {}  # Track pending verification requests
        self.pending_api_requests = {}  # Track pending API requests
        self.log_watch_task = None
        self.is_agent = False  # Track if this connection is an agent
        self.is_authenticated = False  # Track if user is authenticated
        self.user = None  # Store authenticated user
    
    @database_sync_to_async
    def get_user_from_token(self, token):
        """Validate OAuth2 token and get user"""
        from oauth2_provider.models import AccessToken
        from django.utils import timezone
        try:
            access_token = AccessToken.objects.select_related('user').get(
                token=token,
                expires__gt=timezone.now()
            )
            return access_token.user
        except AccessToken.DoesNotExist:
            return None
    
    async def connect(self):
        self.serverid = self.scope['url_route']['kwargs']['serverid']
        self.group_name = f"node_agent_{self.serverid}"
        
        logger.info(f"[CONNECT] New WebSocket connection attempt for serverid: {self.serverid}")
        
        # Check for authentication token in query string
        query_string = self.scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]
        
        logger.info(f"[CONNECT] Query string: {query_string}, has token: {bool(token)}")
        
        if token:
            # Validate token and get user
            self.user = await self.get_user_from_token(token)
            if self.user:
                self.is_authenticated = True
                logger.info(f"[CONNECT] Authenticated user: {self.user.username}")
            else:
                logger.warning(f"[CONNECT] Invalid token provided")
        
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(f"[CONNECT] WebSocket connected - serverid: {self.serverid}, group: {self.group_name}, auth: {self.is_authenticated}, is_agent: {self.is_agent}")

    async def disconnect(self, close_code):
        # Clean up log watching task
        if self.log_watch_task:
            self.log_watch_task.cancel()
            try:
                await self.log_watch_task
            except asyncio.CancelledError:
                pass
        # Clean up any pending verifications
        for future in self.pending_verifications.values():
            if not future.done():
                future.cancel()
        self.pending_verifications.clear()
        # Clean up any pending API requests
        for future in self.pending_api_requests.values():
            if not future.done():
                future.cancel()
        self.pending_api_requests.clear()
        # Remove from group
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f"[DISCONNECT] WebSocket disconnected for serverid: {self.serverid}, group: {self.group_name}")

    async def receive(self, text_data):
        try:
            msg = json.loads(text_data)
            logger.info(f"[RECEIVE] Message received: {msg}")

            # --- FRONTEND CODE VERIFICATION REQUEST ---
            if msg.get("action") == "verify_code":
                # Allow verification requests without authentication
                # Agents authenticate via crypto handshake after verification
                # Frontend can also verify codes (they will use OAuth2 for subsequent operations)
                
                code = msg.get("code")
                verification_id = msg.get("verification_id") or f"verify_{asyncio.get_event_loop().time()}"

                user_info = self.user.username if self.user else "unauthenticated"
                logger.info(f"[RECEIVE] Code verification request - ID: {verification_id}, Code: {code}, User: {user_info}")

                # Create a Future to wait for agent response
                future = asyncio.Future()
                self.pending_verifications[verification_id] = future

                # Forward to agent(s) via group
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "forward_to_agent",
                        "code": code,
                        "verification_id": verification_id
                    }
                )
                logger.info(f"[RECEIVE] Sent verification request to agent group")

                try:
                    # Wait for agent response (with timeout)
                    result = await asyncio.wait_for(future, timeout=10)
                    logger.info(f"[RECEIVE] Verification result: {result}")
                    await self.send(json.dumps(result))
                except asyncio.TimeoutError:
                    logger.error(f"[RECEIVE] Verification timeout for ID: {verification_id}")
                    await self.send(json.dumps({
                        "verified": False,
                        "error": "Timeout waiting for agent verification"
                    }))
                finally:
                    self.pending_verifications.pop(verification_id, None)
                return

            # --- AGENT VERIFICATION RESPONSE ---
            if msg.get("type") == "verify_code_result":
                verification_id = msg.get("verification_id")
                logger.info(f"[RECEIVE] Verification result from agent - ID: {verification_id}, Result: {msg.get('result')}")

                # Forward result to all group members (frontend)
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "forward_to_frontend",
                        "verification_id": verification_id,
                        "result": msg.get("result")
                    }
                )
                return

            # --- API REQUEST (from frontend/backend to agent) ---
            if msg.get("type") == "api_request" and not self.is_agent:
                # Require authentication for API requests
                if not self.is_authenticated:
                    logger.warning(f"[RECEIVE] Unauthenticated API request rejected")
                    await self.send(json.dumps({
                        "type": "api_response",
                        "error": "Authentication required"
                    }))
                    return
                
                api_name = msg.get("api")
                payload = msg.get("payload", {})
                request_id = msg.get("request_id") or f"api_{asyncio.get_event_loop().time()}"

                logger.info(f"[RECEIVE] API request - ID: {request_id}, API: {api_name}, User: {self.user.username}")

                # Create a Future to wait for agent response
                future = asyncio.Future()
                self.pending_api_requests[request_id] = future

                # Forward to agent(s) via group
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "forward_api_to_agent",
                        "api": api_name,
                        "payload": payload,
                        "request_id": request_id
                    }
                )
                logger.info(f"[RECEIVE] Forwarded API request to agent group")

                try:
                    # Wait for agent response (with timeout)
                    result = await asyncio.wait_for(future, timeout=30)
                    logger.info(f"[RECEIVE] API response received for {api_name}")
                    await self.send(json.dumps({
                        "type": "api_response",
                        "api": api_name,
                        "request_id": request_id,
                        "result": result
                    }))
                except asyncio.TimeoutError:
                    logger.error(f"[RECEIVE] API request timeout for ID: {request_id}")
                    await self.send(json.dumps({
                        "type": "api_response",
                        "api": api_name,
                        "request_id": request_id,
                        "error": "Timeout waiting for agent response"
                    }))
                finally:
                    self.pending_api_requests.pop(request_id, None)
                return

            # --- API RESPONSE (from agent to backend/frontend) ---
            if msg.get("type") == "api_response" and self.is_agent:
                request_id = msg.get("request_id")
                result = msg.get("result")
                logger.info(f"[RECEIVE] API response from agent - ID: {request_id}")

                # Forward result to all group members (frontend/backend)
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "forward_api_to_frontend",
                        "request_id": request_id,
                        "result": result
                    }
                )
                return

            # --- AGENT REGISTRATION HANDSHAKE ---
            if msg.get("action") == "hello":
                logger.info("[RECEIVE] Action: hello")
                # Mark this connection as an agent
                self.is_agent = True
                # Accept 'agent_public_key' (base64-encoded PEM) from agent
                if "agent_public_key" not in msg:
                    await self.send(json.dumps({"error": "agent_public_key missing in hello"}))
                    return
                try:
                    agent_pubkey_pem = base64.b64decode(msg["agent_public_key"])
                    agent_public_key = load_pem_public_key(agent_pubkey_pem)
                    node_id = f"node-{self.serverid}"
                    # Save to backend/backend/keys/agent_keys/node-<serverid>-key.pem
                    key_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'keys', 'agent_keys'))
                    os.makedirs(key_dir, exist_ok=True)
                    key_path = os.path.join(key_dir, f'{node_id}-key.pem')
                    with open(key_path, 'wb') as f:
                        f.write(agent_pubkey_pem)
                    logger.info(f"[RECEIVE] Saved agent public key to {key_path}")
                    # Get backend public key
                    from crypto_utils import get_backend_public_key
                    public_key = get_backend_public_key()
                    public_pem = public_key.public_bytes(
                        encoding=__import__('cryptography.hazmat.primitives.serialization').hazmat.primitives.serialization.Encoding.PEM,
                        format=__import__('cryptography.hazmat.primitives.serialization').hazmat.primitives.serialization.PublicFormat.SubjectPublicKeyInfo
                    )
                    backend_public_key = base64.b64encode(public_pem).decode()
                    logger.info("[RECEIVE] Sending backend public key")
                    await self.send(json.dumps({
                        "status": "ok",
                        "backend_public_key": backend_public_key,
                        "serverid": self.serverid
                    }))
                except Exception as e:
                    logger.error(f"[RECEIVE] Error processing hello: {e}")
                    await self.send(json.dumps({"error": f"Failed to process hello: {e}"}))
                return

            # --- ENCRYPTED REGISTRATION ---
            if "cryptdata" in msg and "data" in msg:
                logger.info(f"[RECEIVE] Encrypted registration payload received")
                try:
                    from crypto_utils import hybrid_decrypt, hybrid_encrypt, get_backend_private_key
                    # Decrypt the registration payload
                    private_key = get_backend_private_key()
                    payload = hybrid_decrypt(msg["cryptdata"], msg["data"], private_key)
                    logger.info(f"[RECEIVE] Decrypted registration payload: {payload}")
                    # If payload is bytes, decode and parse JSON
                    if isinstance(payload, bytes):
                        payload = json.loads(payload.decode("utf-8"))
                    serverid = payload.get("serverid", self.serverid)
                    node_id = f"node-{serverid}"
                    import random, string
                    code = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
                    # Load agent public key
                    key_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'keys', 'agent_keys'))
                    key_path = os.path.join(key_dir, f'{node_id}-key.pem')
                    if not os.path.exists(key_path):
                        logger.error(f"[RECEIVE] Agent public key not found at {key_path}")
                        await self.send(json.dumps({"error": "Agent public key not found. Send 'hello' first."}))
                        return
                    with open(key_path, 'rb') as f:
                        agent_pubkey_pem = f.read()
                    # Prepare approval payload
                    approval_payload = {"node_id": node_id, "code": code}
                    from crypto_utils import load_public_key
                    # Serialize payload to JSON and encode to bytes
                    approval_payload_bytes = json.dumps(approval_payload).encode("utf-8")
                    # Load agent public key object
                    agent_public_key = load_public_key(agent_pubkey_pem)
                    # Encrypt with agent's public key
                    enc = hybrid_encrypt(approval_payload_bytes, agent_public_key)
                    logger.info(f"[RECEIVE] Sending encrypted approval for {node_id}")
                    await self.send(json.dumps({
                        "cryptdata": enc["cryptdata"],
                        "data": enc["data"]
                    }))
                    # --- Add as pending node ---
                    try:
                        from .node_models import Node, User
                        from django.utils import timezone
                        from asgiref.sync import sync_to_async
                        # Async-safe DB access
                        async def get_owner():
                            return await sync_to_async(lambda: User.objects.filter(is_superuser=True).first() or User.objects.first())()
                        owner = await get_owner()
                        if not owner:
                            logger.warning("No user found to assign as node owner. Skipping Node creation.")
                        else:
                            # Use payload IP if present and not 0.0.0.0, else use client IP from self.scope
                            payload_ip = payload.get("ip_address")
                            client_ip = None
                            try:
                                client_ip = self.scope.get('client')[0]
                            except Exception:
                                client_ip = None
                            ip_address = payload_ip if payload_ip and payload_ip != "0.0.0.0" else client_ip or "0.0.0.0"
                            hostname = payload.get("hostname") or node_id
                            username = payload.get("username") or "root"
                            sftp_port = payload.get("sftp_port")  # Local SFTP port from agent
                            
                            # Check if node exists and preserve its status if already verified
                            existing_node = await sync_to_async(Node.objects.filter(id=node_id).first)()
                            node_status = "pending"
                            if existing_node and existing_node.status in ["online", "verified"]:
                                node_status = existing_node.status
                                logger.info(f"[RECEIVE] Preserving status '{node_status}' for existing node {node_id}")
                            
                            # Prepare defaults dict
                            node_defaults = {
                                "name": hostname,
                                "hostname": hostname,
                                "ip_address": ip_address,
                                "port": payload.get("port", 22),
                                "node_type": "server",
                                "auth_key": agent_pubkey_pem.decode(errors="ignore"),
                                "username": username,
                                "status": node_status,
                                "last_seen": timezone.now(),
                                "owner": owner,
                                "notes": code
                            }
                            
                            # Add SFTP port to notes - backend will proxy SFTP via WebSocket
                            if sftp_port:
                                node_defaults["notes"] = f"{code}|sftp:{sftp_port}"
                                logger.info(f"[RECEIVE] Node {node_id} registered with SFTP port {sftp_port}")
                            
                            await sync_to_async(Node.objects.update_or_create)(
                                id=node_id,
                                defaults=node_defaults
                            )
                            logger.info(f"[RECEIVE] Added/updated Node {node_id} with status '{node_status}' for owner {owner} (ip={ip_address})")
                    except Exception as e:
                        logger.error(f"[RECEIVE] Failed to add pending Node: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"[RECEIVE] Error processing encrypted registration: {e}", exc_info=True)
                    await self.send(json.dumps({"error": f"Registration failed: {e}"}))
                return

        except Exception as e:
            logger.error(f"[RECEIVE] Error processing message: {e}", exc_info=True)
            await self.send(json.dumps({"error": str(e)}))

    # Handler for group_send to agent(s)
    async def forward_to_agent(self, event):
        # Only agent should process this
        if self.is_agent:
            await self.send(json.dumps({
                "type": "verify_code",
                "code": event["code"],
                "verification_id": event["verification_id"]
            }))

    # Handler for group_send API requests to agent(s)
    async def forward_api_to_agent(self, event):
        # Only agent should process this
        if self.is_agent:
            await self.send(json.dumps({
                "type": "api_request",
                "api": event["api"],
                "payload": event["payload"],
                "request_id": event["request_id"]
            }))

    # Handler for group_send to frontend(s)
    async def forward_to_frontend(self, event):
        verification_id = event["verification_id"]
        result = event["result"]
        resolved = {
            "verified": result == "success",
            "valid": result == "success",
            "error": None if result == "success" else "Invalid code"
        }
        # Send to all frontend connections in the group (broadcast)
        await self.send(json.dumps({
            "type": "verify_code_result",
            "verification_id": verification_id,
            **resolved
        }))
        # Also resolve the future if this connection is waiting
        if verification_id in self.pending_verifications:
            self.pending_verifications[verification_id].set_result(resolved)
            logger.info(f"[GROUP] Resolved verification future for ID: {verification_id}")
        # Always update Node status if successful (even if not the waiting connection)
        if result == "success":
            try:
                from .node_models import Node
                from django.utils import timezone
                from asgiref.sync import sync_to_async
                # Always use node_id = f"node-{self.serverid}" for DB consistency
                node_id = f"node-{self.serverid}"
                now = timezone.now()
                await sync_to_async(Node.objects.filter(id=node_id).update)(status="online", last_seen=now)
                logger.info(f"[GROUP] Node {node_id} status updated to 'online' and last_seen set")
            except Exception as e:
                logger.error(f"[GROUP] Failed to update Node status: {e}", exc_info=True)

    # Handler for group_send API responses to frontend(s)
    async def forward_api_to_frontend(self, event):
        request_id = event["request_id"]
        result = event["result"]
        
        # Resolve the future if this connection is waiting for this response
        if request_id in self.pending_api_requests:
            self.pending_api_requests[request_id].set_result(result)
            logger.info(f"[GROUP] Resolved API request future for ID: {request_id}")
        
        # Also broadcast to all frontend connections in the group
        if not self.is_agent:
            await self.send(json.dumps({
                "type": "api_response",
                "request_id": request_id,
                "result": result
            }))