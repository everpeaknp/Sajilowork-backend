from django.db import models
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from .models import Dispute
from .serializers import DisputeCreateSerializer, DisputeSerializer
from .services import DisputeService


class DisputeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Dispute.objects.select_related('task', 'raised_by', 'against').all()

    def get_serializer_class(self):
        if self.action == 'create':
            return DisputeCreateSerializer
        return DisputeSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return self.queryset
        return self.queryset.filter(
            models.Q(raised_by=user) | models.Q(against=user)
        )

    def create(self, request, *args, **kwargs):
        serializer = DisputeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = serializer.validated_data['task']
        if task.owner != request.user and task.assigned_tasker != request.user:
            return Response({'error': 'Not a party to this task.'}, status=status.HTTP_403_FORBIDDEN)

        against = serializer.validated_data['against']
        dispute = DisputeService.open_dispute(
            task=task,
            raised_by=request.user,
            against=against,
            dispute_type=serializer.validated_data['dispute_type'],
            title=serializer.validated_data['title'],
            description=serializer.validated_data['description'],
        )
        return Response(DisputeSerializer(dispute).data, status=status.HTTP_201_CREATED)
