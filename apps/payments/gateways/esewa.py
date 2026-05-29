"""
eSewa Payment Gateway Integration
Official Documentation: https://developer.esewa.com.np/
"""

import hashlib
import hmac
import base64
import requests
import logging
from typing import Dict, Any
from decimal import Decimal
from django.conf import settings

from .base import PaymentGateway

logger = logging.getLogger(__name__)


class ESewaGateway(PaymentGateway):
    """
    eSewa Payment Gateway Integration for Nepal.
    
    eSewa is one of the most popular digital wallets in Nepal.
    Supports: Payment initiation, verification, and status checking.
    
    Official Documentation: https://developer.esewa.com.np/pages/Epay
    """
    
    # eSewa API URLs (v2)
    PRODUCTION_URL = "https://epay.esewa.com.np/api/epay/main/v2/form"
    SANDBOX_URL = "https://rc-epay.esewa.com.np/api/epay/main/v2/form"
    
    PRODUCTION_STATUS_URL = "https://esewa.com.np/api/epay/transaction/status/"
    SANDBOX_STATUS_URL = "https://rc.esewa.com.np/api/epay/transaction/status/"
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize eSewa gateway.
        
        Config should contain:
        - merchant_id: eSewa merchant ID (product_code)
        - secret_key: eSewa secret key (for signature generation)
        - is_production: Boolean flag for production/sandbox mode
        """
        super().__init__(config)
        
        self.merchant_id = self.config.get('merchant_id') or getattr(settings, 'ESEWA_MERCHANT_ID', '')
        self.secret_key = self.config.get('secret_key') or getattr(settings, 'ESEWA_SECRET_KEY', '')
        self.is_production = self.config.get('is_production', False) or getattr(settings, 'ESEWA_PRODUCTION', False)
        
        self.payment_url = self.PRODUCTION_URL if self.is_production else self.SANDBOX_URL
        self.status_url = self.PRODUCTION_STATUS_URL if self.is_production else self.SANDBOX_STATUS_URL
    
    def generate_signature(self, data: str) -> str:
        """
        Generate HMAC-SHA256 signature for eSewa request.
        
        Args:
            data: Data string to sign
            
        Returns:
            str: Base64 encoded signature
        """
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        return base64.b64encode(signature).decode('utf-8')
    
    def initiate_payment(
        self,
        amount: Decimal,
        transaction_id: str,
        product_name: str,
        customer_info: Dict[str, Any],
        success_url: str,
        failure_url: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Initiate eSewa payment using v2 API.
        
        eSewa uses a form POST method for payment initiation.
        This method returns the payment URL and form data.
        
        Args:
            amount: Payment amount in NPR
            transaction_id: Unique transaction ID (transaction_uuid)
            product_name: Product/service name
            customer_info: Customer details
            success_url: Success redirect URL
            failure_url: Failure redirect URL
            
        Returns:
            dict: Payment form data and URL
        """
        try:
            # Keep calculations in Decimal to avoid string round-trips.
            tax_amount_dec = Decimal(str(kwargs.get('tax_amount', '0')))
            product_service_charge_dec = Decimal(str(kwargs.get('product_service_charge', '0')))
            product_delivery_charge_dec = Decimal(str(kwargs.get('product_delivery_charge', '0')))

            total_amount_dec = amount + tax_amount_dec + product_service_charge_dec + product_delivery_charge_dec

            # Format amount (eSewa expects amounts as string numbers; 2 decimals is accepted)
            amount_str = self.format_amount(amount)
            tax_amount = self.format_amount(tax_amount_dec)
            product_service_charge = self.format_amount(product_service_charge_dec)
            product_delivery_charge = self.format_amount(product_delivery_charge_dec)
            total_amount_str = self.format_amount(total_amount_dec)
            
            # Signed field names (required by eSewa v2 API)
            signed_field_names = "total_amount,transaction_uuid,product_code"
            
            # Generate signature
            # Format: total_amount=100,transaction_uuid=11-201-13,product_code=EPAYTEST
            signature_data = f"total_amount={total_amount_str},transaction_uuid={transaction_id},product_code={self.merchant_id}"
            signature = self.generate_signature(signature_data)
            
            # Prepare payment form data (v2 API format)
            payment_data = {
                'amount': amount_str,
                'tax_amount': tax_amount,
                'total_amount': total_amount_str,
                'transaction_uuid': transaction_id,
                'product_code': self.merchant_id,
                'product_service_charge': product_service_charge,
                'product_delivery_charge': product_delivery_charge,
                'success_url': success_url,
                'failure_url': failure_url,
                'signed_field_names': signed_field_names,
                'signature': signature
            }
            
            logger.info(f"eSewa payment initiated: {transaction_id}, amount: NPR {amount}")
            logger.info(f"eSewa signature data: {signature_data}")
            logger.info(f"eSewa signature: {signature}")
            
            return {
                'success': True,
                'payment_url': self.payment_url,
                'payment_method': 'POST',
                'form_data': payment_data,
                'transaction_id': transaction_id,
                'gateway': 'esewa'
            }
            
        except Exception as e:
            logger.error(f"eSewa payment initiation failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'gateway': 'esewa'
            }
    
    def verify_payment(
        self,
        transaction_id: str,
        reference_id: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Verify eSewa payment using status check API.
        
        Args:
            transaction_id: Original transaction ID (transaction_uuid)
            reference_id: eSewa reference ID (optional, not used in v2 status API)
            
        Returns:
            dict: Verification response
        """
        try:
            # Get amount from kwargs (required for verification)
            amount = kwargs.get('amount')
            if not amount:
                raise ValueError("Amount is required for eSewa verification")
            
            total_amount_str = self.format_amount(amount)
            
            # Prepare status check request
            # URL format: https://rc.esewa.com.np/api/epay/transaction/status/?product_code=EPAYTEST&total_amount=100&transaction_uuid=123
            status_params = {
                'product_code': self.merchant_id,
                'total_amount': total_amount_str,
                'transaction_uuid': transaction_id
            }
            
            logger.info(f"eSewa status check: {transaction_id}, params: {status_params}")
            
            # Make status check request
            response = requests.get(
                self.status_url,
                params=status_params,
                timeout=30
            )
            
            logger.info(f"eSewa status response: {response.status_code}, {response.text}")
            
            # Parse JSON response
            response_data = response.json()
            
            # Check status
            status = response_data.get('status', '').upper()
            ref_id = response_data.get('ref_id')
            
            if status == 'COMPLETE':
                logger.info(f"eSewa payment verified: {transaction_id}, ref: {ref_id}")
                
                return {
                    'success': True,
                    'verified': True,
                    'transaction_id': transaction_id,
                    'reference_id': ref_id,
                    'amount': amount,
                    'status': 'completed',
                    'gateway': 'esewa',
                    'raw_response': response_data
                }
            elif status in ['PENDING', 'AMBIGUOUS']:
                logger.warning(f"eSewa payment pending: {transaction_id}, status: {status}")
                
                return {
                    'success': True,
                    'verified': False,
                    'transaction_id': transaction_id,
                    'reference_id': ref_id,
                    'status': 'pending',
                    'gateway': 'esewa',
                    'message': f'Payment is {status.lower()}',
                    'raw_response': response_data
                }
            else:
                logger.warning(f"eSewa payment verification failed: {transaction_id}, status: {status}")
                
                return {
                    'success': False,
                    'verified': False,
                    'transaction_id': transaction_id,
                    'reference_id': ref_id,
                    'status': 'failed',
                    'gateway': 'esewa',
                    'error': f'Payment {status.lower()}',
                    'raw_response': response_data
                }
                
        except Exception as e:
            logger.error(f"eSewa verification error: {e}")
            return {
                'success': False,
                'verified': False,
                'error': str(e),
                'gateway': 'esewa'
            }
    
    def get_transaction_status(
        self,
        transaction_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get eSewa transaction status using status check API.
        
        Args:
            transaction_id: Transaction ID (transaction_uuid)
            
        Returns:
            dict: Transaction status
        """
        amount = kwargs.get('amount')
        
        if not amount:
            return {
                'success': False,
                'error': 'amount is required',
                'gateway': 'esewa'
            }
        
        # Use verify_payment to check status
        return self.verify_payment(transaction_id, amount=amount)
    
    def validate_webhook(
        self,
        payload: Dict[str, Any],
        signature: str = None,
        **kwargs
    ) -> bool:
        """
        Validate eSewa callback/webhook (v2 API).
        
        After successful payment, eSewa redirects to success_url with Base64 encoded response.
        
        Args:
            payload: Decoded callback payload
            signature: Signature from payload (if provided)
            
        Returns:
            bool: True if valid
        """
        try:
            # eSewa v2 callback parameters (Base64 decoded)
            transaction_code = payload.get('transaction_code')
            status = payload.get('status')
            total_amount = payload.get('total_amount')
            transaction_uuid = payload.get('transaction_uuid')
            product_code = payload.get('product_code')
            signed_field_names = payload.get('signed_field_names')
            response_signature = payload.get('signature')
            
            if not all([transaction_code, status, total_amount, transaction_uuid, product_code]):
                logger.warning("eSewa callback missing required parameters")
                return False
            
            # Validate signature if provided
            if response_signature and signed_field_names:
                # Reconstruct signature data from signed field names
                field_values = []
                for field_name in signed_field_names.split(','):
                    field_value = payload.get(field_name)
                    if field_value is not None:
                        field_values.append(f"{field_name}={field_value}")
                
                signature_data = ','.join(field_values)
                expected_signature = self.generate_signature(signature_data)
                
                if response_signature != expected_signature:
                    logger.warning("eSewa callback signature mismatch")
                    logger.warning(f"Expected: {expected_signature}, Got: {response_signature}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"eSewa webhook validation error: {e}")
            return False
    
    def format_amount(self, amount: Decimal) -> str:
        """
        Format amount the way eSewa expects.

        Per https://developer.esewa.com.np/pages/Epay, whole amounts are
        submitted (and signed) WITHOUT trailing zeros (e.g. "100", "10", "0"),
        while fractional amounts use 2 decimal places (e.g. "99.50").

        Sending "100.00" causes the sandbox to reject the form with
        {"code": 0, "error_message": "Service is currently unavailable"} even
        though our signature is internally consistent, because eSewa normalises
        the amount before recomputing the HMAC on its side.

        Args:
            amount: Amount to format

        Returns:
            str: Formatted amount
        """
        amount_dec = amount if isinstance(amount, Decimal) else Decimal(str(amount))
        if amount_dec == amount_dec.to_integral_value():
            return str(int(amount_dec))
        return f"{amount_dec:.2f}"
    
    def parse_amount(self, amount_str: str) -> Decimal:
        """
        Parse amount from eSewa response.
        
        Args:
            amount_str: Amount string
            
        Returns:
            Decimal: Parsed amount
        """
        return Decimal(amount_str)
    
    @staticmethod
    def get_test_credentials() -> Dict[str, str]:
        """
        Get eSewa test/sandbox credentials.
        
        Returns:
            dict: Test credentials
        """
        return {
            'merchant_id': 'EPAYTEST',
            'secret_key': '8gBm/:&EnhH.1/q',
            'is_production': False
        }
