from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import BlogPost
from .serializers import BlogPostDetailSerializer, BlogPostListSerializer


class BlogPostViewSet(viewsets.ReadOnlyModelViewSet):
    """Public read-only blog posts for marketing pages."""

    permission_classes = [AllowAny]
    lookup_field = 'slug'

    def get_queryset(self):
        return BlogPost.objects.filter(is_published=True)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return BlogPostDetailSerializer
        return BlogPostListSerializer

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Posts for the landing page blog section."""
        try:
            limit = int(request.query_params.get('limit', 3))
        except (TypeError, ValueError):
            limit = 3
        limit = max(1, min(limit, 12))

        posts = (
            self.get_queryset()
            .filter(is_featured=True)
            .order_by('sort_order', '-published_at')[:limit]
        )
        if not posts.exists():
            posts = self.get_queryset().order_by('sort_order', '-published_at')[:limit]

        serializer = BlogPostListSerializer(
            posts, many=True, context={'request': request}
        )
        return Response(serializer.data)
