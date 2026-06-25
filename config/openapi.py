"""OpenAPI / drf-spectacular configuration helpers."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_api_description() -> str:
    path = BASE_DIR / 'docs' / 'openapi_description.md'
    if path.is_file():
        return path.read_text(encoding='utf-8')
    return 'SajiloWork marketplace REST API'


API_TAGS = [
    {
        'name': 'Authentication',
        'description': (
            'JWT login, token refresh, logout, password reset, and email verification. '
            'Start here before calling protected routes.'
        ),
    },
    {
        'name': 'Users',
        'description': 'User profiles, roles (poster/tasker), badges, and account settings.',
    },
    {
        'name': 'Tasks',
        'description': (
            'Create and manage tasks, categories, attachments, status updates, '
            'and dual-party completion (`confirm_work_complete`).'
        ),
    },
    {
        'name': 'Bids',
        'description': 'Taskers submit and manage offers on open tasks.',
    },
    {
        'name': 'Reviews',
        'description': 'Ratings and reviews after completed tasks.',
    },
    {
        'name': 'Chat',
        'description': 'Messaging between poster and tasker on a task.',
    },
    {
        'name': 'Notifications',
        'description': 'In-app notification list and read state.',
    },
    {
        'name': 'Payments',
        'description': (
            'Task payments, escrow, refunds, saved payment methods, and payment history. '
            'For wallet cash-out use **Wallets - withdrawals**, not legacy Payout records.'
        ),
    },
    {
        'name': 'Wallets',
        'description': (
            'Wallet balance, transactions, withdrawal requests, limits. '
            'Primary API for tasker withdrawals (eSewa / bank transfer).'
        ),
    },
    {
        'name': 'Fees',
        'description': 'Preview platform and withdrawal fees before checkout or payout.',
    },
    {
        'name': 'Dashboard',
        'description': 'Aggregated stats for tasker/poster dashboards.',
    },
    {
        'name': 'Search',
        'description': 'Search tasks and users.',
    },
    {
        'name': 'Locations',
        'description': 'Cities, areas, and location helpers.',
    },
    {
        'name': 'Uploads',
        'description': 'Image and file uploads (`multipart/form-data`).',
    },
    {
        'name': 'Analytics',
        'description': 'Analytics and reporting endpoints.',
    },
    {
        'name': 'Blog',
        'description': 'Public blog posts and featured articles.',
    },
    {
        'name': 'Disputes',
        'description': 'Task disputes, evidence, and resolution workflow.',
    },
    {
        'name': 'Rules',
        'description': 'Platform rules, moderation policies, and account enforcement.',
    },
]


# drf-spectacular auto-tags operations from the first URL segment after /api/v1/
# (e.g. "analytics"). We declare human-friendly tags in API_TAGS (e.g. "Analytics").
# This map merges the two so Swagger UI shows a single group per domain.
URL_SEGMENT_TAG_ALIASES = {
    'auth': 'Authentication',
    'analytics': 'Analytics',
    'bids': 'Bids',
    'blog': 'Blog',
    'chat': 'Chat',
    'dashboard': 'Dashboard',
    'disputes': 'Disputes',
    'fees': 'Fees',
    'locations': 'Locations',
    'notifications': 'Notifications',
    'payments': 'Payments',
    'reviews': 'Reviews',
    'rules': 'Rules',
    'search': 'Search',
    'tasks': 'Tasks',
    'uploads': 'Uploads',
    'users': 'Users',
    'wallets': 'Wallets',
}


def build_tag_alias_map() -> dict[str, str]:
    """Lowercase alias -> canonical tag name used in Swagger UI."""
    aliases: dict[str, str] = {}
    for tag in API_TAGS:
        name = tag['name']
        aliases[name.lower()] = name
    for segment, canonical in URL_SEGMENT_TAG_ALIASES.items():
        aliases.setdefault(segment.lower(), canonical)
    return aliases
