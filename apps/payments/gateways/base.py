"""
Base Payment Gateway Interface
All payment gateways must implement this interface
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from decimal import Decimal


class PaymentGateway(ABC):
    """
    Abstract base class for payment gateway integrations.
    All payment gateways (eSewa, Khalti, etc.) must implement these methods.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize payment gateway with configuration.
        
        Args:
            config: Gateway-specific configuration (API keys, URLs, etc.)
        """
        self.config = config or {}
    
    @abstractmethod
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
        Initiate a payment transaction.
        
        Args:
            amount: Payment amount in NPR
            transaction_id: Unique transaction identifier
            product_name: Name/description of product/service
            customer_info: Customer details (name, email, phone)
            success_url: URL to redirect on success
            failure_url: URL to redirect on failure
            **kwargs: Additional gateway-specific parameters
            
        Returns:
            dict: Payment initiation response with payment URL and reference
        """
        pass
    
    @abstractmethod
    def verify_payment(
        self,
        transaction_id: str,
        reference_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Verify a payment transaction.
        
        Args:
            transaction_id: Original transaction identifier
            reference_id: Gateway reference/transaction ID
            **kwargs: Additional gateway-specific parameters
            
        Returns:
            dict: Payment verification response with status and details
        """
        pass
    
    @abstractmethod
    def get_transaction_status(
        self,
        transaction_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get current status of a transaction.
        
        Args:
            transaction_id: Transaction identifier
            **kwargs: Additional gateway-specific parameters
            
        Returns:
            dict: Transaction status details
        """
        pass
    
    def refund_payment(
        self,
        transaction_id: str,
        amount: Decimal,
        reason: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Refund a payment transaction (optional, not all gateways support this).
        
        Args:
            transaction_id: Original transaction identifier
            amount: Refund amount
            reason: Refund reason
            **kwargs: Additional gateway-specific parameters
            
        Returns:
            dict: Refund response
        """
        raise NotImplementedError("Refund not supported by this gateway")
    
    def validate_webhook(
        self,
        payload: Dict[str, Any],
        signature: str = None,
        **kwargs
    ) -> bool:
        """
        Validate webhook/callback from payment gateway.
        
        Args:
            payload: Webhook payload
            signature: Webhook signature (if applicable)
            **kwargs: Additional gateway-specific parameters
            
        Returns:
            bool: True if webhook is valid
        """
        return True  # Default implementation, override if gateway supports webhook validation
    
    def format_amount(self, amount: Decimal) -> str:
        """
        Format amount according to gateway requirements.
        
        Args:
            amount: Amount to format
            
        Returns:
            str: Formatted amount
        """
        return str(amount)
    
    def parse_amount(self, amount_str: str) -> Decimal:
        """
        Parse amount from gateway response.
        
        Args:
            amount_str: Amount string from gateway
            
        Returns:
            Decimal: Parsed amount
        """
        return Decimal(amount_str)
