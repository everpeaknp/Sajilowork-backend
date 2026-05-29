from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0010_user_suspended_until'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='username_changed_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the user last changed their username (6-month cooldown applies).',
                null=True,
            ),
        ),
    ]
