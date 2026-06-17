# Generated manually — scope categories by listing type and seed job categories.

from django.db import migrations, models
from django.utils.text import slugify


JOB_CATEGORY_NAMES = [
    'Design & Creative',
    'Development & IT',
    'Writing & Translation',
    'Digital Marketing',
    'Video & Animation',
    'Finance & Accounting',
]


def seed_job_categories(apps, schema_editor):
    Category = apps.get_model('tasks', 'Category')
    for order, name in enumerate(JOB_CATEGORY_NAMES):
        slug = slugify(name)[:100]
        Category.objects.get_or_create(
            name=name,
            listing_kind='job',
            defaults={
                'slug': slug,
                'order': order,
                'is_active': True,
            },
        )


def unseed_job_categories(apps, schema_editor):
    Category = apps.get_model('tasks', 'Category')
    Category.objects.filter(
        listing_kind='job',
        name__in=JOB_CATEGORY_NAMES,
    ).delete()


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('tasks', '0008_task_cancellation_tracking'),
    ]

    operations = [
        migrations.AlterField(
            model_name='category',
            name='name',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='category',
            name='slug',
            field=models.SlugField(max_length=100),
        ),
        migrations.AddField(
            model_name='category',
            name='listing_kind',
            field=models.CharField(
                choices=[
                    ('task', 'Task'),
                    ('service', 'Service'),
                    ('project', 'Project'),
                    ('job', 'Job'),
                ],
                db_index=True,
                default='task',
                help_text='Which listing type this category belongs to (task, job, project, service).',
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name='category',
            constraint=models.UniqueConstraint(
                fields=('name', 'listing_kind'),
                name='categories_name_listing_kind_uniq',
            ),
        ),
        migrations.AddConstraint(
            model_name='category',
            constraint=models.UniqueConstraint(
                fields=('slug', 'listing_kind'),
                name='categories_slug_listing_kind_uniq',
            ),
        ),
        migrations.RunPython(seed_job_categories, unseed_job_categories),
    ]
