"""
Seed professional marketplace listings (task, job, service, project) for demo accounts.

Usage (from backend/):
  .\\venv\\Scripts\\python.exe manage.py seed_listings
  .\\venv\\Scripts\\python.exe manage.py seed_listings --count 6
"""
from __future__ import annotations

import json
import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify
from django.utils import timezone

from apps.services.service_image_seed import seed_service_cover_images
from apps.tasks.listing import (
    LISTING_KIND_JOB,
    LISTING_KIND_PROJECT,
    LISTING_KIND_SERVICE,
    with_listing_kind,
)
from apps.tasks.models import Category, Task
from apps.users.employer_profile_service import get_or_create_employer_profile
from apps.users.models import EmployerProfile, UserSkill

User = get_user_model()

DEFAULT_EMAILS = ('bishal@baniya.com', 'userc@userc.userc')
DEFAULT_PASSWORD = 'sajilowork123'

NEPAL_LOCATIONS = [
    ('Kathmandu', 'Bagmati', Decimal('27.717200'), Decimal('85.324000')),
    ('Lalitpur', 'Bagmati', Decimal('27.658800'), Decimal('85.324700')),
    ('Bhaktapur', 'Bagmati', Decimal('27.671000'), Decimal('85.429800')),
    ('Pokhara', 'Gandaki', Decimal('28.209600'), Decimal('83.985600')),
    ('Remote', '', None, None),
]

TIME_LABELS = ['Morning', 'Afternoon', 'Evening', 'Anytime', 'Before 5 PM']

TASK_TEMPLATES = [
    {
        'title': 'Deep clean 2BHK apartment before guests arrive',
        'description': (
            'Professional deep clean required for kitchen, two bathrooms, living room, and '
            'bedrooms. Eco-friendly products preferred. Access via building security.'
        ),
        'category': 'Cleaning',
        'budget_range': (3500, 8500),
    },
    {
        'title': 'Repair leaking kitchen tap and replace washer',
        'description': (
            'Tap has dripped for a week. Need diagnosis, washer replacement, and pressure test. '
            'Parts reimbursed with receipt.'
        ),
        'category': 'Plumbing',
        'budget_range': (1200, 3200),
    },
    {
        'title': 'Move sofa, wardrobe, and boxes to new flat',
        'description': (
            'Same-day move within valley. Two heavy items plus ~12 boxes. Third-floor walk-up, '
            'no elevator. Blankets and straps required.'
        ),
        'category': 'Moving',
        'budget_range': (4500, 12000),
    },
    {
        'title': 'Assemble IKEA desk, bookshelf, and TV unit',
        'description': (
            'Three flat-pack items with instructions on site. Client supplies tools if needed. '
            'Estimated 3–4 hours.'
        ),
        'category': 'Assembly',
        'budget_range': (2500, 6000),
    },
    {
        'title': 'Office deep clean — Saturday morning slot',
        'description': (
            'Startup office in Pulchowk: desks, kitchenette, meeting room, and floors. '
            'Recurring monthly option if quality is high.'
        ),
        'category': 'Cleaning',
        'budget_range': (4000, 9000),
    },
    {
        'title': 'Install smart door lock and configure app',
        'description': (
            'Supply-compatible smart lock already purchased. Need fitting, calibration, and '
            'handover demo for household members.'
        ),
        'category': 'Home Services',
        'budget_range': (2000, 5500),
    },
]

JOB_TEMPLATES = [
    {
        'title': 'Senior Frontend Developer (React / Next.js)',
        'description': (
            'Own customer dashboards, design-system components, and performance budgets. '
            'Collaborate with product and QA in two-week sprints.'
        ),
        'category': 'Development & IT',
        'skills': ['React', 'TypeScript', 'Next.js', 'Tailwind CSS'],
        'budget_range': (90000, 160000),
        'type': 'Full Time',
    },
    {
        'title': 'UI/UX Designer for fintech mobile app',
        'description': (
            'End-to-end flows for onboarding, KYC, and wallet top-up. Figma library and '
            'developer handoff required.'
        ),
        'category': 'Design & Creative',
        'skills': ['Figma', 'UI Design', 'Prototyping', 'Design systems'],
        'budget_range': (55000, 95000),
        'type': 'Contract',
    },
    {
        'title': 'Content writer — SEO blog (Nepali & English)',
        'description': (
            'Ten long-form articles per month for travel and lifestyle brand. Keyword briefs, '
            'internal links, and meta descriptions included.'
        ),
        'category': 'Writing & Translation',
        'skills': ['SEO writing', 'Nepali', 'English', 'WordPress'],
        'budget_range': (18000, 42000),
        'type': 'Fixed Price',
    },
    {
        'title': 'Social media manager — Instagram & TikTok',
        'description': (
            'Content calendar, short-form edits, community management, and monthly analytics '
            'for hospitality group.'
        ),
        'category': 'Digital Marketing',
        'skills': ['Instagram', 'TikTok', 'Canva', 'Meta Business Suite'],
        'budget_range': (28000, 58000),
        'type': 'Contract',
    },
    {
        'title': 'Junior full-stack developer (Django + React)',
        'description': (
            'Support feature delivery on marketplace platform. Write tests, participate in code '
            'review, and document APIs.'
        ),
        'category': 'Development & IT',
        'skills': ['Django', 'React', 'PostgreSQL', 'REST APIs'],
        'budget_range': (60000, 110000),
        'type': 'Full Time',
    },
    {
        'title': 'Video editor for product explainers',
        'description': (
            'Edit 8–12 minute YouTube explainers with supplied motion templates, VO, and brand '
            'guidelines.'
        ),
        'category': 'Video & Animation',
        'skills': ['Premiere Pro', 'After Effects', 'Color grading'],
        'budget_range': (15000, 35000),
        'type': 'Hourly',
    },
]

PROJECT_TEMPLATES = [
    {
        'title': 'Company marketing site in Next.js with CMS sections',
        'description': (
            'Responsive landing pages, contact form, careers block, and blog listing. Lighthouse '
            '90+ target on mobile.'
        ),
        'category': 'Web Development',
        'skills': ['Next.js', 'React', 'Tailwind CSS', 'SEO'],
        'budget_range': (45000, 120000),
        'budget_type': 'fixed',
    },
    {
        'title': 'Brand identity — logo, palette, and guidelines',
        'description': (
            'Complete identity for café reopening: logo suite, typography, colour system, and '
            'one-page brand guide PDF.'
        ),
        'category': 'Branding & Identity',
        'skills': ['Branding', 'Illustrator', 'Logo design'],
        'budget_range': (22000, 48000),
        'budget_type': 'fixed',
    },
    {
        'title': 'Mobile app UI redesign — Figma handoff',
        'description': (
            'Redesign onboarding, KYC, and checkout for existing fintech app. Component library '
            'and dev-ready specs.'
        ),
        'category': 'UI/UX Design',
        'skills': ['Figma', 'UI/UX', 'Prototyping'],
        'budget_range': (35000, 85000),
        'budget_type': 'fixed',
    },
    {
        'title': 'Q1 bookkeeping cleanup and VAT-ready reports',
        'description': (
            'Reconcile bank feeds, categorize expenses, and produce monthly P&L summaries for '
            'SME client.'
        ),
        'category': 'Data & Analytics',
        'skills': ['QuickBooks', 'Excel', 'Bookkeeping'],
        'budget_range': (12000, 28000),
        'budget_type': 'fixed',
    },
    {
        'title': 'E-commerce product photo retouching — 80 SKUs',
        'description': (
            'Background removal, colour correction, and consistent shadows for catalog upload. '
            'CSV manifest provided.'
        ),
        'category': 'Design & Creative',
        'skills': ['Photoshop', 'Lightroom', 'E-commerce'],
        'budget_range': (8000, 22000),
        'budget_type': 'fixed',
    },
    {
        'title': 'WordPress/WooCommerce checkout bug fixes',
        'description': (
            'Resolve payment gateway failures, email notification gaps, and mobile layout issues '
            'on live store.'
        ),
        'category': 'E-commerce Development',
        'skills': ['WordPress', 'WooCommerce', 'PHP'],
        'budget_range': (18000, 45000),
        'budget_type': 'hourly',
    },
]

SERVICE_TEMPLATES = [
    {
        'title': 'I will design a modern SaaS landing page in Figma',
        'detail': (
            'Conversion-focused landing page with hero, features, pricing, FAQ, and CTA sections. '
            'Includes desktop and mobile frames plus dev handoff notes.'
        ),
        'category': 'Web & App Design',
        'skills': ['Figma', 'UI Design', 'Landing pages'],
        'price_range': (8000, 25000),
    },
    {
        'title': 'I will build a responsive WordPress business website',
        'detail': (
            'Custom theme setup, speed optimization, contact forms, and basic SEO configuration. '
            'Training session for content updates included.'
        ),
        'category': 'WordPress & CMS',
        'skills': ['WordPress', 'Elementor', 'SEO'],
        'price_range': (15000, 45000),
    },
    {
        'title': 'I will edit professional YouTube videos with motion graphics',
        'detail': (
            'Cut, colour grade, sound mix, and lower-thirds for talking-head or screen-record '
            'content. Two revision rounds.'
        ),
        'category': 'Video & Animation',
        'skills': ['Premiere Pro', 'After Effects'],
        'price_range': (5000, 18000),
    },
    {
        'title': 'I will write SEO-optimized blog posts in English and Nepali',
        'detail': (
            'Research, outline, draft, and meta tags for 1500-word articles. Topic clusters and '
            'internal linking suggestions provided.'
        ),
        'category': 'Translation & Localization',
        'skills': ['SEO', 'Copywriting', 'Nepali', 'English'],
        'price_range': (2500, 8000),
    },
    {
        'title': 'I will create a minimalist logo and brand kit',
        'detail': (
            'Three concepts, two revision rounds, final logo files (SVG/PNG), colour palette, and '
            'social profile variants.'
        ),
        'category': 'Logo Design & Branding',
        'skills': ['Illustrator', 'Branding', 'Logo design'],
        'price_range': (6000, 20000),
    },
    {
        'title': 'I will develop a Django REST API with documentation',
        'detail': (
            'Models, serializers, auth, tests, and OpenAPI/Swagger docs. Deployment guidance for '
            'PostgreSQL on Linux VPS.'
        ),
        'category': 'Development & IT',
        'skills': ['Django', 'DRF', 'PostgreSQL', 'Swagger'],
        'price_range': (25000, 90000),
    },
]

BUDGET_TYPE_MAP = {
    'Hourly': 'hourly',
    'Full Time': 'fixed',
    'Part Time': 'hourly',
    'Fixed Price': 'fixed',
    'Contract': 'fixed',
}

LOGO_BGS = ['bg-[#192338]', 'bg-[#3f3ebd]', 'bg-[#ff1a53]', 'bg-[#0f766e]', 'bg-[#1d4ed8]']
ICON_TYPES = ['wave', 'face', 'in', 'clover']
JOB_LOCATIONS = ['Remote', 'Hybrid', 'In-office']
DURATIONS = ['1-5 Days', '5-10 Days', '10-20 Days', '20-30 Days', '30+ Days']
LEVELS = ['Entry Level', 'Intermediate', 'Expert']
EXPENSE = ['Inexpensive', 'Intermediate', 'Expensive']
HOURS = ['20 hrs/week', '30 hrs/week', '40 hrs/week', 'Flexible']


def _meta_entry(payload: dict) -> list:
    return [{'type': 'dashboard_meta', 'value': json.dumps(payload, ensure_ascii=False)}]


def _default_packages(base_price: int) -> dict:
    basic = int(base_price * 0.7)
    standard = base_price
    premium = int(base_price * 1.6)
    return {
        'tiers': [
            {'id': 'basic', 'name': 'Basic', 'description': 'Essential deliverables for a quick start.'},
            {'id': 'standard', 'name': 'Standard', 'description': 'Most popular — balanced scope and revisions.'},
            {'id': 'premium', 'name': 'Premium', 'description': 'Full scope with priority support and extras.'},
        ],
        'rows': [
            {
                'id': 'revisions',
                'label': 'Revisions',
                'type': 'text',
                'values': {'basic': '1', 'standard': '3', 'premium': '5'},
            },
            {
                'id': 'delivery',
                'label': 'Delivery Time',
                'type': 'text',
                'values': {'basic': '3 Days', 'standard': '5 Days', 'premium': '7 Days'},
            },
            {
                'id': 'total',
                'label': 'Total',
                'type': 'text',
                'values': {
                    'basic': str(basic),
                    'standard': str(standard),
                    'premium': str(premium),
                },
            },
        ],
    }


class Command(BaseCommand):
    help = 'Seed professional task, job, service, and project listings for demo users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=6,
            help='Listings per type per user (default: 6)',
        )
        parser.add_argument(
            '--emails',
            nargs='+',
            default=list(DEFAULT_EMAILS),
            help='Owner emails (default: bishal@baniya.com userc@userc.userc)',
        )
        parser.add_argument(
            '--password',
            type=str,
            default=DEFAULT_PASSWORD,
            help='Password when creating missing users',
        )

    def handle(self, *args, **options):
        count = max(1, options['count'])
        emails = [e.strip().lower() for e in options['emails']]
        password = options['password']

        self._ensure_categories()
        totals = {'task': 0, 'job': 0, 'project': 0, 'service': 0}

        with transaction.atomic():
            for email in emails:
                owner = self._ensure_user(email, password)
                rng = random.Random(f'listings-{email}')
                company = self._company_name(owner)
                self.stdout.write(self.style.MIGRATE_HEADING(f'\n{email} ({company})'))

                for _ in range(count):
                    totals['task'] += self._seed_task(owner, rng)
                    totals['job'] += self._seed_job(owner, rng, company)
                    totals['project'] += self._seed_project(owner, rng, company)
                    totals['service'] += self._seed_service(owner, rng)

        self.stdout.write(self.style.SUCCESS(
            f'\nDone — created {sum(totals.values())} listings: '
            f'{totals["task"]} tasks, {totals["job"]} jobs, '
            f'{totals["project"]} projects, {totals["service"]} services.'
        ))

    def _ensure_categories(self) -> None:
        seeds = [
            (['Cleaning', 'Plumbing', 'Moving', 'Assembly', 'Home Services'], 'task'),
            ([t['category'] for t in JOB_TEMPLATES], 'job'),
            ([t['category'] for t in PROJECT_TEMPLATES], 'project'),
            ([t['category'] for t in SERVICE_TEMPLATES], 'service'),
        ]
        for names, kind in seeds:
            for order, name in enumerate(dict.fromkeys(names)):
                slug = slugify(name)[:100]
                Category.objects.get_or_create(
                    name=name,
                    listing_kind=kind,
                    defaults={'slug': slug, 'order': order, 'is_active': True},
                )

    def _ensure_user(self, email: str, password: str) -> User:
        user = User.objects.filter(email__iexact=email).first()
        is_bishal = email == 'bishal@baniya.com'
        if not user:
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name='Bishal' if is_bishal else 'User',
                last_name='Baniya' if is_bishal else 'C',
                role='customer' if is_bishal else 'tasker',
            )
            self.stdout.write(self.style.SUCCESS(f'  Created user {email}'))
        else:
            user.set_password(password)

        user.is_active = True
        user.email_verified = True
        user.city = user.city or 'Kathmandu'
        user.state = user.state or 'Bagmati'
        user.country = user.country or 'Nepal'
        user.tagline = user.tagline or (
            'Employer & product owner at SajiloWork' if is_bishal else 'Full-stack freelancer & designer'
        )
        user.bio = user.bio or (
            'Posting jobs, projects, and local tasks across Nepal.'
            if is_bishal
            else 'Offering design, development, and content services.'
        )
        user.save()

        if is_bishal or user.role == 'customer':
            profile = get_or_create_employer_profile(user)
            if not profile.company_name:
                profile.company_name = 'Baniya Ventures' if is_bishal else f'{user.get_full_name()} Studio'
                profile.industry = 'Technology'
                profile.team_size = '6-20'
                profile.is_public = True
                profile.save()
        else:
            skills = ['Figma', 'React', 'Django', 'SEO', 'Content Writing']
            for skill in skills[:4]:
                UserSkill.objects.get_or_create(
                    user=user,
                    name=skill,
                    defaults={'proficiency_level': 'expert', 'years_of_experience': 4},
                )

        return user

    def _company_name(self, owner: User) -> str:
        profile = getattr(owner, 'employer_profile', None)
        if profile and profile.company_name.strip():
            return profile.company_name.strip()
        return owner.get_full_name().strip() or owner.email.split('@')[0]

    def _pick_category(self, kind: str, label: str) -> Category | None:
        cat = Category.objects.filter(listing_kind=kind, name=label, is_active=True).first()
        if cat:
            return cat
        slug = slugify(label)[:100]
        return Category.objects.filter(listing_kind=kind, slug=slug, is_active=True).first()

    def _location_fields(self, rng: random.Random) -> dict:
        city, state, lat, lng = rng.choice(NEPAL_LOCATIONS)
        is_remote = city == 'Remote'
        return {
            'is_remote': is_remote,
            'city': '' if is_remote else city,
            'state': '' if is_remote else state,
            'lat': lat,
            'lng': lng,
            'address': '' if is_remote else rng.choice(['Ward 4', 'Ward 8', 'Trade Tower', 'Ring Road']),
        }

    def _base_task_fields(self, owner, rng, *, budget, budget_type='fixed', work_type=None, loc=None):
        loc = loc or self._location_fields(rng)
        now = timezone.now()
        is_remote = loc['is_remote']
        return {
            'owner': owner,
            'status': 'open',
            'work_type': work_type or ('remote' if is_remote else rng.choice(['in_person', 'flexible'])),
            'urgency': rng.choice(['low', 'medium', 'high']),
            'budget_type': budget_type,
            'budget_amount': Decimal(budget),
            'budget_currency': 'NPR',
            'location_type': 'remote' if is_remote else 'physical',
            'address': loc['address'],
            'city': loc['city'],
            'state': loc['state'],
            'country': 'Nepal',
            'latitude': None if is_remote or loc['lat'] is None else loc['lat'] + Decimal(str(round(rng.uniform(-0.015, 0.015), 6))),
            'longitude': None if is_remote or loc['lng'] is None else loc['lng'] + Decimal(str(round(rng.uniform(-0.015, 0.015), 6))),
            'due_date': now + timedelta(days=rng.randint(5, 45)),
            'is_public': True,
            'allow_bids': True,
            'published_at': now - timedelta(days=rng.randint(0, 12), hours=rng.randint(0, 10)),
            'bids_count': rng.randint(0, 6),
            'views_count': rng.randint(12, 240),
        }

    def _unique_title(self, owner, title: str, rng: random.Random) -> str:
        # Titles can repeat; slugs are auto-generated uniquely on save.
        return title

    def _seed_task(self, owner, rng: random.Random) -> int:
        template = rng.choice(TASK_TEMPLATES)
        category = self._pick_category('task', template['category'])
        budget = rng.randint(*template['budget_range'])
        title = self._unique_title(owner, template['title'], rng)
        loc = self._location_fields(rng)

        Task.objects.create(
            title=title,
            description=template['description'],
            category=category,
            requirements=[rng.choice(TIME_LABELS)],
            tags=[slugify(template['category']), loc['city'].lower() or 'remote'],
            **self._base_task_fields(owner, rng, budget=budget, loc=loc),
        )
        self.stdout.write(f'  + task: {title[:60]}')
        return 1

    def _seed_job(self, owner, rng: random.Random, company: str) -> int:
        template = rng.choice(JOB_TEMPLATES)
        category = self._pick_category('job', template['category'])
        budget_min = rng.randint(template['budget_range'][0], template['budget_range'][1] - 5000)
        budget_max = rng.randint(budget_min + 2000, template['budget_range'][1])
        budget_amount = budget_max
        title = self._unique_title(owner, template['title'], rng)
        loc = self._location_fields(rng)
        location_label = rng.choice(JOB_LOCATIONS)
        if location_label == 'Remote':
            loc['is_remote'] = True

        skills = template['skills']
        description = (
            f'{template["description"]}\n\n'
            f'Skills: {", ".join(skills)}\n'
            f'Key responsibilities:\n'
            f'- Deliver milestones on agreed timeline\n'
            f'- Join weekly sync with hiring manager\n'
            f'- Document work and hand off cleanly\n\n'
            f'Work experience:\n'
            f'- 2+ years in a similar role\n'
            f'- Portfolio or published work required'
        )

        job_form = {
            'title': title,
            'category': template['category'],
            'companyName': company,
            'companyLogoBg': rng.choice(LOGO_BGS),
            'companyIconType': rng.choice(ICON_TYPES),
            'verified': rng.random() < 0.4,
            'location': location_label,
            'city': '' if loc['is_remote'] else (loc['city'] or 'Kathmandu'),
            'duration': rng.choice(DURATIONS),
            'type': template['type'],
            'experienceLevel': rng.choice(LEVELS),
            'budgetMin': str(budget_min),
            'budgetMax': str(budget_max),
            'expenseLevel': rng.choice(EXPENSE),
            'hoursLabel': rng.choice(HOURS),
            'postedLabel': rng.choice(['Posted today', 'Posted 2 days ago', 'Posted this week']),
            'skills': skills,
            'description': template['description'],
            'keyResponsibilities': [
                'Own deliverables from kickoff through launch',
                'Collaborate with cross-functional stakeholders',
                'Maintain quality bar and documentation',
            ],
            'workExperience': [
                '2+ years relevant experience',
                'Strong communication in English and Nepali',
                'Comfortable with remote collaboration tools',
            ],
            'status': 'Active',
        }

        Task.objects.create(
            title=title,
            description=description,
            category=category,
            requirements=_meta_entry({'form': 'job', 'category': template['category'], 'jobForm': job_form}),
            tags=with_listing_kind(
                [slugify(template['category']), loc['city'].lower() or 'remote'],
                LISTING_KIND_JOB,
            ),
            **self._base_task_fields(
                owner,
                rng,
                budget=budget_amount,
                budget_type=BUDGET_TYPE_MAP.get(template['type'], 'fixed'),
                loc=loc,
            ),
        )
        self.stdout.write(f'  + job: {title[:60]}')
        return 1

    def _seed_project(self, owner, rng: random.Random, company: str) -> int:
        template = rng.choice(PROJECT_TEMPLATES)
        category = self._pick_category('project', template['category'])
        budget = rng.randint(*template['budget_range'])
        title = self._unique_title(owner, template['title'], rng)
        loc = self._location_fields(rng)
        skills = template['skills']
        languages = rng.sample(['English', 'Nepali', 'Hindi'], k=rng.randint(1, 2))

        project_form = {
            'title': title,
            'category': template['category'],
            'freelancerType': rng.choice(['Individual', 'Agency', 'Team']),
            'priceType': 'Hourly' if template['budget_type'] == 'hourly' else 'Fixed Price',
            'cost': str(budget),
            'projectDuration': rng.choice(['1-5 Days', '6-10 Days', '10-15 Days', '20-30 Days']),
            'level': rng.choice(['Entry', 'Medium', 'Expert']),
            'dateType': rng.choice(['flexible', 'before', 'specific']),
            'specificDate': '',
            'beforeDate': (timezone.now() + timedelta(days=30)).date().isoformat(),
            'timeOfDayRequired': False,
            'timeSlot': None,
            'locationType': 'remote' if loc['is_remote'] else 'in-person',
            'location': loc['city'] or 'Kathmandu Valley',
            'languages': languages,
            'skills': skills,
            'projectDetail': template['description'],
        }

        description = (
            f'{template["description"]}\n\n'
            f'Skills: {", ".join(skills)}\n'
            f'Freelancer type: {project_form["freelancerType"]}\n'
            f'Duration: {project_form["projectDuration"]}\n'
            f'Experience level: {project_form["level"]}\n'
            f'Languages: {", ".join(languages)}\n'
            f'Posted by: {company}'
        )

        Task.objects.create(
            title=title,
            description=description,
            category=category,
            requirements=_meta_entry({
                'form': 'project',
                'category': template['category'],
                'projectForm': project_form,
            }),
            tags=with_listing_kind(
                [slugify(template['category']), loc['city'].lower() or 'remote'],
                LISTING_KIND_PROJECT,
            ),
            **self._base_task_fields(
                owner,
                rng,
                budget=budget,
                budget_type=template['budget_type'],
                loc=loc,
            ),
        )
        self.stdout.write(f'  + project: {title[:60]}')
        return 1

    def _seed_service(self, owner, rng: random.Random) -> int:
        template = rng.choice(SERVICE_TEMPLATES)
        category = self._pick_category('service', template['category'])
        price = rng.randint(*template['price_range'])
        title = self._unique_title(owner, template['title'], rng)
        loc = self._location_fields(rng)
        skills = template['skills']
        languages = rng.sample(['English', 'Nepali'], k=rng.randint(1, 2))
        packages = _default_packages(price)

        service_detail = template['detail']
        description = (
            f'{service_detail}\n\n'
            f'Skills: {", ".join(skills)}\n'
            f'Languages: {", ".join(languages)}\n'
            f'Response time: within 2 hours\n'
            f'Delivery time: 3–7 business days'
        )

        task = Task.objects.create(
            title=title,
            description=description,
            category=category,
            requirements=_meta_entry({
                'form': 'service',
                'category': template['category'],
                'packages': packages,
                'languages': languages,
                'responseTime': 'within 2 hours',
                'deliveryTime': rng.choice(['24h', '3days', '7days']),
                'skills': skills,
                'bullets': skills[:3],
                'serviceDetail': service_detail,
            }),
            tags=with_listing_kind(
                [slugify(template['category']), loc['city'].lower() or 'remote'],
                LISTING_KIND_SERVICE,
            ),
            **self._base_task_fields(owner, rng, budget=price, loc=loc),
        )

        seed_service_cover_images([task], only_missing=True, images_per_service=rng.randint(2, 4), rng=rng)
        self.stdout.write(f'  + service: {title[:60]}')
        return 1
