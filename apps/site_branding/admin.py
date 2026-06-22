from django import forms
from django.contrib import admin
from django.contrib.sites.admin import SiteAdmin as DjangoSiteAdmin
from django.contrib.sites.models import Site
from django.utils.html import format_html

from apps.uploads.cloudinary_folders import cloudinary_site_favicon_folder
from apps.uploads.cloudinary_utils import (
    cloudinary_server_upload_enabled,
    infer_cloudinary_resource_type,
    is_cloudinary_permission_error,
    upload_file_to_cloudinary,
)

from .models import SiteBranding


def _upload_favicon_to_cloudinary(favicon_file) -> str:
    try:
        result = upload_file_to_cloudinary(
            favicon_file,
            folder=cloudinary_site_favicon_folder(),
            resource_type=infer_cloudinary_resource_type(favicon_file),
        )
    except Exception as exc:
        if is_cloudinary_permission_error(exc):
            raise forms.ValidationError(
                'Cloudinary rejected the upload. Ensure your API key has upload '
                'permission, or set CLOUDINARY_UPLOAD_PRESET.'
            ) from exc
        raise forms.ValidationError(f'Favicon upload failed: {exc}') from exc

    url = result.get('secure_url') or result.get('url', '')
    if not url:
        raise forms.ValidationError('Cloudinary upload succeeded but no URL was returned.')
    return url


class SiteAdminForm(forms.ModelForm):
    favicon = forms.FileField(
        required=False,
        label='Site favicon',
        help_text='Upload PNG, ICO, or SVG (48×48 recommended). Stored on Cloudinary.',
    )
    remove_favicon = forms.BooleanField(
        required=False,
        label='Remove current favicon',
    )

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
        if self.instance.pk:
            branding = SiteBranding.objects.filter(site_id=self.instance.pk).first()
            if branding and branding.favicon_url:
                self.fields['favicon'].help_text = (
                    'Choose a file to replace the current favicon on Cloudinary, '
                    'or tick "Remove current favicon".'
                )

    def clean(self):
        cleaned_data = super().clean()
        favicon_file = cleaned_data.get('favicon')
        if favicon_file and not cloudinary_server_upload_enabled():
            self.add_error(
                'favicon',
                'Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, '
                'CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET in the environment.',
            )
            return cleaned_data

        if favicon_file:
            try:
                cleaned_data['favicon_url'] = _upload_favicon_to_cloudinary(favicon_file)
            except forms.ValidationError as exc:
                self.add_error('favicon', exc)
        return cleaned_data

    def save(self, commit=True):
        site = super().save(commit=commit)
        # Django admin saves with commit=False first; branding must update then too.
        if site.pk:
            self._save_branding(site)
        return site

    def _save_branding(self, site: Site) -> None:
        branding, _ = SiteBranding.objects.get_or_create(site=site)
        remove_favicon = self.cleaned_data.get('remove_favicon')
        favicon_url = self.cleaned_data.get('favicon_url')

        if remove_favicon:
            branding.favicon_url = ''
            branding.save(update_fields=['favicon_url'])
        elif favicon_url:
            branding.favicon_url = favicon_url
            branding.save(update_fields=['favicon_url'])


class SiteAdmin(DjangoSiteAdmin):
    form = SiteAdminForm
    list_display = ('domain', 'name', 'has_favicon')
    search_fields = ('domain', 'name')
    readonly_fields = ('favicon_preview',)
    fieldsets = (
        (
            'Site identity',
            {
                'fields': (
                    'name',
                    'domain',
                    'favicon_preview',
                    'favicon',
                    'remove_favicon',
                ),
                'description': 'Set the public site name, domain, and favicon (uploaded to Cloudinary).',
            },
        ),
    )

    @admin.display(description='Current favicon')
    def favicon_preview(self, obj):
        if not obj or not obj.pk:
            return 'Save the site first, then upload a favicon.'

        branding = SiteBranding.objects.filter(site_id=obj.pk).first()
        if branding and branding.favicon_url:
            return format_html(
                '<img src="{}" alt="Favicon preview" '
                'style="height:48px;width:48px;object-fit:contain;border:1px solid #ddd;padding:4px;" />'
                '<div style="margin-top:6px;"><a href="{}" target="_blank" rel="noopener">{}</a></div>',
                branding.favicon_url,
                branding.favicon_url,
                branding.favicon_url,
            )

        return 'No favicon uploaded yet.'

    @admin.display(boolean=True, description='Favicon')
    def has_favicon(self, obj):
        branding = getattr(obj, 'branding', None)
        return bool(branding and branding.favicon_url)


admin.site.unregister(Site)
admin.site.register(Site, SiteAdmin)
