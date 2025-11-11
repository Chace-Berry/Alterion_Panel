from django.urls import path, include
from .custom_token_view import CustomTokenView
from .check_session import check_session
from .user_list_views import get_recent_device_users, record_device_login, get_all_users

urlpatterns = [
    path('login/', CustomTokenView.as_view(), name='custom_token'),
    path('check_session/', check_session, name='check_session'),
    path('users/recent/', get_recent_device_users, name='recent_device_users'),
    path('users/record-login/', record_device_login, name='record_device_login'),
    path('users/', get_all_users, name='all_users'),

    path('', include('authentication.dot_urls')),
]
