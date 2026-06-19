"""
Dashboard Services
Business logic for aggregating statistics and analytics.
"""
from django.conf import settings
from django.db.models import Count, Sum, Avg, Q, F
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

DEFAULT_CURRENCY = getattr(settings, 'DEFAULT_CURRENCY', 'NPR')

from calendar import month_abbr
from urllib.parse import urlparse

from apps.dashboard.tier_service import resolve_tasker_tier
from apps.users.models import User
from apps.tasks.models import Task, Category
from apps.tasks.models import TaskView
from apps.tasks.listing import (
    LISTING_KIND_JOB,
    LISTING_KIND_PROJECT,
    LISTING_KIND_SERVICE,
    LISTING_KIND_TASK,
    LISTING_KIND_CHOICES,
    filter_queryset_by_listing_kind,
    get_listing_kind,
)
from apps.bids.models import Bid
from apps.reviews.models import Review
from apps.payments.models import Payment
from apps.tasks.serializers import _cover_attachment
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
    def _month_window(months_back: int):
        """Return (start, end, label) for a calendar month relative to now."""
        now = timezone.now()
        year = now.year
        month = now.month - months_back
        while month <= 0:
            month += 12
            year -= 1
        start = timezone.make_aware(datetime(year, month, 1))
        if month == 12:
            end = timezone.make_aware(datetime(year + 1, 1, 1))
        else:
            end = timezone.make_aware(datetime(year, month + 1, 1))
        return start, end, month_abbr[month]

    @staticmethod
    def _monthly_view_series(task_ids, months: int = 12):
        """Monthly listing view counts from TaskView rows."""
        points = []
        for offset in range(months - 1, -1, -1):
            start, end, label = DashboardService._month_window(offset)
            if not task_ids:
                count = 0
            else:
                count = TaskView.objects.filter(
                    task_id__in=task_ids,
                    viewed_at__gte=start,
                    viewed_at__lt=end,
                ).count()
            points.append({'month': label, 'val': count})
        return points

    @staticmethod
    def _classify_traffic_source(referrer, user_agent: str = '') -> str:
        """Classify a view into direct, referral, or organic traffic."""
        ref = (referrer or '').lower().strip()
        ua = (user_agent or '').lower()

        search_hosts = (
            'google.',
            'bing.',
            'yahoo.',
            'duckduckgo.',
            'baidu.',
            'yandex.',
            'ecosia.',
            'search.',
        )
        social_hosts = (
            'facebook.',
            'fb.com',
            'twitter.',
            't.co',
            'linkedin.',
            'instagram.',
            'reddit.',
            'pinterest.',
            'tiktok.',
            'youtube.',
        )

        if ref:
            if any(host in ref for host in search_hosts):
                return 'organic'
            if any(host in ref for host in social_hosts):
                return 'referral'
            try:
                host = urlparse(ref).netloc.lower()
            except ValueError:
                host = ''
            internal_markers = ('localhost', '127.0.0.1', 'tasknepal')
            if host and not any(marker in host for marker in internal_markers):
                return 'referral'

        if any(token in ua for token in ('googlebot', 'bingbot', 'duckduckbot', 'yandexbot')):
            return 'organic'

        return 'direct'

    @staticmethod
    def _empty_traffic_breakdown():
        return {
            'direct': 0,
            'referral': 0,
            'organic': 0,
            'direct_percent': 0,
            'referral_percent': 0,
            'organic_percent': 0,
        }

    @staticmethod
    def _build_traffic_breakdown(task_ids, months: int = 12):
        """Aggregate traffic sources for listing views owned by the dashboard user."""
        if not task_ids:
            return DashboardService._empty_traffic_breakdown()

        start, _, _ = DashboardService._month_window(months - 1)
        views = TaskView.objects.filter(task_id__in=task_ids, viewed_at__gte=start)

        direct = 0
        referral = 0
        organic = 0
        for view in views.iterator():
            bucket = DashboardService._classify_traffic_source(view.referrer, view.user_agent)
            if bucket == 'organic':
                organic += 1
            elif bucket == 'referral':
                referral += 1
            else:
                direct += 1

        total = direct + referral + organic
        if total == 0:
            return DashboardService._empty_traffic_breakdown()

        direct_percent = round(direct / total * 100)
        referral_percent = round(referral / total * 100)
        organic_percent = max(0, 100 - direct_percent - referral_percent)

        return {
            'direct': direct,
            'referral': referral,
            'organic': organic,
            'direct_percent': direct_percent,
            'referral_percent': referral_percent,
            'organic_percent': organic_percent,
        }

    @staticmethod
    def _monthly_series(queryset, date_field: str = 'created_at', months: int = 12):
        points = []
        for offset in range(months - 1, -1, -1):
            start, end, label = DashboardService._month_window(offset)
            count = queryset.filter(**{
                f'{date_field}__gte': start,
                f'{date_field}__lt': end,
            }).count()
            points.append({'month': label, 'val': count})
        return points

    @staticmethod
    def _listing_image(task: Task) -> str:
        attachment = _cover_attachment(task)
        if not attachment or not attachment.file_url:
            return ''
        return str(attachment.file_url).strip()

    @staticmethod
    def _user_avatar_url(user) -> str:
        from apps.users.user_media_utils import resolve_user_media_url

        if not user:
            return ''
        return str(resolve_user_media_url(None, getattr(user, 'profile_image', None)) or '').strip()

    @staticmethod
    def _owner_business_profile_for_listing(task: Task) -> dict:
        owner = getattr(task, 'owner', None)
        profile = getattr(owner, 'employer_profile', None) if owner is not None else None

        logo_url = ''
        if profile and profile.logo_image:
            from apps.users.employer_profile_service import resolve_employer_image_url

            logo_url = str(resolve_employer_image_url(None, profile.logo_image) or '').strip()
        if not logo_url and owner:
            logo_url = DashboardService._user_avatar_url(owner)

        company_name = ''
        if profile and profile.company_name.strip():
            company_name = profile.company_name.strip()
        elif owner:
            company_name = (owner.get_full_name() or '').strip()
            if not company_name and getattr(owner, 'email', None):
                company_name = owner.email.split('@')[0]

        logo_color = profile.logo_color if profile and profile.logo_color else 'serif-m'
        if profile and profile.logo_text.strip():
            logo_text = profile.logo_text.strip()
        elif company_name:
            parts = company_name.split()
            logo_text = (
                ''.join(part[0] for part in parts[:2]).upper()
                if len(parts) >= 2
                else (company_name[:2] or 'CO').upper()
            )
        else:
            logo_text = 'CO'

        return {
            'business_logo_url': logo_url,
            'business_name': company_name,
            'logo_color': logo_color,
            'logo_text': logo_text,
        }

    @staticmethod
    def _resolve_listing_kind_label(task: Task) -> str:
        kind = get_listing_kind(task.tags)
        if kind in LISTING_KIND_CHOICES:
            return kind
        return LISTING_KIND_TASK

    @staticmethod
    def _build_my_listings(tasks_qs, limit: int = 5) -> list:
        listings_qs = (
            tasks_qs.select_related('owner', 'owner__employer_profile')
            .prefetch_related('attachments')
            .order_by('-updated_at', '-created_at')[:limit]
        )
        return [
            {
                'id': str(task.id),
                'slug': task.slug,
                'title': task.title,
                'listing_kind': DashboardService._resolve_listing_kind_label(task),
                'status': task.status,
                'budget_amount': float(task.budget_amount or 0),
                'currency': task.budget_currency or DEFAULT_CURRENCY,
                'date': (task.updated_at or task.created_at).isoformat(),
                'image': DashboardService._listing_image(task),
                **DashboardService._owner_business_profile_for_listing(task),
            }
            for task in listings_qs
        ]

    @staticmethod
    def get_user_overview(user):
        """Role-aware dashboard overview widgets for /dashboard home."""
        stats = DashboardService.get_user_statistics(user)
        role = stats.get('role') or user.role

        if role == 'tasker':
            services_qs = filter_queryset_by_listing_kind(
                Task.objects.filter(owner=user),
                LISTING_KIND_SERVICE,
            )
            services_offered = services_qs.count()
            completed_services = Task.objects.filter(
                assigned_tasker=user,
                status='completed',
            ).count()
            queue_services = Task.objects.filter(
                assigned_tasker=user,
                status__in=['assigned', 'funded', 'in_progress', 'pending_approval', 'open'],
            ).count()
            reviews_total = stats.get('reviews', {}).get('received', 0)

            stat_cards = [
                {
                    'title': 'Services Offered',
                    'value': str(services_offered),
                    'change_val': str(services_qs.filter(status='open').count()),
                    'change_text': 'Currently open',
                },
                {
                    'title': 'Completed Services',
                    'value': str(completed_services),
                    'change_val': str(
                        Task.objects.filter(
                            assigned_tasker=user,
                            status='completed',
                            completed_at__gte=timezone.now() - timedelta(days=30),
                        ).count()
                    ),
                    'change_text': 'Last 30 days',
                },
                {
                    'title': 'in Queue Services',
                    'value': str(queue_services),
                    'change_val': str(stats.get('bids', {}).get('pending', 0)),
                    'change_text': 'Pending proposals',
                },
                {
                    'title': 'Total Review',
                    'value': str(reviews_total),
                    'change_val': f"{stats.get('reviews', {}).get('average_rating', 0):.1f}",
                    'change_text': 'Average rating',
                },
            ]

            most_viewed_qs = (
                services_qs.select_related('owner', 'owner__employer_profile')
                .prefetch_related('attachments')
                .order_by('-views_count', '-created_at')[:3]
            )
            recent_purchases = []
            my_listings = []
            completed_projects_qs = (
                filter_queryset_by_listing_kind(
                    Task.objects.filter(assigned_tasker=user, status='completed'),
                    LISTING_KIND_PROJECT,
                )
                .select_related('owner')
                .order_by('-completed_at', '-updated_at')[:3]
            )
            recent_completed_projects = [
                {
                    'client_name': task.owner.get_full_name() or task.owner.email,
                    'project_title': task.title,
                    'amount': float(task.budget_amount or 0),
                    'currency': task.budget_currency or DEFAULT_CURRENCY,
                    'date': (task.completed_at or task.updated_at).isoformat(),
                    'avatar_initial': (task.owner.first_name or task.owner.email or '?')[:2].upper(),
                    'avatar_url': DashboardService._user_avatar_url(task.owner),
                    'slug': task.slug,
                }
                for task in completed_projects_qs
            ]
            activity_qs = Bid.objects.filter(tasker=user).select_related('task', 'task__owner')
        else:
            tasks_qs = Task.objects.filter(owner=user)
            reviews_total = stats.get('reviews', {}).get('received', 0)
            stat_cards = [
                {
                    'title': 'Tasks Posted',
                    'value': str(stats.get('tasks', {}).get('total', 0)),
                    'change_val': str(stats.get('tasks', {}).get('open', 0)),
                    'change_text': 'Open tasks',
                },
                {
                    'title': 'Completed Tasks',
                    'value': str(stats.get('tasks', {}).get('completed', 0)),
                    'change_val': str(
                        tasks_qs.filter(
                            status='completed',
                            completed_at__gte=timezone.now() - timedelta(days=30),
                        ).count()
                    ),
                    'change_text': 'Last 30 days',
                },
                {
                    'title': 'Active Listings',
                    'value': str(
                        filter_queryset_by_listing_kind(tasks_qs, LISTING_KIND_SERVICE).count()
                        + filter_queryset_by_listing_kind(tasks_qs, LISTING_KIND_PROJECT).count()
                        + filter_queryset_by_listing_kind(tasks_qs, LISTING_KIND_JOB).count()
                    ),
                    'change_val': str(
                        Bid.objects.filter(task__owner=user, status='pending').count()
                    ),
                    'change_text': 'Pending proposals',
                },
                {
                    'title': 'Total Review',
                    'value': str(reviews_total),
                    'change_val': f"{stats.get('reviews', {}).get('average_rating', 0):.1f}",
                    'change_text': 'Average rating',
                },
            ]

            most_viewed_qs = (
                filter_queryset_by_listing_kind(tasks_qs, LISTING_KIND_JOB)
                .select_related('owner', 'owner__employer_profile')
                .prefetch_related('attachments')
                .order_by('-views_count', '-created_at')[:3]
            )
            recent_purchases = []
            my_listings = DashboardService._build_my_listings(tasks_qs)
            recent_completed_projects = []
            activity_qs = Payment.objects.filter(payer=user).select_related('payee')

        owned_task_ids = list(Task.objects.filter(owner=user).values_list('id', flat=True))
        profile_views_chart = DashboardService._monthly_view_series(owned_task_ids)

        most_viewed_services = [
            {
                'id': str(task.id),
                'slug': task.slug,
                'title': task.title,
                'rating': float(getattr(task.owner, 'average_rating', 0) or 0),
                'views': task.views_count,
                'starting_price': float(task.budget_amount or 0),
                'currency': task.budget_currency or DEFAULT_CURRENCY,
                'image': DashboardService._listing_image(task),
                **DashboardService._owner_business_profile_for_listing(task),
            }
            for task in most_viewed_qs
        ]

        recent_activity = DashboardService._build_recent_activity(user, role)

        traffic = DashboardService._build_traffic_breakdown(owned_task_ids)

        return {
            **stats,
            'overview': {
                'stat_cards': stat_cards,
                'profile_views_chart': profile_views_chart,
                'traffic': traffic,
                'most_viewed_services': most_viewed_services,
                'recent_purchases': recent_purchases,
                'my_listings': my_listings,
                'recent_completed_projects': recent_completed_projects,
                'recent_activity': recent_activity,
            },
        }

    @staticmethod
    def _payment_task_title(payment: Payment) -> str:
        related = getattr(payment, 'related_object', None)
        if related is not None and hasattr(related, 'title'):
            return related.title
        if payment.content_type_id and payment.object_id:
            model = payment.content_type.model_class()
            if model and model.__name__ == 'Task':
                try:
                    title = model.objects.filter(pk=payment.object_id).values_list('title', flat=True).first()
                    if title:
                        return title
                except Exception:
                    pass
        return 'Service purchase'

    @staticmethod
    def _build_recent_activity(user, role: str):
        items = []
        if role == 'tasker':
            for bid in Bid.objects.filter(tasker=user).select_related('task').order_by('-created_at')[:5]:
                items.append({
                    'time': bid.created_at.strftime('%H:%M'),
                    'title': f'Proposal on {bid.task.title}',
                    'subtitle': f'Status: {bid.status.replace("_", " ")}',
                    'color': '#9a0026' if bid.status == 'accepted' else '#3b82f6',
                })
            for review in Review.objects.filter(reviewee=user).select_related('reviewer').order_by('-created_at')[:3]:
                items.append({
                    'time': review.created_at.strftime('%H:%M'),
                    'title': f'New review from {review.reviewer.get_full_name()}',
                    'subtitle': f'{review.overall_rating} star rating received',
                    'color': '#f43f5e',
                })
        else:
            for payment in Payment.objects.filter(payer=user, status__in=['succeeded', 'released']).order_by('-created_at')[:4]:
                items.append({
                    'time': payment.created_at.strftime('%H:%M'),
                    'title': f'Payment to {payment.payee.get_full_name()}',
                    'subtitle': DashboardService._payment_task_title(payment),
                    'color': '#9a0026',
                })
            for bid in Bid.objects.filter(task__owner=user).select_related('tasker', 'task').order_by('-created_at')[:3]:
                items.append({
                    'time': bid.created_at.strftime('%H:%M'),
                    'title': f'New proposal from {bid.tasker.get_full_name()}',
                    'subtitle': bid.task.title,
                    'color': '#3b82f6',
                })

        items.sort(key=lambda item: item['time'], reverse=True)
        return items[:5]
    
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
            reviews_received = Review.objects.filter(reviewee=user).count()
            avg_rating_received = Review.objects.filter(reviewee=user).aggregate(
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
                    'received': reviews_received,
                    'average_rating': round(float(avg_rating_received), 2),
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
                    'received': 0,
                    'average_rating': 0.00,
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
