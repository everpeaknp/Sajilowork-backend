from django import forms


class TinyMCEWidget(forms.Textarea):
    """Rich text editor for blog post body (TinyMCE via CDN in admin)."""

    class Media:
        js = (
            'https://cdn.jsdelivr.net/npm/tinymce@6.8.5/tinymce.min.js',
            'blog/js/tinymce_init.js',
        )

    def __init__(self, attrs=None):
        default_attrs = {
            'class': 'tinymce-editor',
            'rows': 24,
            'cols': 80,
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)
