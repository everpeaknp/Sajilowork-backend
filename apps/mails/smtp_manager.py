"""
SMTP Manager - Handles SMTP connections and email sending
"""
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.core.mail.backends.smtp import EmailBackend
from typing import Optional, Dict, Any
import logging
import smtplib

from .models import SMTPConfiguration
from utils.field_encryption import decrypt_secret, encrypt_secret

logger = logging.getLogger(__name__)


class SMTPManager:
    """
    Manager for SMTP connections and email sending.
    Handles multiple SMTP providers and configurations.
    """
    
    @classmethod
    def test_connection(cls, smtp_config: SMTPConfiguration) -> tuple[bool, str]:
        """
        Test SMTP connection with provided configuration.
        
        Args:
            smtp_config: SMTPConfiguration object
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Create SMTP connection
            if smtp_config.encryption == 'ssl':
                server = smtplib.SMTP_SSL(smtp_config.host, smtp_config.port, timeout=10)
            else:
                server = smtplib.SMTP(smtp_config.host, smtp_config.port, timeout=10)
                
                if smtp_config.encryption == 'tls':
                    server.starttls()
            
            # Authenticate
            server.login(smtp_config.username, cls.decrypt_password(smtp_config.password))
            
            # Close connection
            server.quit()
            
            logger.info(f"SMTP connection test successful for {smtp_config.name}")
            return True, "Connection successful"
            
        except smtplib.SMTPAuthenticationError:
            message = "Authentication failed. Check username and password."
            logger.error(f"SMTP auth error for {smtp_config.name}: {message}")
            return False, message
            
        except smtplib.SMTPConnectError:
            message = "Connection failed. Check host and port."
            logger.error(f"SMTP connect error for {smtp_config.name}: {message}")
            return False, message
            
        except smtplib.SMTPException as e:
            message = f"SMTP error: {str(e)}"
            logger.error(f"SMTP error for {smtp_config.name}: {message}")
            return False, message
            
        except Exception as e:
            message = f"Unexpected error: {str(e)}"
            logger.error(f"SMTP test error for {smtp_config.name}: {message}")
            return False, message
    
    @classmethod
    def send_email(
        cls,
        smtp_config: SMTPConfiguration,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str = "",
        reply_to: str = None
    ) -> tuple[bool, str]:
        """
        Send email using SMTP configuration.
        
        Args:
            smtp_config: SMTPConfiguration object
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email body
            text_content: Plain text email body (optional)
            reply_to: Reply-to email address (optional)
            
        Returns:
            Tuple of (success, message/error)
        """
        try:
            # Create Django email backend with SMTP config
            backend = EmailBackend(
                host=smtp_config.host,
                port=smtp_config.port,
                username=smtp_config.username,
                password=cls.decrypt_password(smtp_config.password),
                use_tls=(smtp_config.encryption == 'tls'),
                use_ssl=(smtp_config.encryption == 'ssl'),
                fail_silently=False,
            )
            
            # Create email message
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content or html_content,  # Fallback to HTML if no text
                from_email=f"{smtp_config.from_name} <{smtp_config.from_email}>",
                to=[to_email],
                reply_to=[reply_to] if reply_to else None,
                connection=backend
            )
            
            # Attach HTML content
            if html_content:
                email.attach_alternative(html_content, "text/html")
            
            # Send email
            email.send()
            
            logger.info(f"Email sent successfully to {to_email} via {smtp_config.name}")
            return True, "Email sent successfully"
            
        except smtplib.SMTPAuthenticationError as e:
            message = f"Authentication failed: {str(e)}"
            logger.error(f"SMTP auth error: {message}")
            return False, message
            
        except smtplib.SMTPRecipientsRefused as e:
            message = f"Recipient refused: {str(e)}"
            logger.error(f"SMTP recipient error: {message}")
            return False, message
            
        except smtplib.SMTPException as e:
            message = f"SMTP error: {str(e)}"
            logger.error(f"SMTP send error: {message}")
            return False, message
            
        except Exception as e:
            message = f"Unexpected error: {str(e)}"
            logger.error(f"Email send error: {message}", exc_info=True)
            return False, message
    
    @classmethod
    def get_provider_config(cls, provider: str) -> Dict[str, Any]:
        """
        Get default configuration for common email providers.
        
        Args:
            provider: Provider name (gmail, outlook, sendgrid, etc.)
            
        Returns:
            Dictionary with host, port, encryption defaults
        """
        provider_configs = {
            'gmail': {
                'host': 'smtp.gmail.com',
                'port': 587,
                'encryption': 'tls',
                'notes': 'Use App Password if 2FA is enabled'
            },
            'outlook': {
                'host': 'smtp-mail.outlook.com',
                'port': 587,
                'encryption': 'tls',
                'notes': 'Microsoft 365 and Outlook.com accounts'
            },
            'sendgrid': {
                'host': 'smtp.sendgrid.net',
                'port': 587,
                'encryption': 'tls',
                'notes': 'Use "apikey" as username and API key as password'
            },
            'mailgun': {
                'host': 'smtp.mailgun.org',
                'port': 587,
                'encryption': 'tls',
                'notes': 'Use Mailgun SMTP credentials'
            },
            'ses': {
                'host': 'email-smtp.us-east-1.amazonaws.com',
                'port': 587,
                'encryption': 'tls',
                'notes': 'Use AWS SES SMTP credentials (region-specific)'
            },
        }
        
        return provider_configs.get(provider, {
            'host': '',
            'port': 587,
            'encryption': 'tls',
            'notes': 'Custom SMTP configuration'
        })
    
    @classmethod
    def encrypt_password(cls, password: str) -> str:
        return encrypt_secret(password)

    @classmethod
    def decrypt_password(cls, encrypted_password: str) -> str:
        return decrypt_secret(encrypted_password)
