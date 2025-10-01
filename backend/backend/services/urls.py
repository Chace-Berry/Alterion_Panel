from rest_framework.routers import DefaultRouter
from .views import (
    FTPAccountViewSet, DatabaseViewSet,
    EmailAccountViewSet, ServiceStatusViewSet
)
from .views import manage_service

router = DefaultRouter()
router.register(r'ftp', FTPAccountViewSet)
router.register(r'databases', DatabaseViewSet)
router.register(r'emails', EmailAccountViewSet)
router.register(r'services', ServiceStatusViewSet)

urlpatterns = router.urls

# Additional URL patterns
from django.urls import path
urlpatterns += [
    path('manage/', manage_service, name='manage_service'),
]