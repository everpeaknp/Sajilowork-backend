from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_portfolio_document_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='suspended_until',
            field=models.DateTimeField(
                blank=True,
                help_text='When an automatic suspension ends (null = manual / indefinite).',
                null=True,
            ),
        ),
    ]
