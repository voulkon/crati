# Admin Refactoring Migration Plan

## Overview
Migrate from scattered admin components across `api`, `core`, and `users` apps to a consolidated `admin_custom` app.

**Estimated Time:** 6-8 hours (can be done over multiple sessions)
**Risk Level:** Low (incremental with validation at each step)
**Rollback Strategy:** Git branch - can revert at any checkpoint

---

## Pre-Migration Checklist

- [ ] Create a new git branch: `git checkout -b refactor/consolidate-admin`
- [ ] Ensure all tests pass: `python manage.py test`
- [ ] Backup database (if in production)
- [ ] Document current admin URLs (see Appendix A)
- [ ] Verify admin site is accessible at `/api/admin/`

---

## Phase 1: Foundation (30 minutes)

### Step 1.1: Create admin_custom App Structure

**Action:**
```bash
cd backend
python manage.py startapp admin_custom
```

**Then create directory structure:**
```bash
mkdir -p admin_custom/views
mkdir -p admin_custom/admin_classes
mkdir -p admin_custom/utils
mkdir -p admin_custom/templates/admin_custom
touch admin_custom/views/__init__.py
touch admin_custom/admin_classes/__init__.py
touch admin_custom/utils/__init__.py
touch admin_custom/sites.py
```

**Validation:**
```bash
# Verify structure
ls -R admin_custom/

# Expected output:
# admin_custom/:
# __init__.py  admin_classes/  apps.py  sites.py  templates/  utils/  views/
# 
# admin_custom/admin_classes:
# __init__.py
# 
# admin_custom/utils:
# __init__.py
# 
# admin_custom/views:
# __init__.py
```

✅ **Success Criteria:** All directories and files created

---

### Step 1.2: Register admin_custom App

**Action:** Add to `diavgeia_project/settings.py`

```python
INSTALLED_APPS = [
    # ... existing apps ...
    'admin_custom',  # Add BEFORE other apps to ensure it loads first
    'api',
    'core',
    'users',
    # ...
]
```

**Validation:**
```bash
python manage.py check

# Should output:
# System check identified no issues (0 silenced).
```

✅ **Success Criteria:** No errors from `manage.py check`

---

### Step 1.3: Configure admin_custom App

**Action:** Edit `admin_custom/apps.py`

```python
from django.apps import AppConfig


class AdminCustomConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'admin_custom'
    verbose_name = 'Admin Customizations'
```

**Validation:**
```bash
python manage.py shell
>>> from admin_custom.apps import AdminCustomConfig
>>> print(AdminCustomConfig.verbose_name)
Admin Customizations
>>> exit()
```

✅ **Success Criteria:** App config loads without error

---

## Phase 2: Move CustomAdminSite (45 minutes)

### Step 2.1: Create admin_custom/sites.py

**Action:** Create new file with CustomAdminSite

```python
# admin_custom/sites.py
from django.contrib import admin
from django.urls import path


class CustomAdminSite(admin.AdminSite):
    site_header = "Crati Administration"
    site_title = "Crati Admin"
    index_title = "Welcome to Crati Administration"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            # Analytics URLs
            path("analytics/", self._wrap_view('analytics_views', 'redis_analytics'), name="redis_analytics"),
            path("analytics/export/", self._wrap_view('analytics_views', 'export_redis_analytics'), name="export_analytics"),
            path("analytics/patterns/", self._wrap_view('analytics_views', 'pattern_analysis'), name="pattern_analysis"),
            path("analytics/endpoints/", self._wrap_view('analytics_views', 'endpoint_deep_dive'), name="endpoint_deep_dive"),
            
            # Decision URLs
            path("decisions/coverage/", self._wrap_view('decision_views', 'coverage_explorer'), name="coverage_explorer"),
            path("decisions/entity-search/", self._wrap_view('decision_views', 'entity_search'), name="entity_search"),
            path("decisions/daily-analysis/", self._wrap_view('decision_views', 'daily_decision_analysis'), name="daily_decision_analysis"),
            path("decisions/analysis-api/", self._wrap_view('decision_views', 'decision_analysis_api'), name="decision_analysis_api"),
            path("decisions/fetch-daily/", self._wrap_view('decision_views', 'fetch_daily_decisions'), name="fetch_daily_decisions"),
            
            # Organization URLs
            path("organizations/network/", self._wrap_view('organization_views', 'organization_network'), name="organization_network"),
            path("organizations/chart/", self._wrap_view('organization_views', 'organization_org_chart'), name="organization_chart"),
            
            # Document URLs
            path("documents/search/", self._wrap_view('document_views', 'document_search'), name="document_search"),
            path("documents/dashboard/", self._wrap_view('document_views', 'document_processing_dashboard'), name="document_dashboard"),
        ]
        return custom_urls + urls
    
    def _wrap_view(self, module_name, view_name):
        """Lazy import and wrap view to avoid circular imports"""
        from importlib import import_module
        module = import_module(f'admin_custom.views.{module_name}')
        view = getattr(module, view_name)
        return view

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)

        # Add custom Analytics section
        analytics_app = {
            "name": "Analytics & Monitoring",
            "app_label": "analytics",
            "models": [
                {"name": "Redis Analytics", "object_name": "RedisAnalytics", "admin_url": "/api/admin/analytics/", "view_only": True},
                {"name": "Export Analytics", "object_name": "ExportAnalytics", "admin_url": "/api/admin/analytics/export/", "view_only": True},
                {"name": "Pattern Analysis", "object_name": "PatternAnalysis", "admin_url": "/api/admin/analytics/patterns/", "view_only": True},
                {"name": "Endpoint Deep Dive", "object_name": "EndpointDeepDive", "admin_url": "/api/admin/analytics/endpoints/", "view_only": True},
            ],
        }
        app_list.append(analytics_app)

        # Add custom Decision Management section
        decision_mgmt_app = {
            "name": "Decision Management",
            "app_label": "decision_management",
            "models": [
                {"name": "Coverage Explorer", "object_name": "CoverageExplorer", "admin_url": "/api/admin/decisions/coverage/", "view_only": True},
                {"name": "Daily Decision Analysis", "object_name": "DailyDecisionAnalysis", "admin_url": "/api/admin/decisions/daily-analysis/", "view_only": True},
            ],
        }
        app_list.append(decision_mgmt_app)

        # Add custom Organization Tools section
        org_tools_app = {
            "name": "Organization Tools",
            "app_label": "organization_tools",
            "models": [
                {"name": "Organization Network", "object_name": "OrganizationNetwork", "admin_url": "/api/admin/organizations/network/", "view_only": True},
                {"name": "Organization Chart", "object_name": "OrganizationChart", "admin_url": "/api/admin/organizations/chart/", "view_only": True},
            ],
        }
        app_list.append(org_tools_app)

        # Add custom Document Processing section
        doc_processing_app = {
            "name": "Document Processing",
            "app_label": "document_processing",
            "models": [
                {"name": "Document Search", "object_name": "DocumentSearch", "admin_url": "/api/admin/documents/search/", "view_only": True},
                {"name": "Processing Dashboard", "object_name": "DocumentDashboard", "admin_url": "/api/admin/documents/dashboard/", "view_only": True},
            ],
        }
        app_list.append(doc_processing_app)

        return app_list


# Create singleton instance
admin_site = CustomAdminSite(name='custom_admin')
```

**Validation:**
```bash
python manage.py shell
>>> from admin_custom.sites import admin_site
>>> print(admin_site.site_header)
Crati Administration
>>> print(type(admin_site))
<class 'admin_custom.sites.CustomAdminSite'>
>>> exit()
```

✅ **Success Criteria:** CustomAdminSite imports successfully

---

### Step 2.2: Update URL Configuration (Dual Mode)

**Action:** Temporarily support BOTH old and new admin sites in `diavgeia_project/urls.py`

```python
from django.contrib import admin
from django.urls import path, include
from core.views.health import health_check
from api.admin import admin_site as old_admin_site  # Keep old temporarily
from admin_custom.sites import admin_site as new_admin_site  # Add new
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache

schema_view = get_schema_view(
   openapi.Info(
      title="Crati API",
      default_version='v1',
      description="API for searching and processing Greek government decisions",
      contact=openapi.Contact(email="contact@crati.app"),
   ),
   public=True,
   permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    # NEW admin (testing)
    path("api/admin-new/", new_admin_site.urls),  # Test URL
    
    # OLD admin (keep working)
    path("api/admin/", old_admin_site.urls),  # Keep existing
    
    path("health/", health_check, name="health_check"),
    path("", health_check, name="root_health_check"),
    path("api/", include("api.urls")),
    path('api/docs/', csrf_exempt(never_cache(schema_view.with_ui('swagger', cache_timeout=0))), name='schema-swagger-ui'),
    path('api/redoc/', csrf_exempt(never_cache(schema_view.with_ui('redoc', cache_timeout=0))), name='schema-redoc'),
]
```

**Validation:**
```bash
python manage.py check
python manage.py runserver

# In browser:
# 1. Visit http://localhost:8000/api/admin/ (OLD - should still work)
# 2. Visit http://localhost:8000/api/admin-new/ (NEW - should load but without views yet)
```

✅ **Success Criteria:** Both admin URLs accessible, old admin fully functional

---

## Phase 3: Move Admin Views (2 hours)

### Step 3.1: Move Analytics Views

**Action:** Create `admin_custom/views/analytics_views.py`

Copy content from `api/admin_views.py` and update imports:

```python
# admin_custom/views/analytics_views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.http import HttpResponse
from django_redis import get_redis_connection
from django.core.cache import cache
import csv
from datetime import datetime, timedelta
import time
from api.models import APIAnalytics, EndpointStats  # Keep reference to api.models
from collections import Counter
from django.db.models import Count, Avg


@staff_member_required
def redis_analytics(request):
    """Admin view showing Redis analytics dashboard"""
    # ... copy full implementation from api/admin_views.py
    pass


@staff_member_required
def export_redis_analytics(request):
    """Export analytics data as CSV"""
    # ... copy full implementation
    pass


@staff_member_required
def pattern_analysis(request):
    """Advanced pattern analysis view for API Analytics"""
    # ... copy full implementation
    pass


@staff_member_required
def endpoint_deep_dive(request):
    """Deep dive into endpoint usage patterns"""
    # ... copy full implementation
    pass
```

**Validation:**
```bash
python manage.py check

python manage.py shell
>>> from admin_custom.views.analytics_views import redis_analytics
>>> print(redis_analytics.__name__)
redis_analytics
>>> exit()
```

✅ **Success Criteria:** Views import successfully, no syntax errors

---

### Step 3.2: Move Decision Views

**Action:** Create `admin_custom/views/decision_views.py`

Copy relevant views from `core/admin_views.py`:

```python
# admin_custom/views/decision_views.py
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from datetime import date, datetime, timedelta
from core.models.import_jobs import DateCoverage
from core.models.decisions import Decision
from core.services.search_service import SearchService
from core.services.decision_analysis_service import DecisionAnalysisService
from loguru import logger


@staff_member_required
def coverage_explorer(request):
    """View for exploring decision coverage by organization, unit, or signer"""
    # ... copy implementation
    pass


@staff_member_required
def entity_search(request):
    """Search for organizations, units, or signers for the coverage explorer."""
    # ... copy implementation
    pass


@staff_member_required
def daily_decision_analysis(request):
    """Admin view for analyzing daily decision composition"""
    # ... copy implementation
    pass


@staff_member_required
def decision_analysis_api(request):
    """JSON API endpoint for decision analysis data"""
    # ... copy implementation
    pass


@staff_member_required
def fetch_daily_decisions(request):
    """Admin view to trigger fetching decisions for a specific day"""
    # ... copy implementation
    pass
```

**Validation:**
```bash
python manage.py check

python manage.py shell
>>> from admin_custom.views.decision_views import coverage_explorer
>>> print(coverage_explorer.__name__)
coverage_explorer
>>> exit()
```

✅ **Success Criteria:** Views import successfully

---

### Step 3.3: Move Organization Views

**Action:** Create `admin_custom/views/organization_views.py`

```python
# admin_custom/views/organization_views.py
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from core.models.organizations import Organization, OrganizationStatus
from core.services.organization_chart_service import OrganizationChartService


@staff_member_required
def organization_network(request):
    """View for visualizing organization networks"""
    # ... copy implementation
    pass


@staff_member_required
def organization_org_chart(request):
    """View for traditional org chart visualization"""
    # ... copy implementation
    pass
```

**Validation:**
```bash
python manage.py shell
>>> from admin_custom.views.organization_views import organization_network
>>> print(organization_network.__name__)
organization_network
>>> exit()
```

✅ **Success Criteria:** Views import successfully

---

### Step 3.4: Move Document Views

**Action:** Create `admin_custom/views/document_views.py`

```python
# admin_custom/views/document_views.py
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Avg, ExpressionWrapper, fields
from django.db.models.functions import TruncDate
from core.models.document_analysis import DocumentExtraction, ProcessingStatus
from core.services.search_service import SearchService


@staff_member_required
def document_search(request):
    """Advanced search interface for document content"""
    # ... copy implementation
    pass


@staff_member_required
def document_processing_dashboard(request):
    """Dashboard for document extraction processing status"""
    # ... copy implementation
    pass
```

**Validation:**
```bash
python manage.py shell
>>> from admin_custom.views.document_views import document_search
>>> print(document_search.__name__)
document_search
>>> exit()
```

✅ **Success Criteria:** Views import successfully

---

### Step 3.5: Export View Functions in __init__.py

**Action:** Edit `admin_custom/views/__init__.py`

```python
# admin_custom/views/__init__.py
from .analytics_views import (
    redis_analytics,
    export_redis_analytics,
    pattern_analysis,
    endpoint_deep_dive,
)

from .decision_views import (
    coverage_explorer,
    entity_search,
    daily_decision_analysis,
    decision_analysis_api,
    fetch_daily_decisions,
)

from .organization_views import (
    organization_network,
    organization_org_chart,
)

from .document_views import (
    document_search,
    document_processing_dashboard,
)

__all__ = [
    # Analytics
    'redis_analytics',
    'export_redis_analytics',
    'pattern_analysis',
    'endpoint_deep_dive',
    # Decisions
    'coverage_explorer',
    'entity_search',
    'daily_decision_analysis',
    'decision_analysis_api',
    'fetch_daily_decisions',
    # Organizations
    'organization_network',
    'organization_org_chart',
    # Documents
    'document_search',
    'document_processing_dashboard',
]
```

**Validation:**
```bash
python manage.py shell
>>> from admin_custom.views import redis_analytics, coverage_explorer
>>> print(redis_analytics.__name__, coverage_explorer.__name__)
redis_analytics coverage_explorer
>>> exit()
```

✅ **Success Criteria:** All views importable from package

---

### Step 3.6: Test New Admin Site with Views

**Action:** Visit `/api/admin-new/` and test navigation

**Validation:**
1. Visit `http://localhost:8000/api/admin-new/analytics/`
2. Visit `http://localhost:8000/api/admin-new/decisions/coverage/`
3. Visit `http://localhost:8000/api/admin-new/documents/dashboard/`

Check for:
- Views render correctly
- No 404 errors
- Templates load (they still reference old paths, we'll fix that next)

✅ **Success Criteria:** All custom views accessible and render

---

## Phase 4: Extract Helper Utilities (1 hour)

### Step 4.1: Move Helper Functions to Utils

**Action:** Create `admin_custom/utils/calendar_helpers.py`

```python
# admin_custom/utils/calendar_helpers.py
"""Helper functions for calendar-based views"""
import calendar
from datetime import date, timedelta
from core.models.import_jobs import DateCoverage


def get_month_calendar_data(month, year, entity_type, entity_id):
    """Generate calendar data for a specific month including decision counts"""
    # Copy implementation from core/admin_views.py
    pass


def get_year_summary_data(year, entity_type, entity_id):
    """Get summary data for a specific year"""
    # Copy implementation from core/admin_views.py
    pass


def get_entity_name(entity_type, entity_id):
    """Helper function to get entity name"""
    # Copy implementation from core/admin_views.py
    pass
```

**Action:** Create `admin_custom/utils/organization_helpers.py`

```python
# admin_custom/utils/organization_helpers.py
"""Helper functions for organization views"""
from core.models.organizations import Unit, SignerUnit


def build_unit_tree(unit):
    """Helper function to build hierarchical unit tree"""
    # Copy implementation from core/admin_views.py
    pass
```

**Action:** Update views to use helpers:

```python
# In admin_custom/views/decision_views.py
from admin_custom.utils.calendar_helpers import (
    get_month_calendar_data,
    get_year_summary_data,
    get_entity_name
)
```

**Validation:**
```bash
python manage.py shell
>>> from admin_custom.utils.calendar_helpers import get_month_calendar_data
>>> from admin_custom.utils.organization_helpers import build_unit_tree
>>> print(get_month_calendar_data.__name__, build_unit_tree.__name__)
get_month_calendar_data build_unit_tree
>>> exit()
```

✅ **Success Criteria:** Helper functions importable and views still work

---

## Phase 5: Move Admin Classes (1.5 hours)

### Step 5.1: Remove Duplicate DocumentExtractionAdmin

**Action:** Delete `DocumentExtractionAdmin` from `users/admin.py` (lines 18-86)

Keep only the `CustomUserAdmin` and `SubscriptionAdmin` in that file.

**Validation:**
```bash
python manage.py check

# Verify no duplicate registration errors
python manage.py shell
>>> from django.contrib import admin
>>> from core.models.document_analysis import DocumentExtraction
>>> print(len(admin.site._registry.get(DocumentExtraction, [])))
# Should print 1 or similar
>>> exit()
```

✅ **Success Criteria:** No duplicate admin class errors

---

### Step 5.2: Create Admin Class Files

**Action:** Create `admin_custom/admin_classes/api_analytics.py`

```python
# admin_custom/admin_classes/api_analytics.py
from django.contrib import admin
from api.models import APIAnalytics, DailyTraffic, EndpointStats


class APIAnalyticsAdmin(admin.ModelAdmin):
    """Admin interface for API Analytics"""
    # Copy implementation from api/admin.py
    pass


class EndpointStatsAdmin(admin.ModelAdmin):
    """Admin interface for Endpoint Statistics"""
    # Copy implementation from api/admin.py
    pass


class DailyTrafficAdmin(admin.ModelAdmin):
    """Admin interface for Daily Traffic"""
    # Copy implementation from api/admin.py
    pass
```

**Action:** Create `admin_custom/admin_classes/decisions.py`

```python
# admin_custom/admin_classes/decisions.py
from django.contrib import admin
from core.admin import DecisionAdmin  # Import the existing one
from core.models.import_jobs import ImportJob


class ImportJobAdmin(admin.ModelAdmin):
    """Admin interface for Import Jobs"""
    # Copy implementation from api/admin.py
    pass


# Re-export DecisionAdmin for convenience
__all__ = ['DecisionAdmin', 'ImportJobAdmin']
```

**Action:** Create `admin_custom/admin_classes/documents.py`

```python
# admin_custom/admin_classes/documents.py
from django.contrib import admin
from core.admin import DocumentExtractionAdmin  # Import the existing one


# Re-export for convenience
__all__ = ['DocumentExtractionAdmin']
```

**Action:** Create `admin_custom/admin_classes/users.py`

```python
# admin_custom/admin_classes/users.py
from django.contrib import admin
from users.admin import CustomUserAdmin, SubscriptionAdmin  # Import existing


# Re-export for convenience
__all__ = ['CustomUserAdmin', 'SubscriptionAdmin']
```

**Validation:**
```bash
python manage.py shell
>>> from admin_custom.admin_classes.api_analytics import APIAnalyticsAdmin
>>> from admin_custom.admin_classes.decisions import DecisionAdmin, ImportJobAdmin
>>> from admin_custom.admin_classes.documents import DocumentExtractionAdmin
>>> from admin_custom.admin_classes.users import CustomUserAdmin, SubscriptionAdmin
>>> print("All admin classes imported successfully")
>>> exit()
```

✅ **Success Criteria:** All admin classes importable

---

### Step 5.3: Create Central Admin Registration

**Action:** Create `admin_custom/admin.py`

```python
# admin_custom/admin.py
"""
Central admin registration for all models.
This is the single source of truth for the custom admin site.
"""
from admin_custom.sites import admin_site

# Import all admin classes
from admin_custom.admin_classes.api_analytics import (
    APIAnalyticsAdmin,
    EndpointStatsAdmin,
    DailyTrafficAdmin,
)
from admin_custom.admin_classes.decisions import DecisionAdmin, ImportJobAdmin
from admin_custom.admin_classes.documents import DocumentExtractionAdmin
from admin_custom.admin_classes.users import CustomUserAdmin, SubscriptionAdmin

# Import models
from api.models import APIAnalytics, DailyTraffic, EndpointStats
from core.models.decisions import Decision, Attachment
from core.models.organizations import Organization, Unit, Signer
from core.models.import_jobs import ImportJob, DateCoverage
from core.models.document_analysis import (
    DocumentExtraction,
    DocumentAnalysis,
    DocumentEmbedding,
)
from users.models import CustomUser, Subscription

# Register API Analytics models
admin_site.register(APIAnalytics, APIAnalyticsAdmin)
admin_site.register(EndpointStats, EndpointStatsAdmin)
admin_site.register(DailyTraffic, DailyTrafficAdmin)

# Register Core models
admin_site.register(Decision, DecisionAdmin)
admin_site.register(Attachment)
admin_site.register(Organization)
admin_site.register(Unit)
admin_site.register(Signer)
admin_site.register(ImportJob, ImportJobAdmin)
admin_site.register(DateCoverage)

# Register Document models
admin_site.register(DocumentExtraction, DocumentExtractionAdmin)
admin_site.register(DocumentAnalysis)
admin_site.register(DocumentEmbedding)

# Register User models
admin_site.register(CustomUser, CustomUserAdmin)
admin_site.register(Subscription, SubscriptionAdmin)
```

**Validation:**
```bash
python manage.py check

python manage.py shell
>>> from admin_custom.sites import admin_site
>>> print(f"Registered models: {len(admin_site._registry)}")
# Should show 15 models registered
>>> from core.models.decisions import Decision
>>> print(Decision in admin_site._registry)
True
>>> exit()
```

✅ **Success Criteria:** All models registered, no errors

---

## Phase 6: Move Templates (30 minutes)

### Step 6.1: Copy Templates to admin_custom

**Action:**
```bash
# Copy all admin templates to new location
cp -r backend/templates/admin/* backend/admin_custom/templates/admin_custom/

# Verify
ls backend/admin_custom/templates/admin_custom/
```

**Expected files:**
- coverage_explorer.html
- daily_decision_analysis.html
- document_processing_dashboard.html
- document_search.html
- endpoint_deep_dive.html
- organization_chart.html
- organization_network.html
- pattern_analysis.html
- redis_analytics.html
- ... (and any others)

**Validation:**
```bash
find backend/admin_custom/templates/admin_custom/ -name "*.html" | wc -l
# Should match number of templates in backend/templates/admin/
```

✅ **Success Criteria:** All templates copied

---

### Step 6.2: Update Template Paths in Views

**Action:** Update all views in `admin_custom/views/*.py` to use new template paths

Change:
```python
return render(request, "admin/redis_analytics.html", context)
```

To:
```python
return render(request, "admin_custom/redis_analytics.html", context)
```

**Files to update:**
- `admin_custom/views/analytics_views.py` (4 templates)
- `admin_custom/views/decision_views.py` (2 templates)
- `admin_custom/views/organization_views.py` (2 templates)
- `admin_custom/views/document_views.py` (2 templates)

**Validation:**
```bash
# Search for old template paths
grep -r '"admin/' admin_custom/views/
# Should return no results

# Search for new template paths
grep -r '"admin_custom/' admin_custom/views/
# Should show all template references
```

✅ **Success Criteria:** No old template paths remain in views

---

### Step 6.3: Test Template Rendering

**Action:** Visit each custom view URL under `/api/admin-new/`

**Test URLs:**
1. `/api/admin-new/analytics/`
2. `/api/admin-new/analytics/patterns/`
3. `/api/admin-new/decisions/coverage/`
4. `/api/admin-new/decisions/daily-analysis/`
5. `/api/admin-new/organizations/network/`
6. `/api/admin-new/documents/dashboard/`

**Validation:**
- All pages load without template errors
- No 500 errors
- CSS/styling looks correct

✅ **Success Criteria:** All pages render correctly

---

## Phase 7: Switch to New Admin (30 minutes)

### Step 7.1: Final Testing of New Admin

**Action:** Run comprehensive tests

```bash
# 1. Django check
python manage.py check

# 2. Run tests (if you have admin tests)
python manage.py test admin_custom

# 3. Manual testing checklist
```

**Manual Test Checklist:**
- [ ] Can log into `/api/admin-new/`
- [ ] Can view all model list pages
- [ ] Can create/edit/delete models
- [ ] All custom views work
- [ ] Navigation between sections works
- [ ] No console errors in browser

✅ **Success Criteria:** All tests pass, no errors

---

### Step 7.2: Switch URLs

**Action:** Update `diavgeia_project/urls.py` to use new admin as primary

```python
from django.contrib import admin
from django.urls import path, include
from core.views.health import health_check
from admin_custom.sites import admin_site  # Use new admin
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache

schema_view = get_schema_view(
   openapi.Info(
      title="Crati API",
      default_version='v1',
      description="API for searching and processing Greek government decisions",
      contact=openapi.Contact(email="contact@crati.app"),
   ),
   public=True,
   permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    path("api/admin/", admin_site.urls),  # NEW ADMIN IS NOW PRIMARY
    path("health/", health_check, name="health_check"),
    path("", health_check, name="root_health_check"),
    path("api/", include("api.urls")),
    path('api/docs/', csrf_exempt(never_cache(schema_view.with_ui('swagger', cache_timeout=0))), name='schema-swagger-ui'),
    path('api/redoc/', csrf_exempt(never_cache(schema_view.with_ui('redoc', cache_timeout=0))), name='schema-redoc'),
]
```

**Validation:**
```bash
python manage.py runserver

# Visit http://localhost:8000/api/admin/
# Should now show the new admin site
```

✅ **Success Criteria:** `/api/admin/` uses new admin, everything works

---

## Phase 8: Cleanup (30 minutes)

### Step 8.1: Remove Old Admin Code

**Action:** Clean up old files (after confirming new admin works!)

Files to update/remove:

1. **api/admin.py** - Remove CustomAdminSite class and registrations, keep only if you need default admin
2. **api/admin_views.py** - Can be deleted (views moved to admin_custom)
3. **core/admin_views.py** - Remove moved functions, keep only core-specific helpers if any
4. **users/admin.py** - Already cleaned up DocumentExtractionAdmin duplicate

**Action:** Create deprecation markers

```python
# api/admin.py (if keeping file)
"""
DEPRECATED: Admin configuration moved to admin_custom app.
This file kept for backwards compatibility only.
"""
import warnings
warnings.warn(
    "api.admin is deprecated. Use admin_custom.sites instead.",
    DeprecationWarning,
    stacklevel=2
)
```

**Validation:**
```bash
# Verify old imports still work (for any external dependencies)
python manage.py shell
>>> from api.admin import admin_site
# Should work but show deprecation warning
>>> from admin_custom.sites import admin_site
# Should work without warning
>>> exit()
```

✅ **Success Criteria:** Old code removed/deprecated, no broken imports

---

### Step 8.2: Update Documentation

**Action:** Create/update documentation files

1. Create `admin_custom/README.md`:

```markdown
# Admin Custom App

Centralized Django admin customizations for the Crati project.

## Structure

- `sites.py` - CustomAdminSite definition
- `admin.py` - Central model registration
- `views/` - Custom admin views organized by domain
- `admin_classes/` - ModelAdmin classes
- `utils/` - Shared helper functions
- `templates/admin_custom/` - Admin templates

## Adding New Custom Views

1. Create view in appropriate `views/*.py` file
2. Add URL to `sites.py` in `CustomAdminSite.get_urls()`
3. Create template in `templates/admin_custom/`
4. Add to app_list in `sites.py` if needed

## Running Tests

```bash
python manage.py test admin_custom
```
```

2. Update `docs/admin-architecture.md`:

```markdown
# Admin Architecture

## Overview

The Crati admin interface uses a custom Django AdminSite defined in the `admin_custom` app.

## URL Structure

- `/api/admin/` - Main admin interface
- `/api/admin/analytics/` - Analytics dashboard
- `/api/admin/decisions/` - Decision management tools
- `/api/admin/organizations/` - Organization visualization
- `/api/admin/documents/` - Document processing tools

## Key Components

- **CustomAdminSite** (`admin_custom/sites.py`) - Custom admin site with additional URLs
- **Admin Classes** (`admin_custom/admin_classes/`) - ModelAdmin configurations
- **Custom Views** (`admin_custom/views/`) - Domain-specific admin views
- **Utilities** (`admin_custom/utils/`) - Shared helper functions

## Development

See `admin_custom/README.md` for development guidelines.
```

**Validation:**
- [ ] README exists and is accurate
- [ ] Architecture doc updated
- [ ] All team members aware of new structure

✅ **Success Criteria:** Documentation complete

---

### Step 8.3: Commit Changes

**Action:** Commit the refactoring

```bash
git add admin_custom/
git add diavgeia_project/urls.py
git add docs/admin-architecture.md
git add docs/admin-refactoring-plan.md

# Commit staged deprecations
git add api/admin.py api/admin_views.py
git add core/admin_views.py
git add users/admin.py

git commit -m "refactor: Consolidate admin into admin_custom app

- Create new admin_custom app with organized structure
- Move all admin views to domain-specific modules
- Extract helper functions to utils
- Move admin classes to dedicated modules
- Update templates and URLs
- Deprecate old admin code locations
- Add comprehensive documentation

This refactoring improves maintainability by centralizing all admin
customizations in a single app with clear organization.
"
```

**Validation:**
```bash
git log -1 --stat
# Review changes

git diff main..HEAD --stat
# See overall changes from main branch
```

✅ **Success Criteria:** Changes committed with clear message

---

## Phase 9: Post-Migration Validation (30 minutes)

### Step 9.1: Run Full Test Suite

**Action:**
```bash
# Run all tests
python manage.py test

# Check for migrations
python manage.py makemigrations
# Should output: "No changes detected"

# Run system check
python manage.py check --deploy
```

**Validation:**
- [ ] All tests pass
- [ ] No pending migrations
- [ ] No deployment warnings

✅ **Success Criteria:** All validation checks pass

---

### Step 9.2: Performance Check

**Action:** Verify no performance regression

```bash
# Start server
python manage.py runserver

# In another terminal, time some requests
time curl -I http://localhost:8000/api/admin/
time curl -I http://localhost:8000/api/admin/analytics/
time curl -I http://localhost:8000/api/admin/decisions/coverage/
```

**Validation:**
- Response times similar to before refactoring
- No new N+1 query issues
- Memory usage stable

✅ **Success Criteria:** No performance degradation

---

### Step 9.3: Create Rollback Point

**Action:** Tag the commit for easy rollback

```bash
git tag -a v1.0-admin-refactor -m "Admin refactoring complete - v1.0"
git push origin refactor/consolidate-admin
git push origin v1.0-admin-refactor
```

**Validation:**
```bash
git tag -l
# Should show v1.0-admin-refactor

# Test rollback procedure (don't actually do it)
echo "To rollback: git checkout <previous-commit-hash>"
```

✅ **Success Criteria:** Rollback point created

---

## Rollback Procedure (If Needed)

If something goes wrong at any phase:

```bash
# Option 1: Revert specific commit
git revert <commit-hash>

# Option 2: Reset to before refactoring
git reset --hard <commit-before-refactoring>

# Option 3: Checkout previous branch
git checkout main

# Option 4: Emergency URL switch (no code changes needed)
# Just edit diavgeia_project/urls.py to use old_admin_site
```

---

## Appendix A: Current Admin URLs

**Document these before starting:**

```bash
# Run this to document current URLs
python manage.py show_urls | grep admin > docs/admin-urls-before.txt
```

Current structure:
- `/api/admin/` - Main admin
- `/api/admin/analytics/` - Redis analytics
- `/api/admin/analytics/export/` - Export CSV
- `/api/admin/analytics/patterns/` - Pattern analysis
- `/api/admin/analytics/endpoints/` - Endpoint deep dive
- `/api/admin/decisions/coverage/` - Coverage explorer
- `/api/admin/decisions/entity-search/` - Entity search
- `/api/admin/decisions/daily-analysis/` - Daily analysis
- `/api/admin/decisions/analysis-api/` - Analysis API
- `/api/admin/decisions/fetch-daily/` - Fetch daily
- `/api/admin/organizations/network/` - Org network
- `/api/admin/organizations/chart/` - Org chart
- `/api/admin/documents/search/` - Document search
- `/api/admin/documents/dashboard/` - Processing dashboard

---

## Appendix B: File Checklist

### New Files Created:
- [ ] `admin_custom/__init__.py`
- [ ] `admin_custom/apps.py`
- [ ] `admin_custom/sites.py`
- [ ] `admin_custom/admin.py`
- [ ] `admin_custom/views/__init__.py`
- [ ] `admin_custom/views/analytics_views.py`
- [ ] `admin_custom/views/decision_views.py`
- [ ] `admin_custom/views/organization_views.py`
- [ ] `admin_custom/views/document_views.py`
- [ ] `admin_custom/admin_classes/__init__.py`
- [ ] `admin_custom/admin_classes/api_analytics.py`
- [ ] `admin_custom/admin_classes/decisions.py`
- [ ] `admin_custom/admin_classes/documents.py`
- [ ] `admin_custom/admin_classes/users.py`
- [ ] `admin_custom/utils/__init__.py`
- [ ] `admin_custom/utils/calendar_helpers.py`
- [ ] `admin_custom/utils/organization_helpers.py`
- [ ] `admin_custom/README.md`
- [ ] `docs/admin-architecture.md`
- [ ] `docs/admin-refactoring-plan.md` (this file)

### Files Modified:
- [ ] `diavgeia_project/settings.py` (add admin_custom to INSTALLED_APPS)
- [ ] `diavgeia_project/urls.py` (switch to new admin_site)
- [ ] `api/admin.py` (deprecation notice)
- [ ] `users/admin.py` (remove duplicate DocumentExtractionAdmin)

### Files to Review for Removal:
- [ ] `api/admin_views.py` (can be deleted after migration)
- [ ] Parts of `core/admin_views.py` (remove moved code)

---

## Appendix C: Testing Checklist

### Functional Testing:
- [ ] Admin login works
- [ ] All model list pages load
- [ ] Can create new Decision
- [ ] Can edit existing Decision
- [ ] Can delete (test on safe model)
- [ ] Search functionality works
- [ ] Filters work on list pages
- [ ] Pagination works
- [ ] Redis Analytics page loads
- [ ] Pattern Analysis page loads
- [ ] Coverage Explorer works
- [ ] Entity search (AJAX) works
- [ ] Daily Decision Analysis works
- [ ] Organization Network visualizes
- [ ] Organization Chart renders
- [ ] Document Search works
- [ ] Document Processing Dashboard shows stats
- [ ] Export CSV works
- [ ] Batch actions work
- [ ] Inline editing works (if used)
- [ ] Permissions respected (non-staff can't access)

### Cross-browser Testing (if applicable):
- [ ] Chrome/Edge
- [ ] Firefox
- [ ] Safari

### Responsive Testing (if applicable):
- [ ] Desktop view
- [ ] Tablet view
- [ ] Mobile view (if admin is mobile-accessible)

---

## Success Metrics

### Objective Metrics:
- ✅ Zero downtime during migration
- ✅ All URLs functional
- ✅ No regression in test coverage
- ✅ No increase in response time (>10%)
- ✅ All models registered
- ✅ All custom views working

### Subjective Metrics:
- ✅ Easier to find admin code
- ✅ Clearer organization
- ✅ Reduced cognitive load when adding new features
- ✅ Better onboarding experience for new developers

---

## Timeline Summary

| Phase | Duration | Can Pause? |
|-------|----------|------------|
| Phase 1: Foundation | 30 min | ✅ Yes |
| Phase 2: CustomAdminSite | 45 min | ✅ Yes |
| Phase 3: Move Views | 2 hours | ✅ Yes (between files) |
| Phase 4: Extract Helpers | 1 hour | ✅ Yes |
| Phase 5: Move Admin Classes | 1.5 hours | ✅ Yes (between files) |
| Phase 6: Move Templates | 30 min | ✅ Yes |
| Phase 7: Switch Over | 30 min | ⚠️ Must complete |
| Phase 8: Cleanup | 30 min | ✅ Yes |
| Phase 9: Validation | 30 min | ⚠️ Must complete |
| **Total** | **~7.5 hours** | |

You can complete this over multiple sessions, committing after each phase!

---

## Questions or Issues?

If you encounter problems:

1. **Check the validation steps** - Did the validation pass?
2. **Review recent changes** - `git diff`
3. **Check logs** - Look for Python errors
4. **Rollback if needed** - Use procedure in Rollback section
5. **Document the issue** - Add to a "Migration Notes" section

---

## Post-Migration

After successful migration:

1. **Monitor for a week** - Watch for any issues in production
2. **Gather team feedback** - Is the new structure easier to work with?
3. **Update onboarding docs** - New developers should learn admin_custom structure
4. **Consider tests** - Add tests for custom admin views if not present
5. **Celebrate!** 🎉 - You've improved the codebase!

---

**End of Migration Plan**

Good luck! Take your time with each phase and validate thoroughly. The incremental approach means you can pause and resume safely.
