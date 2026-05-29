"""
Locations Service Layer
Business logic for location-based operations.
"""
from django.db.models import Q, Count, F
from math import radians, cos, sin, asin, sqrt
from typing import List, Dict, Optional, Tuple
from decimal import Decimal

from .models import Country, State, City, UserLocation, ServiceArea, LocationSearch


class LocationService:
    """Service class for location operations"""
    
    @staticmethod
    def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two coordinates using Haversine formula.
        Returns distance in kilometers.
        """
        # Convert decimal degrees to radians
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        
        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        
        # Radius of earth in kilometers
        r = 6371
        
        return c * r
    
    @staticmethod
    def get_bounding_box(latitude: float, longitude: float, radius_km: float) -> Dict[str, float]:
        """
        Calculate bounding box for a given point and radius.
        Returns dict with min/max lat/lon for efficient database queries.
        """
        # Earth's radius in kilometers
        earth_radius = 6371
        
        # Angular distance in radians
        angular_distance = radius_km / earth_radius
        
        # Convert to radians
        lat_rad = radians(latitude)
        lon_rad = radians(longitude)
        
        # Calculate bounds
        min_lat = lat_rad - angular_distance
        max_lat = lat_rad + angular_distance
        
        # Account for longitude variation at different latitudes
        delta_lon = asin(sin(angular_distance) / cos(lat_rad))
        min_lon = lon_rad - delta_lon
        max_lon = lon_rad + delta_lon
        
        return {
            'min_lat': float(Decimal(str(min_lat * 180 / 3.14159))),
            'max_lat': float(Decimal(str(max_lat * 180 / 3.14159))),
            'min_lon': float(Decimal(str(min_lon * 180 / 3.14159))),
            'max_lon': float(Decimal(str(max_lon * 180 / 3.14159))),
        }
    
    @staticmethod
    def search_cities(
        query: str,
        country_code: Optional[str] = None,
        state_code: Optional[str] = None,
        limit: int = 20
    ) -> List[City]:
        """Search cities by name with optional country/state filters"""
        queryset = City.objects.filter(is_active=True).select_related('state', 'state__country')
        
        # Apply search filter
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) |
                Q(state__name__icontains=query) |
                Q(state__country__name__icontains=query)
            )
        
        # Apply country filter
        if country_code:
            queryset = queryset.filter(state__country__code=country_code.upper())
        
        # Apply state filter
        if state_code:
            queryset = queryset.filter(state__code=state_code.upper())
        
        # Order by popularity and name
        queryset = queryset.order_by('-is_popular', 'name')
        
        return list(queryset[:limit])
    
    @staticmethod
    def get_nearby_cities(
        latitude: float,
        longitude: float,
        radius_km: int = 50,
        limit: int = 20
    ) -> List[Dict]:
        """Get cities within radius of a point"""
        # Get bounding box for efficient query
        bbox = LocationService.get_bounding_box(latitude, longitude, radius_km)
        
        # Query cities within bounding box
        cities = City.objects.filter(
            is_active=True,
            latitude__gte=bbox['min_lat'],
            latitude__lte=bbox['max_lat'],
            longitude__gte=bbox['min_lon'],
            longitude__lte=bbox['max_lon']
        ).select_related('state', 'state__country')
        
        # Calculate exact distances and filter by radius
        results = []
        for city in cities:
            distance = LocationService.calculate_distance(
                latitude, longitude,
                float(city.latitude), float(city.longitude)
            )
            
            if distance <= radius_km:
                results.append({
                    'city': city,
                    'distance': round(distance, 2)
                })
        
        # Sort by distance
        results.sort(key=lambda x: x['distance'])
        
        return results[:limit]
    
    @staticmethod
    def get_popular_cities(country_code: Optional[str] = None, limit: int = 20) -> List[City]:
        """Get popular cities, optionally filtered by country"""
        queryset = City.objects.filter(
            is_active=True,
            is_popular=True
        ).select_related('state', 'state__country')
        
        if country_code:
            queryset = queryset.filter(state__country__code=country_code.upper())
        
        return list(queryset.order_by('name')[:limit])
    
    @staticmethod
    def geocode_address(address: str) -> Optional[Tuple[float, float]]:
        """
        Geocode an address to coordinates.
        TODO: Integrate with geocoding service (Google Maps, Mapbox, etc.)
        """
        # Placeholder for geocoding service integration
        # In production, integrate with:
        # - Google Maps Geocoding API
        # - Mapbox Geocoding API
        # - OpenStreetMap Nominatim
        return None
    
    @staticmethod
    def reverse_geocode(latitude: float, longitude: float) -> Optional[str]:
        """
        Reverse geocode coordinates to address.
        TODO: Integrate with geocoding service
        """
        # Placeholder for reverse geocoding service integration
        return None
    
    @staticmethod
    def get_user_service_areas(user_id: int) -> List[ServiceArea]:
        """Get all active service areas for a tasker"""
        return list(
            ServiceArea.objects.filter(
                user_id=user_id,
                is_active=True
            ).select_related('city', 'city__state', 'city__state__country')
            .order_by('-created_at')
        )
    
    @staticmethod
    def is_location_in_service_area(
        user_id: int,
        latitude: float,
        longitude: float
    ) -> bool:
        """Check if a location is within any of the user's service areas"""
        service_areas = ServiceArea.objects.filter(
            user_id=user_id,
            is_active=True
        ).select_related('city')
        
        for area in service_areas:
            distance = LocationService.calculate_distance(
                latitude, longitude,
                float(area.city.latitude), float(area.city.longitude)
            )
            
            if distance <= area.radius:
                return True
        
        return False
    
    @staticmethod
    def find_taskers_in_area(
        latitude: float,
        longitude: float,
        radius_km: int = 10,
        skills: Optional[List[str]] = None
    ) -> List[int]:
        """
        Find taskers who service a given location.
        Returns list of user IDs.
        """
        # Get bounding box
        bbox = LocationService.get_bounding_box(latitude, longitude, radius_km)
        
        # Find service areas within bounding box
        service_areas = ServiceArea.objects.filter(
            is_active=True,
            city__is_active=True,
            city__latitude__gte=bbox['min_lat'],
            city__latitude__lte=bbox['max_lat'],
            city__longitude__gte=bbox['min_lon'],
            city__longitude__lte=bbox['max_lon']
        ).select_related('city', 'user')
        
        # Filter by exact distance and radius
        tasker_ids = set()
        for area in service_areas:
            distance = LocationService.calculate_distance(
                latitude, longitude,
                float(area.city.latitude), float(area.city.longitude)
            )
            
            if distance <= area.radius:
                # Check skills if provided
                if skills:
                    user_skills = set(
                        area.user.skills.filter(is_active=True)
                        .values_list('skill__name', flat=True)
                    )
                    if set(skills).issubset(user_skills):
                        tasker_ids.add(area.user_id)
                else:
                    tasker_ids.add(area.user_id)
        
        return list(tasker_ids)
    
    @staticmethod
    def record_location_search(
        query: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius: Optional[int] = None,
        results_count: int = 0,
        user=None,
        session_id: str = '',
        request=None
    ) -> LocationSearch:
        """Record a location search for analytics"""
        ip_address = None
        user_agent = ''
        
        if request:
            ip_address = LocationService._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        
        return LocationSearch.objects.create(
            user=user if user and user.is_authenticated else None,
            session_id=session_id,
            query=query,
            latitude=latitude,
            longitude=longitude,
            radius=radius,
            results_count=results_count,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    def _get_client_ip(request) -> Optional[str]:
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @staticmethod
    def get_location_statistics() -> Dict:
        """Get location-related statistics"""
        return {
            'total_countries': Country.objects.filter(is_active=True).count(),
            'total_states': State.objects.filter(is_active=True).count(),
            'total_cities': City.objects.filter(is_active=True).count(),
            'popular_cities': City.objects.filter(is_active=True, is_popular=True).count(),
            'total_service_areas': ServiceArea.objects.filter(is_active=True).count(),
            'total_user_locations': UserLocation.objects.filter(is_active=True).count(),
            'total_searches': LocationSearch.objects.count(),
        }
    
    @staticmethod
    def get_top_searched_locations(limit: int = 10) -> List[Dict]:
        """Get most searched locations"""
        from django.db.models import Count
        
        searches = LocationSearch.objects.values('query').annotate(
            search_count=Count('id')
        ).order_by('-search_count')[:limit]
        
        return list(searches)
