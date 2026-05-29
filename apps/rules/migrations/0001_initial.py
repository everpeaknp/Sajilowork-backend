import uuid

import django.core.validators
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_auto_suspend_rule(apps, schema_editor):
    PlatformRule = apps.get_model('rules', 'PlatformRule')
    PlatformRule.objects.get_or_create(
        rule_type='AUTO_SUSPEND_EXCESS_CANCELLATIONS',
        defaults={
            'name': 'Auto-suspend after 5+ cancellations',
            'description': (
                'Suspend customer or tasker accounts for 24 hours when they cancel '
                'more than 5 tasks (all-time count).'
            ),
            'is_active': True,
            'max_cancellations': 5,
            'suspension_hours': 24,
            'counting_window_days': None,
            'applies_to_customers': True,
            'applies_to_taskers': True,
        },
    )


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformRule',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    'rule_type',
                    models.CharField(
                        choices=[
                            (
                                'AUTO_SUSPEND_EXCESS_CANCELLATIONS',
                                'Auto-suspend after excess task cancellations',
                            ),
                        ],
                        db_index=True,
                        max_length=64,
                        unique=True,
                    ),
                ),
                ('name', models.CharField(max_length=120)),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                (
                    'max_cancellations',
                    models.PositiveIntegerField(
                        default=5,
                        help_text='Suspend when a user cancels more than this many tasks (in the counting window).',
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                (
                    'suspension_hours',
                    models.PositiveIntegerField(
                        default=24,
                        help_text='How long to suspend the account (hours).',
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                (
                    'counting_window_days',
                    models.PositiveIntegerField(
                        blank=True,
                        help_text='Only count cancellations in the last N days. Leave blank for all-time.',
                        null=True,
                    ),
                ),
                (
                    'applies_to_customers',
                    models.BooleanField(
                        default=True,
                        help_text='Apply to customers (posters) who cancel tasks.',
                    ),
                ),
                (
                    'applies_to_taskers',
                    models.BooleanField(
                        default=True,
                        help_text='Apply to taskers who cancel tasks.',
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Platform rule',
                'verbose_name_plural': 'Platform rules',
                'db_table': 'platform_rules',
                'ordering': ['rule_type'],
            },
        ),
        migrations.CreateModel(
            name='AccountSuspensionLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('cancellation_count', models.PositiveIntegerField()),
                ('suspended_until', models.DateTimeField()),
                ('reason', models.TextField()),
                ('lifted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'rule',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='suspension_logs',
                        to='rules.platformrule',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='suspension_logs',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'account_suspension_logs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.RunPython(seed_auto_suspend_rule, migrations.RunPython.noop),
    ]
