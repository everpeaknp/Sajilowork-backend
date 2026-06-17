import uuid

from django.db import migrations, models
from django.utils.text import slugify


PROFILE_LANGUAGES = ['English', 'Nepali', 'Spanish', 'German', 'French']
PROJECT_LANGUAGES = ['English', 'Spanish', 'French', 'German', 'Nepali']
SERVICE_LANGUAGES = ['English', 'Spanish', 'French', 'German', 'Nepali', 'Hindi']


def seed_languages(apps, schema_editor):
    Language = apps.get_model('language', 'Language')
    seeds = [
        (PROFILE_LANGUAGES, 'profile'),
        (PROJECT_LANGUAGES, 'project'),
        (SERVICE_LANGUAGES, 'service'),
    ]
    for names, listing_kind in seeds:
        for order, name in enumerate(names):
            slug = slugify(name)[:100]
            Language.objects.get_or_create(
                name=name,
                listing_kind=listing_kind,
                defaults={
                    'id': uuid.uuid4(),
                    'slug': slug,
                    'order': order,
                    'is_active': True,
                },
            )


def unseed_languages(apps, schema_editor):
    Language = apps.get_model('language', 'Language')
    all_names = set(PROFILE_LANGUAGES + PROJECT_LANGUAGES + SERVICE_LANGUAGES)
    Language.objects.filter(name__in=all_names).delete()


class Migration(migrations.Migration):
    atomic = False

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Language',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(max_length=100)),
                (
                    'listing_kind',
                    models.CharField(
                        choices=[
                            ('profile', 'Profile'),
                            ('project', 'Project'),
                            ('service', 'Service'),
                        ],
                        db_index=True,
                        default='project',
                        help_text='Profile = freelancer profile, Project/Service = listing forms.',
                        max_length=20,
                    ),
                ),
                ('is_active', models.BooleanField(default=True)),
                ('order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Language',
                'verbose_name_plural': 'Languages',
                'db_table': 'marketplace_languages',
                'ordering': ['listing_kind', 'order', 'name'],
            },
        ),
        migrations.AddConstraint(
            model_name='language',
            constraint=models.UniqueConstraint(
                fields=('name', 'listing_kind'),
                name='marketplace_languages_name_listing_kind_uniq',
            ),
        ),
        migrations.AddConstraint(
            model_name='language',
            constraint=models.UniqueConstraint(
                fields=('slug', 'listing_kind'),
                name='marketplace_languages_slug_listing_kind_uniq',
            ),
        ),
        migrations.RunPython(seed_languages, unseed_languages),
    ]
