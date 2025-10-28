
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from backend.authentication.cookie_oauth2 import CookieOAuth2Authentication

from channels.db import database_sync_to_async

class WSProxyConsumer(AsyncWebsocketConsumer):
    authentication_class = CookieOAuth2Authentication
    """
    Generic WebSocket proxy for node-related APIs (excluding SSH onboard and agent setup).
    Proxies messages between the frontend/backend and the node agent.
    """
    async def connect(self):
        self.node_id = self.scope['url_route']['kwargs'].get('node_id')
        self.api = self.scope['url_route']['kwargs'].get('api')

        # Authenticate user using DRF-style cookie auth
        user = await self._authenticate_user()
        self.user = user
        if not self.user or not getattr(self.user, 'is_authenticated', True):
            await self.close()
            return
        await self.accept()

    @database_sync_to_async
    def _authenticate_user(self):
        from django.http import HttpRequest
        request = HttpRequest()
        # Extract cookies from scope headers
        cookies = {}
        for header in self.scope.get('headers', []):
            if header[0].lower() == b'cookie':
                cookie_str = header[1].decode()
                for part in cookie_str.split(';'):
                    if '=' in part:
                        k, v = part.strip().split('=', 1)
                        cookies[k] = v
        request.COOKIES = cookies
        auth = self.authentication_class()
        result = auth.authenticate(request)
        if result:
            return result[0]
        return None

    async def disconnect(self, close_code):
        # Clean up any resources, close backend connections if needed
        pass

    async def receive(self, text_data=None, bytes_data=None):
        # Forward the message to the node agent (via backend-to-agent WebSocket)
        if not text_data:
            return
        data = json.loads(text_data)

        # Compose the backend-to-agent WebSocket URL (adjust as needed)
        ws_url = f"ws://localhost:8000/alterion/panel/agent/{self.node_id}/"

        # Forward the request to the node agent and await response
        import websockets
        import asyncio
        async def forward_to_node_agent():
            try:
                async with websockets.connect(ws_url) as ws:
                    # Forward the API request to the node agent
                    await ws.send(json.dumps({
                        'type': 'api_request',
                        'api': self.api,
                        'payload': data,
                        'user': str(self.user),  # Optionally pass user info
                    }))
                    # Await the response from the node agent
                    response = await ws.recv()
                    return response
            except Exception as e:
                return json.dumps({'error': str(e)})

        response = await forward_to_node_agent()
        await self.send(text_data=response)

# --- Node Agent API Logic Example ---
# On the node agent side, you would implement something like:
#
# async def handle_api_request(msg):
#     api = msg.get('api')
#     payload = msg.get('payload')
#     if api == 'collect_metrics':
#         return await collect_metrics()
#     elif api == 'list_files':
#         return await list_files(payload)
#     # ... add more API handlers as needed
#     else:
#         return {'error': f'Unknown API: {api}'}
