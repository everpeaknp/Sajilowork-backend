from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('site_branding', '0005_fix_default_site_domain'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitebranding',
            name='facebook_url',
            field=models.URLField(blank=True, default='', help_text='Facebook page URL for Organization sameAs schema.'),
        ),
        migrations.AddField(
            model_name='sitebranding',
            name='instagram_url',
            field=models.URLField(blank=True, default='', help_text='Instagram profile URL for Organization sameAs schema.'),
        ),
        migrations.AddField(
            model_name='sitebranding',
            name='linkedin_url',
            field=models.URLField(blank=True, default='', help_text='LinkedIn company/profile URL for Organization sameAs schema.'),
        ),
    ]
