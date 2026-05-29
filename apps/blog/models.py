import uuid

from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class BlogPost(models.Model):
    """Marketing / tips articles shown on the landing page."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=200, unique=True)
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=100, help_text='Display label, e.g. Cleaning')
    excerpt = models.TextField(help_text='Short summary for cards')
    content = models.TextField(
        blank=True,
        help_text='Full article body (HTML). Shown on the public blog post page.',
    )
    image = models.ImageField(upload_to='blog/', blank=True, null=True)
    image_url = models.URLField(
        max_length=500,
        blank=True,
        help_text='External image URL when no uploaded image',
    )
    link_url = models.URLField(
        max_length=500,
        blank=True,
        help_text='Optional link when the card is clicked',
    )
    is_published = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Show on the home page blog section',
    )
    sort_order = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', '-published_at']
        indexes = [
            models.Index(fields=['is_published', 'is_featured', 'sort_order']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:180] or 'post'
            slug = base
            counter = 1
            while BlogPost.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)
