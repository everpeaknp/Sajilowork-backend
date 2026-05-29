"""
Chat serializers for API responses.
"""
from django.db.models import Count
from rest_framework import serializers
from django.utils import timezone
from .models import (
    Conversation, Message, TypingIndicator,
    MessageReaction, ConversationMute, MessageReport
)
from apps.users.serializers import UserListSerializer
from .messaging_policy import conversation_allows_messaging, get_conversation_task, task_allows_messaging


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message model."""
    sender = UserListSerializer(read_only=True)
    reply_to_message = serializers.SerializerMethodField()
    reactions_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'sender', 'message_type', 'content',
            'attachment', 'attachment_name', 'attachment_size',
            'is_read', 'is_edited', 'is_deleted', 'created_at', 'updated_at',
            'read_at', 'reply_to', 'reply_to_message', 'reactions_count'
        ]
        read_only_fields = ['id', 'sender', 'is_read', 'is_edited', 'created_at', 'updated_at', 'read_at']
    
    def get_reply_to_message(self, obj):
        """Get basic info about the message being replied to."""
        if obj.reply_to:
            return {
                'id': str(obj.reply_to.id),
                'sender': obj.reply_to.sender.get_full_name(),
                'content': obj.reply_to.content[:100],  # First 100 chars
                'created_at': obj.reply_to.created_at
            }
        return None
    
    def get_reactions_count(self, obj):
        """Get count of each reaction type."""
        reactions = obj.reactions.values('reaction_type').annotate(
            count=Count('id')
        )
        return {r['reaction_type']: r['count'] for r in reactions}


class MessageBriefSerializer(serializers.ModelSerializer):
    """Lightweight message payload for list/create (avoids per-message reaction queries)."""
    sender = UserListSerializer(read_only=True)

    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'sender', 'message_type', 'content',
            'is_read', 'created_at',
        ]
        read_only_fields = ['id', 'sender', 'is_read', 'created_at']


class MessageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating messages."""
    
    class Meta:
        model = Message
        fields = ['conversation', 'message_type', 'content', 'attachment', 'reply_to']
    
    def validate_conversation(self, value):
        """Ensure user is a participant in the conversation."""
        user = self.context['request'].user
        if not value.participants.filter(id=user.id).only('id').exists():
            raise serializers.ValidationError("You are not a participant in this conversation.")

        allowed, error_message = conversation_allows_messaging(value)
        if not allowed:
            raise serializers.ValidationError(
                error_message or 'Messaging is not available for this task.'
            )
        return value
    
    def validate(self, data):
        """Validate message content based on type."""
        message_type = data.get('message_type', 'text')
        content = data.get('content', '')
        attachment = data.get('attachment')
        
        if message_type == 'text' and not content.strip():
            raise serializers.ValidationError("Text messages must have content.")
        
        if message_type in ['image', 'file'] and not attachment:
            raise serializers.ValidationError(f"{message_type.title()} messages must have an attachment.")
        
        return data
    
    def create(self, validated_data):
        """Create message and update conversation."""
        validated_data['sender'] = self.context['request'].user
        
        # Handle attachment metadata
        if validated_data.get('attachment'):
            attachment = validated_data['attachment']
            validated_data['attachment_name'] = attachment.name
            validated_data['attachment_size'] = attachment.size
        
        message = super().create(validated_data)
        
        # Update conversation's last_message_at
        conversation = message.conversation
        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=['last_message_at'])
        
        return message


class MessageUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating messages (editing)."""
    
    class Meta:
        model = Message
        fields = ['content']
    
    def update(self, instance, validated_data):
        """Update message and mark as edited."""
        instance.content = validated_data.get('content', instance.content)
        instance.is_edited = True
        instance.save()
        return instance


class ConversationSerializer(serializers.ModelSerializer):
    """Serializer for Conversation model."""
    participants = UserListSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    other_participant = serializers.SerializerMethodField()
    task_status = serializers.SerializerMethodField()
    messaging_enabled = serializers.SerializerMethodField()
    task_title = serializers.SerializerMethodField()
    task_slug = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'task', 'bid', 'participants', 'created_at', 'updated_at',
            'last_message_at', 'is_active', 'is_archived', 'last_message',
            'unread_count', 'other_participant', 'task_status', 'messaging_enabled',
            'task_title', 'task_slug',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_message_at']
    
    def get_last_message(self, obj):
        """Get the last message in the conversation."""
        last_message = obj.messages.filter(is_deleted=False).last()
        if last_message:
            return {
                'id': str(last_message.id),
                'sender': last_message.sender.get_full_name(),
                'content': last_message.content[:100],  # First 100 chars
                'message_type': last_message.message_type,
                'created_at': last_message.created_at,
                'is_read': last_message.is_read
            }
        return None
    
    def get_unread_count(self, obj):
        """Get unread message count for current user."""
        user = self.context['request'].user
        return obj.get_unread_count(user)
    
    def get_other_participant(self, obj):
        """Get the other participant in a 2-person conversation."""
        user = self.context['request'].user
        other = obj.get_other_participant(user)
        if other:
            return UserListSerializer(other, context=self.context).data
        return None

    def get_task_status(self, obj):
        task = get_conversation_task(obj)
        return task.status if task else None

    def get_messaging_enabled(self, obj):
        allowed, _ = conversation_allows_messaging(obj)
        return allowed

    def get_task_title(self, obj):
        task = get_conversation_task(obj)
        return task.title if task else None

    def get_task_slug(self, obj):
        task = get_conversation_task(obj)
        return task.slug if task else None


class ConversationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating conversations."""
    participant_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Conversation
        fields = ['task', 'bid', 'participant_ids']
    
    def validate(self, data):
        """Validate conversation creation."""
        task = data.get('task')
        bid = data.get('bid')
        
        if not task and not bid:
            raise serializers.ValidationError("Conversation must be related to a task or bid.")
        
        if task and bid:
            raise serializers.ValidationError("Conversation cannot be related to both task and bid.")

        resolved_task = task
        if bid is not None and resolved_task is None:
            from apps.bids.models import Bid

            bid_obj = bid if hasattr(bid, 'task_id') else Bid.objects.select_related('task').get(pk=bid)
            resolved_task = bid_obj.task

        allowed, error_message = task_allows_messaging(resolved_task)
        if not allowed:
            raise serializers.ValidationError(
                error_message or 'Messaging is not available for this task.'
            )
        
        return data
    
    def create(self, validated_data):
        """Create conversation with participants (reuse existing thread when possible)."""
        from apps.users.models import User
        from .conversation_resolver import get_or_create_conversation

        participant_ids = list(validated_data.pop('participant_ids', []))
        creator = self.context['request'].user
        task = validated_data.get('task')
        bid = validated_data.get('bid')

        other_users = list(User.objects.filter(id__in=participant_ids))
        conversation, _created = get_or_create_conversation(
            task=task,
            bid=bid,
            participant_users=[creator, *other_users],
        )
        return conversation


class TypingIndicatorSerializer(serializers.ModelSerializer):
    """Serializer for TypingIndicator model."""
    user = UserListSerializer(read_only=True)
    
    class Meta:
        model = TypingIndicator
        fields = ['id', 'conversation', 'user', 'started_at']
        read_only_fields = ['id', 'user', 'started_at']


class MessageReactionSerializer(serializers.ModelSerializer):
    """Serializer for MessageReaction model."""
    user = UserListSerializer(read_only=True)
    
    class Meta:
        model = MessageReaction
        fields = ['id', 'message', 'user', 'reaction_type', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']


class MessageReactionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating message reactions."""
    
    class Meta:
        model = MessageReaction
        fields = ['message', 'reaction_type']
    
    def create(self, validated_data):
        """Create or update reaction."""
        validated_data['user'] = self.context['request'].user
        
        # Remove existing reaction of same type if exists
        MessageReaction.objects.filter(
            message=validated_data['message'],
            user=validated_data['user'],
            reaction_type=validated_data['reaction_type']
        ).delete()
        
        return super().create(validated_data)


class ConversationMuteSerializer(serializers.ModelSerializer):
    """Serializer for ConversationMute model."""
    
    class Meta:
        model = ConversationMute
        fields = ['id', 'conversation', 'muted_until', 'created_at']
        read_only_fields = ['id', 'created_at']


class MessageReportSerializer(serializers.ModelSerializer):
    """Serializer for MessageReport model."""
    reported_by = UserListSerializer(read_only=True)
    reviewed_by = UserListSerializer(read_only=True)
    
    class Meta:
        model = MessageReport
        fields = [
            'id', 'message', 'reported_by', 'reason', 'description',
            'status', 'reviewed_by', 'admin_notes', 'created_at', 'reviewed_at'
        ]
        read_only_fields = ['id', 'reported_by', 'status', 'reviewed_by', 'admin_notes', 'created_at', 'reviewed_at']


class MessageReportCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating message reports."""
    
    class Meta:
        model = MessageReport
        fields = ['message', 'reason', 'description']
    
    def validate_message(self, value):
        """Ensure user hasn't already reported this message."""
        user = self.context['request'].user
        if MessageReport.objects.filter(message=value, reported_by=user).exists():
            raise serializers.ValidationError("You have already reported this message.")
        return value
    
    def create(self, validated_data):
        """Create message report."""
        validated_data['reported_by'] = self.context['request'].user
        return super().create(validated_data)


class ConversationDetailSerializer(ConversationSerializer):
    """Detailed conversation serializer with recent messages."""
    recent_messages = serializers.SerializerMethodField()
    
    class Meta(ConversationSerializer.Meta):
        fields = ConversationSerializer.Meta.fields + ['recent_messages']

    def get_task_slug(self, obj):
        """Resolve on detail serializer so DRF always finds the method after hot-reload."""
        task = get_conversation_task(obj)
        return task.slug if task else None
    
    def get_recent_messages(self, obj):
        """Get recent messages (last 50)."""
        messages = obj.messages.filter(is_deleted=False).order_by('-created_at')[:50]
        return MessageSerializer(messages, many=True, context=self.context).data
