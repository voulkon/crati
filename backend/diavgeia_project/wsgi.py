"""
WSGI config for diavgeia_project project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application
from opentelemetry.instrumentation.django import DjangoInstrumentor

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "diavgeia_project.settings")

# Initialize OpenTelemetry before the application starts
from diavgeia_project.otel_setup import setup_tracing

setup_tracing(service_name="diavgeia-django")

# Instrument Django
DjangoInstrumentor().instrument()

# Get the Django application
application = get_wsgi_application()
