"""
WSGI config for diavgeia_project project.
"""

import os
from django.core.wsgi import get_wsgi_application
from loguru import logger
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "diavgeia_project.settings")

try:
    # Check if tracing is enabled
    transmit_to_jaeger = os.getenv('TRANSMIT_TO_JAEGER', 'True').lower() == 'true'
    
    if transmit_to_jaeger:
        # Simple approach - just force the Django service name
        os.environ["OTEL_SERVICE_NAME"] = "diavgeia-django"
        
        # Import and initialize after setting the service name
        from .otel_init import initialize_otel
        from opentelemetry.instrumentation.django import DjangoInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
        
        # Initialize with Django service name
        tracer = initialize_otel("diavgeia-django")
        
        # Auto-instrument
        DjangoInstrumentor().instrument()
        RequestsInstrumentor().instrument()
        Psycopg2Instrumentor().instrument()
        logger.info("✅ All Django instrumentations complete")
    else:
        logger.info("🔇 Jaeger tracing disabled (TRANSMIT_TO_JAEGER=false)")
    
except Exception as e:
    logger.error(f"❌ OpenTelemetry initialization failed in wsgi.py: {e}")
    import traceback
    traceback.print_exc()

# Get the Django application
application = get_wsgi_application()
logger.info("✅ WSGI application ready")