"""
WebSocket routing for services app
"""
from django.urls import re_path


from .terminal_consumer import TerminalConsumer
from .node_agent_consumer import NodeAgentConsumer
from .ssh_onboard_consumer import SSHOnboardConsumer

websocket_urlpatterns = [
    re_path(r'alterion/panel/terminal/server/(?P<server_id>[^/]+)/$', TerminalConsumer.as_asgi()),
    re_path(r'alterion/panel/terminal/node/(?P<node_id>[^/]+)/$', TerminalConsumer.as_asgi()),
    re_path(r'alterion/panel/agent/(?P<serverid>[^/]+)/$', NodeAgentConsumer.as_asgi()),
    re_path(r'alterion/panel/ssh_onboard/(?P<ip>[^/]+)/?$', SSHOnboardConsumer.as_asgi()),
]
