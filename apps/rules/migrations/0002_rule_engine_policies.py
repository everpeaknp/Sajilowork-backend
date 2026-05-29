import uuid

import django.core.validators
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


DEFAULT_POLICIES = [
    ('ESCROW', 'require_payment_before_start', 'Require escrow before work starts', ['task.started'], {}),
    ('ESCROW', 'freeze_on_dispute', 'Freeze escrow when disputed', ['task.disputed'], {}),
    ('OFFER', 'no_self_bid', 'Tasker cannot bid on own task', ['bid.created'], {}),
    ('OFFER', 'no_duplicate_bid', 'Prevent duplicate offers', ['bid.created'], {}),
    ('OFFER', 'bid_daily_limit', 'Daily offer limit', ['bid.created'], {'max_bids_per_day': 50}),
    ('ASSIGNMENT', 'lock_task_on_accept', 'Lock task when offer accepted', ['bid.accepted'], {'require_escrow_funding': True}),
    ('REVIEW', 'only_after_release', 'Review only after payment release', ['review.submitted'], {}),
    ('REVIEW', 'one_review_per_task', 'One review per user per task', ['review.submitted'], {}),
    ('CANCELLATION', 'free_cancel_before_assignment', 'Free cancel before assignment', ['task.cancelled'], {}),
    ('CANCELLATION', 'fee_after_assignment', 'Fee after assignment cancel', ['task.cancelled'], {}),
    ('CANCELLATION', 'partial_compensation_in_progress', 'Partial tasker pay if in progress', ['task.cancelled'], {'compensation_percent': 25}),
    ('CANCELLATION', 'process_escrow_refund', 'Refund escrow on cancel', ['task.cancelled'], {}),
    ('CANCELLATION', 'apply_moderation_after_cancel', 'Check moderation after cancel', ['task.cancelled'], {}),
    ('DISPUTE', 'freeze_escrow_on_dispute', 'Freeze escrow on dispute', ['task.disputed'], {}),
    ('WALLET', 'no_negative_balance', 'No negative wallet balance', ['withdrawal.requested'], {}),
    ('WALLET', 'locked_cannot_withdraw', 'Locked funds not withdrawable', ['withdrawal.requested'], {'block_if_locked': True}),
    ('TRUST', 'min_trust_for_visibility', 'Minimum trust for search boost', ['trust.updated'], {'minimum_score': 3.0}),
    ('VERIFICATION', 'kyc_for_withdrawal', 'KYC required for withdrawal', ['withdrawal.requested'], {'require_id_verified': True}),
    ('FRAUD', 'velocity_check', 'Hourly action velocity limit', ['bid.created', 'task.created'], {'max_actions_per_hour': 50}),
    ('MESSAGING', 'block_contact_before_assignment', 'Block contact sharing pre-assignment', ['message.sent'], {'enabled': True, 'blocking': True}),
    ('AUTO_RELEASE', 'auto_release_after_inactivity', 'Auto-release escrow after inactivity', ['escrow.auto_release'], {'hours': 48, 'reminder_hours_before': 24}),
    ('REFUND', 'notify_on_refund', 'Notify parties on refund', ['refund.issued'], {}),
    ('PROMOTION', 'boosted_visibility', 'Boost featured tasks in search', ['task.published'], {'rank_boost': 15}),
    ('TASK_EXPIRY', 'expire_unassigned_open_tasks', 'Expire open tasks without assignment', ['task.expired'], {'days': 30}),
    ('TASK_EXPIRY', 'expire_unfunded_assigned', 'Expire assigned tasks without payment', ['task.expired'], {'days': 7}),
    ('PAYMENT_BYPASS', 'detect_external_payment', 'Detect off-platform payment requests', ['message.sent', 'payment_bypass.detected'], {}),
    ('WITHDRAWAL', 'daily_withdrawal_limit', 'Daily NPR withdrawal cap', ['withdrawal.requested'], {'daily_limit_npr': '100000'}),
    ('WITHDRAWAL', 'admin_approval_large_withdrawals', 'Admin approval for large withdrawals', ['withdrawal.requested'], {'admin_approval_above_npr': '50000'}),
    ('WITHDRAWAL', 'withdrawal_cooldown', 'Cooldown between withdrawals', ['withdrawal.requested'], {'cooldown_hours': 24}),
    ('MODERATION', 'block_if_suspended', 'Block actions when suspended', ['task.cancelled'], {}),
]


def seed_policies(apps, schema_editor):
    RulePolicy = apps.get_model('rules', 'RulePolicy')
    for category, slug, name, triggers, params in DEFAULT_POLICIES:
        RulePolicy.objects.get_or_create(
            category=category,
            slug=slug,
            defaults={
                'name': name,
                'description': name,
                'is_active': True,
                'priority': 100,
                'enforcement': 'BLOCK',
                'event_triggers': triggers,
                'conditions': {},
                'parameters': params,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tasks', '0008_task_cancellation_tracking'),
        ('rules', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RulePolicy',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('category', models.CharField(choices=[('ESCROW', 'Escrow'), ('OFFER', 'Offer / bidding'), ('ASSIGNMENT', 'Task assignment'), ('REVIEW', 'Reviews'), ('CANCELLATION', 'Cancellation'), ('DISPUTE', 'Dispute'), ('WALLET', 'Wallet'), ('TRUST', 'Trust & ranking'), ('VERIFICATION', 'Verification'), ('FRAUD', 'Fraud prevention'), ('MESSAGING', 'Messaging'), ('AUTO_RELEASE', 'Auto-release'), ('REFUND', 'Refund'), ('PROMOTION', 'Promotion'), ('TASK_EXPIRY', 'Task expiry'), ('PAYMENT_BYPASS', 'Payment bypass prevention'), ('WITHDRAWAL', 'Withdrawal'), ('NOTIFICATION', 'Notification'), ('MODERATION', 'Account moderation')], db_index=True, max_length=32)),
                ('slug', models.SlugField(max_length=80)),
                ('name', models.CharField(max_length=160)),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('priority', models.PositiveIntegerField(default=100)),
                ('enforcement', models.CharField(choices=[('BLOCK', 'Block action'), ('WARN', 'Warn only'), ('AUTO', 'Automatic side effect'), ('NOTIFY', 'Send notification')], default='BLOCK', max_length=10)),
                ('event_triggers', models.JSONField(blank=True, default=list)),
                ('conditions', models.JSONField(blank=True, default=dict)),
                ('parameters', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Rule policy',
                'verbose_name_plural': 'Rule policies',
                'db_table': 'rule_policies',
                'ordering': ['category', '-priority', 'slug'],
            },
        ),
        migrations.AddConstraint(
            model_name='rulepolicy',
            constraint=models.UniqueConstraint(fields=('category', 'slug'), name='uniq_rule_policy_category_slug'),
        ),
        migrations.AddIndex(
            model_name='rulepolicy',
            index=models.Index(fields=['category', 'is_active'], name='rule_polic_categor_8e0b0d_idx'),
        ),
        migrations.CreateModel(
            name='RuleEvaluationLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('event', models.CharField(db_index=True, max_length=64)),
                ('allowed', models.BooleanField()),
                ('policies_evaluated', models.PositiveIntegerField(default=0)),
                ('violations', models.JSONField(blank=True, default=list)),
                ('actions', models.JSONField(blank=True, default=list)),
                ('context_snapshot', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rule_evaluations', to=settings.AUTH_USER_MODEL)),
                ('task', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rule_evaluations', to='tasks.task')),
            ],
            options={
                'db_table': 'rule_evaluation_logs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='accountsuspensionlog',
            name='policy',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='suspension_logs', to='rules.rulepolicy'),
        ),
        migrations.RunPython(seed_policies, migrations.RunPython.noop),
    ]
