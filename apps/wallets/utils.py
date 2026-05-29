"""Wallet transaction classification helpers."""


def is_wallet_recharge_from_meta(metadata=None, description='') -> bool:
    """True when metadata/description indicate a user top-up."""
    meta = metadata or {}
    if meta.get('channel') == 'admin_manual':
        return True
    if meta.get('gateway') == 'esewa':
        return True
    if meta.get('esewa_transaction_uuid'):
        return True
    desc = (description or '').lower()
    return 'wallet recharge' in desc or 'manual wallet recharge' in desc


def is_wallet_recharge_transaction(tx) -> bool:
    """True when the transaction is a user top-up (eSewa, admin manual, etc.)."""
    return is_wallet_recharge_from_meta(tx.metadata, tx.description)


def is_task_earning_transaction(tx) -> bool:
    """True when the transaction credits task earnings (not a recharge)."""
    if tx.transaction_type not in ('credit', 'bonus'):
        return False
    if tx.status != 'completed':
        return False
    if is_wallet_recharge_transaction(tx):
        return False
    meta = tx.metadata or {}
    if meta.get('settlement_type') == 'escrow_receive':
        return True
    if meta.get('payment_id'):
        return True
    desc = (tx.description or '').lower()
    return 'payment received' in desc


def compute_wallet_breakdown(wallet):
    """Sum completed recharge credits vs task earnings from transaction history."""
    from decimal import Decimal

    from .models import WalletTransaction

    recharge = Decimal('0')
    earned = Decimal('0')
    txs = WalletTransaction.objects.filter(wallet=wallet, status='completed').only(
        'transaction_type', 'amount', 'metadata', 'description', 'status'
    )
    for tx in txs:
        if tx.transaction_type in ('credit', 'bonus') and is_wallet_recharge_transaction(tx):
            recharge += tx.amount
        elif is_task_earning_transaction(tx):
            earned += tx.amount
    return recharge, earned
