from rest_framework import serializers
from .models import Page


class PageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Page
        fields = ['id', 'title', 'slug', 'blocks_json', 'published', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_slug(self, value):
        """Ensure slug is URL-safe"""
        if not value.replace('-', '').replace('_', '').isalnum():
            raise serializers.ValidationError("Slug can only contain letters, numbers, hyphens, and underscores.")
        return value
