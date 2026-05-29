"""
Locations Views
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q

from .models import Country, State, City, UserLocation, ServiceArea, LocationSearch
from .serializers import (
    CountrySerializer, CountryListSerializer,
    StateSerializer, StateListSerializer,
    CitySerializer, CityListSerializer, CityWithDistanceSerializer,
    UserLocationSerializer, UserLocationCreateSerializer,
    ServiceAreaSerializer, ServiceAreaCreateSerializer,
    LocationSearchSerializer, LocationSearchCreateSerializer,
    CitySearchRequestSerializer, NearbyCitiesRequestSerializer,
    FindTaskersRequestSerializer, LocationStatisticsSerializer,
    TopSearchedLocationSerializer
)
from .permissions import IsOwnerOrReadOnly, IsTaskerForServiceArea
from .services import LocationService


class CountryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Country operations (read-only).
    """
    queryset = Country.objects.filter(is_active=True).order_by('name')
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'code3']
    ordering_fields = ['name', 'code']
    
    def get_serializer_class(self):
        """Return appropriate serializer class"""
        if self.action == 'list':
            return CountryListSerializer
        return CountrySerializer
    
    @action(detail=False, methods=['get'])
    def popular(self, request):
        """Get popular countries (with most cities)"""
        from django.db.models import Count
        
        countries = Country.objects.filter(
            is_active=True
        ).annotate(
            city_count=Count('states__cities')
        ).order_by('-city_count')[:20]
        
        serializer = CountryListSerializer(countries, many=True)
        return Response(serializer.data)


class StateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for State operations (read-only).
    """
    queryset = State.objects.filter(is_active=True).select_related('country')
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['country', 'country__code']
    search_fields = ['name', 'code', 'country__name']
    ordering_fields = ['name', 'code']
    
    def get_serializer_class(self):
        """Return appropriate serializer class"""
        if self.action == 'list':
            return StateListSerializer
        return StateSerializer
    
    @action(detail=False, methods=['get'])
    def by_country(self, request):
        """Get states by country code"""
        country_code = request.query_params.get('country_code')
        
        if not country_code:
            return Response({
                'error': 'country_code parameter is required.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        states = State.objects.filter(
            is_active=True,
            country__code=country_code.upper()
        ).select_related('country').order_by('name')
        
        serializer = StateListSerializer(states, many=True)
        return Response(serializer.data)


class CityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for City operations (read-only).
    """
    queryset = City.objects.filter(is_active=True).select_related('state', 'state__country')
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['state', 'state__country', 'is_popular']
    search_fields = ['name', 'state__name', 'state__country__name']
    ordering_fields = ['name', 'population', 'is_popular']
    
    def get_serializer_class(self):
        """Return appropriate serializer class"""
        if self.action == 'list':
            return CityListSerializer
        return CitySerializer
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search cities with filters"""
        serializer = CitySearchRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        query = serializer.validated_data.get('query', '')
        country_code = serializer.validated_data.get('country_code')
        state_code = serializer.validated_data.get('state_code')
        limit = serializer.validated_data.get('limit', 20)
        
        cities = LocationService.search_cities(
            query=query,
            country_code=country_code,
            state_code=state_code,
            limit=limit
        )
        
        # Record search
        if request.user.is_authenticated or request.session.session_key:
            LocationService.record_location_search(
                query=query,
                results_count=len(cities),
                user=request.user if request.user.is_authenticated else None,
                session_id=request.session.session_key or '',
                request=request
            )
        
        result_serializer = CityListSerializer(cities, many=True)
        return Response(result_serializer.data)
    
    @action(detail=False, methods=['get'])
    def nearby(self, request):
        """Get nearby cities"""
        serializer = NearbyCitiesRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        latitude = serializer.validated_data['latitude']
        longitude = serializer.validated_data['longitude']
        radius = serializer.validated_data.get('radius', 50)
        limit = serializer.validated_data.get('limit', 20)
        
        results = LocationService.get_nearby_cities(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius,
            limit=limit
        )
        
        # Add distance to each city
        cities_with_distance = []
        for result in results:
            city_data = CityListSerializer(result['city']).data
            city_data['distance'] = result['distance']
            cities_with_distance.append(city_data)
        
        return Response(cities_with_distance)
    
    @action(detail=False, methods=['get'])
    def popular(self, request):
        """Get popular cities"""
        country_code = request.query_params.get('country_code')
        limit = int(request.query_params.get('limit', 20))
        
        cities = LocationService.get_popular_cities(
            country_code=country_code,
            limit=limit
        )
        
        serializer = CityListSerializer(cities, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_state(self, request):
        """Get cities by state code"""
        state_code = request.query_params.get('state_code')
        country_code = request.query_params.get('country_code')
        
        if not state_code:
            return Response({
                'error': 'state_code parameter is required.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        queryset = City.objects.filter(
            is_active=True,
            state__code=state_code.upper()
        ).select_related('state', 'state__country')
        
        if country_code:
            queryset = queryset.filter(state__country__code=country_code.upper())
        
        cities = queryset.order_by('-is_popular', 'name')
        
        page = self.paginate_queryset(cities)
        if page is not None:
            serializer = CityListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = CityListSerializer(cities, many=True)
        return Response(serializer.data)


class UserLocationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for UserLocation CRUD operations.
    """
    serializer_class = UserLocationSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['location_type', 'is_default', 'is_active']
    ordering_fields = ['created_at', 'is_default']
    
    def get_queryset(self):
        """Return locations for current user"""
        return UserLocation.objects.filter(
            user=self.request.user
        ).select_related('city', 'city__state', 'city__state__country')
    
    def get_serializer_class(self):
        """Return appropriate serializer class"""
        if self.action == 'create':
            return UserLocationCreateSerializer
        return UserLocationSerializer
    
    def perform_create(self, serializer):
        """Create location for current user"""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def default(self, request):
        """Get user's default location"""
        location = UserLocation.objects.filter(
            user=request.user,
            is_default=True,
            is_active=True
        ).select_related('city', 'city__state', 'city__state__country').first()
        
        if not location:
            return Response({
                'error': 'No default location found.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = UserLocationSerializer(location)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set location as default"""
        location = self.get_object()
        
        # Unset other defaults
        UserLocation.objects.filter(
            user=request.user,
            is_default=True
        ).exclude(id=location.id).update(is_default=False)
        
        # Set this as default
        location.is_default = True
        location.save()
        
        serializer = UserLocationSerializer(location)
        return Response(serializer.data)


class ServiceAreaViewSet(viewsets.ModelViewSet):
    """
    ViewSet for ServiceArea CRUD operations.
    """
    serializer_class = ServiceAreaSerializer
    permission_classes = [IsAuthenticated, IsTaskerForServiceArea]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['city', 'is_active']
    ordering_fields = ['created_at', 'radius']
    
    def get_queryset(self):
        """Return service areas for current user"""
        return ServiceArea.objects.filter(
            user=self.request.user
        ).select_related('city', 'city__state', 'city__state__country')
    
    def get_serializer_class(self):
        """Return appropriate serializer class"""
        if self.action == 'create':
            return ServiceAreaCreateSerializer
        return ServiceAreaSerializer
    
    def perform_create(self, serializer):
        """Create service area for current user"""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def check_coverage(self, request):
        """Check if a location is covered by user's service areas"""
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        if not latitude or not longitude:
            return Response({
                'error': 'latitude and longitude are required.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (TypeError, ValueError):
            return Response({
                'error': 'Invalid latitude or longitude.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        is_covered = LocationService.is_location_in_service_area(
            user_id=request.user.id,
            latitude=latitude,
            longitude=longitude
        )
        
        return Response({
            'is_covered': is_covered,
            'latitude': latitude,
            'longitude': longitude
        })
    
    @action(detail=False, methods=['post'])
    def find_taskers(self, request):
        """Find taskers who service a location"""
        serializer = FindTaskersRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        latitude = serializer.validated_data['latitude']
        longitude = serializer.validated_data['longitude']
        radius = serializer.validated_data.get('radius', 10)
        skills = serializer.validated_data.get('skills', [])
        
        tasker_ids = LocationService.find_taskers_in_area(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius,
            skills=skills if skills else None
        )
        
        return Response({
            'tasker_count': len(tasker_ids),
            'tasker_ids': tasker_ids,
            'latitude': latitude,
            'longitude': longitude,
            'radius': radius,
            'skills': skills
        })


class LocationSearchViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for LocationSearch (read-only, analytics).
    """
    serializer_class = LocationSearchSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return searches for current user"""
        return LocationSearch.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_searches(self, request):
        """Get current user's search history"""
        searches = self.get_queryset()[:20]
        serializer = LocationSearchSerializer(searches, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def statistics(self, request):
        """Get location statistics (admin only)"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        stats = LocationService.get_location_statistics()
        serializer = LocationStatisticsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def top_searches(self, request):
        """Get top searched locations (admin only)"""
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        limit = int(request.query_params.get('limit', 10))
        top_searches = LocationService.get_top_searched_locations(limit=limit)
        serializer = TopSearchedLocationSerializer(top_searches, many=True)
        return Response(serializer.data)
