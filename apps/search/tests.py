"""
Search App Tests
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from apps.search.models import (
    SearchHistory, SavedSearch, PopularSearch,
    SearchSuggestion, SearchFilter
)
from apps.tasks.models import Task, Category
from apps.search.services import SearchService

User = get_user_model()


class SearchServiceTests(TestCase):
    """Tests for SearchService"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        
        self.task = Task.objects.create(
            title='Test Task',
            description='Test description',
            owner=self.user,
            category=self.category,
            budget=100,
            status='open'
        )
    
    def test_search_tasks(self):
        """Test task search"""
        results = SearchService.search_tasks('Test', {}, self.user)
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first().title, 'Test Task')
    
    def test_record_search(self):
        """Test recording search history"""
        history = SearchService.record_search(
            user=self.user,
            query='test query',
            search_type='tasks',
            filters={},
            results_count=1
        )
        
        self.assertIsNotNone(history)
        self.assertEqual(history.query, 'test query')
        self.assertEqual(history.user, self.user)


class SearchAPITests(APITestCase):
    """Tests for Search API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        
        self.task = Task.objects.create(
            title='Test Task',
            description='Test description',
            owner=self.user,
            category=self.category,
            budget=100,
            status='open'
        )
    
    def test_search_without_auth(self):
        """Test search without authentication"""
        response = self.client.get('/api/v1/search/?query=test')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_search_with_query(self):
        """Test search with query parameter"""
        response = self.client.get('/api/v1/search/?query=Test&search_type=tasks')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('total_results', response.data)
    
    def test_autocomplete(self):
        """Test autocomplete endpoint"""
        response = self.client.get('/api/v1/search/autocomplete/?query=te')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('suggestions', response.data)
    
    def test_saved_search_requires_auth(self):
        """Test saved search requires authentication"""
        response = self.client.get('/api/v1/search/saved/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_create_saved_search(self):
        """Test creating saved search"""
        self.client.force_authenticate(user=self.user)
        
        data = {
            'name': 'My Search',
            'query': 'test',
            'search_type': 'tasks',
            'filters': {},
            'notify_new_results': True
        }
        
        response = self.client.post('/api/v1/search/saved/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SavedSearch.objects.count(), 1)


class SearchModelTests(TestCase):
    """Tests for Search models"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_search_history_creation(self):
        """Test creating search history"""
        history = SearchHistory.objects.create(
            user=self.user,
            query='test query',
            search_type='tasks',
            results_count=5
        )
        
        self.assertEqual(str(history), f'{self.user.email}: "test query" (tasks)')
    
    def test_saved_search_creation(self):
        """Test creating saved search"""
        saved = SavedSearch.objects.create(
            user=self.user,
            name='My Search',
            query='test',
            search_type='tasks'
        )
        
        self.assertEqual(str(saved), f'{self.user.email}: My Search')
        self.assertTrue(saved.is_active)
    
    def test_popular_search_creation(self):
        """Test creating popular search"""
        popular = PopularSearch.objects.create(
            query='test query',
            search_count=10
        )
        
        self.assertEqual(str(popular), '"test query" (10 searches)')
