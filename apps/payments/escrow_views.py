"""Escrow payment API — initiate, verify, release, refund, status."""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.shortcuts import get_object_or_404

from apps.bids.models import Bid
from apps.tasks.models import Task

from .escrow_lifecycle import EscrowLifecycleError, EscrowLifecycleService
from .escrow_serializers import (
    EscrowInitiateSerializer,
    EscrowRefundSerializer,
    EscrowReleaseSerializer,
    EscrowVerifySerializer,
)


class EscrowInitiateAPIView(APIView):
    """POST /api/v1/payments/initiate/ — start eSewa/Khalti escrow funding."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = EscrowInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        bid = get_object_or_404(Bid.objects.select_related('task', 'tasker'), id=data['bid_id'])
        provider = data['provider']

        if provider == 'wallet':
            return Response(
                {
                    'message': (
                        'Wallet escrow is created automatically when you accept a bid. '
                        'Ensure sufficient wallet balance before acceptance.'
                    ),
                    'use_bid_accept': True,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = EscrowLifecycleService.create_pending_gateway_escrow(
                bid=bid,
                payer=request.user,
                provider=provider,
                idempotency_key=data['idempotency_key'],
                success_url=data['success_url'],
                failure_url=data['failure_url'],
            )
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_201_CREATED)


class EscrowVerifyAPIView(APIView):
    """POST /api/v1/payments/verify/ — verify gateway callback and fund escrow."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = EscrowVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            result = EscrowLifecycleService.verify_gateway_and_fund(
                payer=request.user,
                transaction_id=data['transaction_id'],
                provider=data['provider'],
                pidx=data.get('pidx'),
                idempotency_key=data.get('idempotency_key'),
            )
        except Exception as exc:
            return Response(
                {'verified': False, 'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(result)


class EscrowReleaseAPIView(APIView):
    """POST /api/v1/payments/escrow/release/ — release after completion."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = EscrowReleaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = get_object_or_404(Task, id=serializer.validated_data['task_id'])

        if task.owner != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Only the task owner or staff can release escrow.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            if task.status == 'completed':
                payment = EscrowLifecycleService.release_escrow_for_completed_task(
                    task, actor=request.user
                )
                if payment is None:
                    return Response(
                        {'error': 'No held payment found for this task.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                payment = EscrowLifecycleService.release_escrow(
                    task,
                    actor=request.user,
                    force=serializer.validated_data.get('force', False),
                )
        except EscrowLifecycleError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success': True,
            'payment_id': str(payment.id),
            'status': payment.status,
            'net_amount': str(payment.net_amount),
            'platform_fee': str(payment.platform_fee),
            'escrow': EscrowLifecycleService.get_status_payload(task.id),
        })


class EscrowRefundAPIView(APIView):
    """POST /api/v1/payments/escrow/refund/ — refund/cancel escrow."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = EscrowRefundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = get_object_or_404(Task, id=serializer.validated_data['task_id'])

        if task.owner != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Only the task owner or staff can request escrow refund.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            result = EscrowLifecycleService.refund_escrow(
                task,
                reason=serializer.validated_data.get('reason', ''),
                actor=request.user,
            )
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': True, 'result': result})


class EscrowStatusAPIView(APIView):
    """GET /api/v1/payments/escrow/status/<task_id>/"""

    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        task = get_object_or_404(Task, id=task_id)
        if task.owner != request.user and task.assigned_tasker != request.user:
            if not request.user.is_staff:
                return Response(
                    {'error': 'Not a participant on this task.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
        return Response(EscrowLifecycleService.get_status_payload(task_id))
