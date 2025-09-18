from rest_framework import authentication
from rest_framework import exceptions
from django.conf import settings
import jwt
from users.models import CustomUser
from diavgeia_project.security_tracing import security_tracer, get_client_ip

class ClerkAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None  # No token provided, let other auth methods try

        token = auth_header.split(" ")[1]

        try:
            # Verify JWT token with Clerk's public key
            payload = jwt.decode(
                token,
                settings.CLERK_JWT_PUBLIC_KEY,
                algorithms=["RS256"],
                audience=settings.CLERK_JWT_AUDIENCE,
                options={"verify_exp": True},
            )

            clerk_id = payload.get("sub")
            if not clerk_id:
                security_tracer.log_security_event(
                    "authentication.clerk.invalid",
                    {"reason": "missing_sub_claim"},
                    ip=get_client_ip(request),
                    severity="WARNING"
                )
                raise exceptions.AuthenticationFailed("Invalid token")

            # Get or create user based on Clerk ID
            try:
                user = CustomUser.objects.get(clerk_id=clerk_id)
                # Log successful authentication
                security_tracer.log_security_event(
                    "authentication.clerk.success",
                    {"email": payload.get("email", "")},
                    user=user,
                    ip=get_client_ip(request)
                )
            except CustomUser.DoesNotExist:
                # Auto-provision user from Clerk data
                email = payload.get("email", "")
                username = email or f"user_{clerk_id}"
                
                user = CustomUser.objects.create(
                    username=username,
                    email=email,
                    clerk_id=clerk_id,
                )
                
                # Log user provisioning
                security_tracer.log_security_event(
                    "user.provisioned",
                    {"email": email, "source": "clerk"},
                    user=user,
                    ip=get_client_ip(request)
                )

            return (user, token)

        except jwt.ExpiredSignatureError:
            security_tracer.log_security_event(
                "authentication.clerk.expired",
                {"token_preview": token[:10] + "..."},
                clerk_id=payload.get("sub") if 'payload' in locals() else None,
                ip=get_client_ip(request),
                severity="WARNING"
            )
            raise exceptions.AuthenticationFailed("Token expired")
        except jwt.InvalidTokenError:
            security_tracer.log_security_event(
                "authentication.clerk.invalid",
                {"token_preview": token[:10] + "..."},
                ip=get_client_ip(request),
                severity="WARNING"
            )
            raise exceptions.AuthenticationFailed("Invalid token")
        except Exception as e:
            security_tracer.log_security_event(
                "authentication.clerk.error",
                {"error": str(e)},
                ip=get_client_ip(request),
                severity="ERROR"
            )
            raise exceptions.AuthenticationFailed(f"Authentication failed: {str(e)}")

class ApiKeyAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        api_key = request.META.get('HTTP_X_API_KEY') or request.query_params.get('api_key')
        if not api_key:
            return None
            
        try:
            user = CustomUser.objects.get(api_key=api_key)
            
            # Check if subscription is still valid
            if not user.has_active_subscription:
                security_tracer.log_security_event(
                    "authentication.api_key.expired_subscription",
                    {"api_key_preview": api_key[:5] + "..."},
                    user=user,
                    ip=get_client_ip(request),
                    severity="WARNING"
                )
                raise exceptions.AuthenticationFailed("Subscription expired")
            
            # Log successful API key authentication
            security_tracer.log_security_event(
                "authentication.api_key.success",
                {},
                user=user,
                ip=get_client_ip(request)
            )
            
            return (user, api_key)
        except CustomUser.DoesNotExist:
            security_tracer.log_security_event(
                "authentication.api_key.invalid",
                {"api_key_preview": api_key[:5] + "..."},
                ip=get_client_ip(request),
                severity="WARNING"
            )
            return None
