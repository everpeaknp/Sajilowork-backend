from django.db import migrations

TEXT_REPLACEMENTS = (
    ('tasknepal', 'Sajilowork'),
    ('TaskNepal', 'Sajilowork'),
    ('TASKNEPAL', 'Sajilowork'),
    ('on sajilowork', 'on Sajilowork'),
    ('using sajilowork', 'using Sajilowork'),
    ('with sajilowork', 'with Sajilowork'),
    ('sajilowork is', 'Sajilowork is'),
    ('sajilowork when', 'Sajilowork when'),
    ('sajilowork may', 'Sajilowork may'),
    ('sajilowork.', 'Sajilowork.'),
    ('sajilowork,', 'Sajilowork,'),
)


def _apply_replacements(text: str) -> str:
    updated = text
    for old, new in TEXT_REPLACEMENTS:
        updated = updated.replace(old, new)
    return updated


def normalize_faq_branding(apps, schema_editor):
    FaqItem = apps.get_model('faq', 'FaqItem')
    for item in FaqItem.objects.all().iterator():
        question = _apply_replacements(item.question or '')
        answer = _apply_replacements(item.answer or '')
        if question != item.question or answer != item.answer:
            item.question = question
            item.answer = answer
            item.save(update_fields=['question', 'answer'])


class Migration(migrations.Migration):

    dependencies = [
        ('faq', '0002_seed_faq_items'),
    ]

    operations = [
        migrations.RunPython(normalize_faq_branding, migrations.RunPython.noop),
    ]
