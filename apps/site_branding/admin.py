from django import forms
from django.contrib import admin
from django.contrib.sites.admin import SiteAdmin as DjangoSiteAdmin
from django.contrib.sites.models import Site
from django.utils.html import format_html

from apps.uploads.cloudinary_folders import cloudinary_site_favicon_folder, cloudinary_site_og_folder
from apps.uploads.cloudinary_utils import (
    cloudinary_server_upload_enabled,
    infer_cloudinary_resource_type,
    is_cloudinary_permission_error,
    upload_file_to_cloudinary,
)

from apps.site_branding.services import (
    PLACEHOLDER_SITE_DOMAINS,
    PLACEHOLDER_SITE_NAMES,
    resolve_public_site_domain,
    resolve_public_site_name,
)

from .models import SiteBranding


def _upload_image_to_cloudinary(uploaded_file, *, folder: str, field_label: str) -> str:
    try:
        result = upload_file_to_cloudinary(
            uploaded_file,
            folder=folder,
            resource_type=infer_cloudinary_resource_type(uploaded_file),
        )
    except Exception as exc:
        if is_cloudinary_permission_error(exc):
            raise forms.ValidationError(
                f'Cloudinary rejected the {field_label} upload. Ensure your API key has upload '
                'permission, or set CLOUDINARY_UPLOAD_PRESET.'
            ) from exc
        raise forms.ValidationError(f'{field_label} upload failed: {exc}') from exc

    url = result.get('secure_url') or result.get('url', '')
    if not url:
        raise forms.ValidationError(f'{field_label} upload succeeded but no URL was returned.')
    return url


class SiteAdminForm(forms.ModelForm):
    favicon = forms.FileField(
        required=False,
        label='Site favicon',
        help_text='Upload PNG, ICO, or SVG (48×48 recommended). Stored on Cloudinary.',
    )
    remove_favicon = forms.BooleanField(required=False, label='Remove current favicon')
    og_image = forms.FileField(
        required=False,
        label='Default OG image',
        help_text='Upload PNG or JPG (1200×630 recommended) for social sharing previews.',
    )
    remove_og_image = forms.BooleanField(required=False, label='Remove current OG image')
    meta_description = forms.CharField(
        required=False,
        label='Default meta description',
        widget=forms.Textarea(attrs={'rows': 3, 'maxlength': 320}),
        help_text='Used for homepage and as fallback SEO description (max 320 characters).',
    )
    twitter_handle = forms.CharField(
        required=False,
        max_length=50,
        label='Twitter / X handle',
        help_text='Without @, e.g. sajilowork',
    )
    contact_email = forms.EmailField(
        required=False,
        label='Public contact email',
        help_text='Used in Organization schema and support metadata.',
    )
    facebook_url = forms.URLField(required=False, label='Facebook URL')
    linkedin_url = forms.URLField(required=False, label='LinkedIn URL')
    instagram_url = forms.URLField(required=False, label='Instagram URL')

    class Meta:
        model = Site
        fields = ('name', 'domain')
        labels = {
            'name': 'Site name',
            'domain': 'Site domain',
        }
        help_texts = {
            'name': 'Displayed in browser tabs and shared metadata (e.g. Sajilowork).',
            'domain': 'Primary domain for this site (e.g. www.sajilowork.com).',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            return
        branding = SiteBranding.objects.filter(site_id=self.instance.pk).first()
        if not branding:
            return
        self.fields['meta_description'].initial = branding.meta_description
        self.fields['twitter_handle'].initial = branding.twitter_handle
        self.fields['contact_email'].initial = branding.contact_email
        self.fields['facebook_url'].initial = branding.facebook_url
        self.fields['linkedin_url'].initial = branding.linkedin_url
        self.fields['instagram_url'].initial = branding.instagram_url

    def clean(self):
        cleaned_data = super().clean()
        name = (cleaned_data.get('name') or '').strip()
        domain = (cleaned_data.get('domain') or '').strip().lower()
        domain_host = domain.replace('https://', '').replace('http://', '').strip('/')

        if name.lower() in PLACEHOLDER_SITE_NAMES or name.lower().startswith('localhost'):
            cleaned_data['name'] = resolve_public_site_name(name)
        if (
            not domain_host
            or domain_host in PLACEHOLDER_SITE_DOMAINS
            or domain_host.startswith('localhost')
            or domain_host.startswith('127.0.0.1')
        ):
            cleaned_data['domain'] = resolve_public_site_domain(domain_host)

        if not cloudinary_server_upload_enabled():
            if cleaned_data.get('favicon'):
                self.add_error(
                    'favicon',
                    'Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, '
                    'CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET.',
                )
            if cleaned_data.get('og_image'):
                self.add_error('og_image', 'Cloudinary is not configured for image uploads.')
            return cleaned_data

        favicon_file = cleaned_data.get('favicon')
        if favicon_file:
            try:
                cleaned_data['favicon_url'] = _upload_image_to_cloudinary(
                    favicon_file, folder=cloudinary_site_favicon_folder(), field_label='Favicon'
                )
            except forms.ValidationError as exc:
                self.add_error('favicon', exc)

        og_image_file = cleaned_data.get('og_image')
        if og_image_file:
            try:
                cleaned_data['og_image_url'] = _upload_image_to_cloudinary(
                    og_image_file, folder=cloudinary_site_og_folder(), field_label='OG image'
                )
            except forms.ValidationError as exc:
                self.add_error('og_image', exc)

        return cleaned_data

    def save(self, commit=True):
        site = super().save(commit=commit)
        if site.pk:
            self._save_branding(site)
        return site

    def _save_branding(self, site: Site) -> None:
        branding, _ = SiteBranding.objects.get_or_create(site=site)
        update_fields: list[str] = []

        if self.cleaned_data.get('remove_favicon'):
            branding.favicon_url = ''
            update_fields.append('favicon_url')
        elif self.cleaned_data.get('favicon_url'):
            branding.favicon_url = self.cleaned_data['favicon_url']
            update_fields.append('favicon_url')

        if self.cleaned_data.get('remove_og_image'):
            branding.og_image_url = ''
            update_fields.append('og_image_url')
        elif self.cleaned_data.get('og_image_url'):
            branding.og_image_url = self.cleaned_data['og_image_url']
            update_fields.append('og_image_url')

        for field in (
            'meta_description',
            'twitter_handle',
            'contact_email',
            'facebook_url',
            'linkedin_url',
            'instagram_url',
        ):
            if field in self.cleaned_data:
                setattr(branding, field, self.cleaned_data.get(field) or '')
                update_fields.append(field)

        if update_fields:
            branding.save(update_fields=list(dict.fromkeys(update_fields)))


class SiteAdmin(DjangoSiteAdmin):
    form = SiteAdminForm
    list_display = ('domain', 'name', 'has_favicon', 'has_og_image')
    search_fields = ('domain', 'name')
    readonly_fields = ('favicon_preview', 'og_image_preview')
    fieldsets = (
        (
            'Site identity',
            {
                'fields': ('name', 'domain'),
                'description': 'Public site name and primary domain.',
            },
        ),
        (
            'Branding',
            {
                'fields': (
                    'favicon_preview',
                    'favicon',
                    'remove_favicon',
                    'og_image_preview',
                    'og_image',
                    'remove_og_image',
                ),
            },
        ),
        (
            'SEO defaults',
            {
                'fields': (
                    'meta_description',
                    'twitter_handle',
                    'contact_email',
                    'facebook_url',
                    'linkedin_url',
                    'instagram_url',
                ),
                'description': 'Default metadata for search engines and social platforms.',
            },
        ),
    )

    @admin.display(description='Current favicon')
    def favicon_preview(self, obj):
        return self._image_preview(obj, 'favicon_url', height=48)

    @admin.display(description='Current OG image')
    def og_image_preview(self, obj):
        return self._image_preview(obj, 'og_image_url', height=80)

    def _image_preview(self, obj, field: str, *, height: int):
        if not obj or not obj.pk:
            return 'Save the site first.'
        branding = SiteBranding.objects.filter(site_id=obj.pk).first()
        url = getattr(branding, field, '') if branding else ''
        if url:
            return format_html(
                '<img src="{}" alt="Preview" style="height:{}px;max-width:240px;object-fit:contain;'
                'border:1px solid #ddd;padding:4px;" />'
                '<div style="margin-top:6px;"><a href="{}" target="_blank" rel="noopener">{}</a></div>',
                url,
                height,
                url,
                url,
            )
        return 'Not uploaded yet.'

    @admin.display(boolean=True, description='Favicon')
    def has_favicon(self, obj):
        branding = getattr(obj, 'branding', None)
        return bool(branding and branding.favicon_url)

    @admin.display(boolean=True, description='OG image')
    def has_og_image(self, obj):
        branding = getattr(obj, 'branding', None)
        return bool(branding and branding.og_image_url)


admin.site.unregister(Site)
admin.site.register(Site, SiteAdmin)
