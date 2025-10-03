"""
WebSocket URL routing for Django Channels
"""
from django.urls import re_path
from .terminal_consumer import TerminalConsumer

websocket_urlpatterns = [
    re_path(r'alterion/panel/terminal/server/(?P<server_id>\d+)/$', TerminalConsumer.as_asgi()),
    re_path(r'alterion/panel/terminal/node/(?P<node_id>[^/]+)/$', TerminalConsumer.as_asgi()),
]
