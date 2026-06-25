# Generated migration for mails app

import uuid
import django.core.validators
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailTemplate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Template name', max_length=255, unique=True)),
                ('slug', models.SlugField(help_text='Unique identifier', max_length=255, unique=True)),
                ('description', models.TextField(blank=True, help_text='Template description')),
                ('template_type', models.CharField(choices=[('transactional', 'Transactional'), ('notification', 'Notification'), ('marketing', 'Marketing'), ('system', 'System')], default='notification', help_text='Type of email template', max_length=50)),
                ('subject', models.CharField(help_text='Email subject line (supports variables)', max_length=255)),
                ('html_content', models.TextField(help_text='HTML email body (supports variables)')),
                ('text_content', models.TextField(blank=True, help_text='Plain text version')),
                ('send_email', models.BooleanField(default=True, help_text='Send as email')),
                ('send_in_app_notification', models.BooleanField(default=False, help_text='Send as in-app notification')),
                ('send_push_notification', models.BooleanField(default=False, help_text='Send as push notification')),
                ('is_active', models.BooleanField(default=True, help_text='Is template active')),
                ('language_code', models.CharField(default='en', help_text='Language code (e.g., en, es)', max_length=10)),
                ('template_group', models.CharField(blank=True, help_text='Group templates together', max_length=100, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_email_templates', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Email Template',
                'verbose_name_plural': 'Email Templates',
                'db_table': 'email_templates',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='EmailSetting',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('company_name', models.CharField(default='SajiloWork', max_length=255)),
                ('company_logo', models.ImageField(blank=True, null=True, upload_to='email/logos/')),
                ('support_email', models.EmailField(max_length=254, validators=[django.core.validators.EmailValidator()])),
                ('primary_color', models.CharField(default='#4F46E5', help_text='Hex color code', max_length=7)),
                ('secondary_color', models.CharField(default='#10B981', help_text='Hex color code', max_length=7)),
                ('footer_text', models.TextField(blank=True, default='© 2024 SajiloWork. All rights reserved.')),
                ('social_links', models.JSONField(blank=True, default=dict, help_text='Social media links')),
                ('unsubscribe_url', models.URLField(blank=True, help_text='Unsubscribe page URL')),
                ('email_enabled', models.BooleanField(default=True, help_text='Master toggle for all emails')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Email Setting',
                'verbose_name_plural': 'Email Settings',
                'db_table': 'email_settings',
            },
        ),
        migrations.CreateModel(
            name='SMTPConfiguration',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Configuration name', max_length=100)),
                ('host', models.CharField(help_text='SMTP server host', max_length=255)),
                ('port', models.IntegerField(default=587, help_text='SMTP server port')),
                ('username', models.CharField(help_text='SMTP username', max_length=255)),
                ('password', models.CharField(help_text='SMTP password (encrypted)', max_length=500)),
                ('encryption', models.CharField(choices=[('tls', 'TLS'), ('ssl', 'SSL'), ('none', 'None')], default='tls', help_text='Encryption method', max_length=10)),
                ('from_email', models.EmailField(help_text='From email address', max_length=254, validators=[django.core.validators.EmailValidator()])),
                ('from_name', models.CharField(help_text='From name', max_length=255)),
                ('provider', models.CharField(choices=[('gmail', 'Gmail'), ('outlook', 'Outlook'), ('sendgrid', 'SendGrid'), ('mailgun', 'Mailgun'), ('ses', 'Amazon SES'), ('custom', 'Custom SMTP')], default='custom', help_text='Email service provider', max_length=50)),
                ('is_active', models.BooleanField(default=False, help_text='Active SMTP configuration')),
                ('last_tested_at', models.DateTimeField(blank=True, help_text='Last connection test', null=True)),
                ('test_status', models.CharField(blank=True, help_text='Test result', max_length=20, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'SMTP Configuration',
                'verbose_name_plural': 'SMTP Configurations',
                'db_table': 'smtp_configurations',
            },
        ),
        migrations.CreateModel(
            name='NotificationRule',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('event_name', models.CharField(help_text='Unique event identifier (e.g., user.welcome)', max_length=100, unique=True)),
                ('event_category', models.CharField(choices=[('account', 'Account'), ('jobs', 'Jobs'), ('projects', 'Projects'), ('tasks', 'Tasks'), ('services', 'Services'), ('messages', 'Messages'), ('payments', 'Payments'), ('marketing', 'Marketing')], help_text='Event category', max_length=50)),
                ('display_name', models.CharField(help_text='Human-readable name', max_length=255)),
                ('description', models.TextField(blank=True, help_text='Event description')),
                ('email_enabled', models.BooleanField(default=True, help_text='Send email notification')),
                ('push_enabled', models.BooleanField(default=True, help_text='Send push notification')),
                ('inapp_enabled', models.BooleanField(default=True, help_text='Send in-app notification')),
                ('sms_enabled', models.BooleanField(default=False, help_text='Send SMS notification')),
                ('user_notification', models.BooleanField(default=True, help_text='Send to user')),
                ('admin_notification', models.BooleanField(default=False, help_text='Send to admin')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('email_template', models.ForeignKey(blank=True, help_text='Email template to use', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notification_rules', to='mails.emailtemplate')),
            ],
            options={
                'verbose_name': 'Notification Rule',
                'verbose_name_plural': 'Notification Rules',
                'db_table': 'notification_rules',
                'ordering': ['event_category', 'event_name'],
            },
        ),
        migrations.CreateModel(
            name='EmailLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('recipient_email', models.EmailField(max_length=254, validators=[django.core.validators.EmailValidator()])),
                ('subject', models.CharField(max_length=500)),
                ('html_content', models.TextField()),
                ('text_content', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('sent', 'Sent'), ('delivered', 'Delivered'), ('opened', 'Opened'), ('clicked', 'Clicked'), ('bounced', 'Bounced'), ('failed', 'Failed')], default='pending', help_text='Email delivery status', max_length=20)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('opened_at', models.DateTimeField(blank=True, null=True)),
                ('clicked_at', models.DateTimeField(blank=True, null=True)),
                ('bounced_at', models.DateTimeField(blank=True, null=True)),
                ('failed_at', models.DateTimeField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True)),
                ('retry_count', models.IntegerField(default=0, help_text='Number of retry attempts')),
                ('external_id', models.CharField(blank=True, help_text='Provider message ID', max_length=255)),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional data')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('recipient_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='received_emails', to=settings.AUTH_USER_MODEL)),
                ('smtp_config_used', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='email_logs', to='mails.smtpconfiguration')),
                ('template_used', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='email_logs', to='mails.emailtemplate')),
            ],
            options={
                'verbose_name': 'Email Log',
                'verbose_name_plural': 'Email Logs',
                'db_table': 'email_logs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='emailtemplate',
            index=models.Index(fields=['slug'], name='email_templ_slug_idx'),
        ),
        migrations.AddIndex(
            model_name='emailtemplate',
            index=models.Index(fields=['template_type', 'is_active'], name='email_templ_type_active_idx'),
        ),
        migrations.AddIndex(
            model_name='emailtemplate',
            index=models.Index(fields=['language_code'], name='email_templ_lang_idx'),
        ),
        migrations.AddIndex(
            model_name='notificationrule',
            index=models.Index(fields=['event_name'], name='notif_rule_event_idx'),
        ),
        migrations.AddIndex(
            model_name='notificationrule',
            index=models.Index(fields=['event_category'], name='notif_rule_category_idx'),
        ),
        migrations.AddIndex(
            model_name='emaillog',
            index=models.Index(fields=['recipient_email', '-created_at'], name='email_log_recipient_idx'),
        ),
        migrations.AddIndex(
            model_name='emaillog',
            index=models.Index(fields=['status', '-created_at'], name='email_log_status_idx'),
        ),
        migrations.AddIndex(
            model_name='emaillog',
            index=models.Index(fields=['-sent_at'], name='email_log_sent_idx'),
        ),
        migrations.AddIndex(
            model_name='emaillog',
            index=models.Index(fields=['external_id'], name='email_log_external_idx'),
        ),
    ]
