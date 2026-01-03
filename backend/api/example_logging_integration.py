"""
Example of integrating centralized logging with an existing API view.

This demonstrates how to add comprehensive logging to your Django views
with automatic context capture for Grafana/Loki visualization.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from diavgeia_project.logging.logging_utils import api_logger, log_api_calls
import time


# Method 1: Using decorator for automatic logging
@log_api_calls()
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def user_dashboard(request):
    """
    User dashboard endpoint with automatic logging via decorator.
    
    All requests/responses are automatically logged with:
    - HTTP method, endpoint, status code
    - Response time, user ID, IP address
    - Error details if any exceptions occur
    """
    if request.method == 'GET':
        # Your existing logic here
        data = {
            "user": request.user.username,
            "dashboard_data": "...",
        }
        return JsonResponse(data)
    
    elif request.method == 'POST':
        # Your existing logic here
        return JsonResponse({"status": "updated"})


# Method 2: Manual logging with custom context
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_document(request):
    """
    Document processing endpoint with manual detailed logging.
    
    This shows how to add custom context and intermediate logging
    for complex operations that need detailed monitoring.
    """
    document_id = request.data.get('document_id')
    
    # Set context for all logs in this request
    api_logger.set_context(
        document_id=document_id,
        operation='document_processing',
        user_id=request.user.id
    )
    
    api_logger.info("Document processing request received")
    
    try:
        # Simulate processing steps with detailed logging
        api_logger.info("Starting document validation")
        
        # Your validation logic here
        if not document_id:
            api_logger.warning("Document processing failed: missing document_id")
            return Response(
                {"error": "document_id is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        api_logger.info("Document validation completed")
        
        # Simulate processing with timing
        start_time = time.time()
        api_logger.info("Starting document text extraction")
        
        # Your text extraction logic here
        # ... processing ...
        
        processing_time = (time.time() - start_time) * 1000  # Convert to ms
        api_logger.info(
            "Document text extraction completed", 
            extra={"processing_time_ms": processing_time}
        )
        
        # More processing steps...
        api_logger.info("Document processing completed successfully")
        
        return Response({
            "status": "success",
            "document_id": document_id,
            "processing_time_ms": processing_time
        })
        
    except Exception as e:
        # Detailed error logging
        api_logger.exception(
            "Document processing failed with unexpected error",
            extra={
                "error_type": type(e).__name__,
                "error_details": str(e)[:200]  # Truncate long errors
            }
        )
        return Response(
            {"error": "Internal server error"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    finally:
        # Clean up context
        api_logger.clear_context()


# Method 3: Using temporary context managers
@api_view(['GET'])
@permission_classes([IsAuthenticated])  
def user_analytics(request):
    """
    Analytics endpoint demonstrating context managers for scoped logging.
    """
    user_id = request.user.id
    
    with api_logger.context(operation='analytics_generation', user_id=user_id):
        api_logger.info("Analytics generation started")
        
        try:
            # Different analytics sections with their own context
            with api_logger.context(analytics_type='usage_stats'):
                api_logger.info("Generating usage statistics")
                # Your usage stats logic
                usage_data = {"requests": 42, "last_login": "2025-09-29"}
            
            with api_logger.context(analytics_type='performance_metrics'):
                api_logger.info("Generating performance metrics")  
                # Your performance metrics logic
                performance_data = {"avg_response_time": 120}
            
            api_logger.info("Analytics generation completed successfully")
            
            return Response({
                "usage": usage_data,
                "performance": performance_data
            })
            
        except Exception as e:
            api_logger.exception("Analytics generation failed")
            return Response(
                {"error": "Failed to generate analytics"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Example of Celery task logging integration
from celery import shared_task
from diavgeia_project.logging.logging_utils import task_logger, log_task_execution

@shared_task
@log_task_execution()
def process_document_async(document_id, user_id):
    """
    Async document processing task with automatic logging.
    
    The decorator automatically logs:
    - Task start/completion with timing
    - Task arguments and return values
    - Failure details with stack traces
    """
    # Your task logic here
    task_logger.info("Processing document asynchronously", extra={
        "document_id": document_id,
        "user_id": user_id
    })
    
    # Simulate processing
    import time
    time.sleep(2)  # Simulate work
    
    result = {"status": "processed", "document_id": document_id}
    task_logger.info("Document processing completed", extra=result)
    
    return result


# Example of middleware integration (optional)
class LoggingContextMiddleware:
    """
    Middleware to automatically set request context for all views.
    
    Add to MIDDLEWARE in settings.py:
    'your_app.middleware.LoggingContextMiddleware'
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Set context at start of request
        if hasattr(request, 'user') and request.user.is_authenticated:
            api_logger.set_context(
                user_id=request.user.id,
                username=request.user.username,
                request_id=id(request)  # Unique per request
            )
        
        response = self.get_response(request)
        
        # Clear context at end of request
        api_logger.clear_context()
        
        return response