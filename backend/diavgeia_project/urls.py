"""
URL configuration for diavgeia_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from core.views.health import health_check
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from admin_custom.sites import admin_site

# Define schema_view FIRST before using it
# Note: permission_classes defaults to [] which means it will use
# DEFAULT_PERMISSION_CLASSES from settings, or rely on middleware
schema_view = get_schema_view(
   openapi.Info(
      title="Crati API",
      default_version='v1',
      description="API for searching and processing Greek government decisions",
      contact=openapi.Contact(email="contact@crati.app"),
   ),
   public=True,
   # Removed permission_classes - let middleware handle authentication
)

# Then define your urlpatterns (just once, not twice!)
urlpatterns = [
    path("api/admin/", admin_site.urls),
    path("health/", health_check, name="health_check"),
    path("", health_check, name="root_health_check"),
    path("api/", include("api.urls")),
    path('api/docs/', csrf_exempt(never_cache(schema_view.with_ui('swagger', cache_timeout=0))), name='schema-swagger-ui'),
    path('api/redoc/', csrf_exempt(never_cache(schema_view.with_ui('redoc', cache_timeout=0))), name='schema-redoc'),
]