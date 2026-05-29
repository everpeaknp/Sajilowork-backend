"""Marketplace rule engine event catalog."""

from django.db import models


class RuleEvent(models.TextChoices):
    # Task lifecycle
    TASK_CREATED = 'task.created', 'Task created'
    TASK_PUBLISHED = 'task.published', 'Task published'
    TASK_ASSIGNED = 'task.assigned', 'Task assigned'
    TASK_FUNDED = 'task.funded', 'Task funded'
    TASK_STARTED = 'task.started', 'Task in progress'
    TASK_COMPLETED = 'task.completed', 'Task completed'
    TASK_CANCELLED = 'task.cancelled', 'Task cancelled'
    TASK_EXPIRED = 'task.expired', 'Task expired'
    TASK_DISPUTED = 'task.disputed', 'Task disputed'

    # Offers / bids
    BID_CREATED = 'bid.created', 'Bid created'
    BID_ACCEPTED = 'bid.accepted', 'Bid accepted'
    BID_REJECTED = 'bid.rejected', 'Bid rejected'
    BID_EXPIRED = 'bid.expired', 'Bid expired'

    # Escrow / payments
    ESCROW_CREATED = 'escrow.created', 'Escrow created'
    ESCROW_FUNDED = 'escrow.funded', 'Escrow funded'
    ESCROW_RELEASED = 'escrow.released', 'Escrow released'
    ESCROW_FROZEN = 'escrow.frozen', 'Escrow frozen'
    ESCROW_AUTO_RELEASE = 'escrow.auto_release', 'Escrow auto-release'
    PAYMENT_FAILED = 'payment.failed', 'Payment failed'
    REFUND_ISSUED = 'refund.issued', 'Refund issued'

    # Reviews
    REVIEW_SUBMITTED = 'review.submitted', 'Review submitted'

    # Wallet / withdrawal
    WITHDRAWAL_REQUESTED = 'withdrawal.requested', 'Withdrawal requested'
    WITHDRAWAL_APPROVED = 'withdrawal.approved', 'Withdrawal approved'

    # Trust / verification / fraud
    TRUST_SCORE_UPDATED = 'trust.updated', 'Trust score updated'
    USER_VERIFIED = 'user.verified', 'User verified'
    FRAUD_SIGNAL = 'fraud.signal', 'Fraud signal detected'

    # Messaging / bypass
    MESSAGE_SENT = 'message.sent', 'Message sent'
    PAYMENT_BYPASS_DETECTED = 'payment_bypass.detected', 'Payment bypass detected'

    # Notifications (policy-driven routing)
    NOTIFY_DISPATCH = 'notify.dispatch', 'Notification dispatch'
