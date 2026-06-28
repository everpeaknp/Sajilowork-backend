import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.users.models import User
from apps.mails.models import ContactSubmission

print("User model:")
print(f"  App label: {User._meta.app_label}")
print(f"  Model name: {User._meta.model_name}")
print(f"  DB table: {User._meta.db_table}")

print("\nContactSubmission model:")
print(f"  App label: {ContactSubmission._meta.app_label}")
print(f"  Model name: {ContactSubmission._meta.model_name}")
print(f"  DB table: {ContactSubmission._meta.db_table}")

print("\nContactSubmission responded_by field:")
responded_by_field = ContactSubmission._meta.get_field('responded_by')
print(f"  Related model: {responded_by_field.related_model}")
print(f"  Related model table: {responded_by_field.related_model._meta.db_table}")
print(f"  DB column: {responded_by_field.column}")
