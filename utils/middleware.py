"""
Custom middleware for request/response processing.
"""
import logging
import time
import json
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log all API requests and responses.
    """
    
    def process_request(self, request):
        request.start_time = time.time()
        
        if request.path.startswith('/api/'):
            logger.info(f"API Request: {request.method} {request.path}")
            if request.body:
                try:
                    body = json.loads(request.body)
                    # Mask sensitive data
                    if 'password' in body:
                        body['password'] = '***'
                    logger.debug(f"Request Body: {body}")
                except:
                    pass
        
        return None
    
    def process_response(self, request, response):
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            if request.path.startswith('/api/'):
                logger.info(
                    f"API Response: {request.method} {request.path} "
                    f"Status: {response.status_code} Duration: {duration:.2f}s"
                )
        
        return response


class ExceptionHandlerMiddleware(MiddlewareMixin):
    """
    Middleware to handle uncaught exceptions.
    """
    
    def process_exception(self, request, exception):
        logger.error(
            f"Unhandled exception: {str(exception)}",
            exc_info=True,
            extra={'request': request}
        )
        return None
