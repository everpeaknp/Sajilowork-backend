"""
Locations Models
Handles geographic data including countries, states, cities, and user locations.
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
import uuid

User = get_user_model()


class Country(models.Model):
    """Country model with ISO codes"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=2, unique=True, help_text="ISO 3166-1 alpha-2 code")
    code3 = models.CharField(max_length=3, unique=True, help_text="ISO 3166-1 alpha-3 code")
    phone_code = models.CharField(max_length=10, help_text="International dialing code")
    currency_code = models.CharField(max_length=3, help_text="ISO 4217 currency code")
    currency_symbol = models.CharField(max_length=10)
    latitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        null=True,
        blank=True
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'locations_countries'
        verbose_name = _('Country')
        verbose_name_plural = _('Countries')
        ordering = ['name']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class State(models.Model):
    """State/Province/Region model"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name='states'
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, help_text="State/Province code")
    latitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        null=True,
        blank=True
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'locations_states'
        verbose_name = _('State')
        verbose_name_plural = _('States')
        ordering = ['name']
        unique_together = [['country', 'code']]
        indexes = [
            models.Index(fields=['country', 'code']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name}, {self.country.code}"


class City(models.Model):
    """City model"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    state = models.ForeignKey(
        State,
        on_delete=models.CASCADE,
        related_name='cities'
    )
    name = models.CharField(max_length=100)
    latitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    longitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )
    population = models.IntegerField(null=True, blank=True)
    timezone = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    is_popular = models.BooleanField(default=False, help_text="Popular cities shown first")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'locations_cities'
        verbose_name = _('City')
        verbose_name_plural = _('Cities')
        ordering = ['-is_popular', 'name']
        unique_together = [['state', 'name']]
        indexes = [
            models.Index(fields=['state', 'name']),
            models.Index(fields=['is_active']),
            models.Index(fields=['is_popular']),
            models.Index(fields=['latitude', 'longitude']),
        ]
    
    def __str__(self):
        return f"{self.name}, {self.state.code}"
    
    @property
    def country(self):
        """Get country through state"""
        return self.state.country


class UserLocation(models.Model):
    """User's saved locations (home, work, etc.)"""
    LOCATION_TYPE_CHOICES = [
        ('home', 'Home'),
        ('work', 'Work'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='saved_locations'
    )
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPE_CHOICES)
    label = models.CharField(max_length=100, help_text="Custom label (e.g., 'Mom's House')")
    address = models.TextField()
    city = models.ForeignKey(
        City,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_locations'
    )
    latitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    longitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'locations_user_locations'
        verbose_name = _('User Location')
        verbose_name_plural = _('User Locations')
        ordering = ['-is_default', '-created_at']
        indexes = [
            models.Index(fields=['user', 'location_type']),
            models.Index(fields=['user', 'is_default']),
            models.Index(fields=['latitude', 'longitude']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.label}"
    
    def save(self, *args, **kwargs):
        """Ensure only one default location per user"""
        if self.is_default:
            UserLocation.objects.filter(
                user=self.user,
                is_default=True
            ).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)


class ServiceArea(models.Model):
    """Service areas for taskers (where they can work)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='service_areas',
        limit_choices_to={'role': 'tasker'}
    )
    city = models.ForeignKey(
        City,
        on_delete=models.CASCADE,
        related_name='service_areas'
    )
    radius = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Service radius in kilometers"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'locations_service_areas'
        verbose_name = _('Service Area')
        verbose_name_plural = _('Service Areas')
        ordering = ['-created_at']
        unique_together = [['user', 'city']]
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['city', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.city.name} ({self.radius}km)"


class LocationSearch(models.Model):
    """Track location searches for analytics"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='location_searches'
    )
    session_id = models.CharField(max_length=100, blank=True)
    query = models.CharField(max_length=255)
    latitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        null=True,
        blank=True
    )
    radius = models.IntegerField(null=True, blank=True)
    results_count = models.IntegerField(default=0)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'locations_location_searches'
        verbose_name = _('Location Search')
        verbose_name_plural = _('Location Searches')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['session_id', '-created_at']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.query} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
