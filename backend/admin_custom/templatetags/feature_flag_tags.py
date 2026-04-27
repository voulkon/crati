"""Template tags for feature flag display."""

from django import template
from core.services.feature_flag_service import feature_flags

register = template.Library()


@register.simple_tag
def get_flag_source(flag_key):
    """Get the source information for a feature flag."""
    return feature_flags.get_flag_info(flag_key)
