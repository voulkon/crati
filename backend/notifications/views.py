from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q

from notifications.models import NotificationSubscription
from notifications.serializers import (
    NotificationSubscriptionSerializer,
    NotificationSubscriptionCreateSerializer,
    NotificationSubscriptionListSerializer,
)
from core.models.organizations import Organization
from core.models.entities import AFMEntity


class NotificationSubscriptionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing notification subscriptions.
    
    Users can only see and manage their own subscriptions.
    
    Provides standard CRUD operations:
    - list: GET /api/notifications/subscriptions/
    - create: POST /api/notifications/subscriptions/
    - retrieve: GET /api/notifications/subscriptions/{id}/
    - update: PUT /api/notifications/subscriptions/{id}/
    - partial_update: PATCH /api/notifications/subscriptions/{id}/
    - destroy: DELETE /api/notifications/subscriptions/{id}/
    
    Custom actions:
    - check_organization_subscription: Check if user is subscribed to an organization
    - check_entity_subscription: Check if user is subscribed to an entity
    - check_relationship_subscription: Check if user is subscribed to a relationship
    """
    
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Filter queryset to only show current user's subscriptions.
        Optimize with select_related for nested relationships.
        """
        return NotificationSubscription.objects.filter(
            user=self.request.user
        ).select_related(
            'organization',
            'entity',
            'relationship_org',
            'relationship_entity'
        ).order_by('-created_at')
    
    def get_serializer_class(self):
        """
        Use different serializers for different actions.
        """
        if self.action == 'list':
            return NotificationSubscriptionListSerializer
        elif self.action == 'create':
            return NotificationSubscriptionCreateSerializer
        else:
            return NotificationSubscriptionSerializer
    
    def create(self, request, *args, **kwargs):
        """
        Create a new subscription for the current user.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription = serializer.save()
        
        # Return full details using the detail serializer
        output_serializer = NotificationSubscriptionSerializer(subscription)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """
        Update an existing subscription.
        Note: Users cannot change the subscription type (organization/entity/relationship).
        They should delete and create a new subscription instead.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = NotificationSubscriptionSerializer(
            instance, 
            data=request.data, 
            partial=partial
        )
        serializer.is_valid(raise_exception=True)
        subscription = serializer.save()
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='check-organization/(?P<org_uid>[^/.]+)')
    def check_organization_subscription(self, request, org_uid=None):
        """
        Check if the current user is subscribed to a specific organization.
        
        Returns:
            {
                "subscribed": true/false,
                "subscription": {...} or null
            }
        """
        try:
            subscription = NotificationSubscription.objects.get(
                user=request.user,
                organization__uid=org_uid,
                is_active=True
            )
            serializer = NotificationSubscriptionSerializer(subscription)
            return Response({
                "subscribed": True,
                "subscription": serializer.data
            })
        except NotificationSubscription.DoesNotExist:
            return Response({
                "subscribed": False,
                "subscription": None
            })
    
    @action(detail=False, methods=['get'], url_path='check-entity/(?P<afm>[^/.]+)')
    def check_entity_subscription(self, request, afm=None):
        """
        Check if the current user is subscribed to a specific entity.
        
        Returns:
            {
                "subscribed": true/false,
                "subscription": {...} or null
            }
        """
        try:
            subscription = NotificationSubscription.objects.get(
                user=request.user,
                entity__afm=afm,
                is_active=True
            )
            serializer = NotificationSubscriptionSerializer(subscription)
            return Response({
                "subscribed": True,
                "subscription": serializer.data
            })
        except NotificationSubscription.DoesNotExist:
            return Response({
                "subscribed": False,
                "subscription": None
            })
    
    @action(detail=False, methods=['get'], url_path='check-relationship')
    def check_relationship_subscription(self, request):
        """
        Check if the current user is subscribed to a specific org-entity relationship.
        
        Query params:
            - org_uid: Organization UID
            - entity_afm: Entity AFM
        
        Returns:
            {
                "subscribed": true/false,
                "subscription": {...} or null
            }
        """
        org_uid = request.query_params.get('org_uid')
        entity_afm = request.query_params.get('entity_afm')
        
        if not org_uid or not entity_afm:
            return Response(
                {"error": "Both org_uid and entity_afm query parameters are required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            subscription = NotificationSubscription.objects.get(
                user=request.user,
                relationship_org__uid=org_uid,
                relationship_entity__afm=entity_afm,
                is_active=True
            )
            serializer = NotificationSubscriptionSerializer(subscription)
            return Response({
                "subscribed": True,
                "subscription": serializer.data
            })
        except NotificationSubscription.DoesNotExist:
            return Response({
                "subscribed": False,
                "subscription": None
            })
    
    @action(detail=False, methods=['get'], url_path='check-person/(?P<person_name>[^/.]+)')
    def check_person_subscription(self, request, person_name=None):
        """
        Check if the current user is subscribed to a specific person.
        
        Returns:
            {
                "subscribed": true/false,
                "subscription": {...} or null
            }
        """
        try:
            subscription = NotificationSubscription.objects.get(
                user=request.user,
                person_name=person_name,
                is_active=True
            )
            serializer = NotificationSubscriptionSerializer(subscription)
            return Response({
                "subscribed": True,
                "subscription": serializer.data
            })
        except NotificationSubscription.DoesNotExist:
            return Response({
                "subscribed": False,
                "subscription": None
            })
    
    @action(detail=False, methods=['get'], url_path='check-signer/(?P<signer_name>[^/.]+)')
    def check_signer_subscription(self, request, signer_name=None):
        """
        Check if the current user is subscribed to a specific signer.
        
        Returns:
            {
                "subscribed": true/false,
                "subscription": {...} or null
            }
        """
        try:
            subscription = NotificationSubscription.objects.get(
                user=request.user,
                signer_name=signer_name,
                is_active=True
            )
            serializer = NotificationSubscriptionSerializer(subscription)
            return Response({
                "subscribed": True,
                "subscription": serializer.data
            })
        except NotificationSubscription.DoesNotExist:
            return Response({
                "subscribed": False,
                "subscription": None
            })
