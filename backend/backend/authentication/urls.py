from django.urls import path, include
from .custom_token_view import CustomTokenView
from .check_session import check_session

urlpatterns = [
    path('login/', CustomTokenView.as_view(), name='custom_token'),
    path('check_session/', check_session, name='check_session'),
    # All other DOT endpoints (token, revoke, introspect, etc.)
    path('', include('authentication.dot_urls')),
]
