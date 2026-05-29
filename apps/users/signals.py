"""
Signal handlers for User app.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.crypto import get_random_string
from django.utils import timezone
from .models import User, UserDocument, UserBadge


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


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Perform actions after user creation."""
    if created:
        # TODO: Send welcome email
        # TODO: Create default notification settings
        # TODO: Award welcome badge
        pass


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
