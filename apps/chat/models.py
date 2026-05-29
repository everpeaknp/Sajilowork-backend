"""
Chat models for real-time messaging.
"""
from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
import uuid


class Conversation(models.Model):
    """
    Conversation between users (typically related to a task/bid).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey('tasks.Task', on_delete=models.CASCADE, related_name='conversations', null=True, blank=True)
    bid = models.ForeignKey('bids.Bid', on_delete=models.CASCADE, related_name='conversations', null=True, blank=True)
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='conversations')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'chat_conversations'
        ordering = ['-last_message_at', '-created_at']
        indexes = [
            models.Index(fields=['-last_message_at']),
            models.Index(fields=['task', 'is_active']),
            models.Index(fields=['bid', 'is_active']),
        ]
    
    def __str__(self):
        return f"Conversation {self.id}"
    
    def get_other_participant(self, user):
        """Get the other participant in a 2-person conversation."""
        return self.participants.exclude(id=user.id).first()
    
    def mark_as_read(self, user):
        """Mark all messages as read for a user."""
        self.messages.filter(is_read=False).exclude(sender=user).update(is_read=True)
    
    def get_unread_count(self, user):
        """Get unread message count for a user."""
        return self.messages.filter(is_read=False).exclude(sender=user).count()


class Message(models.Model):
    """
    Individual message in a conversation.
    """
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
        ('system', 'System'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    
    # Content
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    content = models.TextField()
    
    # Attachments
    attachment = models.FileField(
        upload_to='chat/attachments/%Y/%m/%d/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'txt'])]
    )
    attachment_name = models.CharField(max_length=255, blank=True)
    attachment_size = models.IntegerField(null=True, blank=True)  # in bytes
    
    # Status
    is_read = models.BooleanField(default=False)
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Reply to message
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    
    class Meta:
        db_table = 'chat_messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['sender', 'created_at']),
            models.Index(fields=['conversation', 'is_read']),
        ]
    
    def __str__(self):
        return f"Message from {self.sender.get_full_name()} at {self.created_at}"
    
    def mark_as_read(self):
        """Mark message as read."""
        if not self.is_read:
            self.is_read = True
            from django.utils import timezone
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


class TypingIndicator(models.Model):
    """
    Track who is currently typing in a conversation.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='typing_indicators')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='typing_in')
    
    # Metadata
    started_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'chat_typing_indicators'
        unique_together = ['conversation', 'user']
        indexes = [
            models.Index(fields=['conversation', 'started_at']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} typing in {self.conversation.id}"


class MessageReaction(models.Model):
    """
    Reactions to messages (emoji reactions).
    """
    REACTION_TYPES = [
        ('like', '👍'),
        ('love', '❤️'),
        ('laugh', '😂'),
        ('wow', '😮'),
        ('sad', '😢'),
        ('angry', '😠'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='message_reactions')
    reaction_type = models.CharField(max_length=20, choices=REACTION_TYPES)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chat_message_reactions'
        unique_together = ['message', 'user', 'reaction_type']
        indexes = [
            models.Index(fields=['message', 'reaction_type']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} reacted {self.get_reaction_type_display()} to message {self.message.id}"


class ConversationMute(models.Model):
    """
    Mute notifications for a conversation.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='mutes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='muted_conversations')
    
    # Mute settings
    muted_until = models.DateTimeField(null=True, blank=True)  # None = muted forever
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chat_conversation_mutes'
        unique_together = ['conversation', 'user']
        indexes = [
            models.Index(fields=['user', 'muted_until']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} muted {self.conversation.id}"
    
    def is_muted(self):
        """Check if conversation is currently muted."""
        if self.muted_until is None:
            return True
        from django.utils import timezone
        return timezone.now() < self.muted_until


class MessageReport(models.Model):
    """
    Report inappropriate messages.
    """
    REPORT_REASONS = [
        ('spam', 'Spam'),
        ('harassment', 'Harassment'),
        ('inappropriate', 'Inappropriate Content'),
        ('scam', 'Scam'),
        ('other', 'Other'),
    ]
    
    REPORT_STATUSES = [
        ('pending', 'Pending'),
        ('reviewed', 'Reviewed'),
        ('action_taken', 'Action Taken'),
        ('dismissed', 'Dismissed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reports')
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='message_reports')
    
    # Report details
    reason = models.CharField(max_length=50, choices=REPORT_REASONS)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=REPORT_STATUSES, default='pending')
    
    # Admin action
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_message_reports'
    )
    admin_notes = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'chat_message_reports'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['reported_by', '-created_at']),
        ]
    
    def __str__(self):
        return f"Report by {self.reported_by.get_full_name()} - {self.reason}"
