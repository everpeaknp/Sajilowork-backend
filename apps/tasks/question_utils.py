"""Shared helpers for listing Q&A."""
from rest_framework import status
from rest_framework.response import Response


def block_owner_asking_question(task, user):
    """Listing owners answer questions; they cannot ask on their own listing."""
    if task.owner_id == user.id:
        return Response(
            {'detail': 'You cannot ask questions on your own listing.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return None
