from apps.rules.handlers.assignment import AssignmentRuleHandler
from apps.rules.handlers.auto_release import AutoReleaseRuleHandler
from apps.rules.handlers.cancellation import CancellationRuleHandler
from apps.rules.handlers.dispute import DisputeRuleHandler
from apps.rules.handlers.escrow import EscrowRuleHandler
from apps.rules.handlers.fraud import FraudRuleHandler
from apps.rules.handlers.messaging import MessagingRuleHandler
from apps.rules.handlers.moderation import ModerationRuleHandler
from apps.rules.handlers.notification import NotificationRuleHandler
from apps.rules.handlers.offer import OfferRuleHandler
from apps.rules.handlers.payment_bypass import PaymentBypassRuleHandler
from apps.rules.handlers.promotion import PromotionRuleHandler
from apps.rules.handlers.refund import RefundRuleHandler
from apps.rules.handlers.review import ReviewRuleHandler
from apps.rules.handlers.task_expiry import TaskExpiryRuleHandler
from apps.rules.handlers.trust import TrustRuleHandler
from apps.rules.handlers.verification import VerificationRuleHandler
from apps.rules.handlers.wallet import WalletRuleHandler
from apps.rules.handlers.withdrawal import WithdrawalRuleHandler

ALL_HANDLERS = [
    EscrowRuleHandler(),
    OfferRuleHandler(),
    AssignmentRuleHandler(),
    ReviewRuleHandler(),
    CancellationRuleHandler(),
    DisputeRuleHandler(),
    WalletRuleHandler(),
    TrustRuleHandler(),
    VerificationRuleHandler(),
    FraudRuleHandler(),
    MessagingRuleHandler(),
    AutoReleaseRuleHandler(),
    RefundRuleHandler(),
    PromotionRuleHandler(),
    TaskExpiryRuleHandler(),
    PaymentBypassRuleHandler(),
    WithdrawalRuleHandler(),
    NotificationRuleHandler(),
    ModerationRuleHandler(),
]
