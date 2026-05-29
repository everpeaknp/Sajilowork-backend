"""
Locations Serializers
"""
from rest_framework import serializers
from .models import Country, State, City, UserLocation, ServiceArea, LocationSearch


class CountrySerializer(serializers.ModelSerializer):
    """Serializer for Country model"""
    
    class Meta:
        model = Country
        fields = [
            'id', 'name', 'code', 'code3', 'phone_code',
            'currency_code', 'currency_symbol', 'latitude', 'longitude',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CountryListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for country lists"""
    
    class Meta:
        model = Country
        fields = ['id', 'name', 'code', 'phone_code', 'currency_code', 'currency_symbol']


class StateSerializer(serializers.ModelSerializer):
    """Serializer for State model"""
    country = CountryListSerializer(read_only=True)
    country_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = State
        fields = [
            'id', 'country', 'country_id', 'name', 'code',
            'latitude', 'longitude', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class StateListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for state lists"""
    country_code = serializers.CharField(source='country.code', read_only=True)
    country_name = serializers.CharField(source='country.name', read_only=True)
    
    class Meta:
        model = State
        fields = ['id', 'name', 'code', 'country_code', 'country_name']


class CitySerializer(serializers.ModelSerializer):
    """Serializer for City model"""
    state = StateListSerializer(read_only=True)
    state_id = serializers.UUIDField(write_only=True)
    country = serializers.SerializerMethodField()
    
    class Meta:
        model = City
        fields = [
            'id', 'state', 'state_id', 'name', 'latitude', 'longitude',
            'population', 'timezone', 'is_active', 'is_popular',
            'country', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_country(self, obj):
        """Get country information"""
        return {
            'id': obj.state.country.id,
            'name': obj.state.country.name,
            'code': obj.state.country.code
        }


class CityListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for city lists"""
    state_name = serializers.CharField(source='state.name', read_only=True)
    state_code = serializers.CharField(source='state.code', read_only=True)
    country_name = serializers.CharField(source='state.country.name', read_only=True)
    country_code = serializers.CharField(source='state.country.code', read_only=True)
    
    class Meta:
        model = City
        fields = [
            'id', 'name', 'latitude', 'longitude',
            'state_name', 'state_code', 'country_name', 'country_code',
            'is_popular'
        ]


class CityWithDistanceSerializer(CityListSerializer):
    """City serializer with distance information"""
    distance = serializers.FloatField(read_only=True)
    
    class Meta(CityListSerializer.Meta):
        fields = CityListSerializer.Meta.fields + ['distance']


class UserLocationSerializer(serializers.ModelSerializer):
    """Serializer for UserLocation model"""
    city = CityListSerializer(read_only=True)
    city_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = UserLocation
        fields = [
            'id', 'user', 'user_email', 'location_type', 'label',
            'address', 'city', 'city_id', 'latitude', 'longitude',
            'is_default', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
    
    def validate(self, attrs):
        """Validate location data"""
        latitude = attrs.get('latitude')
        longitude = attrs.get('longitude')
        
        if latitude and (latitude < -90 or latitude > 90):
            raise serializers.ValidationError({
                'latitude': 'Latitude must be between -90 and 90.'
            })
        
        if longitude and (longitude < -180 or longitude > 180):
            raise serializers.ValidationError({
                'longitude': 'Longitude must be between -180 and 180.'
            })
        
        return attrs


class UserLocationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating user locations"""
    
    class Meta:
        model = UserLocation
        fields = [
            'location_type', 'label', 'address', 'city_id',
            'latitude', 'longitude', 'is_default'
        ]
    
    def create(self, validated_data):
        """Create user location"""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ServiceAreaSerializer(serializers.ModelSerializer):
    """Serializer for ServiceArea model"""
    city = CityListSerializer(read_only=True)
    city_id = serializers.UUIDField(write_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = ServiceArea
        fields = [
            'id', 'user', 'user_email', 'city', 'city_id',
            'radius', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
    
    def validate_radius(self, value):
        """Validate radius"""
        if value < 1 or value > 100:
            raise serializers.ValidationError(
                'Radius must be between 1 and 100 kilometers.'
            )
        return value


class ServiceAreaCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating service areas"""
    
    class Meta:
        model = ServiceArea
        fields = ['city_id', 'radius']
    
    def validate(self, attrs):
        """Validate service area"""
        user = self.context['request'].user
        
        # Check if user is a tasker
        if user.role != 'tasker':
            raise serializers.ValidationError(
                'Only taskers can create service areas.'
            )
        
        return attrs
    
    def create(self, validated_data):
        """Create service area"""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class LocationSearchSerializer(serializers.ModelSerializer):
    """Serializer for LocationSearch model"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = LocationSearch
        fields = [
            'id', 'user', 'user_email', 'session_id', 'query',
            'latitude', 'longitude', 'radius', 'results_count',
            'ip_address', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'ip_address', 'created_at']


class LocationSearchCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating location searches"""
    
    class Meta:
        model = LocationSearch
        fields = ['query', 'latitude', 'longitude', 'radius', 'session_id']


class CitySearchRequestSerializer(serializers.Serializer):
    """Serializer for city search requests"""
    query = serializers.CharField(required=False, allow_blank=True)
    country_code = serializers.CharField(required=False, max_length=2)
    state_code = serializers.CharField(required=False, max_length=10)
    limit = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)


class NearbyCitiesRequestSerializer(serializers.Serializer):
    """Serializer for nearby cities requests"""
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    radius = serializers.IntegerField(default=50, min_value=1, max_value=500)
    limit = serializers.IntegerField(default=20, min_value=1, max_value=100)


class FindTaskersRequestSerializer(serializers.Serializer):
    """Serializer for finding taskers in area"""
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    radius = serializers.IntegerField(default=10, min_value=1, max_value=100)
    skills = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )


class LocationStatisticsSerializer(serializers.Serializer):
    """Serializer for location statistics"""
    total_countries = serializers.IntegerField()
    total_states = serializers.IntegerField()
    total_cities = serializers.IntegerField()
    popular_cities = serializers.IntegerField()
    total_service_areas = serializers.IntegerField()
    total_user_locations = serializers.IntegerField()
    total_searches = serializers.IntegerField()


class TopSearchedLocationSerializer(serializers.Serializer):
    """Serializer for top searched locations"""
    query = serializers.CharField()
    search_count = serializers.IntegerField()
