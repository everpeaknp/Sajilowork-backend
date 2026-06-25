#!/usr/bin/env python
"""Test script to diagnose Jazzmin template loading"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.conf import settings
from django.template import loader
from django.template.backends.django import DjangoTemplates

print("=" * 60)
print("JAZZMIN DIAGNOSTIC TEST")
print("=" * 60)

# Check INSTALLED_APPS
print("\n1. INSTALLED_APPS Order:")
for i, app in enumerate(settings.INSTALLED_APPS[:10]):
    print(f"   {i}. {app}")

# Check template engines
print("\n2. Template Engines:")
for engine in settings.TEMPLATES:
    print(f"   Backend: {engine['BACKEND']}")
    print(f"   APP_DIRS: {engine.get('APP_DIRS', False)}")
    print(f"   DIRS: {engine.get('DIRS', [])}")

# Check if Jazzmin templates can be found
print("\n3. Template Resolution Test:")
try:
    template = loader.get_template('admin/base.html')
    print(f"   ✓ admin/base.html found")
    print(f"   Path: {template.origin.name if hasattr(template, 'origin') else 'Unknown'}")
except Exception as e:
    print(f"   ✗ Error loading admin/base.html: {e}")

# Check if Jazzmin is in template path
print("\n4. Checking Jazzmin Template Directory:")
import jazzmin
from pathlib import Path
jazzmin_path = Path(jazzmin.__file__).parent / 'templates'
print(f"   Path: {jazzmin_path}")
print(f"   Exists: {jazzmin_path.exists()}")
if jazzmin_path.exists():
    admin_base = jazzmin_path / 'admin' / 'base.html'
    print(f"   admin/base.html exists: {admin_base.exists()}")

print("\n" + "=" * 60)
