"""
Business logic services for User app.
"""
from django.core.mail import send_mail
from django.conf import settings
from django.utils.crypto import get_random_string
from django.core.cache import cache
from .models import User, UserBadge


class UserService:
    """Service class for user-related business logic."""
    
    @staticmethod
    def send_verification_email(user):
        """Send email verification link to user."""
        token = get_random_string(length=64)
        cache_key = f'email_verification_{token}'
        cache.set(cache_key, user.id, timeout=86400)  # 24 hours
        
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        
        send_mail(
            subject='Verify your email address',
            message=f'Please click the link to verify your email: {verification_url}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        return token
    
    @staticmethod
    def verify_email_token(token):
        """Verify email token and activate user."""
        cache_key = f'email_verification_{token}'
        user_id = cache.get(cache_key)
        
        if not user_id:
            return None, 'Invalid or expired token'
        
        try:
            user = User.objects.get(id=user_id)
            user.email_verified = True
            user.save(update_fields=['email_verified'])
            cache.delete(cache_key)
            return user, None
        except User.DoesNotExist:
            return None, 'User not found'
    
    @staticmethod
    def send_password_reset_email(user):
        """Send password reset link to user."""
        token = get_random_string(length=64)
        cache_key = f'password_reset_{token}'
        cache.set(cache_key, user.id, timeout=3600)  # 1 hour
        
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        
        send_mail(
            subject='Reset your password',
            message=f'Please click the link to reset your password: {reset_url}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        return token
    
    @staticmethod
    def reset_password_with_token(token, new_password):
        """Reset password using token."""
        cache_key = f'password_reset_{token}'
        user_id = cache.get(cache_key)
        
        if not user_id:
            return None, 'Invalid or expired token'
        
        try:
            user = User.objects.get(id=user_id)
            user.set_password(new_password)
            user.save()
            cache.delete(cache_key)
            return user, None
        except User.DoesNotExist:
            return None, 'User not found'
    
    @staticmethod
    def award_badge(
        user,
        badge_type,
        name,
        description='',
        icon_url='',
        is_verified=True,
    ):
        """Award a badge to user."""
        from django.utils import timezone

        badge, created = UserBadge.objects.get_or_create(
            user=user,
            badge_type=badge_type,
            name=name,
            defaults={
                'description': description,
                'icon_url': icon_url,
                'is_verified': is_verified,
                'verified_at': timezone.now() if is_verified else None,
            },
        )
        if not created and is_verified and not badge.is_verified:
            badge.is_verified = True
            badge.verified_at = timezone.now()
            badge.save(update_fields=['is_verified', 'verified_at'])
        return badge, created
    
    @staticmethod
    def check_and_award_milestone_badges(user):
        """Check and award milestone badges based on user achievements."""
        badges_to_award = []
        
        # Tasks completed milestones
        if user.tasks_completed >= 10 and not user.badges.filter(badge_type='milestone', name='10 Tasks').exists():
            badges_to_award.append(('milestone', '10 Tasks', 'Completed 10 tasks'))
        
        if user.tasks_completed >= 50 and not user.badges.filter(badge_type='milestone', name='50 Tasks').exists():
            badges_to_award.append(('milestone', '50 Tasks', 'Completed 50 tasks'))
        
        if user.tasks_completed >= 100 and not user.badges.filter(badge_type='milestone', name='100 Tasks').exists():
            badges_to_award.append(('milestone', '100 Tasks', 'Completed 100 tasks'))
        
        # Rating milestones
        if user.average_rating >= 4.5 and user.total_reviews >= 10:
            if not user.badges.filter(badge_type='top_rated').exists():
                badges_to_award.append(('top_rated', 'Top Rated', 'Maintained 4.5+ rating with 10+ reviews'))
        
        # Award badges
        for badge_type, name, description in badges_to_award:
            UserService.award_badge(user, badge_type, name, description)
        
        return len(badges_to_award)
    
    @staticmethod
    def calculate_completion_rate(user):
        """Calculate and update user's task completion rate."""
        if user.role != 'tasker':
            return 0
        
        from apps.tasks.models import Task
        
        assigned_tasks = Task.objects.filter(assigned_tasker=user).count()
        if assigned_tasks == 0:
            return 0
        
        completed_tasks = Task.objects.filter(
            assigned_tasker=user,
            status='completed'
        ).count()
        
        completion_rate = (completed_tasks / assigned_tasks) * 100
        user.completion_rate = round(completion_rate, 2)
        user.save(update_fields=['completion_rate'])
        
        return completion_rate
    
    @staticmethod
    def calculate_response_time(user):
        """Calculate average response time for tasker."""
        if user.role != 'tasker':
            return 0
        
        from apps.bids.models import Bid
        from django.db.models import Avg, F
        
        avg_response = Bid.objects.filter(
            tasker=user
        ).annotate(
            response_minutes=F('created_at') - F('task__created_at')
        ).aggregate(
            avg_minutes=Avg('response_minutes')
        )
        
        if avg_response['avg_minutes']:
            response_time = int(avg_response['avg_minutes'].total_seconds() / 60)
            user.response_time = response_time
            user.save(update_fields=['response_time'])
            return response_time
        
        return 0
