# Generated manually for bidirectional review system

import uuid
from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


def populate_reviewer_type(apps, schema_editor):
    Review = apps.get_model('reviews', 'Review')
    for review in Review.objects.all():
        if review.review_type == 'owner_to_provider':
            review.reviewer_type = 'customer'
        else:
            review.reviewer_type = 'tasker'
        review.save(update_fields=['reviewer_type'])


def populate_invitation_reviewer_type(apps, schema_editor):
    ReviewInvitation = apps.get_model('reviews', 'ReviewInvitation')
    for inv in ReviewInvitation.objects.all():
        if inv.review_type == 'owner_to_provider':
            inv.reviewer_type = 'customer'
        else:
            inv.reviewer_type = 'tasker'
        inv.save(update_fields=['reviewer_type'])


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('reviews', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReviewPlatformSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('visibility_mode', models.CharField(
                    choices=[
                        ('immediate', 'Show immediately'),
                        ('both_submitted', 'Show after both parties submit'),
                        ('delay_24h', 'Show after 24 hours'),
                    ],
                    default='immediate',
                    max_length=30,
                )),
                ('edit_window_minutes', models.PositiveIntegerField(
                    default=0,
                    help_text='0 = immutable after submit; 15 = allow edits within 15 minutes.',
                )),
                ('rate_limit_per_hour', models.PositiveIntegerField(default=10)),
                ('review_window_days', models.PositiveIntegerField(
                    default=14,
                    help_text='Days after escrow release that reviews remain open.',
                )),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Review platform settings',
                'verbose_name_plural': 'Review platform settings',
                'db_table': 'review_platform_settings',
            },
        ),
        migrations.AddField(
            model_name='review',
            name='reviewer_type',
            field=models.CharField(
                choices=[('customer', 'Customer'), ('tasker', 'Tasker')],
                default='customer',
                max_length=20,
            ),
            preserve_default=False,
        ),
        migrations.RunPython(populate_reviewer_type, migrations.RunPython.noop),
        migrations.AddField(
            model_name='review',
            name='tags',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='review',
            name='visible_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='review',
            name='is_finalized',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='review',
            name='finalized_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='review',
            name='submitter_ip',
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='review',
            name='submitter_user_agent',
            field=models.CharField(blank=True, max_length=512),
        ),
        migrations.AlterField(
            model_name='review',
            name='is_public',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='review',
            name='overall_rating',
            field=models.IntegerField(
                help_text='Rating 1–5',
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(5),
                ],
            ),
        ),
        migrations.AlterField(
            model_name='review',
            name='review_text',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='reviewinvitation',
            name='reviewer_type',
            field=models.CharField(
                choices=[('customer', 'Customer'), ('tasker', 'Tasker')],
                default='customer',
                max_length=20,
            ),
            preserve_default=False,
        ),
        migrations.RunPython(populate_invitation_reviewer_type, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='review',
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name='review',
            constraint=models.UniqueConstraint(
                fields=('task', 'reviewer'),
                name='unique_review_per_task_per_reviewer',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='reviewinvitation',
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name='reviewinvitation',
            constraint=models.UniqueConstraint(
                fields=('task', 'invitee'),
                name='unique_review_invitation_per_task_per_user',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='reviewhelpful',
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name='reviewhelpful',
            constraint=models.UniqueConstraint(
                fields=('review', 'user'),
                name='unique_helpful_vote_per_user',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='reviewreport',
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name='reviewreport',
            constraint=models.UniqueConstraint(
                fields=('review', 'reporter'),
                name='unique_review_report_per_user',
            ),
        ),
        migrations.RemoveIndex(
            model_name='review',
            name='reviews_task_id_0cf4ef_idx',
        ),
        migrations.AddIndex(
            model_name='review',
            index=models.Index(fields=['task', 'reviewer_type'], name='reviews_task_id_revtype_idx'),
        ),
    ]
