from django.db import migrations, models


def forwards_convert_usd_to_npr(apps, schema_editor):
    Task = apps.get_model('tasks', 'Task')
    Task.objects.filter(budget_currency='USD').update(budget_currency='NPR')
    Task.objects.filter(budget_currency='AUD').update(budget_currency='NPR')


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        (
            'tasks',
            '0004_rename_task_activi_task_id_ad7e94_idx_task_activi_task_id_e45ba7_idx_and_more',
        ),
    ]

    operations = [
        migrations.RunPython(forwards_convert_usd_to_npr, backwards_noop),
        migrations.AlterField(
            model_name='task',
            name='budget_currency',
            field=models.CharField(default='NPR', max_length=3),
        ),
    ]
