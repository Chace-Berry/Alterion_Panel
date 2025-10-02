from django.urls import path, include
from oauth2_provider import urls as dot_urls

urlpatterns = [

    path('', include(dot_urls, namespace='oauth2_provider')),
]
