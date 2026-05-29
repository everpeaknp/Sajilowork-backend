from decimal import Decimal

from django import forms


class ManualWalletCreditForm(forms.Form):
    amount = forms.DecimalField(
        min_value=Decimal('0.01'),
        max_digits=10,
        decimal_places=2,
        label='Amount (NPR)',
        help_text='Amount received via eSewa, bank transfer, or cash.',
        widget=forms.NumberInput(attrs={'class': 'vTextField', 'step': '0.01', 'min': '0.01'}),
    )
    whatsapp_request_id = forms.CharField(
        required=False,
        max_length=100,
        label='WhatsApp request ID',
        help_text='Optional. Paste Request ID from the user message to avoid double credit.',
        widget=forms.TextInput(attrs={'class': 'vTextField', 'placeholder': 'WA-…'}),
    )
    notes = forms.CharField(
        required=False,
        label='Admin notes',
        widget=forms.Textarea(
            attrs={'class': 'vLargeTextField', 'rows': 4, 'cols': 60, 'placeholder': 'e.g. eSewa ref verified'}
        ),
    )
