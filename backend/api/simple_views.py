from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.core.cache import cache
import time
from .utils import get_client_ip


# Public endpoint example
@api_view(["GET"])
@permission_classes([AllowAny])
def public_endpoint(request):
    return Response({"message": "This is a public endpoint"})


# Protected endpoint example
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def protected_endpoint(request):
    return Response({"message": f"Hello, {request.user.username}!"})


@api_view(["GET"])
@permission_classes([AllowAny])
def check_api_usage(request):
    if request.user.is_authenticated:
        key = f"ratelimit:user:{request.user.id}"
        limit = request.user.daily_request_limit
    else:
        ip = get_client_ip(request)
        key = f"ratelimit:{ip}"
        limit = 100  # Anonymous limit

    usage = cache.get(key, {"count": 0, "reset_time": time.time() + 86400})
    remaining = max(0, limit - usage["count"])
    reset_time = int(usage["reset_time"])

    return Response(
        {
            "limit": limit,
            "remaining": remaining,
            "used": usage["count"],
            "reset_timestamp": reset_time,
            "authenticated": request.user.is_authenticated,
        }
    )


# You can also use ViewSets for your core models
# from core.models import YourModel
# from api.serializers import YourModelSerializer
#
# class YourModelViewSet(viewsets.ModelViewSet):
#     queryset = YourModel.objects.all()
#     serializer_class = YourModelSerializer
