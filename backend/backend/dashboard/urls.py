from rest_framework.routers import DefaultRouter
from .views import simple_speed_test,ServerViewSet, MetricViewSet, AlertViewSet, InitialDataView, MetricsAPIView
from .widget_views import WidgetLayoutView, WidgetLibraryView
from .widget_data_views import (
    AlertsWidgetView,
    TrafficWidgetView,
    UptimeWidgetView,
    PerformanceWidgetView,
    QuickActionsWidgetView,
    ActivityWidgetView,
    DomainExpiryWidgetView
)

router = DefaultRouter()
router.register(r'servers', ServerViewSet)
router.register(r'metrics', MetricViewSet)
router.register(r'alerts', AlertViewSet)

from django.urls import path

urlpatterns = router.urls + [
	path('initial-data/', InitialDataView.as_view(), name='initial-data'),
	path('system-metrics/', MetricsAPIView.as_view(), name='system-metrics'),
    path('internet-speed-test/', simple_speed_test, name='speed-test'),
    path('widget-layout/', WidgetLayoutView.as_view(), name='widget-layout'),
    path('widget-library/', WidgetLibraryView.as_view(), name='widget-library'),
    
    # Widget data endpoints
    path('alterion/panel/widget/alerts', AlertsWidgetView.as_view(), name='widget-alerts'),
    path('alterion/panel/widget/traffic', TrafficWidgetView.as_view(), name='widget-traffic'),
    path('alterion/panel/widget/uptime', UptimeWidgetView.as_view(), name='widget-uptime'),
    path('alterion/panel/widget/performance', PerformanceWidgetView.as_view(), name='widget-performance'),
    path('alterion/panel/widget/quick-actions', QuickActionsWidgetView.as_view(), name='widget-quick-actions'),
    path('alterion/panel/widget/activity', ActivityWidgetView.as_view(), name='widget-activity'),
    path('alterion/panel/widget/domains', DomainExpiryWidgetView.as_view(), name='widget-domains'),
]
