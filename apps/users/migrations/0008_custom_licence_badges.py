# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_userbadge_verification_document'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='userbadge',
            unique_together={('user', 'badge_type', 'name')},
        ),
        migrations.AlterField(
            model_name='userbadge',
            name='badge_type',
            field=models.CharField(
                choices=[
                    ('police_check', 'Police Check'),
                    ('payment_verified', 'Payment Method Verified'),
                    ('mobile_verified', 'Mobile Verified'),
                    ('electrical_licence', 'Electrical Licence'),
                    ('plumbing_licence', 'Plumbing Licence'),
                    ('identity_verified', 'Identity Verified'),
                    ('custom_licence', 'Custom Licence'),
                    ('verified', 'Verified'),
                    ('top_rated', 'Top Rated'),
                    ('fast_responder', 'Fast Responder'),
                    ('reliable', 'Reliable'),
                    ('expert', 'Expert'),
                    ('rising_talent', 'Rising Talent'),
                    ('milestone', 'Milestone'),
                ],
                max_length=50,
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
                    ('custom_licence', 'Custom Licence / Certificate'),
                ],
                max_length=50,
            ),
        ),
    ]
