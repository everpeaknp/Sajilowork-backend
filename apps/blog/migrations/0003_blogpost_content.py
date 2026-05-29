from django.db import migrations, models


def copy_excerpt_to_content(apps, schema_editor):
    BlogPost = apps.get_model('blog', 'BlogPost')
    for post in BlogPost.objects.filter(content=''):
        excerpt = (post.excerpt or '').strip()
        if excerpt:
            post.content = f'<p>{excerpt}</p>'
            post.save(update_fields=['content'])


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0002_seed_featured_posts'),
    ]

    operations = [
        migrations.AddField(
            model_name='blogpost',
            name='content',
            field=models.TextField(
                blank=True,
                help_text='Full article body (HTML). Shown on the public blog post page.',
            ),
        ),
        migrations.RunPython(copy_excerpt_to_content, migrations.RunPython.noop),
    ]
