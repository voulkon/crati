from django.http import JsonResponse
from core.services.version_service import VersionService


def health_check(request):
    """Health check endpoint that returns version and status information."""
    service = VersionService()
    return JsonResponse(service.get_health_info())
