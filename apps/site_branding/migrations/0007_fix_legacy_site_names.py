from django.db import migrations

LEGACY_SITE_NAMES = {
    'example.com',
    'example',
    'tasknepal',
    'task nepal',
    'airtasker',
    'localhost',
}

PLACEHOLDER_DOMAINS = {
    'example.com',
    'www.example.com',
    '',
}


def fix_legacy_site_names(apps, schema_editor):
    Site = apps.get_model('sites', 'Site')
    site = Site.objects.filter(pk=1).first()
    if not site:
        return

    name = (site.name or '').strip().lower()
    domain = (site.domain or '').strip().lower()
    changed = False

    if name in LEGACY_SITE_NAMES or name.startswith('localhost'):
        site.name = 'Sajilowork'
        changed = True

    if domain in PLACEHOLDER_DOMAINS or domain.startswith('localhost'):
        site.domain = 'www.sajilowork.com'
        changed = True

    if changed:
        site.save(update_fields=['name', 'domain'])


class Migration(migrations.Migration):

    dependencies = [
        ('site_branding', '0006_sitebranding_social_urls'),
    ]

    operations = [
        migrations.RunPython(fix_legacy_site_names, migrations.RunPython.noop),
    ]
