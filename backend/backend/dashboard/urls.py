from rest_framework.routers import DefaultRouter
from .views import (
    simple_speed_test, available_servers, activity_logs, resolve_alert, ignore_alert, unignore_alert, ignored_alerts,
    ServerViewSet, MetricViewSet, AlertViewSet, InitialDataView, MetricsAPIView
)
from .widget_views import WidgetLayoutView, WidgetLibraryView
from .widget_data_views import (
    AlertsWidgetView,
    TrafficWidgetView,
    UptimeWidgetView,
    PerformanceWidgetView,
    QuickActionsWidgetView,
    ActivityWidgetView,
    DomainExpiryWidgetView,
    NodeWidgetProxyView
)
from .domain_views import DomainViewSet, ServerDomainViewSet, whois_lookup, verify_domain, get_domain_verification_tokens

router = DefaultRouter()
router.register(r'servers', ServerViewSet)
router.register(r'metrics', MetricViewSet)
router.register(r'alerts', AlertViewSet)
router.register(r'domains', DomainViewSet, basename='domain')
router.register(r'servers/(?P<server_pk>[^/.]+)/domains', ServerDomainViewSet, basename='server-domains')

from django.urls import path

urlpatterns = router.urls + [
	path('initial-data/', InitialDataView.as_view(), name='initial-data'),
	path('system-metrics/', MetricsAPIView.as_view(), name='system-metrics'),
    path('internet-speed-test/', simple_speed_test, name='speed-test'),
    path('widget-layout/', WidgetLayoutView.as_view(), name='widget-layout'),
    path('widget-library/', WidgetLibraryView.as_view(), name='widget-library'),

    path('alterion/panel/server/available-servers', available_servers, name='available-servers'),

    path('alterion/panel/logs/activity', activity_logs, name='activity-logs'),

    path('alterion/panel/alerts/<str:alert_id>/resolve', resolve_alert, name='resolve-alert'),
    path('alterion/panel/alerts/<str:alert_id>/ignore', ignore_alert, name='ignore-alert'),
    path('alterion/panel/alerts/<str:alert_id>/unignore', unignore_alert, name='unignore-alert'),
    path('alterion/panel/alerts/ignored', ignored_alerts, name='ignored-alerts'),

    path('alterion/panel/widget/alerts', AlertsWidgetView.as_view(), name='widget-alerts'),
    path('alterion/panel/widget/traffic', TrafficWidgetView.as_view(), name='widget-traffic'),
    path('alterion/panel/widget/uptime', UptimeWidgetView.as_view(), name='widget-uptime'),
    path('alterion/panel/widget/performance', PerformanceWidgetView.as_view(), name='widget-performance'),
    path('alterion/panel/widget/quick-actions', QuickActionsWidgetView.as_view(), name='widget-quick-actions'),
    path('alterion/panel/widget/activity', ActivityWidgetView.as_view(), name='widget-activity'),
    path('alterion/panel/widget/domains', DomainExpiryWidgetView.as_view(), name='widget-domains'),

    path('alterion/panel/whois', whois_lookup, name='whois-lookup'),
    path('alterion/panel/verify-domain', verify_domain, name='verify-domain'),
    path('alterion/panel/domain-verification-tokens', get_domain_verification_tokens, name='domain-verification-tokens'),

    path('alterion/panel/node/<int:node_id>/<str:widget_type>', NodeWidgetProxyView.as_view(), name='node-widget-proxy'),
]
