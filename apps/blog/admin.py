from django import forms
from django.contrib import admin

from .models import BlogPost
from .widgets import TinyMCEWidget


class BlogPostAdminForm(forms.ModelForm):
    class Meta:
        model = BlogPost
        fields = '__all__'
        widgets = {
            'content': TinyMCEWidget(),
            'excerpt': forms.Textarea(attrs={'rows': 3}),
        }


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    form = BlogPostAdminForm
    list_display = (
        'title',
        'category',
        'is_published',
        'is_featured',
        'sort_order',
        'published_at',
    )
    list_filter = ('is_published', 'is_featured', 'category')
    search_fields = ('title', 'slug', 'category', 'excerpt', 'content')
    prepopulated_fields = {'slug': ('title',)}
    ordering = ('sort_order', '-published_at')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (
            None,
            {
                'fields': (
                    'title',
                    'slug',
                    'category',
                    'excerpt',
                ),
            },
        ),
        (
            'Article body',
            {
                'fields': ('content',),
                'description': 'Use the editor for headings, lists, images, and links.',
            },
        ),
        (
            'Cover image',
            {
                'fields': ('image', 'image_url'),
            },
        ),
        (
            'Publishing',
            {
                'fields': (
                    'is_published',
                    'is_featured',
                    'sort_order',
                    'published_at',
                    'link_url',
                ),
                'description': (
                    'Leave “External link URL” empty to use the on-site page at '
                    '/blog/your-slug/. Set it only to send readers to an external site.'
                ),
            },
        ),
        (
            'Timestamps',
            {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',),
            },
        ),
    )
