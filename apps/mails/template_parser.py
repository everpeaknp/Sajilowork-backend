"""
Email Template Parser
Handles variable replacement and template rendering
"""
import re
from typing import Dict, List, Any
from django.template import Context, Template, TemplateSyntaxError
from django.utils.html import escape
import logging

logger = logging.getLogger(__name__)


class TemplateParser:
    """
    Parses email templates and replaces variables with actual values.
    
    Supports:
    - Simple variables: {{variable_name}}
    - Django template syntax: {{variable|filter}}
    - Nested attributes: {{user.name}}
    - Default values: {{variable|default:"value"}}
    - Filters: {{variable|upper}}, {{variable|lower}}, {{variable|title}}
    """
    
    # Regex pattern for finding variables
    VARIABLE_PATTERN = re.compile(r'\{\{([^}]+)\}\}')
    
    # Supported variable categories and their keys
    AVAILABLE_VARIABLES = {
        'user': [
            'user_id', 'user_name', 'user_email', 'user_first_name', 
            'user_last_name', 'user_phone', 'user_profile_url'
        ],
        'task': [
            'task_id', 'task_title', 'task_description', 'task_budget',
            'task_location', 'task_deadline', 'task_status', 'task_url',
            'task_category'
        ],
        'bid': [
            'bid_id', 'bid_amount', 'bidder_name', 'bidder_email',
            'bid_message', 'bid_deadline', 'bid_url'
        ],
        'payment': [
            'payment_id', 'payment_amount', 'payment_method', 
            'payment_status', 'transaction_id', 'payment_date'
        ],
        'review': [
            'review_id', 'review_rating', 'review_comment', 
            'reviewer_name', 'review_date'
        ],
        'message': [
            'message_id', 'message_text', 'sender_name', 'conversation_url'
        ],
        'system': [
            'company_name', 'company_logo_url', 'support_email', 
            'support_phone', 'website_url', 'app_url'
        ],
        'links': [
            'verification_link', 'reset_password_link', 'unsubscribe_link',
            'dashboard_link', 'task_details_link', 'bid_details_link',
            'payment_details_link', 'settings_link'
        ]
    }
    
    @classmethod
    def parse(cls, template_content: str, context: Dict[str, Any]) -> str:
        """
        Parse template and replace variables with actual values.
        
        Args:
            template_content: Template string with variables
            context: Dictionary of variable values
            
        Returns:
            Parsed template with variables replaced
            
        Raises:
            TemplateSyntaxError: If template syntax is invalid
        """
        try:
            # Use Django template engine for advanced features
            django_template = Template(template_content)
            django_context = Context(context, autoescape=True)
            
            # Render template
            rendered = django_template.render(django_context)
            
            logger.debug(f"Successfully parsed template with {len(context)} variables")
            return rendered
            
        except TemplateSyntaxError as e:
            logger.error(f"Template syntax error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error parsing template: {e}")
            # Return original template if parsing fails (fail gracefully)
            return template_content
    
    @classmethod
    def validate(cls, template_content: str) -> tuple[bool, str]:
        """
        Validate template syntax.
        
        Args:
            template_content: Template string to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Try to create template
            Template(template_content)
            return True, ""
            
        except TemplateSyntaxError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Unknown error: {str(e)}"
    
    @classmethod
    def get_variables(cls, template_content: str) -> List[str]:
        """
        Extract all variables from template.
        
        Args:
            template_content: Template string
            
        Returns:
            List of variable names found in template
        """
        try:
            # Find all {{...}} patterns
            matches = cls.VARIABLE_PATTERN.findall(template_content)
            
            # Extract variable names (strip filters and whitespace)
            variables = []
            for match in matches:
                # Remove filters (e.g., "user_name|upper" -> "user_name")
                var_name = match.split('|')[0].strip()
                
                # Remove quotes from default values
                var_name = var_name.split(':')[0].strip()
                
                variables.append(var_name)
            
            return list(set(variables))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Error extracting variables: {e}")
            return []
    
    @classmethod
    def get_missing_variables(cls, template_content: str, context: Dict[str, Any]) -> List[str]:
        """
        Get list of variables in template that are not in context.
        
        Args:
            template_content: Template string
            context: Context dictionary
            
        Returns:
            List of missing variable names
        """
        template_vars = cls.get_variables(template_content)
        context_keys = set(context.keys())
        
        missing = []
        for var in template_vars:
            # Check simple variable
            if var not in context_keys:
                # Check nested variables (e.g., user.name)
                if '.' in var:
                    root = var.split('.')[0]
                    if root not in context_keys:
                        missing.append(var)
                else:
                    missing.append(var)
        
        return missing
    
    @classmethod
    def get_available_variables(cls) -> Dict[str, List[str]]:
        """
        Get all available template variables organized by category.
        
        Returns:
            Dictionary of variable categories and their keys
        """
        return cls.AVAILABLE_VARIABLES
    
    @classmethod
    def build_sample_context(cls) -> Dict[str, Any]:
        """
        Build a sample context for template preview/testing.
        
        Returns:
            Dictionary with sample values for all variables
        """
        return {
            # User variables
            'user_id': '123e4567-e89b-12d3-a456-426614174000',
            'user_name': 'John Doe',
            'user_email': 'john.doe@example.com',
            'user_first_name': 'John',
            'user_last_name': 'Doe',
            'user_phone': '+1234567890',
            'user_profile_url': 'https://airtasker.com/users/johndoe',
            
            # Task variables
            'task_id': '456e7890-e89b-12d3-a456-426614174000',
            'task_title': 'Website Design and Development',
            'task_description': 'Looking for a professional web designer...',
            'task_budget': '$500 - $1,000',
            'task_location': 'Remote',
            'task_deadline': 'January 30, 2024',
            'task_status': 'Open',
            'task_url': 'https://airtasker.com/tasks/456',
            'task_category': 'Web Development',
            
            # Bid variables
            'bid_id': '789e0123-e89b-12d3-a456-426614174000',
            'bid_amount': '$750',
            'bidder_name': 'Jane Smith',
            'bidder_email': 'jane.smith@example.com',
            'bid_message': 'I have 5 years of experience in web design...',
            'bid_deadline': 'January 25, 2024',
            'bid_url': 'https://airtasker.com/bids/789',
            
            # Payment variables
            'payment_id': '012e3456-e89b-12d3-a456-426614174000',
            'payment_amount': '$750.00',
            'payment_method': 'Credit Card',
            'payment_status': 'Completed',
            'transaction_id': 'TXN-20240115-001',
            'payment_date': 'January 15, 2024',
            
            # Review variables
            'review_id': '345e6789-e89b-12d3-a456-426614174000',
            'review_rating': '5',
            'review_comment': 'Excellent work! Very professional.',
            'reviewer_name': 'John Doe',
            'review_date': 'January 20, 2024',
            
            # Message variables
            'message_id': '678e9012-e89b-12d3-a456-426614174000',
            'message_text': 'Hello, I have a question about the task...',
            'sender_name': 'Jane Smith',
            'conversation_url': 'https://airtasker.com/messages/678',
            
            # System variables
            'company_name': 'Airtasker',
            'company_logo_url': 'https://airtasker.com/logo.png',
            'support_email': 'support@airtasker.com',
            'support_phone': '+1-800-AIRTASK',
            'website_url': 'https://airtasker.com',
            'app_url': 'https://app.airtasker.com',
            
            # Links
            'verification_link': 'https://airtasker.com/verify-email?token=abc123',
            'reset_password_link': 'https://airtasker.com/reset-password?token=xyz789',
            'unsubscribe_link': 'https://airtasker.com/unsubscribe?token=def456',
            'dashboard_link': 'https://airtasker.com/dashboard',
            'task_details_link': 'https://airtasker.com/tasks/456',
            'bid_details_link': 'https://airtasker.com/bids/789',
            'payment_details_link': 'https://airtasker.com/payments/012',
            'settings_link': 'https://airtasker.com/settings',
        }
    
    @classmethod
    def escape_html(cls, value: str) -> str:
        """
        Escape HTML to prevent XSS attacks.
        
        Args:
            value: String to escape
            
        Returns:
            HTML-escaped string
        """
        return escape(value)
    
    @classmethod
    def preview_template(cls, template_content: str, context: Dict[str, Any] = None) -> str:
        """
        Generate a preview of the template with sample or provided context.
        
        Args:
            template_content: Template string
            context: Optional context (uses sample context if not provided)
            
        Returns:
            Rendered template preview
        """
        if context is None:
            context = cls.build_sample_context()
        
        return cls.parse(template_content, context)
