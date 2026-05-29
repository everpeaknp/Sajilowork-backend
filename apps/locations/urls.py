"""
Locations URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CountryViewSet,
    StateViewSet,
    CityViewSet,
    UserLocationViewSet,
    ServiceAreaViewSet,
    LocationSearchViewSet
)

app_name = 'locations'

router = DefaultRouter()
router.register(r'countries', CountryViewSet, basename='country')
router.register(r'states', StateViewSet, basename='state')
router.register(r'cities', CityViewSet, basename='city')
router.register(r'user-locations', UserLocationViewSet, basename='user-location')
router.register(r'service-areas', ServiceAreaViewSet, basename='service-area')
router.register(r'searches', LocationSearchViewSet, basename='location-search')

urlpatterns = [
    path('', include(router.urls)),
]
