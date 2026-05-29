# Nepal marketplace: default currency NPR and migrate existing USD rows

from django.db import migrations, models


def forwards_convert_usd_to_npr(apps, schema_editor):
    Wallet = apps.get_model('wallets', 'Wallet')
    WalletTransaction = apps.get_model('wallets', 'WalletTransaction')
    WithdrawalRequest = apps.get_model('wallets', 'WithdrawalRequest')
    WalletLimit = apps.get_model('wallets', 'WalletLimit')

    for model in (Wallet, WalletTransaction, WithdrawalRequest, WalletLimit):
        model.objects.filter(currency='USD').update(currency='NPR')
        # Legacy rows may store full label from old choices
        model.objects.filter(currency__in=['US Dollar', 'Euro', 'British Pound']).update(
            currency='NPR'
        )


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('wallets', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forwards_convert_usd_to_npr, backwards_noop),
        migrations.AlterField(
            model_name='wallet',
            name='currency',
            field=models.CharField(
                choices=[('NPR', 'Nepalese Rupee')],
                default='NPR',
                max_length=3,
            ),
        ),
        migrations.AlterField(
            model_name='wallettransaction',
            name='currency',
            field=models.CharField(default='NPR', max_length=3),
        ),
        migrations.AlterField(
            model_name='withdrawalrequest',
            name='currency',
            field=models.CharField(default='NPR', max_length=3),
        ),
        migrations.AlterField(
            model_name='walletlimit',
            name='currency',
            field=models.CharField(default='NPR', max_length=3),
        ),
    ]
