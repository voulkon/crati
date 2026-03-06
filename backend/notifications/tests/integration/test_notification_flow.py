"""
Integration tests for the complete notification flow.

These tests verify end-to-end functionality:
- User creates subscriptions via API
- Background tasks check subscriptions
- Notifications are created
- User retrieves and manages notifications
"""
import pytest
from django.utils import timezone
from datetime import timedelta
from rest_framework import status


pytestmark = [
    pytest.mark.django_db,
    pytest.mark.integration
]


class TestCompleteNotificationFlow:
    """
    Test the complete user journey from subscription to notification.
    """
    
    def test_user_subscribes_and_receives_notification(
        self, authenticated_client, user, organization, decision_type, celery_eager_mode
    ):
        """
        Complete flow:
        1. User subscribes to an organization
        2. New decision is created for that organization
        3. Task runs and creates notification
        4. User sees unread notification
        5. User marks notification as read
        """
        # Step 1: User creates subscription via API
        response = authenticated_client.post(
            '/api/notifications/subscriptions/',
            {
                'organization_uid': organization.uid,
                'keywords': ['test', 'contract']
            },
            format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED
        subscription_id = response.data['id']
        
        # Verify subscription was created
        from notifications.models import NotificationSubscription
        subscription = NotificationSubscription.objects.get(id=subscription_id)
        assert subscription.user == user
        assert subscription.organization == organization
        assert subscription.keywords == ['test', 'contract']
        
        # Step 2: Simulate a new decision being published
        from conftest import DecisionFactory
        decision = DecisionFactory(
            organization=organization,
            subject="Test contract decision",
            publish_timestamp=timezone.now()
        )
        
        # Set last_checked to ensure the decision is "new"
        subscription.last_checked = timezone.now() - timedelta(days=1)
        subscription.save()
        
        # Step 3: Run the check task
        from notifications.tasks import check_subscriptions_for_new_decisions
        result = check_subscriptions_for_new_decisions()
        
        assert result['notifications_created'] >= 1
        
        # Step 4: User checks unread count
        response = authenticated_client.get('/api/notifications/unread-count/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['unread_count'] >= 1
        
        # Step 5: User gets notification list
        response = authenticated_client.get('/api/notifications/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
        
        notification_id = response.data[0]['id']
        assert response.data[0]['is_read'] is False
        
        # Step 6: User marks notification as read
        response = authenticated_client.post(
            f'/api/notifications/{notification_id}/mark-read/'
        )
        assert response.status_code == status.HTTP_200_OK
        
        # Verify it's marked read
        response = authenticated_client.get('/api/notifications/unread-count/')
        assert response.data['unread_count'] == 0
    
    def test_user_cannot_see_other_users_notifications(
        self, authenticated_client, user, api_client
    ):
        """
        Verify that users can only see their own notifications.
        """
        from conftest import UserFactory, NotificationFactory
        
        # Create another user with a notification
        other_user = UserFactory()
        other_notification = NotificationFactory(user=other_user)
        
        # Create notification for authenticated user
        my_notification = NotificationFactory(user=user)
        
        # Authenticated user should only see their notification
        response = authenticated_client.get('/api/notifications/')
        assert response.status_code == status.HTTP_200_OK
        
        notification_ids = [n['id'] for n in response.data]
        assert my_notification.id in notification_ids
        assert other_notification.id not in notification_ids
    
    def test_subscription_check_frequency_respected(
        self, user, organization, celery_eager_mode
    ):
        """
        Test that check_frequency='manual' subscriptions are not checked automatically.
        """
        from conftest import NotificationSubscriptionFactory, DecisionFactory
        from notifications.tasks import check_subscriptions_for_new_decisions
        
        # Create subscription with manual check frequency
        manual_sub = NotificationSubscriptionFactory(
            user=user,
            organization=organization,
            check_frequency='manual',
            is_active=True
        )
        manual_sub.last_checked = timezone.now() - timedelta(days=10)
        manual_sub.save()
        
        # Create a matching decision
        DecisionFactory(
            organization=organization,
            publish_timestamp=timezone.now()
        )
        
        # Run scheduled task (should skip manual subscriptions)
        result = check_subscriptions_for_new_decisions()
        
        # No notifications should be created for manual subscription
        from notifications.models import Notification
        notifications = Notification.objects.filter(subscription=manual_sub)
        assert notifications.count() == 0


class TestMultipleSubscriptionTypes:
    """
    Test different subscription types work correctly.
    """
    
    def test_organization_subscription(
        self, authenticated_client, user, organization, celery_eager_mode
    ):
        """Test organization-based subscription creates notifications"""
        from conftest import NotificationSubscriptionFactory, DecisionFactory
        from notifications.tasks import check_single_subscription
        
        # Create subscription
        sub = NotificationSubscriptionFactory(
            user=user,
            organization=organization,
            check_frequency='daily'
        )
        sub.last_checked = timezone.now() - timedelta(days=1)
        sub.save()
        
        # Create matching decision
        DecisionFactory(organization=organization)
        
        # Check subscription
        result = check_single_subscription(sub.id)
        assert result['notifications_created'] >= 1
    
    def test_entity_subscription(
        self, authenticated_client, user, afm_entity, celery_eager_mode
    ):
        """Test entity-based subscription creates notifications"""
        from conftest import EntitySubscriptionFactory, DecisionFactory
        from notifications.tasks import check_single_subscription
        from notifications.models import Notification
        
        # Create entity subscription
        sub = EntitySubscriptionFactory(
            user=user,
            entity=afm_entity
        )
        sub.last_checked = timezone.now() - timedelta(days=1)
        sub.save()
        
        # Create decision with entity relationship
        from core.models.entities import DecisionEntityRelationship, EntityRole
        decision = DecisionFactory()
        DecisionEntityRelationship.objects.create(
            decision=decision,
            entity=afm_entity,
            role=EntityRole.SPONSOR,
            parent_key_path='sponsor[0].sponsorAFMName'
        )
        
        # Check subscription
        result = check_single_subscription(sub.id)
        
        # Should create notification
        notifications = Notification.objects.filter(subscription=sub)
        assert notifications.count() >= 1
    
    def test_keyword_filter(
        self, authenticated_client, user, organization, celery_eager_mode
    ):
        """Test keyword filtering works correctly"""
        from conftest import NotificationSubscriptionFactory, DecisionFactory
        from notifications.tasks import check_single_subscription
        from notifications.models import Notification
        
        # Create subscription with keyword filter
        sub = NotificationSubscriptionFactory(
            user=user,
            organization=organization,
            keywords=['urgent', 'contract']
        )
        sub.last_checked = timezone.now() - timedelta(days=1)
        sub.save()
        
        # Create matching decision
        matching_decision = DecisionFactory(
            organization=organization,
            subject="Urgent contract renewal needed"
        )
        
        # Create non-matching decision
        non_matching_decision = DecisionFactory(
            organization=organization,
            subject="Regular administrative note"
        )
        
        # Check subscription
        check_single_subscription(sub.id)
        
        # Should create notification only for matching decision
        notifications = Notification.objects.filter(subscription=sub)
        assert notifications.count() == 1
        assert notifications.first().decision == matching_decision


class TestNotificationManagement:
    """
    Test notification management operations.
    """
    
    def test_mark_all_as_read(self, authenticated_client, unread_notifications):
        """Test marking all notifications as read"""
        response = authenticated_client.post('/api/notifications/mark-all-read/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['marked_read'] == len(unread_notifications)
        
        # Verify all are marked read
        response = authenticated_client.get('/api/notifications/unread-count/')
        assert response.data['unread_count'] == 0
    
    def test_dismiss_notification(
        self, authenticated_client, notification
    ):
        """Test dismissing a notification"""
        response = authenticated_client.post(
            f'/api/notifications/{notification.id}/dismiss/'
        )
        assert response.status_code == status.HTTP_200_OK
        
        # Verify it's dismissed
        notification.refresh_from_db()
        assert notification.is_dismissed is True
    
    def test_filter_notifications_by_read_status(
        self, authenticated_client, unread_notifications, notification_with_read_status
    ):
        """Test filtering notifications by read status"""
        # Get only unread
        response = authenticated_client.get('/api/notifications/?is_read=false')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == len(unread_notifications)
        
        # Get only read
        response = authenticated_client.get('/api/notifications/?is_read=true')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1


class TestSubscriptionManagement:
    """
    Test subscription CRUD operations via API.
    """
    
    def test_create_organization_subscription(
        self, authenticated_client, organization
    ):
        """Test creating an organization subscription"""
        response = authenticated_client.post(
            '/api/notifications/subscriptions/',
            {
                'organization_uid': organization.uid,
                'keywords': ['test']
            },
            format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert 'id' in response.data
    
    def test_update_subscription(
        self, authenticated_client, notification_subscription
    ):
        """Test updating subscription filters"""
        response = authenticated_client.patch(
            f'/api/notifications/subscriptions/{notification_subscription.id}/',
            {
                'keywords': ['updated', 'keywords'],
                'is_active': False
            },
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK
        
        notification_subscription.refresh_from_db()
        assert notification_subscription.keywords == ['updated', 'keywords']
        assert notification_subscription.is_active is False
    
    def test_delete_subscription(
        self, authenticated_client, notification_subscription
    ):
        """Test deleting a subscription"""
        subscription_id = notification_subscription.id
        
        response = authenticated_client.delete(
            f'/api/notifications/subscriptions/{subscription_id}/'
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify it's deleted
        from notifications.models import NotificationSubscription
        assert not NotificationSubscription.objects.filter(id=subscription_id).exists()
    
    def test_check_subscription_status(
        self, authenticated_client, organization, notification_subscription
    ):
        """Test checking if user is subscribed to an organization"""
        # User is subscribed
        response = authenticated_client.get(
            f'/api/notifications/subscriptions/check-organization/{organization.uid}/'
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['subscribed'] is True
        assert response.data['subscription']['id'] == notification_subscription.id
        
        # Check for organization user is not subscribed to
        from conftest import OrganizationFactory
        other_org = OrganizationFactory()
        
        response = authenticated_client.get(
            f'/api/notifications/subscriptions/check-organization/{other_org.uid}/'
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['subscribed'] is False
        assert response.data['subscription'] is None


class TestTasksAndBackgroundJobs:
    """
    Test Celery tasks for notification checking.
    """
    
    def test_check_single_subscription_task(
        self, old_subscription, celery_eager_mode
    ):
        """Test manual subscription check task"""
        from conftest import DecisionFactory
        from notifications.tasks import check_single_subscription
        
        # Create matching decision
        DecisionFactory(
            organization=old_subscription.organization,
            publish_timestamp=timezone.now()
        )
        
        # Run task
        result = check_single_subscription(
            old_subscription.id,
            lookback_days=15  # Covers the 10-day gap
        )
        
        assert result['subscription_id'] == old_subscription.id
        assert result['notifications_created'] >= 1
        assert result['lookback_days'] == 15
    
    def test_scheduled_task_only_checks_active_subscriptions(
        self, user, organization, celery_eager_mode
    ):
        """Test that inactive subscriptions are skipped"""
        from conftest import NotificationSubscriptionFactory, DecisionFactory
        from notifications.tasks import check_subscriptions_for_new_decisions
        from notifications.models import Notification
        
        # Create inactive subscription
        inactive_sub = NotificationSubscriptionFactory(
            user=user,
            organization=organization,
            is_active=False,
            check_frequency='daily'
        )
        
        # Create decision
        DecisionFactory(organization=organization)
        
        # Run scheduled task
        check_subscriptions_for_new_decisions()
        
        # No notifications should be created for inactive subscription
        notifications = Notification.objects.filter(subscription=inactive_sub)
        assert notifications.count() == 0


class TestPerformanceAndScaling:
    """
    Test performance considerations and N+1 query prevention.
    """
    
    @pytest.mark.django_db(transaction=True)
    def test_notification_list_query_efficiency(
        self, authenticated_client, user, db_with_sample_data
    ):
        """
        Test that listing notifications doesn't cause N+1 queries.
        Uses select_related/prefetch_related properly.
        """
        from conftest import NotificationSubscriptionFactory, NotificationFactory
        from django.test.utils import override_settings
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        
        # Create 10 notifications with different subscriptions/decisions
        for i in range(10):
            org = db_with_sample_data['organizations'][i % 5]
            sub = NotificationSubscriptionFactory(user=user, organization=org)
            decision = db_with_sample_data['decisions'][i]
            NotificationFactory(user=user, subscription=sub, decision=decision)
        
        # Count queries when fetching notifications
        with CaptureQueriesContext(connection) as context:
            response = authenticated_client.get('/api/notifications/')
            assert response.status_code == status.HTTP_200_OK
        
        # Should be a reasonable number of queries (not 10+ due to N+1)
        # Exact number depends on pagination, but should be < 10
        assert len(context.captured_queries) < 10, \
            f"Too many queries ({len(context.captured_queries)}), possible N+1 problem"
