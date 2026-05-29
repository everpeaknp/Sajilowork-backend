"""Review system constants."""

REVIEWER_TYPE_CUSTOMER = 'customer'
REVIEWER_TYPE_TASKER = 'tasker'

REVIEWER_TYPE_CHOICES = [
    (REVIEWER_TYPE_CUSTOMER, 'Customer'),
    (REVIEWER_TYPE_TASKER, 'Tasker'),
]

# Legacy review_type values (kept for invitations / migrations)
REVIEW_TYPE_OWNER_TO_PROVIDER = 'owner_to_provider'
REVIEW_TYPE_PROVIDER_TO_OWNER = 'provider_to_owner'

CUSTOMER_TO_TASKER_TAGS = frozenset({
    'professional',
    'on_time',
    'good_communication',
    'poor_quality',
    'recommended',
})

TASKER_TO_CUSTOMER_TAGS = frozenset({
    'clear_instructions',
    'easy_to_work_with',
    'late_response',
    'uncooperative',
    'friendly',
})

VISIBILITY_IMMEDIATE = 'immediate'
VISIBILITY_BOTH_SUBMITTED = 'both_submitted'
VISIBILITY_DELAY_24H = 'delay_24h'

VISIBILITY_MODE_CHOICES = [
    (VISIBILITY_IMMEDIATE, 'Show immediately'),
    (VISIBILITY_BOTH_SUBMITTED, 'Show after both parties submit'),
    (VISIBILITY_DELAY_24H, 'Show after 24 hours'),
]

DEFAULT_REVIEW_WINDOW_DAYS = 14
DEFAULT_EDIT_WINDOW_MINUTES = 0
DEFAULT_RATE_LIMIT_PER_HOUR = 10
