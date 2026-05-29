"""
Search App Models - Search history and saved searches
"""
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.users.models import User


class SearchHistory(models.Model):
    """
    Track user search history for analytics and personalization
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='search_history',
        null=True,
        blank=True,
        help_text='User who performed the search (null for anonymous)'
    )
    query = models.CharField(
        max_length=500,
        help_text='Search query text'
    )
    search_type = models.CharField(
        max_length=20,
        choices=[
            ('tasks', 'Tasks'),
            ('taskers', 'Taskers'),
            ('categories', 'Categories'),
            ('all', 'All'),
        ],
        default='tasks',
        help_text='Type of search performed'
    )
    filters = models.JSONField(
        default=dict,
        blank=True,
        help_text='Applied filters (category, location, budget, etc.)'
    )
    results_count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Number of results returned'
    )
    clicked_result = models.BooleanField(
        default=False,
        help_text='Whether user clicked on any result'
    )
    clicked_result_id = models.IntegerField(
        null=True,
        blank=True,
        help_text='ID of clicked result'
    )
    clicked_result_type = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text='Type of clicked result (task, tasker, category)'
    )
    session_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text='Session ID for anonymous users'
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text='IP address of searcher'
    )
    user_agent = models.TextField(
        blank=True,
        help_text='Browser user agent'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'search_history'
        verbose_name = 'Search History'
        verbose_name_plural = 'Search Histories'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['query', '-created_at']),
            models.Index(fields=['search_type', '-created_at']),
            models.Index(fields=['session_id', '-created_at']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        user_str = self.user.email if self.user else f'Anonymous ({self.session_id})'
        return f'{user_str}: "{self.query}" ({self.search_type})'


class SavedSearch(models.Model):
    """
    User's saved searches with notifications
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='saved_searches',
        help_text='User who saved the search'
    )
    name = models.CharField(
        max_length=200,
        help_text='User-defined name for the search'
    )
    query = models.CharField(
        max_length=500,
        help_text='Search query text'
    )
    search_type = models.CharField(
        max_length=20,
        choices=[
            ('tasks', 'Tasks'),
            ('taskers', 'Taskers'),
            ('categories', 'Categories'),
        ],
        default='tasks',
        help_text='Type of search'
    )
    filters = models.JSONField(
        default=dict,
        blank=True,
        help_text='Applied filters (category, location, budget, etc.)'
    )
    notify_new_results = models.BooleanField(
        default=True,
        help_text='Send notifications for new matching results'
    )
    notification_frequency = models.CharField(
        max_length=20,
        choices=[
            ('instant', 'Instant'),
            ('daily', 'Daily Digest'),
            ('weekly', 'Weekly Digest'),
        ],
        default='daily',
        help_text='How often to send notifications'
    )
    last_notified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Last time user was notified'
    )
    last_result_count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Number of results in last check'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether search is active'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'saved_searches'
        verbose_name = 'Saved Search'
        verbose_name_plural = 'Saved Searches'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['notify_new_results', 'is_active']),
        ]
    
    def __str__(self):
        return f'{self.user.email}: {self.name}'


class PopularSearch(models.Model):
    """
    Track popular search terms for suggestions
    """
    query = models.CharField(
        max_length=500,
        unique=True,
        help_text='Search query text'
    )
    search_count = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text='Number of times searched'
    )
    click_through_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Percentage of searches that resulted in clicks'
    )
    last_searched_at = models.DateTimeField(
        auto_now=True,
        help_text='Last time this query was searched'
    )
    is_trending = models.BooleanField(
        default=False,
        help_text='Whether this search is currently trending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'popular_searches'
        verbose_name = 'Popular Search'
        verbose_name_plural = 'Popular Searches'
        ordering = ['-search_count', '-last_searched_at']
        indexes = [
            models.Index(fields=['-search_count', '-last_searched_at']),
            models.Index(fields=['is_trending', '-search_count']),
            models.Index(fields=['query']),
        ]
    
    def __str__(self):
        return f'"{self.query}" ({self.search_count} searches)'


class SearchSuggestion(models.Model):
    """
    Curated search suggestions for autocomplete
    """
    query = models.CharField(
        max_length=500,
        unique=True,
        help_text='Suggested search query'
    )
    category = models.ForeignKey(
        'tasks.Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='search_suggestions',
        help_text='Related category'
    )
    priority = models.IntegerField(
        default=0,
        help_text='Display priority (higher = shown first)'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether suggestion is active'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'search_suggestions'
        verbose_name = 'Search Suggestion'
        verbose_name_plural = 'Search Suggestions'
        ordering = ['-priority', 'query']
        indexes = [
            models.Index(fields=['is_active', '-priority']),
            models.Index(fields=['query']),
        ]
    
    def __str__(self):
        return self.query


class SearchFilter(models.Model):
    """
    Track commonly used filter combinations
    """
    name = models.CharField(
        max_length=200,
        help_text='Filter combination name'
    )
    filters = models.JSONField(
        help_text='Filter configuration'
    )
    usage_count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Number of times used'
    )
    is_preset = models.BooleanField(
        default=False,
        help_text='Whether this is a system preset'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether filter is active'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'search_filters'
        verbose_name = 'Search Filter'
        verbose_name_plural = 'Search Filters'
        ordering = ['-usage_count', 'name']
        indexes = [
            models.Index(fields=['is_preset', 'is_active']),
            models.Index(fields=['-usage_count']),
        ]
    
    def __str__(self):
        return self.name
