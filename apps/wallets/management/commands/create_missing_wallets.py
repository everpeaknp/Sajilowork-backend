"""
Management command to create wallets for users who don't have one
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.users.models import User
from apps.wallets.models import Wallet


class Command(BaseCommand):
    help = 'Create wallets for users who do not have one'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating wallets',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Find users without wallets
        users_without_wallets = User.objects.filter(wallet__isnull=True)
        count = users_without_wallets.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('All users already have wallets!'))
            return
        
        self.stdout.write(f'Found {count} users without wallets')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No wallets will be created'))
            for user in users_without_wallets[:10]:  # Show first 10
                self.stdout.write(f'  - Would create wallet for: {user.email}')
            if count > 10:
                self.stdout.write(f'  ... and {count - 10} more')
            return
        
        # Create wallets
        created_count = 0
        with transaction.atomic():
            for user in users_without_wallets:
                try:
                    Wallet.objects.create(user=user)
                    created_count += 1
                    self.stdout.write(f'Created wallet for: {user.email}')
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Failed to create wallet for {user.email}: {str(e)}')
                    )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} wallets!')
        )
