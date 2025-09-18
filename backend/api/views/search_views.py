from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from core.services.search_service import SearchService
from core.services.search_analytics_service import SearchAnalyticsService
from django.conf import settings
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from datetime import datetime, timedelta
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.core.paginator import Paginator
from core.models.decisions import Decision, DecisionAmountKAE
from core.models.organizations import Organization, Signer, Unit
from django.db import models
from django.db.models import Func, F
from django.db.models.functions import TruncMonth, TruncDay, TruncWeek, TruncYear, TruncQuarter
import urllib.parse



