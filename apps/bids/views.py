"""
Views for Bid management.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Avg, Sum, Count
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.core.exceptions import ValidationError, PermissionDenied
import logging

from .models import Bid, BidMessage, BidReview, BidNotification
from .workflow import BidWorkflowService

logger = logging.getLogger(__name__)
from .serializers import (
    BidListSerializer,
    BidDetailSerializer,
    BidCreateSerializer,
    BidUpdateSerializer,
    BidAcceptSerializer,
    BidRejectSerializer,
    BidWithdrawSerializer,
    CounterOfferSerializer,
    BidMessageSerializer,
    BidReviewSerializer,
    BidNotificationSerializer,
    BidStatsSerializer,
)
from .permissions import IsBidOwner, IsTaskOwner, CanAcceptBid, CanRejectBid
from apps.tasks.models import Task


class BidViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing bids.
    
    Endpoints:
    - GET /bids/ - List all bids (filtered by user role)
    - POST /bids/ - Create a new bid
    - GET /bids/{id}/ - Get bid details
    - PATCH /bids/{id}/ - Update bid (only pending bids)
    - DELETE /bids/{id}/ - Delete bid (only pending bids)
    - POST /bids/{id}/accept/ - Accept bid (task owner only)
    - POST /bids/{id}/reject/ - Reject bid (task owner only)
    - POST /bids/{id}/withdraw/ - Withdraw bid (bid owner only)
    - POST /bids/{id}/counter_offer/ - Create counter offer (task owner only)
    - GET /bids/my_bids/ - Get current user's bids
    - GET /bids/received_bids/ - Get bids on user's tasks
    - GET /bids/stats/ - Get bid statistics
    """
    
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'task', 'tasker', 'is_counter_offer']
    search_fields = ['proposal', 'cover_letter', 'task__title']
    ordering_fields = ['created_at', 'amount', 'status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Return bids based on user role.
        - Taskers see their own bids
        - Task owners see bids on their tasks
        - Any authenticated user may list bids on a public task (?task=<id>) for browse
        - Admins see all bids
        """
        user = self.request.user
        base = Bid.objects.select_related('task', 'tasker', 'original_bid')

        if getattr(user, 'is_admin', False):
            return base.all()

        task_id = self.request.query_params.get('task')
        if self.action == 'list' and task_id:
            task_qs = Task.objects.filter(id=task_id)
            if task_qs.filter(is_public=True).exists():
                return base.filter(task_id=task_id).distinct()
            return base.filter(task_id=task_id).filter(
                Q(tasker=user) | Q(task__owner=user)
            ).distinct()

        return base.filter(Q(tasker=user) | Q(task__owner=user)).distinct()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return BidListSerializer
        elif self.action == 'create':
            return BidCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return BidUpdateSerializer
        elif self.action == 'accept':
            return BidAcceptSerializer
        elif self.action == 'reject':
            return BidRejectSerializer
        elif self.action == 'withdraw':
            return BidWithdrawSerializer
        elif self.action == 'counter_offer':
            return CounterOfferSerializer
        elif self.action == 'stats':
            return BidStatsSerializer
        return BidDetailSerializer
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action == 'accept':
            return [IsAuthenticated(), CanAcceptBid()]
        elif self.action == 'reject':
            return [IsAuthenticated(), CanRejectBid()]
        elif self.action == 'withdraw':
            return [IsAuthenticated(), IsBidOwner()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsBidOwner()]
        elif self.action == 'counter_offer':
            return [IsAuthenticated(), IsTaskOwner()]
        return super().get_permissions()
    
    def perform_create(self, serializer):
        """Create bid and send notification."""
        try:
            bid = serializer.save()
            
            # Send notification to task owner
            BidNotification.objects.create(
                bid=bid,
                recipient=bid.task.owner,
                notification_type='new_bid',
                message=f"{bid.tasker.get_full_name()} submitted a bid of Rs. {bid.amount} on your task '{bid.task.title}'"
            )
            
            # Update task bid count
            bid.task.bids_count = bid.task.bids.count()
            bid.task.save(update_fields=['bids_count'])
        except Exception as e:
            logger.error(f"Error creating bid: {e}", exc_info=True)
            raise
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanAcceptBid])
    def accept(self, request, pk=None):
        """
        Accept a bid (task owner only).
        
        This triggers the complete workflow:
        - Creates escrow payment
        - Assigns provider to task
        - Rejects other bids
        - Creates conversation
        - Sends notifications
        """
        bid = self.get_object()
        
        try:
            result = BidWorkflowService.accept_bid(
                bid_id=str(bid.id),
                task_owner=request.user
            )
            
            return Response({
                'success': True,
                'message': 'Bid accepted successfully',
                'data': {
                    'bid_id': str(result['bid'].id),
                    'task_id': str(result['task'].id),
                    'payment_id': str(result['payment'].id),
                    'conversation_id': str(result['conversation'].id),
                    'rejected_bids_count': result['rejected_bids_count']
                }
            }, status=status.HTTP_200_OK)
            
        except ValidationError as e:
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            logger.error(f"Error accepting bid: {e}", exc_info=True)
            from django.conf import settings
            message = str(e) if settings.DEBUG else 'An error occurred while accepting the bid'
            return Response({
                'success': False,
                'message': message
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Reject a bid.
        Only task owner can reject bids.
        """
        bid = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            reason = serializer.validated_data.get('reason', '')
            bid.reject(reason=reason)
            
            # Send notification to tasker
            BidNotification.objects.create(
                bid=bid,
                recipient=bid.tasker,
                notification_type='bid_rejected',
                message=f"Your bid on '{bid.task.title}' has been rejected."
            )
            
            return Response(
                {'message': 'Bid rejected successfully'},
                status=status.HTTP_200_OK
            )
        
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def withdraw(self, request, pk=None):
        """
        Withdraw a bid.
        Only bid owner can withdraw their bid.
        """
        bid = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            reason = serializer.validated_data.get('reason', '')
            bid.withdraw(reason=reason)
            
            # Send notification to task owner
            BidNotification.objects.create(
                bid=bid,
                recipient=bid.task.owner,
                notification_type='bid_withdrawn',
                message=f"{bid.tasker.get_full_name()} withdrew their bid on '{bid.task.title}'"
            )
            
            # Update task bid count
            bid.task.bids_count = bid.task.bids.filter(status='pending').count()
            bid.task.save(update_fields=['bids_count'])
            
            return Response(
                {'message': 'Bid withdrawn successfully'},
                status=status.HTTP_200_OK
            )
        
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def counter_offer(self, request, pk=None):
        """
        Create a counter offer.
        Only task owner can create counter offers.
        """
        bid = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            counter_bid = bid.create_counter_offer(
                new_amount=serializer.validated_data['amount'],
                new_proposal=serializer.validated_data['proposal']
            )
            
            # Send notification to tasker
            BidNotification.objects.create(
                bid=counter_bid,
                recipient=bid.tasker,
                notification_type='counter_offer',
                message=f"You received a counter offer of ${counter_bid.amount} on '{bid.task.title}'"
            )
            
            response_serializer = BidDetailSerializer(counter_bid)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def my_bids(self, request):
        """Get current user's submitted bids."""
        bids = self.get_queryset().filter(tasker=request.user)
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            bids = bids.filter(status=status_filter)
        
        page = self.paginate_queryset(bids)
        if page is not None:
            serializer = BidListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = BidListSerializer(bids, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def received_bids(self, request):
        """Get bids received on user's tasks."""
        bids = self.get_queryset().filter(task__owner=request.user)
        
        # Apply filters
        task_id = request.query_params.get('task')
        if task_id:
            bids = bids.filter(task_id=task_id)
        
        status_filter = request.query_params.get('status')
        if status_filter:
            bids = bids.filter(status=status_filter)
        
        page = self.paginate_queryset(bids)
        if page is not None:
            serializer = BidListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = BidListSerializer(bids, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get bid statistics for current user."""
        user = request.user
        
        # Get bids based on user role
        if user.is_tasker:
            bids = Bid.objects.filter(tasker=user)
        else:
            bids = Bid.objects.filter(task__owner=user)
        
        # Calculate statistics
        stats = bids.aggregate(
            total_bids=Count('id'),
            pending_bids=Count('id', filter=Q(status='pending')),
            accepted_bids=Count('id', filter=Q(status='accepted')),
            rejected_bids=Count('id', filter=Q(status='rejected')),
            withdrawn_bids=Count('id', filter=Q(status='withdrawn')),
            average_bid_amount=Avg('amount'),
            total_bid_value=Sum('amount', filter=Q(status='accepted'))
        )
        
        # Calculate acceptance rate
        total = stats['total_bids'] or 1
        accepted = stats['accepted_bids'] or 0
        stats['acceptance_rate'] = round((accepted / total) * 100, 2)
        
        # Set defaults for None values
        stats['average_bid_amount'] = stats['average_bid_amount'] or 0
        stats['total_bid_value'] = stats['total_bid_value'] or 0
        
        serializer = self.get_serializer(stats)
        return Response(serializer.data)


class BidMessageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for bid messages/negotiations.
    
    Endpoints:
    - GET /bid-messages/ - List messages
    - POST /bid-messages/ - Send message
    - GET /bid-messages/{id}/ - Get message details
    - POST /bid-messages/{id}/mark_read/ - Mark as read
    """
    
    serializer_class = BidMessageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['bid', 'sender', 'is_read']
    ordering = ['created_at']
    
    def get_queryset(self):
        """Return messages for bids user is involved in."""
        user = self.request.user
        return BidMessage.objects.filter(
            Q(bid__tasker=user) | Q(bid__task__owner=user)
        ).select_related('bid', 'sender')
    
    def perform_create(self, serializer):
        """Create message and send notification."""
        message = serializer.save(sender=self.request.user)
        
        # Determine recipient (opposite party)
        recipient = (
            message.bid.task.owner
            if message.sender == message.bid.tasker
            else message.bid.tasker
        )
        
        # Send notification
        BidNotification.objects.create(
            bid=message.bid,
            recipient=recipient,
            notification_type='bid_message',
            message=f"New message from {message.sender.get_full_name()} on bid for '{message.bid.task.title}'"
        )
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark message as read."""
        message = self.get_object()
        message.mark_as_read()
        serializer = self.get_serializer(message)
        return Response(serializer.data)


class BidReviewViewSet(viewsets.ModelViewSet):
    """
    ViewSet for bid reviews.
    
    Endpoints:
    - GET /bid-reviews/ - List reviews
    - POST /bid-reviews/ - Create review
    - GET /bid-reviews/{id}/ - Get review details
    """
    
    serializer_class = BidReviewSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['bid', 'reviewer', 'rating']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return reviews for bids user is involved in."""
        user = self.request.user
        return BidReview.objects.filter(
            Q(bid__tasker=user) | Q(bid__task__owner=user)
        ).select_related('bid', 'reviewer')
    
    def perform_create(self, serializer):
        """Create review."""
        serializer.save(reviewer=self.request.user)


class BidNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for bid notifications.
    
    Endpoints:
    - GET /bid-notifications/ - List notifications
    - GET /bid-notifications/{id}/ - Get notification details
    - POST /bid-notifications/{id}/mark_read/ - Mark as read
    - POST /bid-notifications/mark_all_read/ - Mark all as read
    """
    
    serializer_class = BidNotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['notification_type', 'is_read']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return notifications for current user."""
        return BidNotification.objects.filter(
            recipient=self.request.user
        ).select_related('bid', 'bid__task', 'bid__tasker')
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark notification as read."""
        notification = self.get_object()
        notification.mark_as_read()
        serializer = self.get_serializer(notification)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read."""
        updated = self.get_queryset().filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return Response(
            {'message': f'{updated} notifications marked as read'},
            status=status.HTTP_200_OK
        )
