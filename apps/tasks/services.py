"""
Business logic services for Tasks app.
"""
from django.db.models import Q, Count, Avg
from django.utils import timezone
from datetime import timedelta
from .models import Task, TaskView, Category


class TaskService:
    """Service class for task-related business logic."""
    
    @staticmethod
    def get_nearby_tasks(latitude, longitude, radius_km=50):
        """
        Get tasks near a specific location.
        Uses Haversine formula for distance calculation.
        """
        from django.db.models import F
        from math import radians, cos, sin, asin, sqrt
        
        # Convert radius to degrees (approximate)
        radius_deg = radius_km / 111.0  # 1 degree ≈ 111 km
        
        tasks = Task.objects.filter(
            status='open',
            is_public=True,
            location_type='physical',
            latitude__isnull=False,
            longitude__isnull=False,
            latitude__range=(latitude - radius_deg, latitude + radius_deg),
            longitude__range=(longitude - radius_deg, longitude + radius_deg)
        )
        
        return tasks
    
    @staticmethod
    def get_recommended_tasks_for_tasker(tasker):
        """Get recommended tasks based on tasker's skills and location."""
        # Get tasker's skill categories
        skill_categories = tasker.skills.values_list('category', flat=True)
        
        # Base query for open tasks
        tasks = Task.objects.filter(
            status='open',
            is_public=True,
            allow_bids=True
        )
        
        # Filter by skill categories if available
        if skill_categories:
            tasks = tasks.filter(
                Q(category__name__in=skill_categories) |
                Q(category__parent__name__in=skill_categories)
            )
        
        # Prioritize tasks in tasker's city
        if tasker.city:
            tasks = tasks.filter(
                Q(city__iexact=tasker.city) |
                Q(location_type='remote')
            )
        
        # Order by relevance
        tasks = tasks.order_by('-created_at')
        
        return tasks[:20]
    
    @staticmethod
    def get_trending_tasks():
        """Get trending tasks based on views and bids."""
        # Tasks from last 7 days with high engagement
        week_ago = timezone.now() - timedelta(days=7)
        
        tasks = Task.objects.filter(
            status='open',
            is_public=True,
            created_at__gte=week_ago
        ).annotate(
            engagement_score=F('views_count') + (F('bids_count') * 5)
        ).order_by('-engagement_score')[:10]
        
        return tasks
    
    @staticmethod
    def get_featured_tasks():
        """Get featured tasks."""
        return Task.objects.filter(
            status='open',
            is_public=True,
            is_featured=True
        ).order_by('-created_at')[:10]
    
    @staticmethod
    def search_tasks(query, filters=None):
        """
        Advanced task search with filters.
        
        Args:
            query: Search query string
            filters: Dict of filters (category, city, min_budget, max_budget, work_type)
        """
        tasks = Task.objects.filter(
            status='open',
            is_public=True
        )
        
        # Text search
        if query:
            tasks = tasks.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(tags__icontains=query)
            )
        
        # Apply filters
        if filters:
            if filters.get('category'):
                tasks = tasks.filter(category_id=filters['category'])
            
            if filters.get('city'):
                tasks = tasks.filter(city__iexact=filters['city'])
            
            if filters.get('min_budget'):
                tasks = tasks.filter(budget_amount__gte=filters['min_budget'])
            
            if filters.get('max_budget'):
                tasks = tasks.filter(budget_amount__lte=filters['max_budget'])
            
            if filters.get('work_type'):
                tasks = tasks.filter(work_type=filters['work_type'])
            
            if filters.get('location_type'):
                tasks = tasks.filter(location_type=filters['location_type'])
        
        return tasks.order_by('-created_at')
    
    @staticmethod
    def get_task_analytics(task):
        """Get analytics data for a task."""
        # View analytics
        total_views = task.views_count
        unique_views = TaskView.objects.filter(task=task, user__isnull=False).values('user').distinct().count()
        
        # Time-based views
        today = timezone.now().date()
        views_today = TaskView.objects.filter(task=task, viewed_at__date=today).count()
        
        week_ago = timezone.now() - timedelta(days=7)
        views_this_week = TaskView.objects.filter(task=task, viewed_at__gte=week_ago).count()
        
        return {
            'total_views': total_views,
            'unique_views': unique_views,
            'views_today': views_today,
            'views_this_week': views_this_week,
            'total_bids': task.bids_count,
            'bookmarks': task.bookmarks_count,
        }
    
    @staticmethod
    def get_category_stats():
        """Get statistics for all categories."""
        categories = Category.objects.filter(is_active=True).annotate(
            task_count=Count('tasks'),
            avg_budget=Avg('tasks__budget_amount')
        ).order_by('-task_count')
        
        return categories
    
    @staticmethod
    def auto_expire_old_tasks():
        """
        Auto-expire tasks that are past due date and still open.
        This should be run as a periodic Celery task.
        """
        expired_tasks = Task.objects.filter(
            status='open',
            due_date__lt=timezone.now()
        )
        
        count = expired_tasks.update(status='cancelled')
        return count
    
    @staticmethod
    def calculate_platform_fee(budget_amount, fee_percentage=10):
        """Calculate platform fee for a task."""
        return (budget_amount * fee_percentage) / 100
    
    @staticmethod
    def validate_task_assignment(task, tasker):
        """Validate if a task can be assigned to a tasker."""
        errors = []
        
        # Check if task is open
        if task.status != 'open':
            errors.append('Task is not open for assignment.')
        
        # Check if tasker is verified
        if not tasker.is_verified_tasker:
            errors.append('Tasker must be verified to accept tasks.')
        
        # Check if tasker is the owner
        if task.owner == tasker:
            errors.append('Cannot assign task to the task owner.')
        
        # Check if task already has a tasker
        if task.assigned_tasker:
            errors.append('Task is already assigned to another tasker.')
        
        return len(errors) == 0, errors
