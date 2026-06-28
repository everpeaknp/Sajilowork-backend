#!/usr/bin/env python
"""
Test Email Script - Send test email for job/task/service project
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.mails.models import SMTPConfiguration, EmailLog
from apps.mails.smtp_manager import SMTPManager
from django.utils import timezone

def send_test_email():
    """Send a test email about a job/task/service project"""
    
    print("=" * 60)
    print("SENDING TEST EMAIL - Job/Task/Service Project")
    print("=" * 60)
    
    # Get active SMTP configuration
    smtp_config = SMTPConfiguration.objects.filter(is_active=True).first()
    
    if not smtp_config:
        print("\n❌ ERROR: No active SMTP configuration found!")
        print("\nPlease configure SMTP settings in Django Admin:")
        print("http://localhost:8000/admin/mails/smtpconfiguration/")
        return
    
    print(f"\n✓ Found SMTP Config: {smtp_config.name}")
    print(f"  Host: {smtp_config.host}")
    print(f"  Port: {smtp_config.port}")
    print(f"  From: {smtp_config.from_name} <{smtp_config.from_email}>")
    
    # Test recipient
    recipient_email = "npgamesbazar@gmail.com"
    
    # Create test email content
    subject = "[TEST] New Job Posted - Web Developer Needed"
    
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>New Job Posted</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f9fafb;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f9fafb; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; border: 1px solid #e5e7eb;">
                        <!-- Header -->
                        <tr>
                            <td style="background-color: #1161fe; padding: 40px; text-align: center;">
                                <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px;">
                                    New Job Posted
                                </h1>
                                <p style="color: rgba(255, 255, 255, 0.9); margin: 10px 0 0 0; font-size: 15px;">
                                    A great opportunity just for you
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Content -->
                        <tr>
                            <td style="padding: 40px 32px;">
                                <!-- Job Card -->
                                <div style="background-color: #f9fafb; border: 1px solid #e5e7eb; padding: 24px; border-radius: 8px; margin-bottom: 24px;">
                                    <h2 style="color: #171717; margin: 0 0 16px 0; font-size: 22px; font-weight: 700;">
                                        Web Developer Needed for E-commerce Platform
                                    </h2>
                                    
                                    <div style="margin-bottom: 16px;">
                                        <span style="display: inline-block; background-color: #45a874; color: #ffffff; padding: 6px 14px; border-radius: 6px; font-size: 14px; font-weight: 600;">
                                            NPR 50,000 - 80,000
                                        </span>
                                    </div>
                                    
                                    <p style="color: #6b7280; line-height: 1.7; margin: 16px 0; font-size: 15px;">
                                        We are looking for an experienced web developer to build a modern e-commerce platform. 
                                        The project involves creating a responsive online store with payment gateway integration, 
                                        product management system, and user authentication.
                                    </p>
                                    
                                    <div style="border-top: 1px solid #e5e7eb; padding-top: 16px; margin-top: 20px;">
                                        <table cellpadding="0" cellspacing="0" width="100%">
                                            <tr>
                                                <td style="padding: 6px 0;">
                                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6b7280" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; display: inline-block; margin-right: 8px;">
                                                        <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/>
                                                        <circle cx="12" cy="10" r="3"/>
                                                    </svg>
                                                    <span style="color: #6b7280; font-size: 14px; vertical-align: middle;">
                                                        <strong style="color: #171717;">Location:</strong> Kathmandu, Nepal
                                                    </span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 6px 0;">
                                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6b7280" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; display: inline-block; margin-right: 8px;">
                                                        <circle cx="12" cy="12" r="10"/>
                                                        <polyline points="12 6 12 12 16 14"/>
                                                    </svg>
                                                    <span style="color: #6b7280; font-size: 14px; vertical-align: middle;">
                                                        <strong style="color: #171717;">Posted:</strong> 2 hours ago
                                                    </span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 6px 0;">
                                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6b7280" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; display: inline-block; margin-right: 8px;">
                                                        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                                                        <line x1="16" y1="2" x2="16" y2="6"/>
                                                        <line x1="8" y1="2" x2="8" y2="6"/>
                                                        <line x1="3" y1="10" x2="21" y2="10"/>
                                                    </svg>
                                                    <span style="color: #6b7280; font-size: 14px; vertical-align: middle;">
                                                        <strong style="color: #171717;">Due Date:</strong> January 15, 2024
                                                    </span>
                                                </td>
                                            </tr>
                                        </table>
                                    </div>
                                </div>
                                
                                <!-- Requirements Section -->
                                <div style="margin-bottom: 24px;">
                                    <h3 style="color: #171717; font-size: 17px; font-weight: 700; margin: 0 0 14px 0; display: flex; align-items: center;">
                                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#1161fe" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; display: inline-block; margin-right: 8px;">
                                            <circle cx="12" cy="12" r="10"/>
                                            <circle cx="12" cy="12" r="6"/>
                                            <circle cx="12" cy="12" r="2"/>
                                        </svg>
                                        Required Skills
                                    </h3>
                                    <ul style="color: #6b7280; line-height: 1.8; margin: 0; padding-left: 20px; font-size: 14px;">
                                        <li style="margin-bottom: 6px;">React.js and Next.js</li>
                                        <li style="margin-bottom: 6px;">Node.js and Express</li>
                                        <li style="margin-bottom: 6px;">MongoDB or PostgreSQL</li>
                                        <li style="margin-bottom: 6px;">Payment Gateway Integration (eSewa, Khalti)</li>
                                        <li style="margin-bottom: 6px;">RESTful API Development</li>
                                    </ul>
                                </div>
                                
                                <!-- Client Info -->
                                <div style="background-color: #f4f8f6; border: 1px solid #e5e7eb; padding: 20px; border-radius: 8px; margin-bottom: 28px;">
                                    <h3 style="color: #171717; font-size: 16px; font-weight: 700; margin: 0 0 12px 0; display: flex; align-items: center;">
                                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#193e32" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; display: inline-block; margin-right: 8px;">
                                            <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/>
                                            <circle cx="12" cy="7" r="4"/>
                                        </svg>
                                        About the Client
                                    </h3>
                                    <p style="color: #6b7280; margin: 0; line-height: 1.7; font-size: 14px;">
                                        <strong style="color: #171717;">Rating:</strong> 4.8/5.0<br>
                                        <strong style="color: #171717;">Jobs Posted:</strong> 12 completed<br>
                                        <strong style="color: #171717;">Payment Method:</strong> Verified
                                    </p>
                                </div>
                                
                                <!-- CTA Button -->
                                <div style="text-align: center; margin-top: 32px;">
                                    <a href="http://localhost:3000/task/web-developer-needed-123" 
                                       style="display: inline-block; background-color: #1161fe; color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-size: 15px; font-weight: 600; box-shadow: 0 1px 2px rgba(17, 97, 254, 0.2);">
                                        View Job Details & Apply
                                    </a>
                                </div>
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="background-color: #f9fafb; padding: 24px 32px; text-align: center; border-top: 1px solid #e5e7eb;">
                                <p style="color: #6b7280; font-size: 13px; margin: 0 0 8px 0; line-height: 1.6;">
                                    This is a test email from Sajilowork Email System
                                </p>
                                <p style="color: #9ca3af; font-size: 12px; margin: 0;">
                                    © 2024 Sajilowork. All rights reserved.
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """.replace("{current_time}", timezone.now().strftime("%Y-%m-%d %H:%M:%S %Z"))
    
    text_content = """
    NEW JOB POSTED - Sajilowork
    
    Job Title: Web Developer Needed for E-commerce Platform
    Location: Kathmandu, Nepal
    Budget: NPR 50,000 - 80,000
    Posted: 2 hours ago
    Due Date: January 15, 2024
    
    Description:
    We are looking for an experienced web developer to build a modern e-commerce platform.
    The project involves creating a responsive online store with payment gateway integration,
    product management system, and user authentication.
    
    Required Skills:
    - React.js and Next.js
    - Node.js and Express
    - MongoDB or PostgreSQL
    - Payment Gateway Integration (eSewa, Khalti)
    - RESTful API Development
    
    About the Client:
    Rating: 4.8/5.0
    Jobs Posted: 12 completed
    Payment Method: Verified
    
    View Job Details: http://localhost:3000/task/web-developer-needed-123
    
    ---
    This is a test email from Sajilowork Email System
    © 2024 Sajilowork. All rights reserved.
    """.replace("{current_time}", timezone.now().strftime("%Y-%m-%d %H:%M:%S %Z"))
    
    # Create email log
    print(f"\n📧 Preparing email to: {recipient_email}")
    
    email_log = EmailLog.objects.create(
        recipient_email=recipient_email,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
        smtp_config_used=smtp_config,
        status='pending',
        metadata={
            'is_test': True,
            'test_type': 'job_service_project',
            'sent_via': 'test_script'
        }
    )
    
    print(f"✓ Email log created: {email_log.id}")
    
    # Send email
    print(f"\n📤 Sending email via SMTP...")
    
    success, message = SMTPManager.send_email(
        smtp_config=smtp_config,
        to_email=recipient_email,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
        reply_to=smtp_config.from_email
    )
    
    # Update email log status
    if success:
        email_log.status = 'sent'
        email_log.sent_at = timezone.now()
        email_log.save()
        
        print("\n" + "=" * 60)
        print("✅ SUCCESS - Email sent successfully!")
        print("=" * 60)
        print(f"\n📧 Recipient: {recipient_email}")
        print(f"📝 Subject: {subject}")
        print(f"🆔 Email Log ID: {email_log.id}")
        print(f"⏰ Sent At: {email_log.sent_at}")
        print(f"\n✉️ Please check {recipient_email} inbox!")
        print("   (Check spam folder if not in inbox)")
        
    else:
        email_log.status = 'failed'
        email_log.error_message = message
        email_log.save()
        
        print("\n" + "=" * 60)
        print("❌ FAILED - Email could not be sent")
        print("=" * 60)
        print(f"\n❌ Error: {message}")
        print(f"🆔 Email Log ID: {email_log.id}")
        print("\nTroubleshooting:")
        print("1. Check SMTP credentials in Django Admin")
        print("2. Verify SMTP host and port are correct")
        print("3. For Gmail: Enable 'App Passwords' if 2FA is on")
        print("4. Check firewall/network settings")
    
    print("\n" + "=" * 60)

if __name__ == '__main__':
    send_test_email()
