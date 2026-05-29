# Generated manually

from decimal import Decimal
from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_userfollow'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='trust_score',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Composite trust score (0–100) from ratings, completion, disputes',
                max_digits=5,
                validators=[
                    django.core.validators.MinValueValidator(0.00),
                    django.core.validators.MaxValueValidator(100.00),
                ],
            ),
        ),
    ]
