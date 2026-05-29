from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0006_task_escrow_workflow_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='tasker_marked_complete_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the assigned tasker confirmed work is complete',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='task',
            name='owner_marked_complete_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the poster confirmed work is complete',
                null=True,
            ),
        ),
    ]
