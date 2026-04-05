"""
Django native authentication endpoints.

Provides traditional email/password registration and login alongside Clerk.
Useful for:
- Development and testing
- Admin/internal users
- Fallback authentication
- Testing without Clerk credentials

These endpoints coexist with Clerk - users can authenticate via either method.
"""
import uuid
from datetime import timedelta
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, get_user_model
from django.conf import settings
from django.utils import timezone
from loguru import logger

User = get_user_model()


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    Register a new user with email and password.
    
    Request:
    {
        "email": "user@example.com",
        "password": "secure_password",
        "username": "optional_username"  // Optional, defaults to email
    }
    
    Response:
    {
        "user": {
            "id": 1,
            "email": "user@example.com",
            "username": "user@example.com"
        },
        "token": "drf_token_here"
    }
    """
    email = request.data.get('email')
    password = request.data.get('password')
    username = request.data.get('username', email)  # Default username to email
    
    # Validate
    if not email or not password:
        return Response(
            {'error': 'Email and password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if user exists
    if User.objects.filter(email=email).exists():
        return Response(
            {'error': 'User with this email already exists'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Create user - inactive until email is verified
        user = User.objects.create_user(
            email=email,
            username=username,
            password=password,
            is_active=False  # User cannot login until email is verified
        )
        
        # Generate verification token
        verification_token = uuid.uuid4()
        user.email_verification_token = verification_token
        user.email_verification_token_expires = timezone.now() + timedelta(hours=24)
        user.save()
        
        # Send verification email
        email_sent = False
        if getattr(settings, 'DEFAULT_FROM_EMAIL', None) and settings.DEFAULT_FROM_EMAIL != 'YOUR-ACCESS-KEY-ID':
            try:
                from core.email_service import RegistrationEmailService
                email_sent = RegistrationEmailService.send_verification_email(
                    user_email=user.email,
                    username=user.username,
                    verification_token=str(verification_token)
                )
                if email_sent:
                    logger.info(f"Verification email sent to: {user.email}")
                else:
                    logger.warning(f"Failed to send verification email to: {user.email}")
            except Exception as e:
                logger.error(f"Error sending verification email: {e}", exc_info=True)
        else:
            logger.warning("Email not configured - user created but no verification email sent")
        
        logger.info(f"Created Django user (pending verification): {user.email}")
        
        return Response({
            'message': 'Registration successful! Please check your email to verify your account.',
            'email': user.email,
            'verification_required': True,
            'email_sent': email_sent
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Error creating user: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to create user'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """
    Login with email and password.
    
    Request:
    {
        "email": "user@example.com",
        "password": "password"
    }
    
    Response:
    {
        "user": {
            "id": 1,
            "email": "user@example.com",
            "username": "user@example.com"
        },
        "token": "drf_token_here"
    }
    """
    email = request.data.get('email')
    password = request.data.get('password')
    
    if not email or not password:
        return Response(
            {'error': 'Email and password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Authenticate using Django's auth backends
    user = authenticate(request, username=email, password=password)
    
    if user is None:
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Check if user is active (for Django-registered users, this means email is verified)
    if not user.is_active:
        # Check if it's specifically because email is not verified
        if not user.email_verified and user.email_verification_token:
            return Response(
                {
                    'error': 'Email not verified. Please check your email for the verification link.',
                    'verification_required': True
                },
                status=status.HTTP_403_FORBIDDEN
            )
        return Response(
            {'error': 'User account is disabled'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get or create DRF token
    token, _ = Token.objects.get_or_create(user=user)
    
    logger.info(f"Django login: {user.email}")
    
    return Response({
        'user': {
            'id': user.id,
            'email': user.email,
            'username': user.username,
        },
        'token': token.key
    })


@api_view(['POST'])
def logout(request):
    """
    Logout - delete the user's auth token.
    
    Requires authentication.
    """
    if not request.user or not request.user.is_authenticated:
        return Response(
            {'error': 'Not authenticated'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Delete the user's token (if using token auth)
    try:
        Token.objects.filter(user=request.user).delete()
        logger.info(f"Logged out user: {request.user.email}")
    except Exception:
        pass  # No token to delete
    
    return Response({'message': 'Logged out successfully'})


@api_view(['POST', 'GET'])
@permission_classes([AllowAny])
def verify_email(request):
    """
    Verify user's email address using the token sent via email.
    
    Supports both GET (from email link) and POST (from frontend form).
    
    GET: /auth/verify-email/?token=uuid-token-from-email
    POST: {"token": "uuid-token-from-email"}
    
    Response:
    {
        "message": "Email verified successfully",
        "user": {...},
        "token": "drf_token_here"
    }
    """
    # Support both GET and POST
    if request.method == 'GET':
        verification_token = request.query_params.get('token')
    else:
        verification_token = request.data.get('token')
    
    if not verification_token:
        return Response(
            {'error': 'Verification token is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Find user with this verification token
        user = User.objects.get(email_verification_token=verification_token)
        
        # Check if token has expired
        if user.email_verification_token_expires and user.email_verification_token_expires < timezone.now():
            return Response(
                {'error': 'Verification token has expired. Please request a new one.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if already verified
        if user.email_verified and user.is_active:
            return Response(
                {'message': 'Email already verified. You can log in now.'},
                status=status.HTTP_200_OK
            )
        
        # Verify the user
        user.email_verified = True
        user.is_active = True  # Allow login
        user.email_verification_token = None  # Clear the token
        user.email_verification_token_expires = None
        user.save()
        
        # Create DRF token for automatic login
        token, _ = Token.objects.get_or_create(user=user)
        
        # Optionally send welcome email
        if getattr(settings, 'DEFAULT_FROM_EMAIL', None) and settings.DEFAULT_FROM_EMAIL != 'YOUR-ACCESS-KEY-ID':
            try:
                from core.email_service import RegistrationEmailService
                RegistrationEmailService.send_welcome_email(
                    user_email=user.email,
                    username=user.username
                )
            except Exception as e:
                logger.warning(f"Failed to send welcome email: {e}")
        
        logger.info(f"Email verified for user: {user.email}")
        
        return Response({
            'message': 'Email verified successfully! You are now logged in.',
            'user': {
                'id': user.id,
                'email': user.email,
                'username': user.username,
            },
            'token': token.key
        }, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response(
            {'error': 'Invalid verification token'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Error verifying email: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to verify email'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def me(request):
    """
    Get current authenticated user info.
    
    Works for both Django-authenticated and Clerk-authenticated users.
    """
    if not request.user or not request.user.is_authenticated:
        return Response(
            {'error': 'Not authenticated'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    return Response({
        'user': {
            'id': request.user.id,
            'email': request.user.email,
            'username': request.user.username,
            'auth_method': 'clerk' if hasattr(request.user, 'clerk_id') else 'django',
        }
    })
