"""
Seed development users for the marketplace admin and local sign-in.
"""
from __future__ import annotations

import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.users.models import EmployerProfile, UserSkill

User = get_user_model()

FIRST_NAMES = [
    'Aarav', 'Sita', 'Rohan', 'Priya', 'Nabin', 'Anisha', 'Kiran', 'Maya',
    'Bishal', 'Sunita', 'Dev', 'Riya', 'Sandesh', 'Nisha', 'Prakash', 'Anjali',
    'Suman', 'Kabita', 'Ashish', 'Rekha', 'Manish', 'Puja', 'Dipesh', 'Sneha',
]

LAST_NAMES = [
    'Shrestha', 'Gurung', 'Tamang', 'Thapa', 'Karki', 'Rai', 'Lama', 'Maharjan',
    'Shakya', 'Basnet', 'Adhikari', 'Poudel', 'Baniya', 'KC', 'Bhandari', 'Nepal',
]

CITIES = [
    ('Kathmandu', 'Bagmati', 'Nepal'),
    ('Lalitpur', 'Bagmati', 'Nepal'),
    ('Pokhara', 'Gandaki', 'Nepal'),
    ('Bharatpur', 'Bagmati', 'Nepal'),
    ('Biratnagar', 'Koshi', 'Nepal'),
    ('Butwal', 'Lumbini', 'Nepal'),
]

TAGLINES = [
    'Reliable help for your everyday tasks',
    'Design, build, and deliver on time',
    'Professional services across Nepal',
    'Trusted freelancer with 5-star reviews',
    'Fast turnaround and clear communication',
]

SKILLS = [
    'React', 'Django', 'Python', 'Figma', 'SEO', 'Content Writing',
    'Photography', 'Video Editing', 'Plumbing', 'Electrical Work',
    'Graphic Design', 'Data Entry', 'Translation', 'Mobile Development',
]

INDUSTRIES = [
    'Technology', 'Retail', 'Hospitality', 'Construction', 'Education',
    'Healthcare', 'Marketing', 'Finance',
]


class Command(BaseCommand):
    help = 'Seed random marketplace users (plus a primary dev account)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=20,
            help='Number of random users to create (default: 20)',
        )
        parser.add_argument(
            '--email',
            type=str,
            default='bishalbaniya1@gmail.com',
            help='Primary account email',
        )
        parser.add_argument(
            '--password',
            type=str,
            default='sajilowork123',
            help='Password for all seeded users',
        )
        parser.add_argument(
            '--superuser',
            action='store_true',
            default=True,
            help='Make the primary account a superuser (default: true)',
        )
        parser.add_argument(
            '--no-superuser',
            action='store_false',
            dest='superuser',
            help='Do not grant superuser to the primary account',
        )

    def handle(self, *args, **options):
        count = max(0, options['count'])
        primary_email = options['email'].strip().lower()
        password = options['password']
        make_superuser = options['superuser']

        created = 0
        updated = 0

        with transaction.atomic():
            primary, was_created = self._upsert_primary_user(
                primary_email,
                password,
                make_superuser=make_superuser,
            )
            if was_created:
                created += 1
            else:
                updated += 1

            for index in range(count):
                user, was_created = self._create_random_user(index, password)
                if was_created:
                    created += 1
                else:
                    updated += 1

        total = User.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f'Seed complete: {created} created, {updated} updated/reset ({total} users total).'
        ))
        self.stdout.write('')
        self.stdout.write('Primary account:')
        self.stdout.write(f'  Email:    {primary_email}')
        self.stdout.write(f'  Password: {password}')
        self.stdout.write(f'  Admin:    {"yes" if primary.is_superuser else "no"}')
        self.stdout.write('')
        self.stdout.write('Random users use the same password and emails like user001@sajilowork.dev')
        self.stdout.write('View users at http://localhost:8000/admin/users/user/')

    def _upsert_primary_user(
        self,
        email: str,
        password: str,
        *,
        make_superuser: bool,
    ) -> tuple[User, bool]:
        user = User.objects.filter(email=email).first()
        was_created = user is None

        if was_created:
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name='Bishal',
                last_name='Baniya',
                role='customer',
            )
        else:
            user.set_password(password)

        user.first_name = user.first_name or 'Bishal'
        user.last_name = user.last_name or 'Baniya'
        user.role = user.role or 'customer'
        user.is_active = True
        user.email_verified = True
        user.phone_verified = True
        user.city = user.city or 'Kathmandu'
        user.state = user.state or 'Bagmati'
        user.country = user.country or 'Nepal'
        user.tagline = user.tagline or 'SajiloWork platform admin and employer'
        user.bio = user.bio or 'Primary development account for SajiloWork marketplace.'
        user.wallet_balance = user.wallet_balance or Decimal('5000.00')

        if make_superuser:
            user.is_staff = True
            user.is_superuser = True
            user.role = 'admin'

        user.save()

        self._ensure_employer_profile(user, company_name='TaskNepal', industry='Technology')
        self.stdout.write(
            self.style.SUCCESS(f'  {"Created" if was_created else "Updated"} primary user: {email}')
        )
        return user, was_created

    def _create_random_user(self, index: int, password: str) -> tuple[User, bool]:
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        email = f'user{index + 1:03d}@sajilowork.dev'
        role = random.choice(['customer', 'tasker', 'tasker', 'customer'])
        city, state, country = random.choice(CITIES)

        user = User.objects.filter(email=email).first()
        was_created = user is None

        if was_created:
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=role,
            )
        else:
            user.set_password(password)
            user.first_name = first_name
            user.last_name = last_name
            user.role = role

        user.is_active = True
        user.email_verified = True
        user.phone = user.phone or f'98{random.randint(10000000, 99999999)}'
        user.city = city
        user.state = state
        user.country = country
        user.tagline = random.choice(TAGLINES)
        user.bio = (
            f'{first_name} is a {"freelancer" if role == "tasker" else "employer"} '
            f'based in {city}, {country}.'
        )
        user.average_rating = Decimal(str(round(random.uniform(3.8, 5.0), 2)))
        user.total_reviews = random.randint(0, 48)
        user.trust_score = Decimal(str(round(random.uniform(55, 98), 2)))
        user.tasks_completed = random.randint(0, 120) if role == 'tasker' else 0
        user.tasks_posted = random.randint(0, 40) if role == 'customer' else random.randint(0, 8)
        user.completion_rate = Decimal(str(round(random.uniform(85, 100), 2))) if role == 'tasker' else Decimal('0.00')
        user.hourly_rate = Decimal(str(random.choice([500, 800, 1200, 1500, 2000, 2500, 3500]))) if role == 'tasker' else None
        user.wallet_balance = Decimal(str(random.randint(0, 15000)))
        user.is_online = random.choice([True, False, False])
        user.save()

        if role == 'customer':
            company = f'{last_name} {random.choice(["Group", "Services", "Studio", "Works", "Hub"])}'
            self._ensure_employer_profile(user, company_name=company, industry=random.choice(INDUSTRIES))
        else:
            self._ensure_tasker_skills(user)

        action = 'Created' if was_created else 'Updated'
        self.stdout.write(f'  {action} {email} ({role})')
        return user, was_created

    def _ensure_employer_profile(
        self,
        user: User,
        *,
        company_name: str,
        industry: str,
    ) -> None:
        profile, _ = EmployerProfile.objects.get_or_create(
            user=user,
            defaults={
                'account_type': 'company' if ' ' in company_name else 'individual',
                'company_name': company_name,
                'industry': industry,
                'team_size': random.choice(['1-5', '6-20', '21-50']),
                'contact_email': user.email,
                'contact_phone': user.phone or '',
                'is_public': True,
            },
        )
        if not profile.company_name:
            profile.company_name = company_name
            profile.industry = industry or profile.industry
            profile.is_public = True
            profile.save(update_fields=['company_name', 'industry', 'is_public'])

    def _ensure_tasker_skills(self, user: User) -> None:
        chosen = random.sample(SKILLS, k=random.randint(2, 5))
        for skill_name in chosen:
            UserSkill.objects.get_or_create(
                user=user,
                name=skill_name,
                defaults={
                    'proficiency_level': random.choice(['beginner', 'intermediate', 'expert']),
                    'years_of_experience': random.randint(1, 10),
                    'verified': random.choice([True, False]),
                },
            )
