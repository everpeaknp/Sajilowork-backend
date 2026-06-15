"""Service-facing serializers (backed by Task rows tagged listing:service)."""
from rest_framework import serializers

from apps.tasks.serializers import (
    TaskCreateSerializer,
    TaskDetailSerializer,
    TaskListSerializer,
    TaskUpdateSerializer,
)
from .meta import parse_service_meta


class ServiceListSerializer(TaskListSerializer):
    service_meta = serializers.SerializerMethodField()

    class Meta(TaskListSerializer.Meta):
        fields = [*TaskListSerializer.Meta.fields, 'service_meta']

    def get_service_meta(self, obj):
        return parse_service_meta(obj)


class ServiceDetailSerializer(TaskDetailSerializer):
    service_meta = serializers.SerializerMethodField()

    class Meta(TaskDetailSerializer.Meta):
        fields = [*TaskDetailSerializer.Meta.fields, 'service_meta']

    def get_service_meta(self, obj):
        return parse_service_meta(obj)


class ServiceCreateSerializer(TaskCreateSerializer):
    """Create a service listing (listing_kind is always service)."""

    def validate(self, attrs):
        attrs['listing_kind'] = 'service'
        return super().validate(attrs)


class ServiceUpdateSerializer(TaskUpdateSerializer):
    """Update a service listing without changing listing tags."""

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if 'tags' in attrs:
            from apps.tasks.listing import get_listing_kind, with_listing_kind

            kind = get_listing_kind(self.instance.tags) or 'service'
            attrs['tags'] = with_listing_kind(attrs['tags'], kind)
        return attrs


class ServicePurchaseSerializer(serializers.Serializer):
    package_id = serializers.CharField(max_length=32, default='basic')
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class ServicePurchasePreviewSerializer(serializers.Serializer):
    package_id = serializers.CharField(max_length=32, default='basic')
