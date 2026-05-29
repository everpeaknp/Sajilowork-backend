import uuid

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='BlogPost',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('slug', models.SlugField(max_length=200, unique=True)),
                ('title', models.CharField(max_length=255)),
                ('category', models.CharField(help_text='Display label, e.g. Cleaning', max_length=100)),
                ('excerpt', models.TextField(help_text='Short summary for cards')),
                ('image', models.ImageField(blank=True, null=True, upload_to='blog/')),
                ('image_url', models.URLField(blank=True, help_text='External image URL when no uploaded image', max_length=500)),
                ('link_url', models.URLField(blank=True, help_text='Optional link when the card is clicked', max_length=500)),
                ('is_published', models.BooleanField(db_index=True, default=True)),
                ('is_featured', models.BooleanField(db_index=True, default=False, help_text='Show on the home page blog section')),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('published_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['sort_order', '-published_at'],
                'indexes': [models.Index(fields=['is_published', 'is_featured', 'sort_order'], name='blog_blogpo_is_publ_0a8f2d_idx')],
            },
        ),
    ]
