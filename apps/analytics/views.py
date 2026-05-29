"""
Views for Analytics app.
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend

from .models import Event, Metric, Funnel, FunnelStep, Cohort, Report
from .serializers import (
    EventSerializer, EventCreateSerializer, MetricSerializer,
    FunnelSerializer, FunnelStepSerializer, CohortSerializer,
    CohortDetailSerializer, ReportSerializer,
    EventStatsSerializer, MetricStatsSerializer,
    FunnelAnalysisSerializer, CohortAnalysisSerializer
)
from .services import AnalyticsService
from .permissions import IsAdminOrReadOnly


class EventViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Event tracking and retrieval.
    """
    queryset = Event.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'event_type', 'user']
    search_fields = ['event_name', 'properties']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return EventCreateSerializer
        return EventSerializer
    
    def get_queryset(self):
        """Filter events based on user role."""
        if self.request.user.is_staff:
            return Event.objects.all()
        return Event.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Create event for current user."""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def stats(self, request):
        """Get event statistics."""
        days = int(request.query_params.get('days', 30))
        stats = AnalyticsService.get_event_stats(days=days)
        serializer = EventStatsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_activity(self, request):
        """Get current user's activity."""
        days = int(request.query_params.get('days', 30))
        activity = AnalyticsService.get_user_activity(request.user.id, days=days)
        return Response(activity)


class MetricViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Metric management.
    Admin only.
    """
    queryset = Metric.objects.all()
    serializer_class = MetricSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['name', 'metric_type', 'category', 'aggregation_period']
    ordering_fields = ['period_start', 'value']
    ordering = ['-period_start']
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get metric statistics."""
        days = int(request.query_params.get('days', 30))
        stats = AnalyticsService.get_metric_stats(days=days)
        serializer = MetricStatsSerializer(stats)
        return Response(serializer.data)


class FunnelViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Funnel management.
    """
    queryset = Funnel.objects.all()
    serializer_class = FunnelSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def analyze(self, request, pk=None):
        """Analyze funnel conversion rates."""
        days = int(request.query_params.get('days', 30))
        analysis = AnalyticsService.analyze_funnel(pk, days=days)
        serializer = FunnelAnalysisSerializer(analysis)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def track_step(self, request, pk=None):
        """Track a funnel step completion."""
        funnel = self.get_object()
        step_name = request.data.get('step_name')
        step_index = request.data.get('step_index')
        session_id = request.data.get('session_id')
        properties = request.data.get('properties', {})
        
        if not step_name or step_index is None:
            return Response(
                {'error': 'step_name and step_index are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        funnel_step = AnalyticsService.track_funnel_step(
            funnel=funnel,
            user=request.user,
            step_name=step_name,
            step_index=step_index,
            session_id=session_id,
            properties=properties
        )
        
        serializer = FunnelStepSerializer(funnel_step)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class FunnelStepViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing FunnelStep data.
    Admin only.
    """
    queryset = FunnelStep.objects.all()
    serializer_class = FunnelStepSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['funnel', 'user', 'step_name', 'completed']
    ordering_fields = ['created_at', 'step_index']
    ordering = ['-created_at']


class CohortViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Cohort management.
    """
    queryset = Cohort.objects.all()
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'member_count', 'created_at']
    ordering = ['name']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CohortDetailSerializer
        return CohortSerializer
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def update_members(self, request, pk=None):
        """Update cohort membership based on criteria."""
        cohort = self.get_object()
        cohort.update_members()
        serializer = self.get_serializer(cohort)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def analyze(self, request, pk=None):
        """Analyze cohort behavior and engagement."""
        days = int(request.query_params.get('days', 30))
        analysis = AnalyticsService.analyze_cohort(pk, days=days)
        serializer = CohortAnalysisSerializer(analysis)
        return Response(serializer.data)


class ReportViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Report management.
    Admin only.
    """
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['report_type', 'frequency', 'is_active']
    ordering_fields = ['name', 'last_run', 'next_run']
    ordering = ['name']
    
    @action(detail=True, methods=['post'])
    def run_now(self, request, pk=None):
        """Run report immediately."""
        report = self.get_object()
        # TODO: Implement report generation
        return Response({
            'message': 'Report generation started',
            'report_id': str(report.id)
        })
