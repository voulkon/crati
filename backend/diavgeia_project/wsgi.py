"""
WSGI config for diavgeia_project project.
"""

import os
from django.core.wsgi import get_wsgi_application

# Add this at the very top to see if wsgi.py is loaded
print("🚨🚨🚨 WSGI.PY IS BEING EXECUTED 🚨🚨🚨")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "diavgeia_project.settings")

try:
    # Check if tracing is enabled
    transmit_to_jaeger = os.getenv('TRANSMIT_TO_JAEGER', 'True').lower() == 'true'
    
    if transmit_to_jaeger:
        # Simple approach - just force the Django service name
        print("🚀 Setting Django service name...")
        os.environ["OTEL_SERVICE_NAME"] = "diavgeia-django"
        
        # Import and initialize after setting the service name
        from .otel_init import initialize_otel
        from opentelemetry.instrumentation.django import DjangoInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
        
        # Initialize with Django service name
        tracer = initialize_otel("diavgeia-django")
        print(f"✅ OpenTelemetry initialized for Django with tracer: {tracer}")
        
        # Auto-instrument
        DjangoInstrumentor().instrument()
        RequestsInstrumentor().instrument()
        Psycopg2Instrumentor().instrument()
        print("✅ All Django instrumentations complete")
    else:
        print("🔇 Jaeger tracing disabled (TRANSMIT_TO_JAEGER=false)")
    
except Exception as e:
    print(f"❌ OpenTelemetry initialization failed in wsgi.py: {e}")
    import traceback
    traceback.print_exc()

# Get the Django application
print("📱 Getting Django WSGI application...")
application = get_wsgi_application()
print("✅ WSGI application ready")