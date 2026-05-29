import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_user_has_payment_method'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserFollow',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'follower',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='user_following',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'following',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='user_followers',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'user_follows',
            },
        ),
        migrations.AddIndex(
            model_name='userfollow',
            index=models.Index(fields=['follower', 'following'], name='user_follow_followe_0a8f2d_idx'),
        ),
        migrations.AddIndex(
            model_name='userfollow',
            index=models.Index(fields=['following'], name='user_follow_followi_4b2c91_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='userfollow',
            unique_together={('follower', 'following')},
        ),
    ]
