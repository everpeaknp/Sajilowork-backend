from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0017_employer_media_urls'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userbadge',
            name='verification_document',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Uploaded certificate or police check document URL (Cloudinary) or local path.',
                max_length=2048,
            ),
        ),
    ]
