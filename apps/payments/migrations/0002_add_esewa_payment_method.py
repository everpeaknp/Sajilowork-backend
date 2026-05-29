# Generated manually for eSewa payment method support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0001_initial'),
    ]

    operations = [
        # Add eSewa to METHOD_TYPE_CHOICES
        migrations.AlterField(
            model_name='paymentmethod',
            name='method_type',
            field=models.CharField(
                choices=[
                    ('card', 'Credit/Debit Card'),
                    ('bank_account', 'Bank Account'),
                    ('paypal', 'PayPal'),
                    ('esewa', 'eSewa'),
                ],
                max_length=20
            ),
        ),
        # Make Stripe fields optional
        migrations.AlterField(
            model_name='paymentmethod',
            name='stripe_payment_method_id',
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='paymentmethod',
            name='stripe_customer_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        # Add eSewa fields
        migrations.AddField(
            model_name='paymentmethod',
            name='esewa_account_name',
            field=models.CharField(blank=True, help_text='Full name on eSewa account', max_length=255),
        ),
        migrations.AddField(
            model_name='paymentmethod',
            name='esewa_phone_number',
            field=models.CharField(blank=True, help_text='eSewa phone number (10 digits)', max_length=15),
        ),
    ]
