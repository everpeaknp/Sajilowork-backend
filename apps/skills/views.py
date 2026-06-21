from django.db import IntegrityError
from django.utils.text import slugify
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Skill
from .serializers import SkillCreateSerializer, SkillSerializer


def _unique_slug(base: str, listing_kind: str) -> str:
    slug = slugify(base)[:100] or 'skill'
    candidate = slug
    counter = 1
    while Skill.objects.filter(slug=candidate, listing_kind=listing_kind).exists():
        suffix = f'-{counter}'
        candidate = f'{slug[: 100 - len(suffix)]}{suffix}'
        counter += 1
    return candidate


class SkillViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Public skill taxonomy for dashboard listings."""

    serializer_class = SkillSerializer
    lookup_field = 'slug'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['listing_kind', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['order', 'name']
    ordering = ['order', 'name']

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        return Skill.objects.filter(is_active=True)

    def create(self, request, *args, **kwargs):
        serializer = SkillCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        name = serializer.validated_data['name']
        listing_kind = serializer.validated_data['listing_kind']

        existing = Skill.objects.filter(name__iexact=name, listing_kind=listing_kind).first()
        if existing:
            if not existing.is_active:
                existing.is_active = True
                existing.save(update_fields=['is_active'])
            return Response(
                SkillSerializer(existing, context=self.get_serializer_context()).data,
                status=status.HTTP_200_OK,
            )

        slug = _unique_slug(name, listing_kind)
        try:
            skill = Skill.objects.create(
                name=name,
                slug=slug,
                listing_kind=listing_kind,
                is_active=True,
                order=0,
            )
        except IntegrityError:
            existing = Skill.objects.filter(name__iexact=name, listing_kind=listing_kind).first()
            if existing:
                return Response(
                    SkillSerializer(existing, context=self.get_serializer_context()).data,
                    status=status.HTTP_200_OK,
                )
            raise

        return Response(
            SkillSerializer(skill, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )
