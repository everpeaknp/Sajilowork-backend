"""Restore available_balance for withdrawals that reserved funds while still pending."""

from decimal import Decimal

from django.db import migrations


def restore_pending_withdrawal_reservations(apps, schema_editor):
    WithdrawalRequest = apps.get_model('wallets', 'WithdrawalRequest')
    Wallet = apps.get_model('wallets', 'Wallet')
    WalletTransaction = apps.get_model('wallets', 'WalletTransaction')

    pending_qs = WithdrawalRequest.objects.filter(
        status__in=['pending', 'approved', 'processing'],
    )
    for withdrawal in pending_qs.iterator():
        meta = withdrawal.metadata or {}
        if not meta.get('funds_reserved'):
            continue

        wallet = Wallet.objects.select_for_update().get(pk=withdrawal.wallet_id)
        wallet.available_balance += Decimal(str(withdrawal.amount))
        wallet.save(update_fields=['available_balance', 'updated_at'])

        withdrawal_id = str(withdrawal.id)
        WalletTransaction.objects.filter(
            wallet_id=wallet.pk,
            transaction_type='debit',
            status='pending',
            metadata__withdrawal_id=withdrawal_id,
        ).update(status='cancelled')

        meta = dict(meta)
        meta['funds_reserved'] = False
        meta['reservation_released_by_migration'] = True
        withdrawal.metadata = meta
        withdrawal.save(update_fields=['metadata', 'updated_at'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('wallets', '0003_remove_stripe_paypal'),
    ]

    operations = [
        migrations.RunPython(restore_pending_withdrawal_reservations, noop_reverse),
    ]
