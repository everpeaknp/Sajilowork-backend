"""
Signal handlers for User app.
"""
import logging

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils.crypto import get_random_string
from django.utils import timezone
from .models import User, UserDocument, UserBadge

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=User)
def generate_referral_code(sender, instance, **kwargs):
    """Generate unique referral code for new users."""
    if not instance.referral_code:
        instance.referral_code = get_random_string(length=10).upper()


@receiver(pre_save, sender=User)
def generate_username(sender, instance, **kwargs):
    """Generate username from email if not provided."""
    if not instance.username:
        base_username = instance.email.split('@')[0]
        username = base_username
        counter = 1
        
        while User.objects.filter(username=username).exclude(pk=instance.pk).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        instance.username = username


@receiver(pre_save, sender=User)
def log_user_account_changes(sender, instance, **kwargs):
    """Log important account mutations for later audit/debugging."""
    if not instance.pk:
        return

    previous = User.objects.filter(pk=instance.pk).first()
    if not previous:
        return

    changes = []
    watched_fields = [
        'email',
        'role',
        'is_active',
        'is_staff',
        'is_superuser',
        'account_suspended',
        'suspended_until',
    ]
    for field in watched_fields:
        old_value = getattr(previous, field)
        new_value = getattr(instance, field)
        if old_value != new_value:
            changes.append(f"{field}: {old_value!r} -> {new_value!r}")

    if previous.password != instance.password:
        changes.append('password: changed')

    if changes:
        logger.warning(
            "User account changed user_id=%s email=%s changes=%s",
            instance.pk,
            previous.email,
            "; ".join(changes),
        )


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Perform actions after user creation."""
    if created:
        logger.info(
            "User created user_id=%s email=%s role=%s is_staff=%s is_superuser=%s",
            instance.pk,
            instance.email,
            instance.role,
            instance.is_staff,
            instance.is_superuser,
        )
        from .models import UserKYC
        UserKYC.objects.get_or_create(user=instance)


@receiver(post_delete, sender=User)
def log_user_deletion(sender, instance, **kwargs):
    """Log physical user deletions explicitly."""
    logger.error(
        "User deleted user_id=%s email=%s role=%s is_staff=%s is_superuser=%s",
        instance.pk,
        instance.email,
        instance.role,
        instance.is_staff,
        instance.is_superuser,
    )


@receiver(post_save, sender=UserDocument)
def sync_kyc_on_document_change(sender, instance, **kwargs):
    """Ensure KYC record exists and reflects pending review after document upload."""
    from .kyc_service import get_or_create_kyc, mark_kyc_submitted

    get_or_create_kyc(instance.user)
    if instance.status == 'pending':
        mark_kyc_submitted(instance.user)


@receiver(post_save, sender=UserDocument)
def update_verification_status(sender, instance, **kwargs):
    """Update user verification status when documents are approved."""
    if instance.status == 'approved':
        user = instance.user
        
        # Check if identity document is approved
        if instance.document_type in ['id_card', 'passport', 'driver_license']:
            user.identity_verified = True
            user.save(update_fields=['identity_verified'])
        
        # Check if user has all required documents for tasker verification
        if user.role == 'tasker':
            required_docs = ['id_card', 'proof_of_address']
            approved_docs = UserDocument.objects.filter(
                user=user,
                status='approved',
                document_type__in=required_docs
            ).values_list('document_type', flat=True)
            
            if set(required_docs).issubset(set(approved_docs)):
                user.is_verified_tasker = True
                user.save(update_fields=['is_verified_tasker'])

        badge_types = ['police_check', 'electrical_licence', 'plumbing_licence']
        if instance.document_type in badge_types:
            UserBadge.objects.filter(
                user=user,
                badge_type=instance.document_type,
            ).update(is_verified=True, verified_at=timezone.now())

        if instance.document_type == 'custom_licence' and instance.document_number.startswith('badge:'):
            badge_id = instance.document_number.split('|')[0].replace('badge:', '').strip()
            if badge_id:
                UserBadge.objects.filter(
                    user=user,
                    id=badge_id,
                    badge_type='custom_licence',
                ).update(is_verified=True, verified_at=timezone.now())
