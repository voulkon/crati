"""
Notifications-related URL patterns.
"""

from django.urls import path, include

# URL prefix for this module
PREFIX = 'notifications/'
from rest_framework.routers import DefaultRouter
from notifications.views import NotificationSubscriptionViewSet, NotificationBatchViewSet
from notifications.views_metadata import (
    subscription_metadata,
    decision_types_list,
    popular_decision_types
)

# Create router for notification viewsets
router = DefaultRouter()
router.register('subscriptions', NotificationSubscriptionViewSet, basename='notification-subscription')
router.register('batches', NotificationBatchViewSet, basename='notification-batch')

urlpatterns = [
    # Include router URLs (creates /notifications/subscriptions/ and /notifications/batches/)
    path('', include(router.urls)),
    
    # Metadata endpoints
    path('meta/metadata/', subscription_metadata, name='subscription_metadata'),
    path('meta/metadata/decision-types/', decision_types_list, name='decision_types_list'),
    path('meta/metadata/popular-decision-types/', popular_decision_types, name='popular_decision_types'),
]
