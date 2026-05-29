# Generated manually — default marketplace fee rules (editable in Django Admin).

from decimal import Decimal

from django.db import migrations


def seed_fee_rules(apps, schema_editor):
    FeeRule = apps.get_model('fees', 'FeeRule')

    if FeeRule.objects.exists():
        return

    # Migrate commission from legacy PlatformFeeSettings if present
    commission_percent = Decimal('10.00')
    try:
        PlatformFeeSettings = apps.get_model('payments', 'PlatformFeeSettings')
        legacy = PlatformFeeSettings.objects.filter(pk=1).first()
        if legacy and legacy.is_enabled:
            commission_percent = legacy.tasker_commission_percent
    except LookupError:
        pass

    defaults = [
        {
            'name': 'Default tasker commission',
            'fee_type': 'COMMISSION',
            'value_type': 'PERCENTAGE',
            'value': commission_percent,
            'priority': 100,
            'admin_notes': 'Deducted from worker payout on task completion.',
        },
        {
            'name': 'Default escrow / service fee',
            'fee_type': 'ESCROW',
            'value_type': 'PERCENTAGE',
            'value': Decimal('2.00'),
            'priority': 100,
            'admin_notes': 'Added to customer total when funding escrow.',
        },
        {
            'name': 'Default tax',
            'fee_type': 'TAX',
            'value_type': 'PERCENTAGE',
            'value': Decimal('1.00'),
            'priority': 100,
            'admin_notes': 'Tax component on customer total.',
        },
        {
            'name': 'Cancellation before accept',
            'fee_type': 'CANCELLATION',
            'value_type': 'PERCENTAGE',
            'value': Decimal('0.00'),
            'priority': 110,
            'cancellation_stage': 'BEFORE_ACCEPT',
        },
        {
            'name': 'Cancellation after accept',
            'fee_type': 'CANCELLATION',
            'value_type': 'PERCENTAGE',
            'value': Decimal('2.00'),
            'priority': 100,
            'cancellation_stage': 'AFTER_ACCEPT',
        },
        {
            'name': 'Cancellation in progress',
            'fee_type': 'CANCELLATION',
            'value_type': 'PERCENTAGE',
            'value': Decimal('5.00'),
            'priority': 100,
            'cancellation_stage': 'IN_PROGRESS',
            'admin_notes': 'Partial compensation / platform fee on late cancellation.',
        },
        {
            'name': 'Withdrawal — all methods (default)',
            'fee_type': 'WITHDRAWAL',
            'value_type': 'PERCENTAGE',
            'value': Decimal('1.00'),
            'priority': 50,
            'withdrawal_method': '',
            'admin_notes': 'Fallback when no method-specific rule matches.',
        },
        {
            'name': 'Withdrawal — eSewa',
            'fee_type': 'WITHDRAWAL',
            'value_type': 'PERCENTAGE',
            'value': Decimal('1.00'),
            'priority': 100,
            'withdrawal_method': 'esewa',
        },
        {
            'name': 'Withdrawal — Khalti',
            'fee_type': 'WITHDRAWAL',
            'value_type': 'PERCENTAGE',
            'value': Decimal('1.00'),
            'priority': 100,
            'withdrawal_method': 'khalti',
        },
        {
            'name': 'Withdrawal — bank transfer',
            'fee_type': 'WITHDRAWAL',
            'value_type': 'FIXED',
            'value': Decimal('25.00'),
            'priority': 100,
            'withdrawal_method': 'bank_transfer',
            'min_fee': Decimal('25.00'),
            'max_fee': Decimal('25.00'),
        },
    ]

    for row in defaults:
        FeeRule.objects.create(is_active=True, currency='NPR', **row)


def unseed_fee_rules(apps, schema_editor):
    FeeRule = apps.get_model('fees', 'FeeRule')
    FeeRule.objects.filter(
        name__in=[
            'Default tasker commission',
            'Default escrow / service fee',
            'Default tax',
            'Cancellation before accept',
            'Cancellation after accept',
            'Cancellation in progress',
            'Withdrawal — all methods (default)',
            'Withdrawal — eSewa',
            'Withdrawal — Khalti',
            'Withdrawal — bank transfer',
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('fees', '0001_initial_fee_engine'),
        ('payments', '0005_platform_fee_settings'),
    ]

    operations = [
        migrations.RunPython(seed_fee_rules, unseed_fee_rules),
    ]
