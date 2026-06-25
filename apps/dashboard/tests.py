"""
Dashboard Tests
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status

from apps.dashboard.tier_service import resolve_tasker_tier
from apps.dashboard.services import DashboardService
from apps.payments.models import Payment
from apps.tasks.models import Task, TaskView, Category
from django.contrib.contenttypes.models import ContentType

User = get_user_model()


class DashboardAPITestCase(TestCase):
    """Test cases for Dashboard API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create admin user
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            first_name='Admin',
            last_name='User',
            role='admin'
        )
        
        # Create regular user
        self.regular_user = User.objects.create_user(
            email='user@test.com',
            password='testpass123',
            first_name='Regular',
            last_name='User',
            role='customer'
        )

        self.tasker_user = User.objects.create_user(
            email='tasker@test.com',
            password='testpass123',
            first_name='Task',
            last_name='Er',
            role='tasker'
        )
    
    def test_platform_overview_admin_access(self):
        """Test that admin can access platform overview"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/v1/dashboard/platform_overview/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('users', response.data)
        self.assertIn('tasks', response.data)
        self.assertIn('bids', response.data)
    
    def test_platform_overview_regular_user_denied(self):
        """Test that regular users cannot access platform overview"""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/api/v1/dashboard/platform_overview/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_my_stats_authenticated_access(self):
        """Test that authenticated users can access their own stats"""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/api/v1/dashboard/my_stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('role', response.data)
    
    def test_my_stats_unauthenticated_denied(self):
        """Test that unauthenticated users cannot access stats"""
        response = self.client.get('/api/v1/dashboard/my_stats/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_growth_metrics_admin_access(self):
        """Test that admin can access growth metrics"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/v1/dashboard/growth_metrics/?days=30')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('period_days', response.data)
        self.assertIn('new_users', response.data)
    
    def test_admin_dashboard_comprehensive(self):
        """Test comprehensive admin dashboard endpoint"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/v1/dashboard/admin_dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('platform_overview', response.data)
        self.assertIn('growth_metrics', response.data)
        self.assertIn('category_statistics', response.data)
        self.assertIn('recent_activity', response.data)
        self.assertIn('financial_summary', response.data)
        self.assertIn('top_performers', response.data)

    def test_tasker_my_stats_includes_tier(self):
        """Tasker dashboard stats include tier and rolling earnings."""
        self.client.force_authenticate(user=self.tasker_user)
        response = self.client.get('/api/v1/dashboard/my_stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['role'], 'tasker')
        self.assertIn('tier', response.data)
        self.assertIn('current', response.data['tier'])
        self.assertEqual(response.data['tier']['current']['slug'], 'bronze')
        self.assertIn('last_30_days', response.data['earnings'])

    def test_resolve_tasker_tier_silver(self):
        tier = resolve_tasker_tier(Decimal('900'))
        self.assertEqual(tier['current']['slug'], 'silver')
        self.assertEqual(tier['next']['slug'], 'gold')

    def test_tasker_earnings_last_30_days(self):
        ct = ContentType.objects.get_for_model(User)
        Payment.objects.create(
            payer=self.regular_user,
            payee=self.tasker_user,
            content_type=ct,
            object_id=self.tasker_user.id,
            amount=Decimal('1000.00'),
            net_amount=Decimal('900.00'),
            currency='NPR',
            payment_type='task_payment',
            payment_method='wallet',
            status='released',
            escrow_released_at=timezone.now() - timedelta(days=5),
        )

        self.client.force_authenticate(user=self.tasker_user)
        response = self.client.get('/api/v1/dashboard/my_stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['earnings']['last_30_days'], 900.0)
        self.assertEqual(response.data['tier']['current']['slug'], 'silver')

    def test_my_overview_traffic_from_listing_views(self):
        category = Category.objects.create(name='Test Cat', slug='test-cat-traffic')
        task = Task.objects.create(
            owner=self.regular_user,
            title='Traffic test task',
            slug='traffic-test-task',
            description='Test',
            category=category,
            budget_amount=Decimal('1000.00'),
            budget_currency='NPR',
            status='open',
        )
        TaskView.objects.create(
            task=task,
            referrer='https://www.google.com/search?q=sajilowork',
            user_agent='Mozilla/5.0',
        )
        TaskView.objects.create(
            task=task,
            referrer='https://www.facebook.com/post/1',
            user_agent='Mozilla/5.0',
        )
        TaskView.objects.create(task=task, referrer='', user_agent='Mozilla/5.0')

        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/api/v1/dashboard/my_overview/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        traffic = response.data['overview']['traffic']
        self.assertEqual(traffic['direct'], 1)
        self.assertEqual(traffic['referral'], 1)
        self.assertEqual(traffic['organic'], 1)
        self.assertEqual(traffic['direct_percent'] + traffic['referral_percent'] + traffic['organic_percent'], 100)
        self.assertNotEqual(traffic['direct_percent'], 50)

    def test_classify_traffic_source(self):
        self.assertEqual(
            DashboardService._classify_traffic_source('https://www.google.com/search?q=hi', ''),
            'organic',
        )
        self.assertEqual(
            DashboardService._classify_traffic_source('https://www.facebook.com/x', ''),
            'referral',
        )
        self.assertEqual(DashboardService._classify_traffic_source('', 'Mozilla/5.0'), 'direct')
