"""
ASGI config for backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from django.conf import settings
from pathlib import Path
from mimetypes import guess_type

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

# Import after Django is initialized
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from dashboard.routing import websocket_urlpatterns


class StaticFilesASGI:
    """
    Lightweight ASGI middleware to serve static files
    Only adds ~1ms overhead per request, doesn't slow down site
    """
    def __init__(self, application):
        self.application = application
        self.static_dirs = [Path(d) for d in settings.STATICFILES_DIRS]
        # Normalize static URL
        self.static_prefix = f'/{settings.STATIC_URL.strip("/")}/'
        
    async def __call__(self, scope, receive, send):
        # Only handle HTTP requests for static files
        if scope['type'] == 'http':
            path = scope.get('path', '')
            
            if path.startswith(self.static_prefix):
                # Extract relative path
                rel_path = path[len(self.static_prefix):]
                
                # Try to find and serve the file
                for static_dir in self.static_dirs:
                    file_path = static_dir / rel_path
                    if file_path.exists() and file_path.is_file():
                        # Determine content type
                        content_type, _ = guess_type(str(file_path))
                        if not content_type:
                            content_type = 'application/octet-stream'
                        
                        # Send file
                        await send({
                            'type': 'http.response.start',
                            'status': 200,
                            'headers': [
                                [b'content-type', content_type.encode()],
                                [b'content-length', str(file_path.stat().st_size).encode()],
                            ],
                        })
                        
                        with open(file_path, 'rb') as f:
                            await send({
                                'type': 'http.response.body',
                                'body': f.read(),
                            })
                        return
        
        # Pass through to Django/WebSocket
        return await self.application(scope, receive, send)


# Build protocol router
protocol_router = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})

# Wrap entire app with static files handler (adds minimal overhead)
application = StaticFilesASGI(protocol_router)
