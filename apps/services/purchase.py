"""Direct service purchase — wallet escrow from buyer, release to seller on completion."""
from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.bids.models import Bid
from apps.bids.workflow import BidWorkflowService
from apps.payments.services import EscrowService
from apps.services.meta import parse_service_meta
from apps.tasks.listing import LISTING_KIND_SERVICE, with_listing_kind
from apps.tasks.models import Task
from apps.wallets.models import Wallet


def _parse_price_from_text(text: str) -> Decimal | None:
    digits = re.sub(r'[^\d.]', '', text or '')
    if not digits:
        return None
    try:
        value = Decimal(digits)
    except Exception:
        return None
    return value if value > 0 else None


def _row_value_for_tier(rows: list[dict], matcher: re.Pattern, tier_id: str) -> str:
    for row in rows:
        label = str(row.get('label') or '')
        row_id = str(row.get('id') or '')
        if matcher.search(label) or matcher.search(row_id):
            values = row.get('values') or {}
            raw = values.get(tier_id)
            return '' if raw is None else str(raw)
    return ''


def _tier_package_id(tier_id: str, index: int) -> str:
    if tier_id in ('basic', 'standard', 'premium'):
        return tier_id
    if index == 0:
        return 'basic'
    if index == 1:
        return 'standard'
    return 'premium'


def resolve_service_packages(service: Task) -> list[dict[str, Any]]:
    """Resolve purchasable packages for a service listing (mirrors frontend logic)."""
    meta = parse_service_meta(service) or {}
    packages_config = meta.get('packages') or {}
    tiers = packages_config.get('tiers') or []
    rows = packages_config.get('rows') or []
    base_price = Decimal(str(service.budget_amount or 0))

    if tiers and rows:
        total_re = re.compile(r'total', re.I)
        result = []
        for index, tier in enumerate(tiers):
            tier_id = str(tier.get('id') or f'tier-{index}')
            fallback = (
                base_price
                if index == 0
                else (base_price * Decimal('1.6') if index == 1 else base_price * Decimal('2.4'))
            )
            total_text = _row_value_for_tier(rows, total_re, tier_id)
            price = _parse_price_from_text(total_text) or fallback.quantize(Decimal('0.01'))
            result.append(
                {
                    'id': _tier_package_id(tier_id, index),
                    'name': str(tier.get('name') or tier_id.title()),
                    'description': str(tier.get('description') or ''),
                    'price': price,
                }
            )
        return result

    if base_price <= 0:
        return []

    return [
        {
            'id': 'basic',
            'name': 'Basic',
            'description': '',
            'price': base_price,
        }
    ]


def get_package_for_service(service: Task, package_id: str) -> dict[str, Any]:
    packages = resolve_service_packages(service)
    if not packages:
        raise ValidationError('This service has no purchasable packages.')

    normalized = (package_id or 'basic').strip().lower()
    for pkg in packages:
        if str(pkg['id']).lower() == normalized:
            return pkg

    raise ValidationError(f'Unknown package: {package_id}')


class ServicePurchaseService:
    @staticmethod
    def preview_purchase(service: Task, buyer, package_id: str) -> dict:
        if service.owner_id == buyer.id:
            raise ValidationError('You cannot purchase your own service.')

        if service.status not in ('open',):
            raise ValidationError('This service is not available for purchase.')

        package = get_package_for_service(service, package_id)
        amount = Decimal(str(package['price']))
        hold_amount = EscrowService.get_escrow_hold_amount_for_amount(
            amount,
            category_id=getattr(service, 'category_id', None),
            task=service,
        )

        wallet, _ = Wallet.objects.get_or_create(user=buyer)
        currency = service.budget_currency or wallet.currency or 'NPR'

        return {
            'package': package,
            'amount': amount,
            'hold_amount': hold_amount,
            'currency': currency,
            'wallet_available': wallet.available_balance,
            'wallet_sufficient': wallet.available_balance >= hold_amount,
            'seller_id': str(service.owner_id),
            'seller_name': service.owner.get_full_name() or service.owner.email,
        }

    @staticmethod
    @transaction.atomic
    def purchase(service: Task, buyer, package_id: str, note: str = '') -> dict:
        preview = ServicePurchaseService.preview_purchase(service, buyer, package_id)
        package = preview['package']
        amount = Decimal(str(package['price']))
        hold_amount = Decimal(str(preview['hold_amount']))

        wallet, _ = Wallet.objects.get_or_create(user=buyer)
        if wallet.is_frozen:
            raise ValidationError(
                'Your wallet is frozen. Please contact support before purchasing.'
            )
        if wallet.available_balance < hold_amount:
            currency = preview['currency']
            raise ValidationError(
                f'Insufficient wallet balance. You need {hold_amount} {currency} available '
                f'to purchase this service (your available balance is '
                f'{wallet.available_balance} {currency}). Add funds to your wallet and try again.'
            )

        seller = service.owner
        package_name = package['name']
        order_title = f'{service.title} — {package_name}'

        order_meta = {
            'service_order': True,
            'parent_service_id': str(service.id),
            'parent_service_slug': service.slug,
            'package_id': package['id'],
            'package_name': package_name,
            'buyer_id': str(buyer.id),
        }

        order_task = Task.objects.create(
            title=order_title,
            description=note.strip() or service.description,
            owner=buyer,
            category=service.category,
            budget_amount=amount,
            budget_currency=service.budget_currency,
            work_type=service.work_type,
            location_type=service.location_type,
            city=service.city,
            state=service.state,
            country=service.country,
            address=service.address,
            postal_code=service.postal_code,
            status='open',
            is_public=False,
            allow_bids=True,
            tags=with_listing_kind(list(service.tags or []), LISTING_KIND_SERVICE),
            requirements=[
                {
                    'type': 'dashboard_meta',
                    'value': json.dumps(order_meta, ensure_ascii=False),
                }
            ],
        )

        bid = Bid.objects.create(
            task=order_task,
            tasker=seller,
            amount=amount,
            currency=service.budget_currency or 'NPR',
            proposal=note.strip() or f'Service order: {package_name}',
            estimated_duration=None,
            status='pending',
        )

        result = BidWorkflowService.accept_bid(str(bid.id), buyer)

        return {
            'order_task': result['task'],
            'bid': result['bid'],
            'payment': result.get('payment'),
            'conversation': result.get('conversation'),
            'package': package,
            'hold_amount': hold_amount,
            'parent_service_slug': service.slug,
        }
