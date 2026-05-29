# Generated manually for UserBadge verification fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_user_trust_score'),
    ]

    operations = [
        migrations.AddField(
            model_name='userbadge',
            name='is_verified',
            field=models.BooleanField(
                default=False,
                help_text='When true, badge shows as active on the tasker profile.',
            ),
        ),
        migrations.AddField(
            model_name='userbadge',
            name='verified_at',
            field=models.DateTimeField(blank=True, null=True),
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
    ]
