# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_userbadge_verification_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='userbadge',
            name='document_number',
            field=models.CharField(
                blank=True,
                help_text='Licence or certificate number (optional).',
                max_length=100,
            ),
        ),
        migrations.AddField(
            model_name='userbadge',
            name='verification_document',
            field=models.FileField(
                blank=True,
                help_text='Uploaded certificate or police check document.',
                null=True,
                upload_to='badge_verification/%Y/%m/',
            ),
        ),
        migrations.AlterField(
            model_name='userdocument',
            name='document_type',
            field=models.CharField(
                choices=[
                    ('id_card', 'ID Card'),
                    ('passport', 'Passport'),
                    ('driver_license', 'Driver License'),
                    ('proof_of_address', 'Proof of Address'),
                    ('business_license', 'Business License'),
                    ('certificate', 'Certificate'),
                    ('police_check', 'Police Check'),
                    ('electrical_licence', 'Electrical Licence'),
                    ('plumbing_licence', 'Plumbing Licence'),
                ],
                max_length=50,
            ),
        ),
    ]
