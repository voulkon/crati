"""
Stealth Mode Middleware

Enforces authentication on all API endpoints when STEALTH_MODE is enabled.
Can optionally enforce an allowlist when STEALTH_ALLOWLIST is also enabled.
"""

from django.conf import settings
from django.http import JsonResponse
from django.db import models
from rest_framework import status


class StealthModeMiddleware:
    """
    Middleware to enforce authentication in stealth mode.
    
    When STEALTH_MODE=true, all /api/* requests must be authenticated.
    When STEALTH_MODE=true AND STEALTH_ALLOWLIST=true, authenticated users
    must also be in the AllowedUser table.
    
    Returns 401 Unauthorized for unauthenticated requests.
    Returns 403 Forbidden for authenticated but not allowed requests.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.stealth_mode = getattr(settings, 'STEALTH_MODE', False)
        self.stealth_allowlist = getattr(settings, 'STEALTH_ALLOWLIST', False)
        
    def __call__(self, request):
        # Only enforce in stealth mode and for API endpoints
        if self.stealth_mode and request.path.startswith('/api/'):
            # Exempt health check and similar endpoints if needed
            exempt_paths = [
                '/api/health/',
                '/api/v1/health/',
            ]
            
            if request.path not in exempt_paths:
                # Check if user is authenticated
                if not request.user or not request.user.is_authenticated:
                    return JsonResponse(
                        {
                            'error': 'Authentication required',
                            'detail': 'This API is in stealth mode. Please authenticate to access.',
                            'stealth_mode': True
                        },
                        status=status.HTTP_401_UNAUTHORIZED
                    )
                
                # If allowlist is enabled, check if user is allowed
                if self.stealth_allowlist:
                    is_allowed = self._check_user_allowed(request.user)
                    if not is_allowed:
                        return JsonResponse(
                            {
                                'error': 'Access forbidden',
                                'detail': 'Your account is not authorized to access this application.',
                                'stealth_mode': True,
                                'allowlist_enabled': True
                            },
                            status=status.HTTP_403_FORBIDDEN
                        )
        
        response = self.get_response(request)
        return response
    
    def _check_user_allowed(self, user):
        """
        Check if user is in the allowlist.
        Checks by clerk_id (if available) or email.
        """
        from users.models import AllowedUser
        
        # Get user's email and clerk_id
        email = getattr(user, 'email', None)
        clerk_id = getattr(user, 'clerk_id', None)
        
        if not email and not clerk_id:
            return False
        
        # Check if user exists in allowlist and is active
        try:
            allowed_user = AllowedUser.objects.filter(is_active=True).filter(
                models.Q(email=email) | models.Q(clerk_user_id=clerk_id)
            ).first()
            
            # If found by email but clerk_user_id is not set, update it
            if allowed_user and clerk_id and not allowed_user.clerk_user_id:
                allowed_user.clerk_user_id = clerk_id
                allowed_user.save(update_fields=['clerk_user_id', 'updated_at'])
            
            return allowed_user is not None
        except Exception:
            # If there's any error (e.g., table doesn't exist yet), deny access
            return False

