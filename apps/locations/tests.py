"""
Locations Tests
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from .models import Country, State, City, UserLocation, ServiceArea, LocationSearch
from .services import LocationService

User = get_user_model()


class LocationServiceTests(TestCase):
    """Test LocationService methods"""
    
    def setUp(self):
        """Set up test data"""
        # Create country
        self.country = Country.objects.create(
            name='Australia',
            code='AU',
            code3='AUS',
            phone_code='+61',
            currency_code='AUD',
            currency_symbol='$',
            latitude=Decimal('-25.2744'),
            longitude=Decimal('133.7751')
        )
        
        # Create state
        self.state = State.objects.create(
            country=self.country,
            name='New South Wales',
            code='NSW',
            latitude=Decimal('-33.8688'),
            longitude=Decimal('151.2093')
        )
        
        # Create city
        self.city = City.objects.create(
            state=self.state,
            name='Sydney',
            latitude=Decimal('-33.8688'),
            longitude=Decimal('151.2093'),
            population=5000000,
            timezone='Australia/Sydney',
            is_popular=True
        )
        
        # Create user
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            role='tasker'
        )
    
    def test_calculate_distance(self):
        """Test distance calculation"""
        # Sydney to Melbourne (approx 714 km)
        sydney_lat, sydney_lon = -33.8688, 151.2093
        melbourne_lat, melbourne_lon = -37.8136, 144.9631
        
        distance = LocationService.calculate_distance(
            sydney_lat, sydney_lon,
            melbourne_lat, melbourne_lon
        )
        
        # Distance should be approximately 714 km
        self.assertAlmostEqual(distance, 714, delta=10)
    
    def test_get_bounding_box(self):
        """Test bounding box calculation"""
        bbox = LocationService.get_bounding_box(-33.8688, 151.2093, 10)
        
        self.assertIn('min_lat', bbox)
        self.assertIn('max_lat', bbox)
        self.assertIn('min_lon', bbox)
        self.assertIn('max_lon', bbox)
        
        # Min should be less than max
        self.assertLess(bbox['min_lat'], bbox['max_lat'])
        self.assertLess(bbox['min_lon'], bbox['max_lon'])
    
    def test_search_cities(self):
        """Test city search"""
        cities = LocationService.search_cities('Sydney')
        
        self.assertEqual(len(cities), 1)
        self.assertEqual(cities[0].name, 'Sydney')
    
    def test_get_popular_cities(self):
        """Test getting popular cities"""
        cities = LocationService.get_popular_cities()
        
        self.assertEqual(len(cities), 1)
        self.assertEqual(cities[0].name, 'Sydney')
        self.assertTrue(cities[0].is_popular)


class LocationModelTests(TestCase):
    """Test Location models"""
    
    def setUp(self):
        """Set up test data"""
        self.country = Country.objects.create(
            name='Australia',
            code='AU',
            code3='AUS',
            phone_code='+61',
            currency_code='AUD',
            currency_symbol='$'
        )
        
        self.state = State.objects.create(
            country=self.country,
            name='New South Wales',
            code='NSW'
        )
        
        self.city = City.objects.create(
            state=self.state,
            name='Sydney',
            latitude=Decimal('-33.8688'),
            longitude=Decimal('151.2093')
        )
        
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_country_creation(self):
        """Test country model creation"""
        self.assertEqual(self.country.name, 'Australia')
        self.assertEqual(self.country.code, 'AU')
        self.assertTrue(self.country.is_active)
    
    def test_state_creation(self):
        """Test state model creation"""
        self.assertEqual(self.state.name, 'New South Wales')
        self.assertEqual(self.state.country, self.country)
    
    def test_city_creation(self):
        """Test city model creation"""
        self.assertEqual(self.city.name, 'Sydney')
        self.assertEqual(self.city.state, self.state)
        self.assertEqual(self.city.country, self.country)
    
    def test_user_location_creation(self):
        """Test user location creation"""
        location = UserLocation.objects.create(
            user=self.user,
            location_type='home',
            label='Home',
            address='123 Test St, Sydney',
            city=self.city,
            latitude=Decimal('-33.8688'),
            longitude=Decimal('151.2093'),
            is_default=True
        )
        
        self.assertEqual(location.user, self.user)
        self.assertTrue(location.is_default)
    
    def test_service_area_creation(self):
        """Test service area creation"""
        tasker = User.objects.create_user(
            email='tasker@example.com',
            password='testpass123',
            role='tasker'
        )
        
        service_area = ServiceArea.objects.create(
            user=tasker,
            city=self.city,
            radius=10
        )
        
        self.assertEqual(service_area.user, tasker)
        self.assertEqual(service_area.city, self.city)
        self.assertEqual(service_area.radius, 10)
