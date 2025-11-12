
from django.contrib import admin
from django.urls import path, include, re_path
from django.http import FileResponse
from pathlib import Path
from django.http import JsonResponse
import json
import psutil

def get_system_metrics():
    
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
    
    index_path = Path(__file__).resolve().parent.parent / 'static' / 'index.html'
    return FileResponse(open(index_path, 'rb'))


def favicon(request):
    
    favicon_path = Path(__file__).resolve().parent.parent / 'static' / 'favicon.ico'
    return FileResponse(open(favicon_path, 'rb'), content_type='image/x-icon')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/alterion/panel/', include('dashboard.urls')),
    path('api/alterion/panel/', include('services.urls')),
    path('api/alterion/panel/auth/', include('authentication.urls')),
    path('api/alterion/panel/pagebuilder/', include('pagebuilder.urls')),

    path('static/favicon.ico', favicon),

    re_path(r'^(?!api/|assets/|static/|alterion/panel/api/).*', index),
]
