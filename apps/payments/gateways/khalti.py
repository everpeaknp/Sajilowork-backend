"""
Khalti Payment Gateway Integration
Official Documentation: https://docs.khalti.com/
"""

import requests
import logging
from typing import Dict, Any
from decimal import Decimal
from django.conf import settings

from .base import PaymentGateway

logger = logging.getLogger(__name__)


class KhaltiGateway(PaymentGateway):
    """
    Khalti Payment Gateway Integration for Nepal.
    
    Khalti is a popular digital wallet and payment gateway in Nepal.
    Supports: Payment initiation, verification, and lookup.
    """
    
    # Khalti API URLs
    PRODUCTION_BASE_URL = "https://khalti.com/api/v2"
    SANDBOX_BASE_URL = "https://a.khalti.com/api/v2"
    
    # API Endpoints
    INITIATE_ENDPOINT = "/epayment/initiate/"
    VERIFY_ENDPOINT = "/epayment/lookup/"
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize Khalti gateway.
        
        Config should contain:
        - public_key: Khalti public key
        - secret_key: Khalti secret key
        - is_production: Boolean flag for production/sandbox mode
        """
        super().__init__(config)
        
        self.public_key = self.config.get('public_key') or getattr(settings, 'KHALTI_PUBLIC_KEY', '')
        self.secret_key = self.config.get('secret_key') or getattr(settings, 'KHALTI_SECRET_KEY', '')
        self.is_production = self.config.get('is_production', False) or getattr(settings, 'KHALTI_PRODUCTION', False)
        
        self.base_url = self.PRODUCTION_BASE_URL if self.is_production else self.SANDBOX_BASE_URL
        self.initiate_url = f"{self.base_url}{self.INITIATE_ENDPOINT}"
        self.verify_url = f"{self.base_url}{self.VERIFY_ENDPOINT}"
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Get API request headers.
        
        Returns:
            dict: Request headers with authorization
        """
        return {
            'Authorization': f'Key {self.secret_key}',
            'Content-Type': 'application/json'
        }
    
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
        Initiate Khalti payment.
        
        Khalti uses API-based payment initiation.
        Returns payment URL for customer to complete payment.
        
        Args:
            amount: Payment amount in NPR (paisa - smallest unit)
            transaction_id: Unique transaction ID
            product_name: Product/service name
            customer_info: Customer details (name, email, phone)
            success_url: Success redirect URL
            failure_url: Failure redirect URL
            
        Returns:
            dict: Payment initiation response with payment URL
        """
        try:
            # Convert amount to paisa (Khalti uses paisa as smallest unit)
            # 1 NPR = 100 paisa
            amount_paisa = int(amount * 100)
            
            # Prepare request payload
            payload = {
                'return_url': success_url,
                'website_url': kwargs.get('website_url', success_url.split('/')[0:3]),  # Base URL
                'amount': amount_paisa,
                'purchase_order_id': transaction_id,
                'purchase_order_name': product_name,
                'customer_info': {
                    'name': customer_info.get('name', ''),
                    'email': customer_info.get('email', ''),
                    'phone': customer_info.get('phone', '')
                }
            }
            
            # Add optional parameters
            if 'product_details' in kwargs:
                payload['product_details'] = kwargs['product_details']
            
            if 'amount_breakdown' in kwargs:
                payload['amount_breakdown'] = kwargs['amount_breakdown']
            
            # Make API request
            response = requests.post(
                self.initiate_url,
                json=payload,
                headers=self._get_headers(),
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"Khalti payment initiated: {transaction_id}, amount: NPR {amount}")
            
            return {
                'success': True,
                'payment_url': data.get('payment_url'),
                'pidx': data.get('pidx'),  # Khalti payment index
                'transaction_id': transaction_id,
                'amount': amount,
                'gateway': 'khalti',
                'expires_at': data.get('expires_at'),
                'expires_in': data.get('expires_in')
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Khalti payment initiation failed: {e}")
            error_message = str(e)
            
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_message = error_data.get('detail', error_message)
                except:
                    error_message = e.response.text
            
            return {
                'success': False,
                'error': error_message,
                'gateway': 'khalti'
            }
        except Exception as e:
            logger.error(f"Khalti payment initiation error: {e}")
            return {
                'success': False,
                'error': str(e),
                'gateway': 'khalti'
            }
    
    def verify_payment(
        self,
        transaction_id: str,
        reference_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Verify Khalti payment.
        
        Args:
            transaction_id: Original transaction ID
            reference_id: Khalti pidx (payment index)
            
        Returns:
            dict: Verification response
        """
        try:
            # Prepare verification payload
            payload = {
                'pidx': reference_id
            }
            
            # Make verification request
            response = requests.post(
                self.verify_url,
                json=payload,
                headers=self._get_headers(),
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Check payment status
            status = data.get('status', '').lower()
            is_completed = status == 'completed'
            
            # Parse amount (convert from paisa to NPR)
            amount_paisa = data.get('total_amount', 0)
            amount = Decimal(amount_paisa) / 100
            
            if is_completed:
                logger.info(f"Khalti payment verified: {transaction_id}, pidx: {reference_id}")
                
                return {
                    'success': True,
                    'verified': True,
                    'transaction_id': transaction_id,
                    'reference_id': reference_id,
                    'pidx': reference_id,
                    'amount': amount,
                    'status': 'completed',
                    'gateway': 'khalti',
                    'transaction_date': data.get('created_on'),
                    'fee': Decimal(data.get('fee', 0)) / 100,
                    'refunded': data.get('refunded', False),
                    'raw_response': data
                }
            else:
                logger.warning(f"Khalti payment not completed: {transaction_id}, status: {status}")
                
                return {
                    'success': False,
                    'verified': False,
                    'transaction_id': transaction_id,
                    'reference_id': reference_id,
                    'status': status,
                    'gateway': 'khalti',
                    'error': f'Payment status: {status}',
                    'raw_response': data
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Khalti verification failed: {e}")
            error_message = str(e)
            
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_message = error_data.get('detail', error_message)
                except:
                    error_message = e.response.text
            
            return {
                'success': False,
                'verified': False,
                'error': error_message,
                'gateway': 'khalti'
            }
        except Exception as e:
            logger.error(f"Khalti verification error: {e}")
            return {
                'success': False,
                'verified': False,
                'error': str(e),
                'gateway': 'khalti'
            }
    
    def get_transaction_status(
        self,
        transaction_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get Khalti transaction status.
        
        Args:
            transaction_id: Transaction ID
            **kwargs: Must contain 'pidx' (Khalti payment index)
            
        Returns:
            dict: Transaction status
        """
        pidx = kwargs.get('pidx') or kwargs.get('reference_id')
        
        if not pidx:
            return {
                'success': False,
                'error': 'pidx (payment index) is required',
                'gateway': 'khalti'
            }
        
        # Use verify_payment to check status
        return self.verify_payment(transaction_id, pidx)
    
    def refund_payment(
        self,
        transaction_id: str,
        amount: Decimal,
        reason: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Refund Khalti payment.
        
        Note: Khalti refunds are processed manually through merchant dashboard.
        This method is for record-keeping purposes.
        
        Args:
            transaction_id: Original transaction ID
            amount: Refund amount
            reason: Refund reason
            
        Returns:
            dict: Refund response
        """
        logger.info(f"Khalti refund requested: {transaction_id}, amount: NPR {amount}")
        
        return {
            'success': False,
            'error': 'Khalti refunds must be processed manually through merchant dashboard',
            'gateway': 'khalti',
            'transaction_id': transaction_id,
            'amount': amount,
            'reason': reason,
            'instructions': 'Please contact Khalti support to process this refund'
        }
    
    def validate_webhook(
        self,
        payload: Dict[str, Any],
        signature: str = None,
        **kwargs
    ) -> bool:
        """
        Validate Khalti webhook.
        
        Args:
            payload: Webhook payload
            signature: Webhook signature (if provided)
            
        Returns:
            bool: True if valid
        """
        try:
            # Khalti webhook parameters
            pidx = payload.get('pidx')
            transaction_id = payload.get('purchase_order_id')
            amount = payload.get('amount')
            status = payload.get('status')
            
            if not all([pidx, transaction_id, amount, status]):
                logger.warning("Khalti webhook missing required parameters")
                return False
            
            # Verify the payment through API to ensure authenticity
            verification = self.verify_payment(transaction_id, pidx)
            
            return verification.get('verified', False)
            
        except Exception as e:
            logger.error(f"Khalti webhook validation error: {e}")
            return False
    
    def format_amount(self, amount: Decimal) -> int:
        """
        Format amount for Khalti (convert to paisa).
        
        Args:
            amount: Amount in NPR
            
        Returns:
            int: Amount in paisa
        """
        return int(amount * 100)
    
    def parse_amount(self, amount_paisa: int) -> Decimal:
        """
        Parse amount from Khalti response (convert from paisa to NPR).
        
        Args:
            amount_paisa: Amount in paisa
            
        Returns:
            Decimal: Amount in NPR
        """
        return Decimal(amount_paisa) / 100
    
    @staticmethod
    def get_test_credentials() -> Dict[str, str]:
        """
        Get Khalti test/sandbox credentials.
        
        Returns:
            dict: Test credentials
        """
        return {
            'public_key': 'test_public_key_dc74e0fd57cb46cd93832aee0a390234',
            'secret_key': 'test_secret_key_f59e8b7d18b4499ca40f68195a846e9b',
            'is_production': False
        }
