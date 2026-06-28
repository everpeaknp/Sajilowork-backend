"""Check columns in contact_submissions table"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("PRAGMA table_info(contact_submissions)")
    columns = cursor.fetchall()
    
    print("\nColumns in contact_submissions table:")
    print("-" * 80)
    for col in columns:
        print(f"  {col[1]:20s} {col[2]:15s} NULL={bool(col[3])} DEFAULT={col[4]}")
