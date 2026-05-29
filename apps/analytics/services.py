"""
Business logic for Analytics app.
"""
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from datetime import timedelta
from .models import Event, Metric, Funnel, FunnelStep, Cohort


class AnalyticsService:
    """Service for analytics operations."""
    
    @staticmethod
    def track_event(user, category, event_type, event_name, **kwargs):
        """
        Track an event.
        
        Args:
            user: User instance (can be None for anonymous events)
            category: Event category
            event_type: Event type
            event_name: Human-readable event name
            **kwargs: Additional event properties
        
        Returns:
            Event instance
        """
        event = Event.objects.create(
            user=user,
            category=category,
            event_type=event_type,
            event_name=event_name,
            **kwargs
        )
        return event
    
    @staticmethod
    def get_event_stats(days=30):
        """Get event statistics for the last N days."""
        start_date = timezone.now() - timedelta(days=days)
        events = Event.objects.filter(created_at__gte=start_date)
        
        return {
            'total_events': events.count(),
            'events_by_category': dict(
                events.values('category').annotate(count=Count('id')).values_list('category', 'count')
            ),
            'events_by_type': dict(
                events.values('event_type').annotate(count=Count('id')).values_list('event_type', 'count')
            ),
            'top_events': list(
                events.values('event_name').annotate(count=Count('id')).order_by('-count')[:10]
            ),
            'recent_events': events[:20]
        }
    
    @staticmethod
    def record_metric(name, value, metric_type='counter', **kwargs):
        """
        Record a metric value.
        
        Args:
            name: Metric name
            value: Metric value
            metric_type: Type of metric (counter, gauge, histogram, rate)
            **kwargs: Additional metric properties
        
        Returns:
            Metric instance
        """
        metric = Metric.objects.create(
            name=name,
            value=value,
            metric_type=metric_type,
            **kwargs
        )
        return metric
    
    @staticmethod
    def get_metric_stats(days=30):
        """Get metric statistics for the last N days."""
        start_date = timezone.now() - timedelta(days=days)
        metrics = Metric.objects.filter(period_start__gte=start_date)
        
        return {
            'total_metrics': metrics.count(),
            'metrics_by_type': dict(
                metrics.values('metric_type').annotate(count=Count('id')).values_list('metric_type', 'count')
            ),
            'metrics_by_category': dict(
                metrics.values('category').annotate(count=Count('id')).values_list('category', 'count')
            ),
            'recent_metrics': metrics[:20]
        }
    
    @staticmethod
    def track_funnel_step(funnel, user, step_name, step_index, session_id=None, **kwargs):
        """
        Track a funnel step completion.
        
        Args:
            funnel: Funnel instance
            user: User instance
            step_name: Step name
            step_index: Step index (0-based)
            session_id: Session identifier
            **kwargs: Additional properties
        
        Returns:
            FunnelStep instance
        """
        funnel_step = FunnelStep.objects.create(
            funnel=funnel,
            user=user,
            step_name=step_name,
            step_index=step_index,
            session_id=session_id or '',
            completed=True,
            completed_at=timezone.now(),
            properties=kwargs.get('properties', {})
        )
        return funnel_step
    
    @staticmethod
    def analyze_funnel(funnel_id, days=30):
        """
        Analyze funnel conversion rates.
        
        Args:
            funnel_id: Funnel UUID
            days: Number of days to analyze
        
        Returns:
            Dictionary with funnel analysis
        """
        funnel = Funnel.objects.get(id=funnel_id)
        start_date = timezone.now() - timedelta(days=days)
        
        # Get all funnel steps for this period
        steps = FunnelStep.objects.filter(
            funnel=funnel,
            created_at__gte=start_date
        )
        
        # Count unique users at each step
        total_users = steps.values('user').distinct().count()
        
        step_data = []
        for i, step_name in enumerate(funnel.steps):
            step_users = steps.filter(step_index=i).values('user').distinct().count()
            conversion_rate = (step_users / total_users * 100) if total_users > 0 else 0
            
            step_data.append({
                'step_name': step_name,
                'step_index': i,
                'users': step_users,
                'conversion_rate': round(conversion_rate, 2)
            })
        
        # Calculate overall conversion rate (users who completed all steps)
        completed_users = steps.filter(
            step_index=len(funnel.steps) - 1
        ).values('user').distinct().count()
        
        overall_conversion = (completed_users / total_users * 100) if total_users > 0 else 0
        drop_off_rate = 100 - overall_conversion
        
        return {
            'funnel_id': str(funnel.id),
            'funnel_name': funnel.name,
            'total_users': total_users,
            'steps': step_data,
            'conversion_rate': round(overall_conversion, 2),
            'drop_off_rate': round(drop_off_rate, 2)
        }
    
    @staticmethod
    def analyze_cohort(cohort_id, days=30):
        """
        Analyze cohort behavior and engagement.
        
        Args:
            cohort_id: Cohort UUID
            days: Number of days to analyze
        
        Returns:
            Dictionary with cohort analysis
        """
        cohort = Cohort.objects.get(id=cohort_id)
        start_date = timezone.now() - timedelta(days=days)
        
        # Get cohort members
        members = cohort.users.all()
        member_count = members.count()
        
        # Calculate retention rate (users active in last 7 days)
        active_users = Event.objects.filter(
            user__in=members,
            created_at__gte=timezone.now() - timedelta(days=7)
        ).values('user').distinct().count()
        
        retention_rate = (active_users / member_count * 100) if member_count > 0 else 0
        
        # Calculate engagement score (average events per user)
        total_events = Event.objects.filter(
            user__in=members,
            created_at__gte=start_date
        ).count()
        
        engagement_score = (total_events / member_count) if member_count > 0 else 0
        
        # Get top activities
        top_activities = list(
            Event.objects.filter(
                user__in=members,
                created_at__gte=start_date
            ).values('event_name').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
        )
        
        return {
            'cohort_id': str(cohort.id),
            'cohort_name': cohort.name,
            'member_count': member_count,
            'retention_rate': round(retention_rate, 2),
            'engagement_score': round(engagement_score, 2),
            'top_activities': top_activities
        }
    
    @staticmethod
    def get_user_activity(user_id, days=30):
        """Get user activity summary."""
        start_date = timezone.now() - timedelta(days=days)
        events = Event.objects.filter(
            user_id=user_id,
            created_at__gte=start_date
        )
        
        return {
            'total_events': events.count(),
            'events_by_category': dict(
                events.values('category').annotate(count=Count('id')).values_list('category', 'count')
            ),
            'events_by_day': list(
                events.extra(
                    select={'day': 'DATE(created_at)'}
                ).values('day').annotate(count=Count('id')).order_by('day')
            ),
            'recent_events': events[:20]
        }
