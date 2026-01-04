from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.conf import settings


@api_view(["GET"])
@permission_classes([AllowAny])
def system_config(request):
    """
    Get system configuration and feature flags.
    This endpoint can be called by the frontend to determine which features are enabled.
    """
    return Response({
        "features": {
            "opensearch_indexing": settings.INDEX_THE_OPENSEARCH,
            "company_enrichment": settings.HAVE_AFM_FETCH_JOB,
            "document_extraction": settings.EXTRACT_THE_DOCS_FROM_PDFS,
        },
        "settings": {
            "retry_afm_fetches_after_days": settings.RETRY_AFM_FETCHES_AFTER_NUMBER_OF_DAYS,
        },
        "messages": {
            "opensearch": (
                "OpenSearch indexing is disabled. Document search uses PostgreSQL fallback only."
                if not settings.INDEX_THE_OPENSEARCH else None
            ),
            "company_enrichment": (
                "Company data enrichment is disabled. Only AFM entity information is maintained."
                if not settings.HAVE_AFM_FETCH_JOB else None
            ),
            "document_extraction": (
                "Document text extraction is disabled. PDF content analysis is not available."
                if not settings.EXTRACT_THE_DOCS_FROM_PDFS else None
            ),
        }
    })
