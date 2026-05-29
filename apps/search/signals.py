"""
Search App Signals
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta

from apps.search.models import SearchHistory, PopularSearch


@receiver(post_save, sender=SearchHistory)
def update_popular_search_ctr(sender, instance, created, **kwargs):
    """
    Update click-through rate for popular searches
    """
    if created and instance.clicked_result:
        try:
            popular = PopularSearch.objects.get(query=instance.query.lower())
            
            # Calculate CTR
            total_searches = SearchHistory.objects.filter(
                query__iexact=instance.query
            ).count()
            
            clicked_searches = SearchHistory.objects.filter(
                query__iexact=instance.query,
                clicked_result=True
            ).count()
            
            ctr = (clicked_searches / total_searches * 100) if total_searches > 0 else 0
            
            popular.click_through_rate = round(ctr, 2)
            popular.save(update_fields=['click_through_rate'])
            
        except PopularSearch.DoesNotExist:
            pass


@receiver(post_save, sender=PopularSearch)
def detect_trending_searches(sender, instance, created, **kwargs):
    """
    Automatically detect trending searches based on recent activity
    """
    if not created:
        # Check if search count increased significantly in last 24 hours
        yesterday = timezone.now() - timedelta(days=1)
        
        recent_searches = SearchHistory.objects.filter(
            query__iexact=instance.query,
            created_at__gte=yesterday
        ).count()
        
        # If more than 20% of total searches happened in last 24 hours, mark as trending
        if instance.search_count > 10 and recent_searches > (instance.search_count * 0.2):
            if not instance.is_trending:
                instance.is_trending = True
                instance.save(update_fields=['is_trending'])
