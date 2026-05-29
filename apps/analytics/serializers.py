"""
Serializers for Analytics app.
"""
from rest_framework import serializers
from .models import Event, Metric, Funnel, FunnelStep, Cohort, Report


class EventSerializer(serializers.ModelSerializer):
    """Serializer for Event model."""
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = Event
        fields = [
            'id', 'user', 'user_email', 'session_id',
            'category', 'event_type', 'event_name',
            'content_type', 'object_id',
            'properties', 'ip_address', 'user_agent', 'referrer',
            'country', 'city', 'device_type', 'os', 'browser',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class EventCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating events."""
    
    class Meta:
        model = Event
        fields = [
            'session_id', 'category', 'event_type', 'event_name',
            'content_type', 'object_id', 'properties',
            'ip_address', 'user_agent', 'referrer',
            'country', 'city', 'device_type', 'os', 'browser'
        ]


class MetricSerializer(serializers.ModelSerializer):
    """Serializer for Metric model."""
    
    class Meta:
        model = Metric
        fields = [
            'id', 'name', 'metric_type', 'category',
            'value', 'aggregation_period',
            'period_start', 'period_end',
            'dimensions', 'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class FunnelSerializer(serializers.ModelSerializer):
    """Serializer for Funnel model."""
    
    step_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Funnel
        fields = [
            'id', 'name', 'description', 'steps',
            'step_count', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_step_count(self, obj):
        return len(obj.steps) if obj.steps else 0


class FunnelStepSerializer(serializers.ModelSerializer):
    """Serializer for FunnelStep model."""
    
    funnel_name = serializers.CharField(source='funnel.name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = FunnelStep
        fields = [
            'id', 'funnel', 'funnel_name', 'user', 'user_email',
            'session_id', 'step_name', 'step_index',
            'completed', 'completed_at', 'properties',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class CohortSerializer(serializers.ModelSerializer):
    """Serializer for Cohort model."""
    
    class Meta:
        model = Cohort
        fields = [
            'id', 'name', 'description', 'criteria',
            'member_count', 'is_active', 'auto_update',
            'last_updated', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'member_count', 'last_updated', 'created_at', 'updated_at']


class CohortDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Cohort with user list."""
    
    users = serializers.SerializerMethodField()
    
    class Meta:
        model = Cohort
        fields = [
            'id', 'name', 'description', 'criteria',
            'users', 'member_count', 'is_active', 'auto_update',
            'last_updated', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'member_count', 'last_updated', 'created_at', 'updated_at']
    
    def get_users(self, obj):
        users = obj.users.all()[:100]  # Limit to 100 users
        return [
            {
                'id': str(user.id),
                'email': user.email,
                'full_name': user.get_full_name()
            }
            for user in users
        ]


class ReportSerializer(serializers.ModelSerializer):
    """Serializer for Report model."""
    
    class Meta:
        model = Report
        fields = [
            'id', 'name', 'report_type', 'description',
            'frequency', 'recipients', 'parameters',
            'is_active', 'last_run', 'next_run',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'last_run', 'next_run', 'created_at', 'updated_at']


class EventStatsSerializer(serializers.Serializer):
    """Serializer for event statistics."""
    
    total_events = serializers.IntegerField()
    events_by_category = serializers.DictField()
    events_by_type = serializers.DictField()
    top_events = serializers.ListField()
    recent_events = EventSerializer(many=True)


class MetricStatsSerializer(serializers.Serializer):
    """Serializer for metric statistics."""
    
    total_metrics = serializers.IntegerField()
    metrics_by_type = serializers.DictField()
    metrics_by_category = serializers.DictField()
    recent_metrics = MetricSerializer(many=True)


class FunnelAnalysisSerializer(serializers.Serializer):
    """Serializer for funnel analysis."""
    
    funnel_id = serializers.UUIDField()
    funnel_name = serializers.CharField()
    total_users = serializers.IntegerField()
    steps = serializers.ListField()
    conversion_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    drop_off_rate = serializers.DecimalField(max_digits=5, decimal_places=2)


class CohortAnalysisSerializer(serializers.Serializer):
    """Serializer for cohort analysis."""
    
    cohort_id = serializers.UUIDField()
    cohort_name = serializers.CharField()
    member_count = serializers.IntegerField()
    retention_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    engagement_score = serializers.DecimalField(max_digits=5, decimal_places=2)
    top_activities = serializers.ListField()
