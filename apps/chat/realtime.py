"""
Broadcast chat events to WebSocket subscribers.
"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def broadcast_chat_message(conversation_id, message_payload: dict) -> None:
    """Push a new message to everyone in the conversation room."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    try:
        async_to_sync(channel_layer.group_send)(
            f'chat_{conversation_id}',
            {
                'type': 'chat_message',
                'message': message_payload,
            },
        )
    except Exception as exc:
        logger.warning('Failed to broadcast chat message: %s', exc)
