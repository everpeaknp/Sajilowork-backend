from django.db import migrations


def fix_default_site_domain(apps, schema_editor):
    Site = apps.get_model('sites', 'Site')
    site = Site.objects.filter(pk=1).first()
    if not site:
        return

    placeholder_domains = {'example.com', 'www.example.com', ''}
    if site.domain in placeholder_domains:
        site.domain = 'www.sajilowork.com'
        site.name = 'Sajilowork'
        site.save(update_fields=['domain', 'name'])


class Migration(migrations.Migration):

    dependencies = [
        ('site_branding', '0004_alter_sitebranding_options_and_more'),
    ]

    operations = [
        migrations.RunPython(fix_default_site_domain, migrations.RunPython.noop),
    ]
