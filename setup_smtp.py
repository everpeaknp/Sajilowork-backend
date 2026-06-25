#!/usr/bin/env python
"""
Setup SMTP Configuration - Create SMTP config from .env settings
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.conf import settings
from apps.mails.models import SMTPConfiguration, EmailSetting

def setup_smtp():
    """Create or update SMTP configuration from Django settings"""
    
    print("=" * 60)
    print("SMTP CONFIGURATION SETUP")
    print("=" * 60)
    
    # Check if we have email settings
    email_host = getattr(settings, 'EMAIL_HOST', None)
    email_port = getattr(settings, 'EMAIL_PORT', None)
    email_user = getattr(settings, 'EMAIL_HOST_USER', None)
    email_password = getattr(settings, 'EMAIL_HOST_PASSWORD', None)
    
    if not all([email_host, email_port, email_user, email_password]):
        print("\n❌ ERROR: Email settings not configured in .env file!")
        print("\nRequired settings:")
        print("  EMAIL_HOST")
        print("  EMAIL_PORT")
        print("  EMAIL_HOST_USER")
        print("  EMAIL_HOST_PASSWORD")
        return False
    
    print(f"\n✓ Found email settings:")
    print(f"  Host: {email_host}")
    print(f"  Port: {email_port}")
    print(f"  User: {email_user}")
    
    # Determine encryption
    use_tls = getattr(settings, 'EMAIL_USE_TLS', False)
    use_ssl = getattr(settings, 'EMAIL_USE_SSL', False)
    
    if use_ssl:
        encryption = 'ssl'
    elif use_tls:
        encryption = 'tls'
    else:
        encryption = 'none'
    
    print(f"  Encryption: {encryption.upper()}")
    
    # Determine provider
    if 'gmail' in email_host.lower():
        provider = 'gmail'
    elif 'outlook' in email_host.lower() or 'office365' in email_host.lower():
        provider = 'outlook'
    elif 'sendgrid' in email_host.lower():
        provider = 'sendgrid'
    elif 'mailgun' in email_host.lower():
        provider = 'mailgun'
    elif 'amazonaws' in email_host.lower():
        provider = 'ses'
    else:
        provider = 'custom'
    
    # Create or update SMTP configuration
    smtp_config, created = SMTPConfiguration.objects.update_or_create(
        name=f"{provider.title()} SMTP",
        defaults={
            'provider': provider,
            'host': email_host,
            'port': email_port,
            'username': email_user,
            'password': email_password,
            'from_email': email_user,
            'from_name': getattr(settings, 'APP_NAME', 'Sajilowork'),
            'encryption': encryption,
            'is_active': True,
            'test_status': 'untested',
        }
    )
    
    if created:
        print(f"\n✓ Created new SMTP configuration: {smtp_config.name}")
    else:
        print(f"\n✓ Updated existing SMTP configuration: {smtp_config.name}")
    
    print(f"  ID: {smtp_config.id}")
    print(f"  Provider: {smtp_config.provider}")
    print(f"  Active: {smtp_config.is_active}")
    
    # Create/update email settings
    email_settings, created = EmailSetting.objects.get_or_create(
        id=1,  # Singleton
        defaults={
            'company_name': getattr(settings, 'APP_NAME', 'Sajilowork'),
            'support_email': email_user,
            'primary_color': '#667eea',
            'secondary_color': '#764ba2',
            'footer_text': f'© 2024 {getattr(settings, "APP_NAME", "Sajilowork")}. All rights reserved.',
            'social_links': {
                'facebook': '',
                'twitter': '',
                'linkedin': '',
                'instagram': '',
            },
            'unsubscribe_url': f'{getattr(settings, "FRONTEND_URL", "http://localhost:3000")}/unsubscribe',
            'email_enabled': True,
        }
    )
    
    if created:
        print(f"\n✓ Created email settings")
    else:
        print(f"\n✓ Email settings already exist")
    
    print(f"  Company: {email_settings.company_name}")
    print(f"  Support Email: {email_settings.support_email}")
    print(f"  Email Enabled: {email_settings.email_enabled}")
    
    print("\n" + "=" * 60)
    print("✅ SMTP CONFIGURATION COMPLETE")
    print("=" * 60)
    
    return True

if __name__ == '__main__':
    success = setup_smtp()
    if success:
        print("\n✓ You can now send test emails!")
        print("  Run: python send_test_email.py")
