from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0016_user_profile_media_urls'),
    ]

    operations = [
        migrations.AlterField(
            model_name='employerprofile',
            name='logo_image',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Employer logo URL (Cloudinary) or local media path',
                max_length=2048,
            ),
        ),
        migrations.AlterField(
            model_name='employergalleryimage',
            name='image',
            field=models.CharField(
                help_text='Gallery image URL (Cloudinary) or local media path',
                max_length=2048,
            ),
        ),
    ]
