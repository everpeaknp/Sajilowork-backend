"""
Custom exception handlers and error responses.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF that provides consistent error responses.
    """
    response = exception_handler(exc, context)
    
    if response is not None:
        custom_response_data = {
            'success': False,
            'error': {
                'message': str(exc),
                'details': response.data if isinstance(response.data, dict) else {'detail': response.data}
            }
        }
        response.data = custom_response_data
    
    return response


class APIException(Exception):
    """Base API exception."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_message = 'An error occurred'
    
    def __init__(self, message=None, status_code=None):
        self.message = message or self.default_message
        if status_code:
            self.status_code = status_code
    
    def __str__(self):
        return self.message


class ValidationError(APIException):
    """Validation error exception."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_message = 'Validation error'


class AuthenticationError(APIException):
    """Authentication error exception."""
    status_code = status.HTTP_401_UNAUTHORIZED
    default_message = 'Authentication failed'


class PermissionDenied(APIException):
    """Permission denied exception."""
    status_code = status.HTTP_403_FORBIDDEN
    default_message = 'Permission denied'


class NotFound(APIException):
    """Not found exception."""
    status_code = status.HTTP_404_NOT_FOUND
    default_message = 'Resource not found'


class ConflictError(APIException):
    """Conflict error exception."""
    status_code = status.HTTP_409_CONFLICT
    default_message = 'Resource conflict'
