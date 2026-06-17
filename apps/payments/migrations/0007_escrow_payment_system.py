# Escrow payment system — lifecycle states, gateway transactions, audit

import uuid
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


def migrate_escrow_statuses(apps, schema_editor):
    Escrow = apps.get_model('payments', 'Escrow')
    mapping = {
        'pending': 'pending_payment',
        'held': 'funded',
        'released': 'released',
        'refunded': 'refunded',
        'disputed': 'disputed',
    }
    for escrow in Escrow.objects.select_related('payment', 'task', 'bid').all():
        new_status = mapping.get(escrow.status, 'funded')
        escrow.status = new_status
        if new_status == 'funded' and not escrow.locked_at:
            escrow.locked_at = getattr(escrow, 'held_at', None)
        if not escrow.payer_id and escrow.payment_id:
            escrow.payer_id = escrow.payment.payer_id
        if not escrow.payee_id:
            if escrow.payment_id and escrow.payment.payee_id:
                escrow.payee_id = escrow.payment.payee_id
            elif escrow.bid_id:
                escrow.payee_id = escrow.bid.tasker_id
        escrow.save()


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('payments', '0006_remove_stripe_paypal'),
        ('tasks', '0005_nepal_npr_budget_currency'),
        ('bids', '0004_nepal_npr_currency'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='escrow',
            name='payer',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='escrows_funded',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='escrow',
            name='payee',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='escrows_as_tasker',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='escrow',
            name='funding_method',
            field=models.CharField(default='wallet', max_length=20),
        ),
        migrations.AddField(
            model_name='escrow',
            name='idempotency_key',
            field=models.CharField(blank=True, db_index=True, max_length=128),
        ),
        migrations.AddField(
            model_name='escrow',
            name='locked_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='escrow',
            name='auto_release_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(migrate_escrow_statuses, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='escrow',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending_payment', 'Pending Payment'),
                    ('funded', 'Funded'),
                    ('in_progress', 'In Progress'),
                    ('submitted', 'Submitted'),
                    ('completed', 'Completed'),
                    ('released', 'Released'),
                    ('disputed', 'Disputed'),
                    ('refunded', 'Refunded'),
                    ('cancelled', 'Cancelled'),
                ],
                default='pending_payment',
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name='escrow',
            name='payment',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='escrow_account',
                to='payments.payment',
            ),
        ),
        migrations.AddConstraint(
            model_name='escrow',
            constraint=models.UniqueConstraint(fields=('task',), name='unique_escrow_per_task'),
        ),
        migrations.CreateModel(
            name='PaymentTransaction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('provider', models.CharField(max_length=20)),
                ('transaction_id', models.CharField(db_index=True, max_length=128)),
                ('idempotency_key', models.CharField(max_length=128, unique=True)),
                ('provider_reference', models.CharField(blank=True, max_length=255)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('currency', models.CharField(default='NPR', max_length=3)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('processing', 'Processing'),
                        ('success', 'Success'),
                        ('failed', 'Failed'),
                    ],
                    default='pending',
                    max_length=20,
                )),
                ('failure_reason', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('verified_at', models.DateTimeField(blank=True, null=True)),
                ('escrow', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='gateway_transactions',
                    to='payments.escrow',
                )),
                ('payment', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='gateway_transactions',
                    to='payments.payment',
                )),
                ('payer', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='payment_transactions',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'payment_transactions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='EscrowAuditLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('from_status', models.CharField(blank=True, max_length=30)),
                ('to_status', models.CharField(max_length=30)),
                ('note', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
                ('escrow', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='audit_logs',
                    to='payments.escrow',
                )),
            ],
            options={
                'db_table': 'escrow_audit_logs',
                'ordering': ['created_at'],
            },
        ),
    ]
