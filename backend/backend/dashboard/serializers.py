from rest_framework import serializers
from .models import Server, Metric, Alert

class ServerSerializer(serializers.ModelSerializer):
    identifier = serializers.ReadOnlyField()
    is_web_server = serializers.ReadOnlyField()
    domain_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Server
        fields = '__all__'
    
    def get_domain_count(self, obj):
        return obj.domains.filter(is_active=True).count()

class MetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = Metric
        fields = '__all__'

class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = '__all__'
