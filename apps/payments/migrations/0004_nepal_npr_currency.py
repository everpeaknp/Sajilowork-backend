from django.db import migrations, models


def forwards_convert_usd_to_npr(apps, schema_editor):
    Payment = apps.get_model('payments', 'Payment')
    Refund = apps.get_model('payments', 'Refund')
    Payout = apps.get_model('payments', 'Payout')
    Escrow = apps.get_model('payments', 'Escrow')
    Transaction = apps.get_model('payments', 'Transaction')

    for model in (Payment, Refund, Payout, Escrow, Transaction):
        model.objects.filter(currency='USD').update(currency='NPR')


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0003_escrow'),
    ]

    operations = [
        migrations.RunPython(forwards_convert_usd_to_npr, backwards_noop),
        migrations.AlterField(
            model_name='payment',
            name='currency',
            field=models.CharField(default='NPR', max_length=3),
        ),
        migrations.AlterField(
            model_name='refund',
            name='currency',
            field=models.CharField(default='NPR', max_length=3),
        ),
        migrations.AlterField(
            model_name='payout',
            name='currency',
            field=models.CharField(default='NPR', max_length=3),
        ),
        migrations.AlterField(
            model_name='escrow',
            name='currency',
            field=models.CharField(default='NPR', max_length=3),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='currency',
            field=models.CharField(default='NPR', max_length=3),
        ),
    ]
