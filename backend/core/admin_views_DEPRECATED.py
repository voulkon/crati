# DEPRECATED: This file has been refactored and moved to admin_custom/views/
#
# Migration Guide:
# 
# Decision-related views have been moved to: admin_custom/views/decisions/
#   - coverage_explorer() → decisions/decisions_coverage.py
#   - entity_search() → decisions/decisions_coverage.py  
#   - daily_decision_analysis() → decisions/decisions_analysis.py
#   - decision_analysis_api() → decisions/decisions_analysis.py
#   - fetch_daily_decisions() → decisions/decisions_fetching.py
#   - Helper functions → decisions/decisions_utils.py
#
# Organization-related views should move to: admin_custom/views/organization/
#   - organization_network() → TODO
#   - organization_org_chart() → TODO
#   - build_unit_tree() → TODO
#
# Document-related views should move to: admin_custom/views/documents/
#   - document_processing_dashboard() → TODO
#   - document_search() → TODO
#
# This file will be deleted once all views are migrated.

import warnings

# Re-export the moved functions with deprecation warnings
def _deprecated_import(new_location, func_name):
    """Factory for creating deprecated import wrappers"""
    def wrapper(*args, **kwargs):
        warnings.warn(
            f"{func_name} has been moved to {new_location}. "
            f"Please update your imports.",
            DeprecationWarning,
            stacklevel=2
        )
        # Dynamic import of new location
        module_path, func = new_location.rsplit('.', 1)
        from importlib import import_module
        module = import_module(module_path)
        new_func = getattr(module, func)
        return new_func(*args, **kwargs)
    return wrapper

# Decision views
coverage_explorer = _deprecated_import('admin_custom.views.decisions.coverage_explorer', 'coverage_explorer')
entity_search = _deprecated_import('admin_custom.views.decisions.entity_search', 'entity_search')
daily_decision_analysis = _deprecated_import('admin_custom.views.decisions.daily_decision_analysis', 'daily_decision_analysis')
decision_analysis_api = _deprecated_import('admin_custom.views.decisions.decision_analysis_api', 'decision_analysis_api')
fetch_daily_decisions = _deprecated_import('admin_custom.views.decisions.fetch_daily_decisions', 'fetch_daily_decisions')
