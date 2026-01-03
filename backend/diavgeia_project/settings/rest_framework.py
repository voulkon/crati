"""
REST Framework settings.

Contains REST_FRAMEWORK configuration including authentication and permission classes.
"""

import os

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.BasicAuthentication",  # Add this for development
        "rest_framework.authentication.TokenAuthentication",
        # Add Clerk authentication class (we'll create this)
        "api.authentication.ClerkAuthentication",
        "api.authentication.ApiKeyAuthentication"
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        # In stealth mode, require authentication for ALL endpoints
        # Otherwise use IsAuthenticated (individual views can override)
        "rest_framework.permissions.IsAuthenticated" if os.getenv("STEALTH_MODE", "False").lower() in ("true", "1", "t")
        else "rest_framework.permissions.IsAuthenticated",
    ],
    'DEFAULT_PARSER_CLASSES': [
        'api.parsers.SanitizedJSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
}
