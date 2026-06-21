from rest_framework import serializers

from apps.tasks.listing import LISTING_KIND_CATEGORY_CHOICES

from .models import LISTING_SKILL_KINDS, Skill


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = [
            'id',
            'name',
            'slug',
            'listing_kind',
            'description',
            'is_active',
            'order',
        ]
        read_only_fields = fields


class SkillCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, trim_whitespace=True)
    listing_kind = serializers.ChoiceField(choices=LISTING_SKILL_KINDS)

    def validate_name(self, value):
        name = ' '.join((value or '').split())
        if not name:
            raise serializers.ValidationError('Skill name is required.')
        if len(name) < 2:
            raise serializers.ValidationError('Skill name must be at least 2 characters.')
        return name

    def validate_listing_kind(self, value):
        if value not in LISTING_SKILL_KINDS:
            raise serializers.ValidationError('Invalid listing type for this skill.')
        allowed = {choice[0] for choice in LISTING_KIND_CATEGORY_CHOICES}
        if value not in allowed:
            raise serializers.ValidationError('Invalid listing type for this skill.')
        return value
