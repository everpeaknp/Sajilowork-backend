# Generated manually — listing-kind fee rules for tasks, projects, and services.

from decimal import Decimal

from django.db import migrations, models


LISTING_FEE_SPECS = (
    # (listing_kind, commission %, customer service fee %, tax %)
    ('task', Decimal('10.00'), Decimal('5.00'), Decimal('0.00')),
    ('project', Decimal('12.00'), Decimal('5.00'), Decimal('0.00')),
    ('service', Decimal('15.00'), Decimal('3.00'), Decimal('0.00')),
)


def seed_listing_kind_fee_rules(apps, schema_editor):
    FeeRule = apps.get_model('fees', 'FeeRule')

    for kind, commission, service_fee, tax in LISTING_FEE_SPECS:
        label = kind.capitalize()

        if FeeRule.objects.filter(
            listing_kind=kind,
            fee_type='TASKER_COMMISSION',
            name=f'{label} — tasker commission',
        ).exists():
            continue

        FeeRule.objects.create(
            name=f'{label} — tasker commission',
            fee_type='TASKER_COMMISSION',
            applies_to='TASKER',
            listing_kind=kind,
            value_type='PERCENTAGE',
            value=commission,
            priority=120,
            is_active=True,
            currency='NPR',
        )
        FeeRule.objects.create(
            name=f'{label} — customer service fee',
            fee_type='CUSTOMER_SERVICE_FEE',
            applies_to='CUSTOMER',
            listing_kind=kind,
            value_type='PERCENTAGE',
            value=service_fee,
            priority=120,
            is_active=True,
            currency='NPR',
        )
        FeeRule.objects.create(
            name=f'{label} — tax',
            fee_type='TAX_FEE',
            applies_to='CUSTOMER',
            listing_kind=kind,
            value_type='PERCENTAGE',
            value=tax,
            priority=110,
            is_active=True,
            currency='NPR',
        )

        for stage, pct, priority in (
            ('BEFORE_ACCEPT', Decimal('0.00'), 130),
            ('AFTER_ACCEPT', Decimal('2.00'), 120),
            ('IN_PROGRESS', Decimal('5.00'), 120),
        ):
            FeeRule.objects.create(
                name=f'{label} — cancellation ({stage.replace("_", " ").lower()})',
                fee_type='CANCELLATION_FEE',
                applies_to='CUSTOMER',
                listing_kind=kind,
                value_type='PERCENTAGE',
                value=pct,
                priority=priority,
                cancellation_stage=stage,
                is_active=True,
                currency='NPR',
            )


def unseed_listing_kind_fee_rules(apps, schema_editor):
    FeeRule = apps.get_model('fees', 'FeeRule')
    kinds = [kind for kind, *_ in LISTING_FEE_SPECS]
    FeeRule.objects.filter(listing_kind__in=kinds, priority__gte=110).delete()


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('fees', '0004_fix_default_service_fee'),
    ]

    operations = [
        migrations.AddField(
            model_name='feerule',
            name='listing_kind',
            field=models.CharField(
                blank=True,
                choices=[
                    ('task', 'Task (marketplace)'),
                    ('project', 'Project'),
                    ('service', 'Service'),
                    ('job', 'Job'),
                ],
                db_index=True,
                default='',
                help_text='Apply only to this listing type (task, project, service, job). Blank = all types.',
                max_length=16,
            ),
        ),
        migrations.AddIndex(
            model_name='feerule',
            index=models.Index(
                fields=['listing_kind', 'fee_type', 'is_active'],
                name='fee_rules_listing_fee_idx',
            ),
        ),
        migrations.RunPython(seed_listing_kind_fee_rules, unseed_listing_kind_fee_rules),
    ]
