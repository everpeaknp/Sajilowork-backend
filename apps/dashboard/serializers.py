"""
Dashboard Serializers
Serializers for dashboard statistics and analytics.
"""
from rest_framework import serializers


class PlatformOverviewSerializer(serializers.Serializer):
    """Serializer for platform overview statistics"""
    users = serializers.DictField()
    tasks = serializers.DictField()
    bids = serializers.DictField()
    reviews = serializers.DictField()
    financials = serializers.DictField()


class UserStatisticsSerializer(serializers.Serializer):
    """Serializer for user-specific statistics"""
    role = serializers.CharField()
    tasks = serializers.DictField(required=False)
    bids = serializers.DictField(required=False)
    spending = serializers.DictField(required=False)
    earnings = serializers.DictField(required=False)
    tier = serializers.DictField(required=False)
    reviews = serializers.DictField()


class GrowthMetricsSerializer(serializers.Serializer):
    """Serializer for growth metrics"""
    period_days = serializers.IntegerField()
    new_users = serializers.IntegerField()
    new_tasks = serializers.IntegerField()
    new_bids = serializers.IntegerField()
    revenue = serializers.FloatField()
    currency = serializers.CharField()


class CategoryStatisticsSerializer(serializers.Serializer):
    """Serializer for category statistics"""
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    total_tasks = serializers.IntegerField()
    open_tasks = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()


class RecentTaskSerializer(serializers.Serializer):
    """Serializer for recent task activity"""
    id = serializers.IntegerField()
    title = serializers.CharField()
    owner = serializers.CharField()
    category = serializers.CharField(allow_null=True)
    budget = serializers.FloatField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


class RecentBidSerializer(serializers.Serializer):
    """Serializer for recent bid activity"""
    id = serializers.IntegerField()
    tasker = serializers.CharField()
    task_title = serializers.CharField()
    amount = serializers.FloatField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


class RecentReviewSerializer(serializers.Serializer):
    """Serializer for recent review activity"""
    id = serializers.IntegerField()
    reviewer = serializers.CharField()
    reviewee = serializers.CharField()
    rating = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class RecentActivitySerializer(serializers.Serializer):
    """Serializer for recent platform activity"""
    recent_tasks = RecentTaskSerializer(many=True)
    recent_bids = RecentBidSerializer(many=True)
    recent_reviews = RecentReviewSerializer(many=True)


class FinancialSummarySerializer(serializers.Serializer):
    """Serializer for financial summary"""
    period_days = serializers.IntegerField()
    total_revenue = serializers.FloatField()
    platform_fees = serializers.FloatField()
    refunds = serializers.FloatField()
    payouts = serializers.FloatField()
    net_revenue = serializers.FloatField()
    currency = serializers.CharField()


class TopPerformerSerializer(serializers.Serializer):
    """Serializer for top performing taskers"""
    id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    completed_tasks = serializers.IntegerField()
    average_rating = serializers.FloatField()
    total_earned = serializers.FloatField()


class DashboardStatsRequestSerializer(serializers.Serializer):
    """Serializer for dashboard stats request parameters"""
    days = serializers.IntegerField(default=30, min_value=1, max_value=365)
    limit = serializers.IntegerField(default=10, min_value=1, max_value=100)
