from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0005_nepal_npr_budget_currency'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='started_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='task',
            name='completion_requested_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='task',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='task',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('open', 'Open'),
                    ('assigned', 'Assigned'),
                    ('funded', 'Funded'),
                    ('in_progress', 'In Progress'),
                    ('pending_approval', 'Pending Approval'),
                    ('completed', 'Completed'),
                    ('cancelled', 'Cancelled'),
                    ('disputed', 'Disputed'),
                ],
                default='draft',
                max_length=20,
            ),
        ),
    ]
