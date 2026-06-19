from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0015_userkyc'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='profile_image',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Profile image URL (Cloudinary) or local media path',
                max_length=2048,
            ),
        ),
        migrations.AlterField(
            model_name='user',
            name='cover_image',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Cover image URL (Cloudinary) or local media path',
                max_length=2048,
            ),
        ),
    ]
