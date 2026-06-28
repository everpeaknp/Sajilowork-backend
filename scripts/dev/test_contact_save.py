"""
Test creating a ContactSubmission to see the actual SQL being generated
"""
import os
import django

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

# Patch for Python 3.14 compatibility
try:
    from config.django_py314_patch import patched_copy
except ImportError:
    pass

django.setup()

from apps.mails.models import ContactSubmission

# Enable SQL logging
import logging
logging.basicConfig()
logging.getLogger('django.db.backends').setLevel(logging.DEBUG)

print("Testing ContactSubmission creation...")
print("=" * 80)

try:
    submission = ContactSubmission.objects.create(
        name="Test User",
        email="test@example.com",
        message="This is a test message from the debug script.",
        ip_address="127.0.0.1",
        user_agent="Test Script"
    )
    print(f"\n✓ SUCCESS: Created ContactSubmission with ID: {submission.id}")
    print(f"  Name: {submission.name}")
    print(f"  Email: {submission.email}")
    print(f"  Status: {submission.status}")
    
except Exception as e:
    print(f"\n✗ ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
