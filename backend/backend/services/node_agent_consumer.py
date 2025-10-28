# Node Agent Consumer for Alterion Panel
from channels.generic.websocket import AsyncWebsocketConsumer
import json
import os
import base64
import logging
import asyncio
from cryptography.hazmat.primitives.serialization import load_pem_public_key

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NodeAgentConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pending_verifications = {}  # Track pending verification requests
        self.log_watch_task = None
    
    async def connect(self):
        self.serverid = self.scope['url_route']['kwargs']['serverid']
        self.group_name = f"node_agent_{self.serverid}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(f"[CONNECT] WebSocket connected for serverid: {self.serverid}, group: {self.group_name}")

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
        # Remove from group
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f"[DISCONNECT] WebSocket disconnected for serverid: {self.serverid}, group: {self.group_name}")

    async def receive(self, text_data):
        try:
            msg = json.loads(text_data)
            logger.info(f"[RECEIVE] Message received: {msg}")

            # --- FRONTEND CODE VERIFICATION REQUEST ---
            if msg.get("action") == "verify_code":
                code = msg.get("code")
                verification_id = msg.get("verification_id") or f"verify_{asyncio.get_event_loop().time()}"

                logger.info(f"[RECEIVE] Code verification request - ID: {verification_id}, Code: {code}")

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
                            await sync_to_async(Node.objects.update_or_create)(
                                id=node_id,
                                defaults={
                                    "name": hostname,
                                    "hostname": hostname,
                                    "ip_address": ip_address,
                                    "port": payload.get("port", 22),
                                    "node_type": "server",
                                    "auth_key": agent_pubkey_pem.decode(errors="ignore"),
                                    "username": username,
                                    "status": "pending",
                                    "last_seen": timezone.now(),
                                    "owner": owner,
                                    "notes": code
                                }
                            )
                            logger.info(f"[RECEIVE] Added/updated pending Node {node_id} for owner {owner} (ip={ip_address})")
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
        if hasattr(self, "is_agent") and self.is_agent:
            await self.send(json.dumps({
                "type": "verify_code",
                "code": event["code"],
                "verification_id": event["verification_id"]
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