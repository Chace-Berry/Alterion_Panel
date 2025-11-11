
import json
import asyncio
import websockets
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class NodeAPIClient:
    
    
    def __init__(self, node_id, timeout=30):
        self.node_id = node_id
        self.timeout = timeout
        self.ws_url = self._get_ws_url()
    
    def _get_ws_url(self):
        

        backend_host = getattr(settings, 'BACKEND_WS_HOST', 'localhost:8000')

        backend_host = backend_host.replace('http://', '').replace('https://', '')

        ws_url = f"ws://{backend_host}/alterion/panel/agent/{self.node_id}/"
        return ws_url
    
    async def call_api(self, api_name, payload=None):
        
        if payload is None:
            payload = {}
        
        try:
            logger.info(f"[NodeAPIClient] Calling {api_name} on node {self.node_id}")

            ws = await asyncio.wait_for(websockets.connect(self.ws_url), timeout=self.timeout)
            try:

                request = {
                    "type": "api_request",
                    "api": api_name,
                    "payload": payload
                }
                await ws.send(json.dumps(request))
                logger.debug(f"[NodeAPIClient] Sent request: {request}")

                response_str = await asyncio.wait_for(ws.recv(), timeout=self.timeout)
                response = json.loads(response_str)
                logger.debug(f"[NodeAPIClient] Received response: {response}")

                if response.get("type") == "api_response":
                    result = response.get("result", {})
                    logger.info(f"[NodeAPIClient] {api_name} completed successfully")
                    return result
                else:
                    logger.warning(f"[NodeAPIClient] Unexpected response type: {response.get('type')}")
                    return {"error": "Unexpected response format"}
            finally:
                await ws.close()
        
        except asyncio.TimeoutError:
            logger.error(f"[NodeAPIClient] Timeout calling {api_name} on node {self.node_id}")
            return {"error": f"Timeout connecting to node {self.node_id}"}
        
        except websockets.exceptions.WebSocketException as e:
            logger.error(f"[NodeAPIClient] WebSocket error: {e}")
            return {"error": f"WebSocket connection failed: {str(e)}"}
        
        except Exception as e:
            logger.error(f"[NodeAPIClient] Error calling {api_name}: {e}", exc_info=True)
            return {"error": f"Failed to call API: {str(e)}"}

    
    async def list_files(self, path="/"):
        
        return await self.call_api("list_files", {"path": path})
    
    async def read_file(self, path):
        
        return await self.call_api("read_file", {"path": path})
    
    async def write_file(self, path, content):
        
        return await self.call_api("write_file", {"path": path, "content": content})
    
    async def upload_file(self, path, file_name, file_bytes):
        
        import base64
        file_bytes_b64 = base64.b64encode(file_bytes).decode()
        return await self.call_api("upload_file", {
            "path": path,
            "file_name": file_name,
            "file_bytes": file_bytes_b64
        })
    
    async def create_directory(self, path):
        
        return await self.call_api("create_directory", {"path": path})
    
    async def delete(self, path):
        
        return await self.call_api("delete", {"path": path})
    
    async def rename(self, old_path, new_path):
        
        return await self.call_api("rename", {"old_path": old_path, "new_path": new_path})
    
    async def collect_metrics(self):
        
        return await self.call_api("collect_metrics")
    
    async def nlb_status(self):
        
        return await self.call_api("nlb_status")

def call_node_api_sync(node_id, api_name, payload=None, timeout=30):
    
    import asyncio
    import websockets
    import json
    import uuid
    
    if payload is None:
        payload = {}

    from oauth2_provider.models import AccessToken
    from django.utils import timezone
    from datetime import timedelta
    
    auth_token = None
    try:

        token = AccessToken.objects.filter(
            expires__gt=timezone.now()
        ).first()
        
        if not token:

            from oauth2_provider.models import Application
            from django.contrib.auth import get_user_model
            User = get_user_model()

            service_user, _ = User.objects.get_or_create(
                username='node_service',
                defaults={'is_staff': True}
            )

            app, _ = Application.objects.get_or_create(
                name='Node Service',
                client_type=Application.CLIENT_CONFIDENTIAL,
                authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS
            )

            token = AccessToken.objects.create(
                user=service_user,
                application=app,
                expires=timezone.now() + timedelta(days=365),
                token=AccessToken.generate_token(),
                scope='read write'
            )
            logger.info(f"[call_node_api_sync] Created new service token")
        
        auth_token = token.token
        logger.info(f"[call_node_api_sync] Got auth token for node API call")
    except Exception as e:
        logger.error(f"[call_node_api_sync] Failed to get auth token: {e}", exc_info=True)
    
    async def send_request():
        from django.conf import settings
        
        # Get the configured port from settings
        backend_port = getattr(settings, 'PORT', 8000)
        
        # Always use localhost for backend connecting to its own consumer
        backend_host = f'localhost:{backend_port}'
        logger.info(f"[call_node_api_sync] Using {backend_host} for backend-to-consumer connection")
        
        # Use ws:// for localhost (backend connecting to itself)
        ws_scheme = 'ws'

        if auth_token:
            ws_url = f"{ws_scheme}://{backend_host}/alterion/panel/agent/{node_id}/?token={auth_token}"
        else:
            ws_url = f"{ws_scheme}://{backend_host}/alterion/panel/agent/{node_id}/"
        
        logger.info(f"[call_node_api_sync] Connecting to {ws_url.replace(auth_token, '***') if auth_token else ws_url}")
        logger.info(f"[call_node_api_sync] API: {api_name}, Payload: {payload}")
        
        try:
            logger.info(f"[call_node_api_sync] Attempting WebSocket connection with timeout={timeout}...")

            ws = await asyncio.wait_for(
                websockets.connect(ws_url), 
                timeout=timeout
            )
            logger.info(f"[call_node_api_sync] WebSocket connected successfully")
            try:

                request_id = str(uuid.uuid4())
                request = {
                    "type": "api_request",
                    "api": api_name,
                    "payload": payload,
                    "request_id": request_id
                }
                logger.info(f"[call_node_api_sync] Sending request: {request}")
                await ws.send(json.dumps(request))
                logger.info(f"[call_node_api_sync] Request sent, waiting for response...")

                response_str = await asyncio.wait_for(ws.recv(), timeout=timeout)
                logger.info(f"[call_node_api_sync] Received response (length: {len(response_str)})")
                response = json.loads(response_str)
                logger.info(f"[call_node_api_sync] Response parsed - type: {response.get('type')}, keys: {response.keys()}")

                if response.get("type") == "api_response":
                    result = response.get("result", {})
                    logger.info(f"[call_node_api_sync] Returning result: {result.keys() if isinstance(result, dict) else type(result)}")
                    return result
                else:
                    logger.warning(f"[call_node_api_sync] Unexpected response type: {response.get('type')}")
                    return {"error": "Unexpected response format"}
            finally:
                logger.info(f"[call_node_api_sync] Closing WebSocket connection")
                await ws.close()
        except asyncio.TimeoutError:
            logger.error(f"[call_node_api_sync] Timeout error after {timeout} seconds")
            return {"error": f"Timeout after {timeout} seconds"}
        except Exception as e:
            logger.error(f"[call_node_api_sync] Error: {e}", exc_info=True)
            return {"error": str(e)}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(send_request())
        return result
    finally:
        loop.close()
