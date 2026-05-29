from rest_framework import serializers

from .models import Dispute, DisputeEvidence, DisputeMessage


class DisputeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dispute
        fields = [
            'id', 'task', 'raised_by', 'against', 'dispute_type', 'title', 'description',
            'status', 'resolution', 'resolution_notes', 'created_at', 'updated_at', 'resolved_at',
        ]
        read_only_fields = ['id', 'raised_by', 'status', 'resolution', 'resolved_at', 'created_at', 'updated_at']


class DisputeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dispute
        fields = ['task', 'against', 'dispute_type', 'title', 'description']
