"""Escrow lifecycle states and transitions."""

# Escrow account states (Airtasker-style)
PENDING_PAYMENT = 'pending_payment'
FUNDED = 'funded'
IN_PROGRESS = 'in_progress'
SUBMITTED = 'submitted'
COMPLETED = 'completed'
RELEASED = 'released'
DISPUTED = 'disputed'
REFUNDED = 'refunded'
CANCELLED = 'cancelled'

ESCROW_STATUS_CHOICES = [
    (PENDING_PAYMENT, 'Pending Payment'),
    (FUNDED, 'Funded'),
    (IN_PROGRESS, 'In Progress'),
    (SUBMITTED, 'Submitted'),
    (COMPLETED, 'Completed'),
    (RELEASED, 'Released'),
    (DISPUTED, 'Disputed'),
    (REFUNDED, 'Refunded'),
    (CANCELLED, 'Cancelled'),
]

# Valid transitions: from_state -> set(to_states)
ESCROW_TRANSITIONS = {
    PENDING_PAYMENT: {FUNDED, CANCELLED},
    FUNDED: {IN_PROGRESS, CANCELLED, DISPUTED},
    IN_PROGRESS: {SUBMITTED, CANCELLED, DISPUTED},
    SUBMITTED: {COMPLETED, IN_PROGRESS, DISPUTED},
    COMPLETED: {RELEASED, DISPUTED},
    DISPUTED: {FUNDED, REFUNDED, RELEASED, CANCELLED},
    RELEASED: set(),
    REFUNDED: set(),
    CANCELLED: set(),
}

PAYMENT_TX_SUCCESS = 'success'
PAYMENT_TX_FAILED = 'failed'
PAYMENT_TX_PENDING = 'pending'
PAYMENT_TX_PROCESSING = 'processing'

PAYMENT_TX_STATUS_CHOICES = [
    (PAYMENT_TX_PENDING, 'Pending'),
    (PAYMENT_TX_PROCESSING, 'Processing'),
    (PAYMENT_TX_SUCCESS, 'Success'),
    (PAYMENT_TX_FAILED, 'Failed'),
]
