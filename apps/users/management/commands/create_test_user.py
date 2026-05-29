"""
Management command to create test users for development.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Create test users for development'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            default='test@example.com',
            help='Email address for the test user'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='Test123456',
            help='Password for the test user'
        )
        parser.add_argument(
            '--role',
            type=str,
            default='customer',
            choices=['customer', 'tasker', 'admin'],
            help='Role for the test user'
        )

    def handle(self, *args, **options):
        email = options['email']
        password = options['password']
        role = options['role']

        # Check if user already exists
        if User.objects.filter(email=email).exists():
            self.stdout.write(
                self.style.WARNING(f'User with email {email} already exists!')
            )
            user = User.objects.get(email=email)
            self.stdout.write(f'User ID: {user.id}')
            self.stdout.write(f'Email: {user.email}')
            self.stdout.write(f'Role: {user.role}')
            self.stdout.write(f'Active: {user.is_active}')
            self.stdout.write(f'Email Verified: {user.email_verified}')
            return

        # Create user
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name='Test',
            last_name='User',
            role=role
        )
        
        # Verify email by default for test users
        user.email_verified = True
        user.save()

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created test user!')
        )
        self.stdout.write(f'Email: {email}')
        self.stdout.write(f'Password: {password}')
        self.stdout.write(f'Role: {role}')
        self.stdout.write(f'User ID: {user.id}')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('You can now login at http://localhost:3000/signin'))
