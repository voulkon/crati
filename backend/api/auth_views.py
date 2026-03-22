"""
Django authentication views for when Clerk is not configured.
Provides username/password login and token-based authentication.
"""
from django.contrib.auth import authenticate, login, logout
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from loguru import logger


@swagger_auto_schema(
    method='post',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['email', 'password'],
        properties={
            'email': openapi.Schema(type=openapi.TYPE_STRING, description='User email address'),
            'password': openapi.Schema(type=openapi.TYPE_STRING, description='User password'),
        },
    ),
    responses={
        200: openapi.Response(
            description='Login successful',
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'user': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'username': openapi.Schema(type=openapi.TYPE_STRING),
                            'email': openapi.Schema(type=openapi.TYPE_STRING),
                            'first_name': openapi.Schema(type=openapi.TYPE_STRING),
                            'last_name': openapi.Schema(type=openapi.TYPE_STRING),
                        }
                    ),
                    'token': openapi.Schema(type=openapi.TYPE_STRING, description='Authentication token'),
                }
            )
        ),
        400: 'Bad Request - Missing email or password',
        401: 'Unauthorized - Invalid credentials',
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def django_login(request):
    """
    Login with Django email/password.
    Creates a session and returns user info + auth token.
    """
    email = request.data.get('email')
    password = request.data.get('password')
    
    if not email or not password:
        return Response(
            {'error': 'Email and password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    user = authenticate(request, username=email, password=password)
    
    if user is not None:
        login(request, user)
        
        # Get or create auth token
        token, created = Token.objects.get_or_create(user=user)
        
        logger.info(f"User {email} logged in successfully")
        
        return Response({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'token': token.key,
        })
    else:
        logger.warning(f"Failed login attempt for email: {email}")
        return Response(
            {'error': 'Invalid email or password'},
            status=status.HTTP_401_UNAUTHORIZED
        )


@swagger_auto_schema(
    method='post',
    responses={
        200: openapi.Response(
            description='Logout successful',
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'message': openapi.Schema(type=openapi.TYPE_STRING),
                }
            )
        ),
        400: 'Bad Request - Not authenticated',
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def django_logout(request):
    """
    Logout current user.
    """
    if request.user.is_authenticated:
        # Delete auth token if it exists
        try:
            request.user.auth_token.delete()
        except:
            pass
        
        logout(request)
        return Response({'success': True, 'message': 'Logged out successfully'})
    else:
        return Response(
            {'error': 'Not authenticated'},
            status=status.HTTP_400_BAD_REQUEST
        )


@swagger_auto_schema(
    method='get',
    responses={
        200: openapi.Response(
            description='Current user info',
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'authenticated': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'user': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'username': openapi.Schema(type=openapi.TYPE_STRING),
                            'email': openapi.Schema(type=openapi.TYPE_STRING),
                            'first_name': openapi.Schema(type=openapi.TYPE_STRING),
                            'last_name': openapi.Schema(type=openapi.TYPE_STRING),
                        }
                    ),
                }
            )
        ),
        401: 'Not authenticated',
    }
)
@api_view(['GET'])
def current_user(request):
    """
    Get current authenticated user info.
    Requires authentication via Session, Token, or Basic Auth.
    """
    if request.user.is_authenticated:
        return Response({
            'authenticated': True,
            'user': {
                'id': request.user.id,
                'username': request.user.username,
                'email': request.user.email,
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
            }
        })
    else:
        return Response(
            {'authenticated': False},
            status=status.HTTP_401_UNAUTHORIZED
        )
