from rest_framework.routers import DefaultRouter
from .views import simple_speed_test,ServerViewSet, MetricViewSet, AlertViewSet, InitialDataView, MetricsAPIView

router = DefaultRouter()
router.register(r'servers', ServerViewSet)
router.register(r'metrics', MetricViewSet)
router.register(r'alerts', AlertViewSet)

from django.urls import path

urlpatterns = router.urls + [
	path('initial-data/', InitialDataView.as_view(), name='initial-data'),
	path('system-metrics/', MetricsAPIView.as_view(), name='system-metrics'),
    path('internet-speed-test/', simple_speed_test, name='speed-test'),
]
