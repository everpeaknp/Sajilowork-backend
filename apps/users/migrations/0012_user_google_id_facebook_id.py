# Generated manually for social OAuth fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0011_user_username_changed_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='facebook_id',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Facebook user id for OAuth login.',
                max_length=255,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='google_id',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Google account subject id for OAuth login.',
                max_length=255,
                null=True,
                unique=True,
            ),
        ),
    ]
