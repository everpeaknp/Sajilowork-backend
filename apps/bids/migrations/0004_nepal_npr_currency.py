from django.db import migrations, models


def forwards_convert_usd_to_npr(apps, schema_editor):
    Bid = apps.get_model('bids', 'Bid')
    Bid.objects.filter(currency='USD').update(currency='NPR')


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bids', '0003_initial'),
    ]

    operations = [
        migrations.RunPython(forwards_convert_usd_to_npr, backwards_noop),
        migrations.AlterField(
            model_name='bid',
            name='currency',
            field=models.CharField(default='NPR', max_length=3),
        ),
    ]
