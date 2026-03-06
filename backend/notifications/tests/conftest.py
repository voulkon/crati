"""
Notification-specific test fixtures and utilities.

This conftest.py is specific to the notifications app and provides
fixtures that build on top of the shared backend-level factories.
"""
import pytest
from datetime import timedelta
from django.utils import timezone


@pytest.fixture
def subscription_with_keywords(user, organization):
    """Create a subscription with keyword filters"""
    from conftest import NotificationSubscriptionFactory
    return NotificationSubscriptionFactory(
        user=user,
        organization=organization,
        keywords=['contract', 'tender', 'διαγωνισμός']
    )


@pytest.fixture
def subscription_with_amount_filter(user, organization):
    """Create a subscription with amount filters"""
    from conftest import NotificationSubscriptionFactory
    from decimal import Decimal
    return NotificationSubscriptionFactory(
        user=user,
        organization=organization,
        amount_min=Decimal('10000.00'),
        amount_max=Decimal('100000.00')
    )


@pytest.fixture
def entity_subscription(user, afm_entity):
    """Create an entity-based subscription"""
    from conftest import EntitySubscriptionFactory
    return EntitySubscriptionFactory(
        user=user,
        entity=afm_entity
    )


@pytest.fixture
def relationship_subscription(user, organization, afm_entity):
    """Create a relationship-based subscription"""
    from conftest import RelationshipSubscriptionFactory
    return RelationshipSubscriptionFactory(
        user=user,
        relationship_org=organization,
        relationship_entity=afm_entity
    )


@pytest.fixture
def old_subscription(user, organization):
    """Create a subscription that hasn't been checked in a while"""
    from conftest import NotificationSubscriptionFactory
    sub = NotificationSubscriptionFactory(
        user=user,
        organization=organization
    )
    sub.last_checked = timezone.now() - timedelta(days=10)
    sub.save()
    return sub


@pytest.fixture
def multiple_subscriptions(user):
    """Create multiple subscriptions for a user"""
    from conftest import (
        NotificationSubscriptionFactory,
        OrganizationFactory,
        AFMEntityFactory
    )
    
    org1 = OrganizationFactory()
    org2 = OrganizationFactory()
    entity = AFMEntityFactory()
    
    return {
        'org_sub_1': NotificationSubscriptionFactory(user=user, organization=org1),
        'org_sub_2': NotificationSubscriptionFactory(user=user, organization=org2),
        'entity_sub': NotificationSubscriptionFactory(user=user, organization=None, entity=entity),
    }


@pytest.fixture
def decision_matching_subscription(notification_subscription):
    """Create a decision that matches a subscription"""
    from conftest import DecisionFactory
    return DecisionFactory(
        organization=notification_subscription.organization,
        subject=f"Test decision for {notification_subscription.organization.label}"
    )


@pytest.fixture
def recent_decisions(organization, decision_type):
    """Create several recent decisions for testing"""
    from conftest import DecisionFactory
    
    decisions = []
    for i in range(5):
        decisions.append(
            DecisionFactory(
                organization=organization,
                decision_type=decision_type,
                publish_timestamp=timezone.now() - timedelta(hours=i)
            )
        )
    return decisions


@pytest.fixture
def notification_with_read_status(user, notification_subscription, decision):
    """Create a notification that's already been read"""
    from conftest import NotificationFactory
    notif = NotificationFactory(
        user=user,
        subscription=notification_subscription,
        decision=decision,
        is_read=True
    )
    notif.read_at = timezone.now() - timedelta(hours=2)
    notif.save()
    return notif


@pytest.fixture
def unread_notifications(user, notification_subscription):
    """Create multiple unread notifications"""
    from conftest import NotificationFactory, DecisionFactory
    
    notifications = []
    for i in range(3):
        decision = DecisionFactory(
            organization=notification_subscription.organization
        )
        notifications.append(
            NotificationFactory(
                user=user,
                subscription=notification_subscription,
                decision=decision,
                is_read=False
            )
        )
    return notifications
