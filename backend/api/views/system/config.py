from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.conf import settings
from core.services.feature_flag_service import feature_flags


@api_view(["GET"])
@permission_classes([AllowAny])
def system_config(request):
    """
    Get system configuration and feature flags.
    This endpoint can be called by the frontend to determine which features are enabled.
    Uses the feature flag service to check DB first, then environment variables.
    """
    return Response({
        "features": {
            "opensearch_indexing": feature_flags.is_enabled('INDEX_THE_OPENSEARCH'),
            "company_enrichment": feature_flags.is_enabled('HAVE_AFM_FETCH_JOB'),
            "document_extraction": feature_flags.is_enabled('EXTRACT_THE_DOCS_FROM_PDFS'),
            "jaeger_tracing": feature_flags.is_enabled('TRANSMIT_TO_JAEGER'),
        },
        "settings": {
            "retry_afm_fetches_after_days": settings.RETRY_AFM_FETCHES_AFTER_NUMBER_OF_DAYS,
        },
        "messages": {
            "opensearch": (
                "OpenSearch indexing is disabled. Document search uses PostgreSQL fallback only."
                if not feature_flags.is_enabled('INDEX_THE_OPENSEARCH') else None
            ),
            "company_enrichment": (
                "Company data enrichment is disabled. Only AFM entity information is maintained."
                if not feature_flags.is_enabled('HAVE_AFM_FETCH_JOB') else None
            ),
            "document_extraction": (
                "Document text extraction is disabled. PDF content analysis is not available."
                if not feature_flags.is_enabled('EXTRACT_THE_DOCS_FROM_PDFS') else None
            ),
            "jaeger_tracing": (
                "Distributed tracing is disabled. No telemetry data is sent to Jaeger."
                if not feature_flags.is_enabled('TRANSMIT_TO_JAEGER') else None
            ),
        }
    })
