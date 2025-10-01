"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.http import FileResponse
from pathlib import Path
from django.http import JsonResponse
import json
import psutil

def get_system_metrics():
    """Get basic system metrics"""
    return {
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_percent': psutil.disk_usage('/').percent,
        'network': {
            'bytes_sent': psutil.net_io_counters().bytes_sent,
            'bytes_recv': psutil.net_io_counters().bytes_recv,
        }
    }

def index(request):
    """Serve the static React index.html file"""
    index_path = Path(__file__).resolve().parent.parent / 'static' / 'index.html'
    return FileResponse(open(index_path, 'rb'))


def favicon(request):
    """Serve the favicon.ico file from static directory"""
    favicon_path = Path(__file__).resolve().parent.parent / 'static' / 'favicon.ico'
    return FileResponse(open(favicon_path, 'rb'), content_type='image/x-icon')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('dashboard.urls')),
    path('api/', include('services.urls')),
    path('api/alterion/panel/auth/', include('authentication.urls')),

    # Serve favicon.ico from static
    path('static/favicon.ico', favicon),

    re_path(r'^(?!api/|assets/|static/|alterion/panel/api/).*', index),
]
