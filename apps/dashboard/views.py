"""
Dashboard Views
API endpoints for dashboard statistics and analytics.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from .services import DashboardService
from .serializers import (
    PlatformOverviewSerializer,
    UserStatisticsSerializer,
    GrowthMetricsSerializer,
    CategoryStatisticsSerializer,
    RecentActivitySerializer,
    FinancialSummarySerializer,
    TopPerformerSerializer,
    DashboardStatsRequestSerializer,
)
from .permissions import IsAdminUser, IsAuthenticatedUser


class DashboardViewSet(viewsets.ViewSet):
    """
    ViewSet for dashboard statistics and analytics.
    
    Provides various endpoints for retrieving platform-wide and user-specific statistics.
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = PlatformOverviewSerializer

    def get_serializer_class(self):
        if self.action == 'platform_overview':
            return PlatformOverviewSerializer
        if self.action == 'my_stats':
            return UserStatisticsSerializer
        if self.action == 'growth_metrics':
            return GrowthMetricsSerializer
        if self.action == 'category_statistics':
            return CategoryStatisticsSerializer
        if self.action == 'recent_activity':
            return RecentActivitySerializer
        if self.action == 'financial_summary':
            return FinancialSummarySerializer
        if self.action == 'top_performers':
            return TopPerformerSerializer
        return PlatformOverviewSerializer
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    @extend_schema(tags=['Dashboard'], responses={200: PlatformOverviewSerializer})
    def platform_overview(self, request):
        """
        Get overall platform statistics.
        
        Returns comprehensive statistics including:
        - User counts (total, customers, taskers, verified)
        - Task statistics (total, open, completed, completion rate)
        - Bid statistics (total, accepted, acceptance rate)
        - Review statistics (total, average rating)
        - Financial statistics (total payments, platform fees)
        
        **Permissions:** Admin only
        """
        data = DashboardService.get_platform_overview()
        serializer = PlatformOverviewSerializer(data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticatedUser])
    @extend_schema(tags=['Dashboard'], responses={200: UserStatisticsSerializer})
    def my_stats(self, request):
        """
        Get statistics for the current user.
        
        Returns role-specific statistics:
        - For customers: tasks posted, spending, reviews given
        - For taskers: bids submitted, earnings, reviews received, wallet balance
        
        **Permissions:** Authenticated users
        """
        data = DashboardService.get_user_statistics(request.user)
        serializer = UserStatisticsSerializer(data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    @extend_schema(tags=['Dashboard'], responses={200: GrowthMetricsSerializer})
    def growth_metrics(self, request):
        """
        Get growth metrics for a specified period.
        
        Query Parameters:
        - days (int): Number of days to analyze (default: 30, max: 365)
        
        Returns:
        - New users, tasks, bids
        - Revenue for the period
        
        **Permissions:** Admin only
        """
        params_serializer = DashboardStatsRequestSerializer(data=request.query_params)
        params_serializer.is_valid(raise_exception=True)
        
        days = params_serializer.validated_data.get('days', 30)
        data = DashboardService.get_growth_metrics(days=days)
        serializer = GrowthMetricsSerializer(data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    @extend_schema(tags=['Dashboard'], responses={200: CategoryStatisticsSerializer(many=True)})
    def category_statistics(self, request):
        """
        Get statistics by category.
        
        Returns top 10 categories with:
        - Total tasks
        - Open tasks
        - Completed tasks
        
        **Permissions:** Admin only
        """
        data = DashboardService.get_category_statistics()
        serializer = CategoryStatisticsSerializer(data, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    @extend_schema(tags=['Dashboard'], responses={200: RecentActivitySerializer})
    def recent_activity(self, request):
        """
        Get recent platform activity.
        
        Query Parameters:
        - limit (int): Number of items per category (default: 10, max: 100)
        
        Returns:
        - Recent tasks
        - Recent bids
        - Recent reviews
        
        **Permissions:** Admin only
        """
        params_serializer = DashboardStatsRequestSerializer(data=request.query_params)
        params_serializer.is_valid(raise_exception=True)
        
        limit = params_serializer.validated_data.get('limit', 10)
        data = DashboardService.get_recent_activity(limit=limit)
        serializer = RecentActivitySerializer(data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def financial_summary(self, request):
        """
        Get financial summary for a specified period.
        
        Query Parameters:
        - days (int): Number of days to analyze (default: 30, max: 365)
        
        Returns:
        - Total revenue
        - Platform fees
        - Refunds
        - Payouts
        - Net revenue
        
        **Permissions:** Admin only
        """
        params_serializer = DashboardStatsRequestSerializer(data=request.query_params)
        params_serializer.is_valid(raise_exception=True)
        
        days = params_serializer.validated_data.get('days', 30)
        data = DashboardService.get_financial_summary(days=days)
        serializer = FinancialSummarySerializer(data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def top_performers(self, request):
        """
        Get top performing taskers.
        
        Query Parameters:
        - limit (int): Number of taskers to return (default: 10, max: 100)
        
        Returns list of top taskers with:
        - Completed tasks count
        - Average rating
        - Total earnings
        
        **Permissions:** Admin only
        """
        params_serializer = DashboardStatsRequestSerializer(data=request.query_params)
        params_serializer.is_valid(raise_exception=True)
        
        limit = params_serializer.validated_data.get('limit', 10)
        data = DashboardService.get_top_performers(limit=limit)
        serializer = TopPerformerSerializer(data, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def admin_dashboard(self, request):
        """
        Get comprehensive admin dashboard data.
        
        Returns all dashboard statistics in a single response:
        - Platform overview
        - Growth metrics (30 days)
        - Category statistics
        - Recent activity (5 items each)
        - Financial summary (30 days)
        - Top performers (5 taskers)
        
        **Permissions:** Admin only
        """
        data = {
            'platform_overview': DashboardService.get_platform_overview(),
            'growth_metrics': DashboardService.get_growth_metrics(days=30),
            'category_statistics': DashboardService.get_category_statistics(),
            'recent_activity': DashboardService.get_recent_activity(limit=5),
            'financial_summary': DashboardService.get_financial_summary(days=30),
            'top_performers': DashboardService.get_top_performers(limit=5),
        }
        return Response(data)
