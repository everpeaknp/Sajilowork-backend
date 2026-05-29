"""
Dashboard Services
Business logic for aggregating statistics and analytics.
"""
from django.conf import settings
from django.db.models import Count, Sum, Avg, Q, F
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

DEFAULT_CURRENCY = getattr(settings, 'DEFAULT_CURRENCY', 'NPR')

from apps.dashboard.tier_service import resolve_tasker_tier
from apps.users.models import User
from apps.tasks.models import Task, Category
from apps.bids.models import Bid
from apps.reviews.models import Review
from apps.payments.models import Payment
from apps.wallets.models import Wallet, WalletTransaction


class DashboardService:
    """Service for dashboard statistics and analytics"""
    
    @staticmethod
    def get_platform_overview():
        """Get overall platform statistics"""
        total_users = User.objects.count()
        total_customers = User.objects.filter(role='customer').count()
        total_taskers = User.objects.filter(role='tasker').count()
        verified_taskers = User.objects.filter(role='tasker', is_verified_tasker=True).count()
        
        total_tasks = Task.objects.count()
        open_tasks = Task.objects.filter(status='open').count()
        completed_tasks = Task.objects.filter(status='completed').count()
        
        total_bids = Bid.objects.count()
        accepted_bids = Bid.objects.filter(status='accepted').count()
        
        total_reviews = Review.objects.count()
        avg_rating = Review.objects.aggregate(avg=Avg('overall_rating'))['avg'] or 0
        
        total_payments = Payment.objects.filter(status='succeeded').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        platform_fees = Payment.objects.filter(
            status='succeeded',
            payment_type='service_fee'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        return {
            'users': {
                'total': total_users,
                'customers': total_customers,
                'taskers': total_taskers,
                'verified_taskers': verified_taskers,
            },
            'tasks': {
                'total': total_tasks,
                'open': open_tasks,
                'completed': completed_tasks,
                'completion_rate': (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
            },
            'bids': {
                'total': total_bids,
                'accepted': accepted_bids,
                'acceptance_rate': (accepted_bids / total_bids * 100) if total_bids > 0 else 0,
            },
            'reviews': {
                'total': total_reviews,
                'average_rating': round(float(avg_rating), 2),
            },
            'financials': {
                'total_payments': float(total_payments),
                'platform_fees': float(platform_fees),
                'currency': DEFAULT_CURRENCY,
            }
        }
    
    @staticmethod
    def get_user_statistics(user):
        """Get statistics for a specific user"""
        if user.role == 'customer':
            return DashboardService._get_customer_stats(user)
        elif user.role == 'tasker':
            return DashboardService._get_tasker_stats(user)
        else:
            return {}
    
    @staticmethod
    def _get_customer_stats(user):
        """Get statistics for a customer"""
        try:
            total_tasks = Task.objects.filter(owner=user).count()
            open_tasks = Task.objects.filter(owner=user, status='open').count()
            completed_tasks = Task.objects.filter(owner=user, status='completed').count()
            
            total_spent = Payment.objects.filter(
                payer=user,
                status='succeeded'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            reviews_given = Review.objects.filter(reviewer=user).count()
            avg_rating_given = Review.objects.filter(reviewer=user).aggregate(
                avg=Avg('overall_rating')
            )['avg'] or 0
            
            return {
                'role': 'customer',
                'tasks': {
                    'total': total_tasks,
                    'open': open_tasks,
                    'completed': completed_tasks,
                },
                'spending': {
                    'total': float(total_spent),
                    'currency': DEFAULT_CURRENCY,
                },
                'reviews': {
                    'given': reviews_given,
                    'average_rating_given': round(float(avg_rating_given), 2),
                }
            }
        except Exception as e:
            # Log the error and return safe defaults
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting customer stats for user {user.id}: {str(e)}")
            
            return {
                'role': 'customer',
                'tasks': {
                    'total': 0,
                    'open': 0,
                    'completed': 0,
                },
                'spending': {
                    'total': 0.00,
                    'currency': DEFAULT_CURRENCY,
                },
                'reviews': {
                    'given': 0,
                    'average_rating_given': 0.00,
                }
            }
    
    @staticmethod
    def _tasker_earned_payments(user):
        return Payment.objects.filter(
            payee=user,
            status__in=['released', 'succeeded'],
            payment_type='task_payment',
        )

    @staticmethod
    def _tasker_earnings_in_period(user, start_date):
        return DashboardService._tasker_earned_payments(user).filter(
            Q(escrow_released_at__gte=start_date)
            | Q(completed_at__gte=start_date, escrow_released_at__isnull=True)
            | Q(
                completed_at__isnull=True,
                escrow_released_at__isnull=True,
                created_at__gte=start_date,
            )
        ).aggregate(total=Sum(Coalesce('net_amount', 'amount')))['total'] or Decimal('0.00')

    @staticmethod
    def _get_tasker_stats(user):
        """Get statistics for a tasker"""
        try:
            total_bids = Bid.objects.filter(tasker=user).count()
            accepted_bids = Bid.objects.filter(tasker=user, status='accepted').count()
            pending_bids = Bid.objects.filter(tasker=user, status='pending').count()

            completed_tasks = Task.objects.filter(
                assigned_tasker=user,
                status='completed',
            ).count()
            active_tasks = Task.objects.filter(
                assigned_tasker=user,
                status__in=['assigned', 'funded', 'in_progress', 'pending_approval'],
            ).count()

            total_earned = DashboardService._tasker_earned_payments(user).aggregate(
                total=Sum(Coalesce('net_amount', 'amount'))
            )['total'] or Decimal('0.00')

            thirty_days_ago = timezone.now() - timedelta(days=30)
            earnings_last_30_days = DashboardService._tasker_earnings_in_period(
                user, thirty_days_ago
            )

            reviews_received = Review.objects.filter(reviewee=user).count()
            avg_rating = Review.objects.filter(reviewee=user).aggregate(
                avg=Avg('overall_rating')
            )['avg'] or 0

            try:
                wallet = Wallet.objects.get(user=user)
                wallet_balance = wallet.available_balance
            except Wallet.DoesNotExist:
                wallet = Wallet.objects.create(user=user, currency=DEFAULT_CURRENCY)
                wallet_balance = Decimal('0.00')

            active_task_list = list(
                Task.objects.filter(
                    assigned_tasker=user,
                    status__in=['assigned', 'funded', 'in_progress', 'pending_approval'],
                )
                .order_by('-updated_at')[:5]
                .values('id', 'title', 'slug', 'status', 'budget_amount', 'budget_currency')
            )

            tier = resolve_tasker_tier(earnings_last_30_days)

            return {
                'role': 'tasker',
                'bids': {
                    'total': total_bids,
                    'accepted': accepted_bids,
                    'pending': pending_bids,
                    'acceptance_rate': (accepted_bids / total_bids * 100) if total_bids > 0 else 0,
                },
                'tasks': {
                    'completed': completed_tasks,
                    'active': active_tasks,
                    'active_list': [
                        {
                            'id': str(task['id']),
                            'title': task['title'],
                            'slug': task['slug'],
                            'status': task['status'],
                            'budget': float(task['budget_amount']),
                            'currency': task['budget_currency'],
                        }
                        for task in active_task_list
                    ],
                },
                'earnings': {
                    'total': float(total_earned),
                    'last_30_days': float(earnings_last_30_days),
                    'wallet_balance': float(wallet_balance),
                    'currency': DEFAULT_CURRENCY,
                },
                'tier': tier,
                'reviews': {
                    'received': reviews_received,
                    'average_rating': round(float(avg_rating), 2),
                },
            }
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting tasker stats for user {user.id}: {str(e)}")

            tier = resolve_tasker_tier(Decimal('0.00'))
            return {
                'role': 'tasker',
                'bids': {
                    'total': 0,
                    'accepted': 0,
                    'pending': 0,
                    'acceptance_rate': 0,
                },
                'tasks': {
                    'completed': 0,
                    'active': 0,
                    'active_list': [],
                },
                'earnings': {
                    'total': 0.00,
                    'last_30_days': 0.00,
                    'wallet_balance': 0.00,
                    'currency': DEFAULT_CURRENCY,
                },
                'tier': tier,
                'reviews': {
                    'received': 0,
                    'average_rating': 0.00,
                },
            }
    
    @staticmethod
    def get_growth_metrics(days=30):
        """Get growth metrics for the specified period"""
        start_date = timezone.now() - timedelta(days=days)
        
        new_users = User.objects.filter(date_joined__gte=start_date).count()
        new_tasks = Task.objects.filter(created_at__gte=start_date).count()
        new_bids = Bid.objects.filter(created_at__gte=start_date).count()
        
        revenue = Payment.objects.filter(
            created_at__gte=start_date,
            status='succeeded'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        return {
            'period_days': days,
            'new_users': new_users,
            'new_tasks': new_tasks,
            'new_bids': new_bids,
            'revenue': float(revenue),
            'currency': DEFAULT_CURRENCY,
        }
    
    @staticmethod
    def get_category_statistics():
        """Get statistics by category"""
        categories = Category.objects.annotate(
            task_count=Count('tasks'),
            open_task_count=Count('tasks', filter=Q(tasks__status='open')),
            completed_task_count=Count('tasks', filter=Q(tasks__status='completed')),
        ).order_by('-task_count')[:10]
        
        return [
            {
                'id': cat.id,
                'name': cat.name,
                'slug': cat.slug,
                'total_tasks': cat.task_count,
                'open_tasks': cat.open_task_count,
                'completed_tasks': cat.completed_task_count,
            }
            for cat in categories
        ]
    
    @staticmethod
    def get_recent_activity(limit=10):
        """Get recent platform activity"""
        recent_tasks = Task.objects.select_related('owner', 'category').order_by('-created_at')[:limit]
        recent_bids = Bid.objects.select_related('tasker', 'task').order_by('-created_at')[:limit]
        recent_reviews = Review.objects.select_related('reviewer', 'reviewee').order_by('-created_at')[:limit]
        
        return {
            'recent_tasks': [
                {
                    'id': task.id,
                    'title': task.title,
                    'owner': task.owner.get_full_name(),
                    'category': task.category.name if task.category else None,
                    'budget': float(task.budget_amount),
                    'status': task.status,
                    'created_at': task.created_at.isoformat(),
                }
                for task in recent_tasks
            ],
            'recent_bids': [
                {
                    'id': bid.id,
                    'tasker': bid.tasker.get_full_name(),
                    'task_title': bid.task.title,
                    'amount': float(bid.amount),
                    'status': bid.status,
                    'created_at': bid.created_at.isoformat(),
                }
                for bid in recent_bids
            ],
            'recent_reviews': [
                {
                    'id': review.id,
                    'reviewer': review.reviewer.get_full_name(),
                    'reviewee': review.reviewee.get_full_name(),
                    'rating': review.overall_rating,
                    'created_at': review.created_at.isoformat(),
                }
                for review in recent_reviews
            ],
        }
    
    @staticmethod
    def get_financial_summary(days=30):
        """Get financial summary for the specified period"""
        start_date = timezone.now() - timedelta(days=days)
        
        payments = Payment.objects.filter(
            created_at__gte=start_date,
            status='succeeded'
        )
        
        total_revenue = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        platform_fees = payments.filter(payment_type='service_fee').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        refunds = Payment.objects.filter(
            created_at__gte=start_date,
            status='refunded'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        payouts = Payment.objects.filter(
            created_at__gte=start_date,
            payment_type='payout',
            status='succeeded'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        return {
            'period_days': days,
            'total_revenue': float(total_revenue),
            'platform_fees': float(platform_fees),
            'refunds': float(refunds),
            'payouts': float(payouts),
            'net_revenue': float(total_revenue - refunds),
            'currency': DEFAULT_CURRENCY,
        }
    
    @staticmethod
    def get_top_performers(limit=10):
        """Get top performing taskers"""
        top_taskers = User.objects.filter(
            role='tasker',
            is_verified_tasker=True
        ).annotate(
            completed_count=Count('assigned_tasks', filter=Q(assigned_tasks__status='completed')),
            avg_rating=Avg('reviews_received__overall_rating'),
            total_earned=Sum('payments_received__amount', filter=Q(payments_received__status='succeeded'))
        ).filter(
            completed_count__gt=0
        ).order_by('-completed_count', '-avg_rating')[:limit]
        
        return [
            {
                'id': tasker.id,
                'name': tasker.get_full_name(),
                'email': tasker.email,
                'completed_tasks': tasker.completed_count,
                'average_rating': round(float(tasker.avg_rating or 0), 2),
                'total_earned': float(tasker.total_earned or 0),
            }
            for tasker in top_taskers
        ]
