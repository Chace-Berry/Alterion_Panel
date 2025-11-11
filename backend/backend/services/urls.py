from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import (
    FTPAccountViewSet, DatabaseViewSet,
    EmailAccountViewSet, ServiceStatusViewSet
)
from .views import manage_service
from .node_views import NodeViewSet, NodeAlertViewSet
from .file_manager_views import FileManagerViewSet
from .domain_views import (
    DomainViewSet, whois_lookup, verify_domain, get_domain_verification_tokens
)
from .secret_manager_views import (
    SecretProjectViewSet, SecretEnvironmentViewSet, SecretViewSet
)

router = DefaultRouter()
router.register(r'ftp', FTPAccountViewSet)
router.register(r'databases', DatabaseViewSet)
router.register(r'emails', EmailAccountViewSet)
router.register(r'services', ServiceStatusViewSet)
router.register(r'nodes', NodeViewSet, basename='node')
router.register(r'node-alerts', NodeAlertViewSet, basename='node-alert')
router.register(r'files', FileManagerViewSet, basename='file-manager')
router.register(r'domains', DomainViewSet, basename='domain')
router.register(r'secret-projects', SecretProjectViewSet, basename='secret-project')
router.register(r'secret-environments', SecretEnvironmentViewSet, basename='secret-environment')
router.register(r'secrets', SecretViewSet, basename='secret')

# Prefix added in main backend/urls.py as /api/alterion/panel/
urlpatterns = router.urls + [
    path('manage/', manage_service, name='manage_service'),
    # Domain-related endpoints
    path('domains/whois/', whois_lookup, name='whois-lookup'),
    path('domains/verify/', verify_domain, name='verify-domain'),
    path('domains/verification-tokens/', get_domain_verification_tokens, name='domain-verification-tokens'),
]