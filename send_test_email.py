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
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
            .content { background: #f9f9f9; padding: 30px; border: 1px solid #e0e0e0; }
            .project-card { background: white; padding: 20px; margin: 20px 0; border-left: 4px solid #667eea; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .project-title { font-size: 20px; font-weight: bold; color: #2d3748; margin-bottom: 10px; }
            .project-meta { color: #718096; font-size: 14px; margin: 5px 0; }
            .budget { font-size: 24px; font-weight: bold; color: #48bb78; margin: 15px 0; }
            .button { display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
            .footer { background: #2d3748; color: white; padding: 20px; text-align: center; border-radius: 0 0 10px 10px; font-size: 12px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎯 New Job Posted</h1>
                <p>A new task matching your skills is available!</p>
            </div>
            
            <div class="content">
                <div class="project-card">
                    <div class="project-title">
                        💻 Web Developer Needed for E-commerce Platform
                    </div>
                    
                    <div class="project-meta">
                        <strong>📍 Location:</strong> Remote (Nepal)
                    </div>
                    
                    <div class="project-meta">
                        <strong>⏰ Posted:</strong> 2 hours ago
                    </div>
                    
                    <div class="project-meta">
                        <strong>📅 Deadline:</strong> 7 days from now
                    </div>
                    
                    <div class="budget">
                        💰 Budget: NPR 50,000 - 80,000
                    </div>
                    
                    <div class="project-meta">
                        <strong>📋 Description:</strong>
                    </div>
                    <p style="margin: 15px 0; line-height: 1.8;">
                        Looking for an experienced web developer to build a modern e-commerce platform. 
                        The project includes frontend (React/Next.js), backend (Django/Python), 
                        payment integration (eSewa/Khalti), and admin dashboard.
                    </p>
                    
                    <div class="project-meta">
                        <strong>🛠️ Required Skills:</strong>
                    </div>
                    <p style="margin: 10px 0;">
                        • React.js & Next.js<br>
                        • Python & Django<br>
                        • PostgreSQL<br>
                        • Payment Gateway Integration<br>
                        • RESTful API Development
                    </p>
                    
                    <div class="project-meta">
                        <strong>👤 Client:</strong> Verified Business Account ✓
                    </div>
                    
                    <div class="project-meta">
                        <strong>⭐ Client Rating:</strong> 4.8/5.0 (23 reviews)
                    </div>
                    
                    <a href="http://localhost:3000/task/web-developer-ecommerce" class="button">
                        📝 Make an Offer
                    </a>
                </div>
                
                <div style="margin: 20px 0; padding: 15px; background: #fff3cd; border-left: 4px solid #ffc107; border-radius: 5px;">
                    <strong>💡 Tip:</strong> Apply early! Projects with early bids get 3x more client responses.
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <p style="color: #718096; margin: 10px 0;">
                        This is a <strong>TEST EMAIL</strong> from the Enterprise Email Management System
                    </p>
                    <p style="color: #718096; margin: 10px 0;">
                        Email sent at: {current_time}
                    </p>
                </div>
            </div>
            
            <div class="footer">
                <p><strong>Sajilowork - Nepal's Premier Freelance Platform</strong></p>
                <p>Connect with skilled professionals and grow your business</p>
                <p style="margin-top: 15px;">
                    <a href="http://localhost:3000" style="color: #90cdf4; text-decoration: none;">Visit Website</a> | 
                    <a href="mailto:mr.bishal.baniya@gmail.com" style="color: #90cdf4; text-decoration: none;">Contact Support</a>
                </p>
                <p style="margin-top: 15px; font-size: 11px; color: #a0aec0;">
                    © 2024 Sajilowork. All rights reserved.<br>
                    This is an automated test email. Do not reply to this message.
                </p>
            </div>
        </div>
    </body>
    </html>
    """.replace("{current_time}", timezone.now().strftime("%Y-%m-%d %H:%M:%S %Z"))
    
    text_content = """
    NEW JOB POSTED - Sajilowork
    
    Job Title: Web Developer Needed for E-commerce Platform
    Location: Remote (Nepal)
    Budget: NPR 50,000 - 80,000
    Posted: 2 hours ago
    Deadline: 7 days from now
    
    Description:
    Looking for an experienced web developer to build a modern e-commerce platform.
    The project includes frontend (React/Next.js), backend (Django/Python),
    payment integration (eSewa/Khalti), and admin dashboard.
    
    Required Skills:
    - React.js & Next.js
    - Python & Django
    - PostgreSQL
    - Payment Gateway Integration
    - RESTful API Development
    
    Client: Verified Business Account
    Client Rating: 4.8/5.0 (23 reviews)
    
    Make an offer: http://localhost:3000/task/web-developer-ecommerce
    
    ---
    This is a TEST EMAIL from the Enterprise Email Management System
    Email sent at: {current_time}
    
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
