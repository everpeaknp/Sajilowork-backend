# Generated manually — portfolio document type label (CharField choices only).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0008_custom_licence_badges'),
    ]

    operations = [
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
                    ('custom_licence', 'Custom Licence / Certificate'),
                    ('portfolio', 'Portfolio Item'),
                ],
                max_length=50,
            ),
        ),
    ]
