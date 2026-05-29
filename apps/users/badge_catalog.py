"""Badge definitions shared by API, admin, and tasker dashboard."""

from __future__ import annotations

# badge_type -> (display name, description)
BADGE_CATALOG: dict[str, tuple[str, str]] = {
    'police_check': (
        'Police Check',
        'Provide peace of mind by successfully completing a Police Check.',
    ),
    'payment_verified': (
        'Payment Method Verified',
        'Make payments with ease by having your payment method verified.',
    ),
    'mobile_verified': (
        'Mobile Verified',
        'Verified mobile number for instant task notifications.',
    ),
    'electrical_licence': (
        'Electrical Licence',
        'Holds a valid electrical contractor licence.',
    ),
    'plumbing_licence': (
        'Plumbing Licence',
        'Holds a valid plumbing licence.',
    ),
    'custom_licence': (
        'Custom Licence',
        'Professional licence or certification submitted by the tasker.',
    ),
    'identity_verified': (
        'Identity Verified',
        'Government identity document verified.',
    ),
    'verified': ('Verified', 'Platform verified member.'),
    'top_rated': ('Top Rated', 'Maintained excellent ratings.'),
    'fast_responder': ('Fast Responder', 'Responds quickly to tasks.'),
    'reliable': ('Reliable', 'Consistently completes tasks on time.'),
    'expert': ('Expert', 'Recognized expert in their category.'),
    'rising_talent': ('Rising Talent', 'Emerging top performer.'),
    'milestone': ('Milestone', 'Achievement milestone unlocked.'),
}

# Badges a tasker can request from the dashboard (admin may verify)
REQUESTABLE_BADGE_TYPES = frozenset({
    'police_check',
    'electrical_licence',
    'plumbing_licence',
    'custom_licence',
    'identity_verified',
})

# Badges that require an uploaded document from the tasker dashboard
DOCUMENT_REQUIRED_BADGE_TYPES = frozenset({
    'police_check',
    'electrical_licence',
    'plumbing_licence',
    'custom_licence',
})

MAX_CUSTOM_LICENCE_BADGES_PER_USER = 10

# Synced automatically from user profile state
AUTO_BADGE_TYPES = frozenset({
    'mobile_verified',
    'payment_verified',
})

ALL_BADGE_TYPE_CHOICES = [
    (key, value[0]) for key, value in BADGE_CATALOG.items()
]
