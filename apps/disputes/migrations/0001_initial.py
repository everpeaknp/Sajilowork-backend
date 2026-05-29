# Generated manually for disputes app

import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tasks', '0008_task_cancellation_tracking'),
    ]

    operations = [
        migrations.CreateModel(
            name='Dispute',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('dispute_type', models.CharField(choices=[('quality', 'Quality Issue'), ('incomplete', 'Incomplete Work'), ('deadline', 'Deadline Missed'), ('payment', 'Payment Issue'), ('communication', 'Communication Problem'), ('other', 'Other')], max_length=30)),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField()),
                ('status', models.CharField(choices=[('open', 'Open'), ('under_review', 'Under Review'), ('resolved', 'Resolved'), ('closed', 'Closed'), ('escalated', 'Escalated')], default='open', max_length=20)),
                ('resolution', models.CharField(blank=True, choices=[('refund_full', 'Full Refund'), ('refund_partial', 'Partial Refund'), ('release_payment', 'Release Payment'), ('revision_required', 'Revision Required'), ('no_action', 'No Action')], max_length=30, null=True)),
                ('resolution_notes', models.TextField(blank=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('against', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='disputes_against', to=settings.AUTH_USER_MODEL)),
                ('assigned_to', models.ForeignKey(blank=True, limit_choices_to={'role': 'admin'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_disputes', to=settings.AUTH_USER_MODEL)),
                ('raised_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='disputes_raised', to=settings.AUTH_USER_MODEL)),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='disputes_resolved', to=settings.AUTH_USER_MODEL)),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='disputes', to='tasks.task')),
            ],
            options={
                'db_table': 'disputes',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='DisputeEvidence',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('evidence_type', models.CharField(choices=[('image', 'Image'), ('document', 'Document'), ('video', 'Video'), ('message', 'Message Screenshot'), ('other', 'Other')], max_length=20)),
                ('file_url', models.URLField()),
                ('file_name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('dispute', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='evidence', to='disputes.dispute')),
                ('submitted_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'dispute_evidence',
                'ordering': ['-uploaded_at'],
            },
        ),
        migrations.CreateModel(
            name='DisputeMessage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('message', models.TextField()),
                ('is_admin_message', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('dispute', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='disputes.dispute')),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'dispute_messages',
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='dispute',
            index=models.Index(fields=['status'], name='disputes_status_idx'),
        ),
        migrations.AddIndex(
            model_name='dispute',
            index=models.Index(fields=['task'], name='disputes_task_id_idx'),
        ),
        migrations.AddIndex(
            model_name='dispute',
            index=models.Index(fields=['raised_by'], name='disputes_raised_by_idx'),
        ),
    ]
