"""
Management command to seed test tasks
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import random

from apps.tasks.models import Task, Category

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed database with test tasks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=20,
            help='Number of tasks to create'
        )

    def handle(self, *args, **options):
        count = options['count']
        
        self.stdout.write('🌱 Seeding tasks...')
        
        # Get or create categories
        categories_data = [
            {'name': 'Cleaning', 'slug': 'cleaning', 'icon': '🧹'},
            {'name': 'Handyman', 'slug': 'handyman', 'icon': '🔧'},
            {'name': 'Moving', 'slug': 'moving', 'icon': '📦'},
            {'name': 'Gardening', 'slug': 'gardening', 'icon': '🌱'},
            {'name': 'Delivery', 'slug': 'delivery', 'icon': '🚚'},
            {'name': 'Assembly', 'slug': 'assembly', 'icon': '🔩'},
            {'name': 'Painting', 'slug': 'painting', 'icon': '🎨'},
            {'name': 'Plumbing', 'slug': 'plumbing', 'icon': '🚰'},
        ]
        
        categories = []
        for cat_data in categories_data:
            category, created = Category.objects.get_or_create(
                slug=cat_data['slug'],
                defaults={
                    'name': cat_data['name'],
                    'icon': cat_data['icon'],
                    'is_active': True
                }
            )
            categories.append(category)
            if created:
                self.stdout.write(f'  ✅ Created category: {category.name}')
        
        # Get or create test users
        users = []
        for i in range(5):
            user, created = User.objects.get_or_create(
                email=f'user{i+1}@example.com',
                defaults={
                    'first_name': f'User',
                    'last_name': f'{i+1}',
                    'role': 'customer',
                    'is_active': True
                }
            )
            if created:
                user.set_password('password123')
                user.save()
                self.stdout.write(f'  ✅ Created user: {user.email}')
            users.append(user)
        
        # Task templates
        task_templates = [
            {
                'title': 'Clean my 3-bedroom apartment',
                'description': 'Need a thorough cleaning of my apartment including kitchen, bathrooms, and living areas.',
                'category': 'cleaning',
                'budget_range': (80, 150)
            },
            {
                'title': 'Fix leaking kitchen faucet',
                'description': 'Kitchen faucet has been leaking for a week. Need someone to fix it ASAP.',
                'category': 'plumbing',
                'budget_range': (50, 100)
            },
            {
                'title': 'Help move furniture to new apartment',
                'description': 'Moving to a new place and need help with heavy furniture. Truck available.',
                'category': 'moving',
                'budget_range': (100, 200)
            },
            {
                'title': 'Assemble IKEA furniture',
                'description': 'Bought new IKEA furniture and need help assembling it. About 3-4 pieces.',
                'category': 'assembly',
                'budget_range': (60, 120)
            },
            {
                'title': 'Paint bedroom walls',
                'description': 'Need someone to paint my bedroom. Paint and supplies provided.',
                'category': 'painting',
                'budget_range': (150, 300)
            },
            {
                'title': 'Mow lawn and trim hedges',
                'description': 'Regular lawn maintenance needed. Medium-sized yard.',
                'category': 'gardening',
                'budget_range': (40, 80)
            },
            {
                'title': 'Deliver packages across town',
                'description': 'Need someone with a vehicle to deliver 5 packages to different locations.',
                'category': 'delivery',
                'budget_range': (30, 60)
            },
            {
                'title': 'Install ceiling fan',
                'description': 'Have a new ceiling fan that needs installation. Wiring already in place.',
                'category': 'handyman',
                'budget_range': (70, 130)
            },
        ]
        
        # Cities for variety
        cities = ['Sydney', 'Melbourne', 'Brisbane', 'Perth', 'Adelaide']
        
        # Create tasks
        created_count = 0
        for i in range(count):
            template = random.choice(task_templates)
            category = Category.objects.get(slug=template['category'])
            owner = random.choice(users)
            
            # Random budget within range
            budget = Decimal(random.randint(template['budget_range'][0], template['budget_range'][1]))
            
            # Random due date (1-30 days from now)
            due_date = timezone.now() + timedelta(days=random.randint(1, 30))
            
            # Random city
            city = random.choice(cities)
            
            # Random coordinates (Australia)
            latitude = Decimal(str(random.uniform(-35, -25)))
            longitude = Decimal(str(random.uniform(115, 153)))
            
            task = Task.objects.create(
                title=f"{template['title']} #{i+1}",
                description=template['description'],
                category=category,
                owner=owner,
                status='open',
                work_type=random.choice(['remote', 'in_person', 'flexible']),
                urgency=random.choice(['low', 'medium', 'high']),
                budget_type='fixed',
                budget_amount=budget,
                budget_currency='AUD',
                location_type='physical',
                city=city,
                country='Australia',
                latitude=latitude,
                longitude=longitude,
                due_date=due_date,
                is_public=True,
                allow_bids=True,
                published_at=timezone.now()
            )
            
            created_count += 1
            
            if created_count % 5 == 0:
                self.stdout.write(f'  📝 Created {created_count} tasks...')
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Successfully created {created_count} tasks!')
        )
