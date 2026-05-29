"""
Utility functions and helpers.
"""
import uuid
import hashlib
from django.utils.text import slugify


def generate_unique_id():
    """Generate a unique ID."""
    return str(uuid.uuid4())


def generate_slug(text):
    """Generate a URL-friendly slug."""
    return slugify(text)


def hash_string(text):
    """Generate SHA256 hash of a string."""
    return hashlib.sha256(text.encode()).hexdigest()


def calculate_platform_fee(amount, percentage=15):
    """Calculate platform fee."""
    return round(amount * (percentage / 100), 2)


def format_currency(amount):
    """Format amount as currency."""
    return f"${amount:.2f}"
