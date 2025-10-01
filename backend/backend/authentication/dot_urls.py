from django.urls import path, include
from oauth2_provider import urls as dot_urls

urlpatterns = [
    # All DOT endpoints (token, revoke, introspect, etc.) under the custom API path
    path('', include(dot_urls, namespace='oauth2_provider')),
]
