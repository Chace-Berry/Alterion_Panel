from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PageViewSet
from .deployment_views import (
    ProjectViewSet, DomainConfigViewSet, DeploymentViewSet,
    ComponentLibraryViewSet, AnimationViewSet
)

router = DefaultRouter()
router.register(r'pages', PageViewSet, basename='page')
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'domains', DomainConfigViewSet, basename='domain')
router.register(r'deployments', DeploymentViewSet, basename='deployment')
router.register(r'components', ComponentLibraryViewSet, basename='component')
router.register(r'animations', AnimationViewSet, basename='animation')

urlpatterns = [
    path('', include(router.urls)),
]
