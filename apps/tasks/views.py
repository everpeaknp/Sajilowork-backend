"""
Views for Task management.
"""
import uuid as uuid_module

from django.http import Http404
from rest_framework import viewsets, status, filters, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly
from django.db import transaction
from django.db.models import Prefetch, Q, Count, Avg, Sum
from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from .models import (
    Task, Category, TaskAttachment, TaskBookmark,
    TaskView, TaskQuestion, TaskReport
)
from .attachment_service import (
    TASK_ATTACHMENT_TYPE_ERROR,
    is_allowed_task_attachment,
    MAX_TASK_ATTACHMENT_BYTES,
    build_task_attachment_file_url,
    classify_task_attachment_type,
    save_task_attachment_upload,
)
from .serializers import (
    TaskListSerializer, TaskDetailSerializer, TaskCreateSerializer,
    TaskUpdateSerializer, TaskStatusSerializer, CategorySerializer,
    TaskAttachmentSerializer, TaskBookmarkSerializer, TaskQuestionSerializer,
    DashboardTaskQuestionSerializer,
    TaskReportSerializer, TaskStatsSerializer
)
from apps.users.permissions import IsOwner, IsCustomer, IsTasker
from apps.bookmark.mixins import BookmarkSerializerContextMixin
from apps.bookmark.services import add_bookmark, list_bookmarked_tasks, remove_bookmark
from .permissions import IsTaskOwner, IsTaskOwnerOrReadOnly, CanCreateTask
from .question_utils import block_owner_asking_question
from .listing import (
    LISTING_KIND_CHOICES,
    LISTING_KIND_CATEGORY_CHOICES,
    LISTING_KIND_JOB,
    LISTING_KIND_TASK,
    filter_queryset_by_listing_kind,
    filter_queryset_plain_tasks,
    get_listing_kind,
)
from apps.rules.integrations import cancel_task_with_rules
from apps.rules.permissions import NotSuspended


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for categories."""

    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'

    def get_queryset(self):
        listing_kind = self.request.query_params.get('listing_kind', LISTING_KIND_TASK)
        if listing_kind not in dict(LISTING_KIND_CATEGORY_CHOICES):
            listing_kind = LISTING_KIND_TASK
        return Category.objects.filter(
            is_active=True,
            parent=None,
            listing_kind=listing_kind,
        )
    
    @action(detail=True, methods=['get'])
    def tasks(self, request, slug=None):
        """Get tasks in this category."""
        category = self.get_object()
        tasks = Task.objects.filter(
            category=category,
            status='open',
            is_public=True
        )
        
        page = self.paginate_queryset(tasks)
        if page is not None:
            serializer = TaskListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = TaskListSerializer(tasks, many=True, context={'request': request})
        return Response(serializer.data)


class TaskViewSet(BookmarkSerializerContextMixin, viewsets.ModelViewSet):
    """ViewSet for Task CRUD operations."""
    
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'city', 'tags']
    ordering_fields = ['created_at', 'budget_amount', 'due_date', 'bids_count']
    filterset_fields = ['status', 'category', 'work_type', 'location_type', 'city', 'country']
    lookup_field = 'slug'  # Use slug instead of pk for lookups
    
    def get_queryset(self):
        """Return appropriate queryset based on user."""
        user = self.request.user

        queryset = Task.objects.all()
        if user.is_authenticated:
            queryset = queryset.filter(
                Q(is_public=True)
                | Q(owner=user)
                | Q(assigned_tasker=user)
            )
        else:
            queryset = queryset.filter(is_public=True, status='open')

        return queryset.select_related(
            'owner', 'owner__employer_profile', 'category', 'assigned_tasker'
        ).prefetch_related(
            'attachments',
            Prefetch(
                'questions',
                queryset=TaskQuestion.objects.select_related('asked_by').order_by('-created_at'),
            ),
        )
    
    def filter_queryset(self, queryset):
        """Apply DRF filters plus optional listing_kind query param."""
        queryset = super().filter_queryset(queryset)
        listing_kind = self.request.query_params.get('listing_kind')
        if listing_kind in LISTING_KIND_CHOICES:
            queryset = filter_queryset_by_listing_kind(queryset, listing_kind)
        elif listing_kind == LISTING_KIND_TASK:
            queryset = filter_queryset_plain_tasks(queryset)
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer class."""
        if self.action == 'list':
            return TaskListSerializer
        elif self.action == 'retrieve':
            return TaskDetailSerializer
        elif self.action == 'create':
            return TaskCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return TaskUpdateSerializer
        return TaskDetailSerializer
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action == 'create':
            return [IsAuthenticated(), CanCreateTask()]
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsTaskOwner()]
        if self.action in ['publish', 'answer_question']:
            return [IsAuthenticated(), IsTaskOwner()]
        if self.action == 'reviews':
            return [AllowAny()]
        if self.action == 'cancel':
            return [IsAuthenticated(), NotSuspended()]
        if self.action in [
            'my_tasks',
            'assigned_tasks',
            'bookmarked',
            'stats',
            'dashboard_questions',
            'update_status',
            'confirm_work_complete',
            'bookmark',
            'ask_question',
            'report',
        ]:
            return [IsAuthenticated()]
        return [IsAuthenticatedOrReadOnly()]

    @action(detail=True, methods=['get'], permission_classes=[AllowAny], url_path='reviews')
    def reviews(self, request, slug=None):
        """
        GET /api/v1/tasks/{id|slug}/reviews/
        Public reviews on this task.
        """
        from apps.reviews.serializers import ReviewListSerializer
        from apps.reviews.services import ReviewService

        task = self.get_object()
        qs = ReviewService.public_reviews_queryset().filter(task=task).select_related(
            'reviewer', 'reviewee',
        ).prefetch_related('helpful_votes', 'reports')
        return Response({
            'task_id': str(task.id),
            'count': qs.count(),
            'results': ReviewListSerializer(qs, many=True, context={'request': request}).data,
        })

    def get_object(self):
        """
        Resolve task by slug (canonical) or by UUID for legacy/deep links.
        """
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)

        if not lookup_value:
            raise Http404('No Task matches the given query.')

        obj = queryset.filter(slug=lookup_value).first()
        if obj is None:
            try:
                uuid_module.UUID(str(lookup_value))
            except (ValueError, TypeError, AttributeError):
                pass
            else:
                obj = queryset.filter(pk=lookup_value).first()

        if obj is None:
            raise Http404('No Task matches the given query.')

        self.check_object_permissions(self.request, obj)
        return obj
    
    def create(self, request, *args, **kwargs):
        """Create task with rich validation-error logging."""
        import logging
        logger = logging.getLogger(__name__)
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            try:
                payload_preview = {
                    k: (
                        (v[:120] + '...') if isinstance(v, str) and len(v) > 120 else v
                    )
                    for k, v in (request.data.items() if hasattr(request.data, 'items') else [])
                }
            except Exception:
                payload_preview = '<unloggable>'
            logger.warning(
                "Task create validation failed | user=%s role=%s | errors=%s | payload=%s",
                getattr(request.user, 'email', None),
                getattr(request.user, 'role', None),
                dict(serializer.errors),
                payload_preview,
            )
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        """Delete a task with proper error handling."""
        import logging
        import traceback
        from django.db import transaction

        logger = logging.getLogger(__name__)

        def _safe_count(relation):
            # Diagnostic counts must never break the delete. If a related
            # table is missing or the query fails, log "?" instead of raising.
            try:
                return relation.count()
            except Exception as exc:  # pragma: no cover - diagnostic-only
                return f"?({exc.__class__.__name__})"

        try:
            instance = self.get_object()
            task_slug = instance.slug
            task_id = instance.id

            # Cannot delete once a tasker has been assigned or work has started.
            if instance.assigned_tasker_id or instance.status in (
                'assigned', 'in_progress', 'completed', 'disputed'
            ):
                return Response({
                    'error': 'Cannot delete a task that has been assigned to a tasker.',
                    'detail': (
                        'This task is assigned or in progress. Cancel the task instead '
                        'of deleting it.'
                    ),
                }, status=status.HTTP_400_BAD_REQUEST)

            logger.info(f"Attempting to delete task: {task_slug} (ID: {task_id})")
            logger.info(f"   - Owner: {instance.owner.email}")
            logger.info(f"   - Status: {instance.status}")
            logger.info(f"   - Bids count: {_safe_count(instance.bids)}")
            logger.info(f"   - Bookmarks count: {_safe_count(instance.bookmarks)}")
            logger.info(f"   - Views count: {_safe_count(instance.views)}")
            logger.info(f"   - Questions count: {_safe_count(instance.questions)}")
            logger.info(f"   - Reports count: {_safe_count(instance.reports)}")
            logger.info(f"   - Activities count: {_safe_count(instance.activities)}")
            logger.info(f"   - Attachments count: {_safe_count(instance.attachments)}")

            logger.info("Starting deletion process...")
            with transaction.atomic():
                self.perform_destroy(instance)

            logger.info(f"Task {task_slug} deleted successfully")
            return Response(status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            logger.error(f"Error deleting task: {type(e).__name__}: {str(e)}")
            logger.error("Full traceback:")
            logger.error(traceback.format_exc())

            # Surface the real cause so the frontend can show a useful toast
            # instead of the generic "Failed to delete task".
            return Response({
                'error': f"{type(e).__name__}: {str(e)}" or 'Failed to delete task',
                'detail': str(e),
                'type': type(e).__name__,
                'traceback': traceback.format_exc() if request.user.is_staff else None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve task and track view."""
        instance = self.get_object()
        
        # Track view
        TaskView.objects.create(
            task=instance,
            user=request.user if request.user.is_authenticated else None,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            referrer=(request.META.get('HTTP_REFERER') or '')[:2048] or None,
        )
        
        # Increment view count
        instance.views_count += 1
        instance.save(update_fields=['views_count'])
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsTaskOwner])
    def publish(self, request, slug=None):
        """Publish a draft task."""
        task = self.get_object()
        
        if task.status != 'draft':
            return Response({
                'error': 'Only draft tasks can be published.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        task.publish()
        
        return Response({
            'message': 'Task published successfully.',
            'task': TaskDetailSerializer(task, context={'request': request}).data
        })
    
    @action(
        detail=True,
        methods=['post'],
        permission_classes=[IsAuthenticated, NotSuspended],
    )
    def cancel(self, request, slug=None):
        """Cancel a task (rule engine + escrow refund + moderation)."""
        from rest_framework.exceptions import PermissionDenied

        task = self.get_object()

        if task.owner != request.user and task.assigned_tasker != request.user:
            return Response({
                'error': 'Only the task poster or assigned tasker can cancel this task.'
            }, status=status.HTTP_403_FORBIDDEN)

        if task.status in ['completed', 'cancelled']:
            return Response({
                'error': 'Cannot cancel a completed or already cancelled task.'
            }, status=status.HTTP_400_BAD_REQUEST)

        reason = (request.data.get('cancellation_reason') or '').strip()
        try:
            payload = cancel_task_with_rules(task, request.user, reason)
        except PermissionDenied as exc:
            return Response({'error': str(exc.detail)}, status=status.HTTP_403_FORBIDDEN)
        return Response(payload)
    
    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated])
    @transaction.atomic
    def update_status(self, request, slug=None):
        """Update task status."""
        task = self.get_object()
        
        # Check permissions
        if task.owner != request.user and task.assigned_tasker != request.user:
            return Response({
                'error': 'You do not have permission to update this task status.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = TaskStatusSerializer(
            data=request.data,
            context={'task': task}
        )
        serializer.is_valid(raise_exception=True)
        
        new_status = serializer.validated_data['status']

        if new_status == 'completed':
            is_job_listing = get_listing_kind(task.tags) == LISTING_KIND_JOB
            if (
                is_job_listing
                and task.owner_id == request.user.id
                and task.status in ('assigned', 'in_progress', 'funded')
            ):
                now = timezone.now()
                task.status = 'completed'
                task.completion_date = now
                task.completed_at = now
                if not task.owner_marked_complete_at:
                    task.owner_marked_complete_at = now
                task.save(
                    update_fields=[
                        'status',
                        'completion_date',
                        'completed_at',
                        'owner_marked_complete_at',
                        'updated_at',
                    ]
                )
                return Response({
                    'message': 'Applicant hired successfully.',
                    'task': TaskDetailSerializer(task, context={'request': request}).data,
                })

            unassigned_open = (
                task.status == 'open'
                and not task.assigned_tasker_id
                and task.owner_id == request.user.id
            )
            if unassigned_open and task.bids.filter(status='pending').exists():
                return Response(
                    {
                        'error': (
                            'Cannot mark as completed while proposals are still pending. '
                            'Accept or reject them first.'
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not unassigned_open:
                return Response(
                    {
                        'error': (
                            'Both the poster and tasker must confirm completion before '
                            'payment is released. Use POST .../confirm_work_complete/ instead.'
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            task.status = 'completed'
            task.completion_date = timezone.now()
            task.completed_at = timezone.now()
            task.save(update_fields=['status', 'completion_date', 'completed_at', 'updated_at'])
            return Response({
                'message': 'Task marked as completed.',
                'task': TaskDetailSerializer(task, context={'request': request}).data,
            })

        task.status = new_status

        if new_status == 'in_progress':
            task.start_date = timezone.now()

        task.save()

        try:
            from apps.payments.escrow_lifecycle import EscrowLifecycleService

            if new_status == 'in_progress':
                EscrowLifecycleService.on_task_started(task, actor=request.user)
        except Exception as exc:
            transaction.set_rollback(True)
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'message': f'Task status updated to {new_status}.',
            'task': TaskDetailSerializer(task, context={'request': request}).data,
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    @transaction.atomic
    def confirm_work_complete(self, request, slug=None):
        """
        Poster or tasker confirms work is complete. Funds are released only after
        both parties have confirmed.
        """
        from .completion_service import confirm_work_complete_by_user

        task = self.get_object()

        if task.owner != request.user and task.assigned_tasker != request.user:
            return Response(
                {'error': 'You do not have permission to confirm completion for this task.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            result = confirm_work_complete_by_user(task, request.user)
        except DjangoValidationError as exc:
            transaction.set_rollback(True)
            message = exc.messages[0] if getattr(exc, 'messages', None) else str(exc)
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            transaction.set_rollback(True)
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        task.refresh_from_db()
        payload = {
            'message': (
                f'Task completed. {result["payment_released"].net_amount} '
                f'{result["payment_released"].currency} released to the tasker wallet.'
                if result['both_confirmed'] and result['payment_released']
                else (
                    'You confirmed completion. Waiting for the other party to confirm '
                    'before payment is released.'
                    if not result['both_confirmed']
                    else 'Task completed.'
                )
            ),
            'both_confirmed': result['both_confirmed'],
            'tasker_marked_complete_at': result['tasker_marked_complete_at'],
            'owner_marked_complete_at': result['owner_marked_complete_at'],
            'task': TaskDetailSerializer(task, context={'request': request}).data,
        }
        if result['payment_released'] is not None:
            payment = result['payment_released']
            payload['payment_released'] = True
            payload['net_amount'] = str(payment.net_amount)
            payload['currency'] = payment.currency

        return Response(payload)
    
    @action(detail=True, methods=['post', 'delete'], permission_classes=[IsAuthenticated])
    def bookmark(self, request, slug=None):
        """Bookmark or unbookmark a task."""
        task = self.get_object()

        if request.method == 'POST':
            _, created = add_bookmark(request.user, task)
            if created:
                return Response({
                    'message': 'Task bookmarked successfully.'
                }, status=status.HTTP_201_CREATED)
            return Response({
                'message': 'Task already bookmarked.'
            })

        if remove_bookmark(request.user, task):
            return Response({
                'message': 'Bookmark removed successfully.'
            })
        return Response({
            'error': 'Task was not bookmarked.'
        }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_tasks(self, request):
        """Get current user's posted tasks."""
        tasks = Task.objects.filter(owner=request.user).order_by('-created_at')

        listing_kind = request.query_params.get('listing_kind')
        if listing_kind in LISTING_KIND_CHOICES:
            tasks = filter_queryset_by_listing_kind(tasks, listing_kind)
        elif listing_kind == LISTING_KIND_TASK:
            tasks = filter_queryset_plain_tasks(tasks)
        
        page = self.paginate_queryset(tasks)
        if page is not None:
            serializer = TaskListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = TaskListSerializer(tasks, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def assigned_tasks(self, request):
        """Get tasks assigned to current user."""
        tasks = Task.objects.filter(assigned_tasker=request.user).order_by('-created_at')
        
        page = self.paginate_queryset(tasks)
        if page is not None:
            serializer = TaskListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = TaskListSerializer(tasks, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def bookmarked(self, request):
        """Get user's bookmarked tasks."""
        listing_kind = request.query_params.get('listing_kind')
        tasks = list_bookmarked_tasks(request.user, listing_kind)

        page = self.paginate_queryset(tasks)
        if page is not None:
            serializer = TaskListSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)

        serializer = TaskListSerializer(tasks, many=True, context=self.get_serializer_context())
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def stats(self, request):
        """Get task statistics for current user."""
        user = request.user
        
        tasks = Task.objects.filter(owner=user)
        
        stats = {
            'total_tasks': tasks.count(),
            'open_tasks': tasks.filter(status='open').count(),
            'assigned_tasks': tasks.filter(status='assigned').count(),
            'in_progress_tasks': tasks.filter(status='in_progress').count(),
            'completed_tasks': tasks.filter(status='completed').count(),
            'cancelled_tasks': tasks.filter(status='cancelled').count(),
            'total_budget': tasks.aggregate(Sum('budget_amount'))['budget_amount__sum'] or 0,
            'average_budget': tasks.aggregate(Avg('budget_amount'))['budget_amount__avg'] or 0,
        }
        
        serializer = TaskStatsSerializer(stats)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated], url_path='dashboard_questions')
    def dashboard_questions(self, request):
        """
        GET /api/v1/tasks/dashboard_questions/?view=received|asked
        received — questions on listings you own (employer inbox)
        asked — questions you posted on other listings (freelancer inbox)
        """
        view = (request.query_params.get('view') or 'received').strip().lower()
        if view == 'asked':
            queryset = TaskQuestion.objects.filter(
                asked_by=request.user,
                is_public=True,
            )
        else:
            queryset = TaskQuestion.objects.filter(
                task__owner=request.user,
                is_public=True,
            )

        queryset = queryset.select_related(
            'task', 'asked_by', 'task__owner',
        ).order_by('-created_at')

        page = self.paginate_queryset(queryset)
        serializer_class = DashboardTaskQuestionSerializer
        context = {'request': request}
        if page is not None:
            serializer = serializer_class(page, many=True, context=context)
            return self.get_paginated_response(serializer.data)

        serializer = serializer_class(queryset, many=True, context=context)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def ask_question(self, request, slug=None):
        """Ask a question about the task."""
        task = self.get_object()

        blocked = block_owner_asking_question(task, request.user)
        if blocked is not None:
            return blocked

        serializer = TaskQuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.save(task=task, asked_by=request.user)

        output = TaskQuestionSerializer(question, context={'request': request})
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=['patch'],
        url_path=r'questions/(?P<question_id>[0-9a-f-]{36})',
        permission_classes=[IsAuthenticated, IsTaskOwner],
    )
    def answer_question(self, request, slug=None, question_id=None):
        """Post or update an answer (task owner only)."""
        task = self.get_object()

        try:
            question = task.questions.get(pk=question_id)
        except TaskQuestion.DoesNotExist:
            return Response(
                {'detail': 'Question not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        answer = (request.data.get('answer') or '').strip()
        if not answer:
            return Response(
                {'answer': ['Answer cannot be empty.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        question.answer = answer
        question.answered_at = timezone.now()
        question.save(update_fields=['answer', 'answered_at'])

        serializer = TaskQuestionSerializer(question, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def report(self, request, slug=None):
        """Report a task."""
        task = self.get_object()
        
        serializer = TaskReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(task=task, reported_by=request.user)
        
        return Response({
            'message': 'Task reported successfully. Our team will review it.'
        }, status=status.HTTP_201_CREATED)


class TaskAttachmentViewSet(viewsets.ModelViewSet):
    """ViewSet for task attachments."""
    
    serializer_class = TaskAttachmentSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']
    
    def get_queryset(self):
        """Return attachments for tasks owned by user."""
        return TaskAttachment.objects.filter(
            task__owner=self.request.user
        )
    
    def create(self, request, *args, **kwargs):
        """Accept multipart file upload and attach to a task owned by the user."""
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response(
                {'error': 'No file provided.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task_id = request.data.get('task')
        if not task_id:
            return Response(
                {'error': 'Task id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            task = Task.objects.get(id=task_id, owner=request.user)
        except (Task.DoesNotExist, ValueError, TypeError):
            return Response(
                {'error': 'Task not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if uploaded_file.size > MAX_TASK_ATTACHMENT_BYTES:
            return Response(
                {'error': 'File size exceeds 10MB limit.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        content_type = (uploaded_file.content_type or '').lower()
        if not is_allowed_task_attachment(content_type, uploaded_file.name):
            return Response(
                {'error': TASK_ATTACHMENT_TYPE_ERROR},
                status=status.HTTP_400_BAD_REQUEST,
            )
        file_type = classify_task_attachment_type(content_type, uploaded_file.name)
        if file_type not in ('image', 'document'):
            return Response(
                {'error': TASK_ATTACHMENT_TYPE_ERROR},
                status=status.HTTP_400_BAD_REQUEST,
            )

        storage_path = save_task_attachment_upload(request.user, task, uploaded_file)
        file_url = build_task_attachment_file_url(request, storage_path)

        attachment = TaskAttachment.objects.create(
            task=task,
            file_url=file_url,
            file_name=(uploaded_file.name or 'attachment')[:255],
            file_type=file_type,
            file_size=uploaded_file.size,
            uploaded_by=request.user,
        )

        serializer = self.get_serializer(attachment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
