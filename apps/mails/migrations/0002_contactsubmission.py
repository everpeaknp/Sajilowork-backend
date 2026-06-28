# Generated manually for ContactSubmission model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('mails', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContactSubmission',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Contact name', max_length=255)),
                ('email', models.EmailField(help_text='Contact email', max_length=254)),
                ('message', models.TextField(help_text='Contact message')),
                ('status', models.CharField(
                    choices=[
                        ('new', 'New'),
                        ('read', 'Read'),
                        ('replied', 'Replied'),
                        ('archived', 'Archived')
                    ],
                    default='new',
                    help_text='Submission status',
                    max_length=20
                )),
                ('ip_address', models.GenericIPAddressField(blank=True, help_text='Sender IP address', null=True)),
                ('user_agent', models.CharField(blank=True, help_text='Browser user agent', max_length=500)),
                ('admin_notes', models.TextField(blank=True, help_text='Admin notes/response')),
                ('responded_at', models.DateTimeField(blank=True, help_text='When admin responded', null=True)),
                ('responded_by', models.ForeignKey(
                    blank=True,
                    help_text='Admin who responded',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='contact_responses',
                    to=settings.AUTH_USER_MODEL
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Contact Submission',
                'verbose_name_plural': 'Contact Submissions',
                'db_table': 'contact_submissions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='contactsubmission',
            index=models.Index(fields=['status', '-created_at'], name='mails_conta_status_idx'),
        ),
        migrations.AddIndex(
            model_name='contactsubmission',
            index=models.Index(fields=['email'], name='mails_conta_email_idx'),
        ),
        migrations.AddIndex(
            model_name='contactsubmission',
            index=models.Index(fields=['-created_at'], name='mails_conta_created_idx'),
        ),
    ]
