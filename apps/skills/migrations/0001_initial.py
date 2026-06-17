import uuid

from django.db import migrations, models
from django.utils.text import slugify


JOB_SKILLS = [
    'Figma',
    'React',
    'Node.js',
    'UI/UX Design',
    'TypeScript',
    'PostgreSQL',
    'Mobile Development',
    'SEO',
    'Next.js',
    'Python',
    'DevOps',
    'Project Management',
]

PROJECT_SKILLS = [
    'Figma',
    'React',
    'Node.js',
    'UI/UX Design',
    'TypeScript',
    'PostgreSQL',
    'Mobile Development',
    'SEO',
]

SERVICE_SKILLS = [
    'Figma',
    'Adobe XD',
    'UI/UX Design',
    'HTML/CSS',
    'React',
    'Illustration',
    'Logo Design',
]


def seed_skills(apps, schema_editor):
    Skill = apps.get_model('skills', 'Skill')
    seeds = [
        (JOB_SKILLS, 'job'),
        (PROJECT_SKILLS, 'project'),
        (SERVICE_SKILLS, 'service'),
    ]
    for names, listing_kind in seeds:
        for order, name in enumerate(names):
            slug = slugify(name)[:100]
            Skill.objects.get_or_create(
                name=name,
                listing_kind=listing_kind,
                defaults={
                    'id': uuid.uuid4(),
                    'slug': slug,
                    'order': order,
                    'is_active': True,
                },
            )


def unseed_skills(apps, schema_editor):
    Skill = apps.get_model('skills', 'Skill')
    all_names = set(JOB_SKILLS + PROJECT_SKILLS + SERVICE_SKILLS)
    Skill.objects.filter(name__in=all_names).delete()


class Migration(migrations.Migration):
    atomic = False

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Skill',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(max_length=100)),
                (
                    'listing_kind',
                    models.CharField(
                        choices=[
                            ('task', 'Task'),
                            ('service', 'Service'),
                            ('project', 'Project'),
                            ('job', 'Job'),
                        ],
                        db_index=True,
                        help_text='Which listing type this skill applies to.',
                        max_length=20,
                    ),
                ),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Skill',
                'verbose_name_plural': 'Skills',
                'db_table': 'marketplace_skills',
                'ordering': ['listing_kind', 'order', 'name'],
            },
        ),
        migrations.AddConstraint(
            model_name='skill',
            constraint=models.UniqueConstraint(
                fields=('name', 'listing_kind'),
                name='marketplace_skills_name_listing_kind_uniq',
            ),
        ),
        migrations.AddConstraint(
            model_name='skill',
            constraint=models.UniqueConstraint(
                fields=('slug', 'listing_kind'),
                name='marketplace_skills_slug_listing_kind_uniq',
            ),
        ),
        migrations.RunPython(seed_skills, unseed_skills),
    ]
