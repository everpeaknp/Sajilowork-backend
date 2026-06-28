"""Test ContactSubmission model"""
import os
import sys
import django

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

# Setup Django without Celery
os.environ['SKIP_CELERY'] = '1'

# Import the celery app to prevent import errors
import config

# Now setup Django
django.setup()

from apps.mails.models import ContactSubmission

# Test creating a contact submission
try:
    print("Testing ContactSubmission model...")
    print("-" * 80)
    
    # Create test submission
    submission = ContactSubmission.objects.create(
        name="Test User",
        email="test@example.com",
        message="This is a test message from the model test script.",
        ip_address="127.0.0.1",
        user_agent="Test User Agent"
    )
    
    print(f"✓ Created submission: {submission.id}")
    print(f"  Name: {submission.name}")
    print(f"  Email: {submission.email}")
    print(f"  Status: {submission.status}")
    print(f"  Admin Notes: {submission.admin_notes or '(empty)'}")
    print(f"  Responded By: {submission.responded_by or '(none)'}")
    
    # Try to update admin_notes
    print("\nUpdating admin_notes...")
    submission.admin_notes = "This is a test admin note"
    submission.save()
    print(f"✓ Updated admin_notes: {submission.admin_notes}")
    
    # Clean up
    print("\nCleaning up test data...")
    submission.delete()
    print("✓ Test submission deleted")
    
    print("\n" + "=" * 80)
    print("✓ All tests passed! ContactSubmission model is working correctly.")
    print("=" * 80)
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
