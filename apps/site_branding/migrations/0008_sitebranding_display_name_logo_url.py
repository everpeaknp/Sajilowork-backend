from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('site_branding', '0007_fix_legacy_site_names'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitebranding',
            name='display_name',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Name shown in the site header and footer. Leave blank to use the Django site name above.',
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name='sitebranding',
            name='logo_url',
            field=models.URLField(
                blank=True,
                default='',
                help_text='Cloudinary URL for the header/footer logo (PNG or SVG, ~200×48 recommended).',
            ),
        ),
    ]
