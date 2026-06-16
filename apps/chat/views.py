"""
Chat views for API endpoints.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Q, Count, Max
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter

from .models import (
    Conversation, Message, TypingIndicator,
    MessageReaction, ConversationMute, MessageReport
)
from .serializers import (
    ConversationSerializer, ConversationCreateSerializer, ConversationDetailSerializer,
    MessageSerializer, MessageBriefSerializer, MessageCreateSerializer, MessageUpdateSerializer,
    TypingIndicatorSerializer, MessageReactionSerializer, MessageReactionCreateSerializer,
    ConversationMuteSerializer, MessageReportSerializer, MessageReportCreateSerializer
)
from .permissions import IsConversationParticipant, IsMessageSender
from .realtime import broadcast_chat_message


@extend_schema_view(
    list=extend_schema(
        tags=['Chat'],
        summary='List conversations',
        parameters=[
            OpenApiParameter('view', str, description='employer or tasker inbox filter'),
            OpenApiParameter('archived', bool, description='Include archived threads'),
            OpenApiParameter('task', str, description='Filter by task UUID'),
            OpenApiParameter('bid', str, description='Filter by bid UUID'),
        ],
    ),
    retrieve=extend_schema(tags=['Chat'], summary='Get conversation details'),
    create=extend_schema(tags=['Chat'], summary='Create or resolve conversation'),
)
class ConversationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing conversations.
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Get conversations for current user."""
        user = self.request.user
        queryset = Conversation.objects.filter(
            participants=user,
            is_active=True
        ).select_related('task', 'task__owner', 'bid', 'bid__task', 'bid__task__owner').prefetch_related('participants')
        
        # Filter by archived status
        is_archived = self.request.query_params.get('archived', 'false').lower() == 'true'
        queryset = queryset.filter(is_archived=is_archived)

        view = (self.request.query_params.get('view') or '').strip().lower()
        direct_threads = Q(task__isnull=True, bid__isnull=True)
        if view in ('employer', 'customer', 'received'):
            queryset = queryset.filter(
                Q(task__owner=user) | Q(bid__task__owner=user) | direct_threads,
            )
        elif view in ('tasker', 'freelancer', 'asked'):
            queryset = queryset.filter(
                direct_threads
                | (~Q(task__owner=user) & ~Q(bid__task__owner=user))
            )
        
        # Filter by task or bid
        task_id = self.request.query_params.get('task')
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        
        bid_id = self.request.query_params.get('bid')
        if bid_id:
            queryset = queryset.filter(bid_id=bid_id)
        
        return queryset.distinct()
    
    def get_serializer_class(self):
        """Return appropriate serializer class."""
        if self.action == 'create':
            return ConversationCreateSerializer
        elif self.action == 'retrieve':
            return ConversationDetailSerializer
        return ConversationSerializer
    
    def perform_create(self, serializer):
        """Create conversation."""
        serializer.save()
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """Mark all messages in conversation as read."""
        conversation = self.get_object()
        conversation.mark_as_read(request.user)
        return Response({'status': 'messages marked as read'})

    @extend_schema(tags=['Chat'], summary='List or send messages in conversation')
    @action(detail=True, methods=['get', 'post'], url_path='messages')
    def messages(self, request, pk=None):
        """List or create messages in this conversation."""
        conversation = self.get_object()

        if request.method == 'GET':
            queryset = Message.objects.filter(
                conversation=conversation,
                is_deleted=False,
            ).select_related('sender').order_by('-created_at')

            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = MessageBriefSerializer(
                    reversed(page), many=True, context={'request': request}
                )
                return self.get_paginated_response(serializer.data)

            serializer = MessageBriefSerializer(
                reversed(list(queryset)), many=True, context={'request': request}
            )
            return Response(serializer.data)

        payload = {**request.data, 'conversation': str(conversation.id)}
        serializer = MessageCreateSerializer(data=payload, context={'request': request})
        serializer.is_valid(raise_exception=True)
        message = serializer.save()
        output = MessageBriefSerializer(message, context={'request': request})
        data = output.data
        broadcast_chat_message(str(conversation.id), data)
        return Response(data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive conversation."""
        conversation = self.get_object()
        conversation.is_archived = True
        conversation.save(update_fields=['is_archived'])
        return Response({'status': 'conversation archived'})
    
    @action(detail=True, methods=['post'])
    def unarchive(self, request, pk=None):
        """Unarchive conversation."""
        conversation = self.get_object()
        conversation.is_archived = False
        conversation.save(update_fields=['is_archived'])
        return Response({'status': 'conversation unarchived'})
    
    @extend_schema(tags=['Chat'], summary='Total unread message count')
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get total unread message count across all conversations."""
        user = request.user
        total_unread = Message.objects.filter(
            conversation__participants=user,
            is_read=False,
            is_deleted=False
        ).exclude(sender=user).count()
        
        return Response({'unread_count': total_unread})


@extend_schema_view(
    list=extend_schema(tags=['Chat'], summary='List messages'),
    create=extend_schema(tags=['Chat'], summary='Send a message'),
)
class MessageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing messages.
    """
    permission_classes = [IsAuthenticated, IsConversationParticipant]
    
    def get_queryset(self):
        """Get messages for current user's conversations."""
        user = self.request.user
        queryset = Message.objects.filter(
            conversation__participants=user,
            is_deleted=False
        ).select_related('sender', 'conversation', 'reply_to')
        
        # Filter by conversation
        conversation_id = self.request.query_params.get('conversation')
        if conversation_id:
            queryset = queryset.filter(conversation_id=conversation_id)
        
        # Filter by message type
        message_type = self.request.query_params.get('type')
        if message_type:
            queryset = queryset.filter(message_type=message_type)
        
        # Filter unread messages
        unread_only = self.request.query_params.get('unread', 'false').lower() == 'true'
        if unread_only:
            queryset = queryset.filter(is_read=False).exclude(sender=user)
        
        return queryset.order_by('created_at')
    
    def get_serializer_class(self):
        """Return appropriate serializer class."""
        if self.action == 'create':
            return MessageCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return MessageUpdateSerializer
        return MessageSerializer
    
    def perform_create(self, serializer):
        """Create message and broadcast to WebSocket subscribers."""
        message = serializer.save()
        output = MessageBriefSerializer(message, context={'request': self.request})
        broadcast_chat_message(str(message.conversation_id), output.data)
    
    def perform_update(self, serializer):
        """Update message (only sender can edit)."""
        if serializer.instance.sender != self.request.user:
            raise PermissionError("You can only edit your own messages.")
        serializer.save()
    
    def perform_destroy(self, instance):
        """Soft delete message."""
        if instance.sender != self.request.user:
            raise PermissionError("You can only delete your own messages.")
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted'])
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """Mark message as read."""
        message = self.get_object()
        if message.sender != request.user:
            message.mark_as_read()
        return Response({'status': 'message marked as read'})
    
    @action(detail=True, methods=['post'])
    def react(self, request, pk=None):
        """Add reaction to message."""
        message = self.get_object()
        serializer = MessageReactionCreateSerializer(
            data={'message': message.id, 'reaction_type': request.data.get('reaction_type')},
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['delete'])
    def remove_reaction(self, request, pk=None):
        """Remove reaction from message."""
        message = self.get_object()
        reaction_type = request.data.get('reaction_type')
        
        MessageReaction.objects.filter(
            message=message,
            user=request.user,
            reaction_type=reaction_type
        ).delete()
        
        return Response({'status': 'reaction removed'})
    
    @action(detail=True, methods=['post'])
    def report(self, request, pk=None):
        """Report message."""
        message = self.get_object()
        serializer = MessageReportCreateSerializer(
            data={**request.data, 'message': message.id},
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TypingIndicatorViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing typing indicators.
    """
    permission_classes = [IsAuthenticated, IsConversationParticipant]
    serializer_class = TypingIndicatorSerializer
    http_method_names = ['get', 'post', 'delete']
    
    def get_queryset(self):
        """Get typing indicators for user's conversations."""
        user = self.request.user
        queryset = TypingIndicator.objects.filter(
            conversation__participants=user
        ).select_related('user', 'conversation')
        
        # Filter by conversation
        conversation_id = self.request.query_params.get('conversation')
        if conversation_id:
            queryset = queryset.filter(conversation_id=conversation_id)
        
        # Remove stale indicators (older than 10 seconds)
        stale_time = timezone.now() - timezone.timedelta(seconds=10)
        queryset = queryset.filter(started_at__gte=stale_time)
        
        return queryset
    
    def perform_create(self, serializer):
        """Create or update typing indicator."""
        conversation = serializer.validated_data['conversation']
        user = self.request.user
        
        # Update or create typing indicator
        TypingIndicator.objects.update_or_create(
            conversation=conversation,
            user=user,
            defaults={'started_at': timezone.now()}
        )
    
    def perform_destroy(self, instance):
        """Remove typing indicator."""
        if instance.user == self.request.user:
            instance.delete()


class ConversationMuteViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing conversation mutes.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ConversationMuteSerializer
    http_method_names = ['get', 'post', 'delete']
    
    def get_queryset(self):
        """Get mutes for current user."""
        return ConversationMute.objects.filter(
            user=self.request.user
        ).select_related('conversation')
    
    def perform_create(self, serializer):
        """Create conversation mute."""
        serializer.save(user=self.request.user)
    
    def perform_destroy(self, instance):
        """Remove conversation mute."""
        if instance.user == self.request.user:
            instance.delete()


class MessageReportViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing message reports (admin only).
    """
    permission_classes = [IsAuthenticated]
    serializer_class = MessageReportSerializer
    
    def get_queryset(self):
        """Get message reports."""
        user = self.request.user
        
        # Only admins can view all reports
        if user.role == 'admin':
            queryset = MessageReport.objects.all()
        else:
            # Users can only see their own reports
            queryset = MessageReport.objects.filter(reported_by=user)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.select_related('message', 'reported_by', 'reviewed_by')
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def review(self, request, pk=None):
        """Review a message report (admin only)."""
        if request.user.role != 'admin':
            return Response(
                {'error': 'Only admins can review reports'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        report = self.get_object()
        report.status = request.data.get('status', 'reviewed')
        report.admin_notes = request.data.get('admin_notes', '')
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.save()
        
        serializer = self.get_serializer(report)
        return Response(serializer.data)
