"""
Shared fixtures and factories for all backend tests.

This conftest.py is at the root of the backend directory, making all fixtures
and factories available to any test in any app (core, notifications, api, etc.).
"""
import pytest
import factory
from factory.django import DjangoModelFactory
from faker import Faker
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

fake = Faker()
User = get_user_model()


# ============================================================================
# Auto-use Fixtures (run automatically for all tests)
# ============================================================================

@pytest.fixture(autouse=True)
def clear_rate_limit_cache(db):
    """
    Clear rate limit cache before each test to prevent rate limit errors.
    This runs automatically for all tests that use the database.
    """
    try:
        from django.core.cache import cache
        from django_redis import get_redis_connection
        
        # Clear all rate limit keys from cache
        cache.delete_pattern("ratelimit:*")
        
        # Also clear from Redis directly
        redis = get_redis_connection("default")
        for key in redis.scan_iter("ratelimit:*"):
            redis.delete(key)
    except Exception:
        # If Redis is not available or there's any error, just skip
        # This ensures tests can run even without Redis
        pass
    
    yield


# ============================================================================
# User Factories
# ============================================================================

class SubscriptionFactory(DjangoModelFactory):
    """Factory for Subscription model"""
    
    class Meta:
        model = 'users.Subscription'
        django_get_or_create = ('name',)
    
    name = factory.Sequence(lambda n: f"Plan {n}")
    max_requests_per_day = 1000
    price = Decimal('9.99')
    can_access_premium_data = False
    can_queue_bulk_tasks = False
    max_saved_items = 100
    max_search_history = 50


class UserFactory(DjangoModelFactory):
    """Factory for CustomUser model"""
    
    class Meta:
        model = User
        django_get_or_create = ('username',)
    
    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    is_staff = False
    is_superuser = False
    subscription = factory.SubFactory(SubscriptionFactory)
    subscription_expires = factory.LazyFunction(
        lambda: timezone.now() + timedelta(days=30)
    )


class AdminUserFactory(UserFactory):
    """Factory for admin/superuser"""
    is_staff = True
    is_superuser = True


# ============================================================================
# Core Model Factories
# ============================================================================

class OrganizationFactory(DjangoModelFactory):
    """Factory for Organization model"""
    
    class Meta:
        model = 'core.Organization'
        django_get_or_create = ('uid',)
    
    uid = factory.Sequence(lambda n: f"{100000000 + n}")
    label = factory.Faker('company')
    latin_name = factory.LazyAttribute(lambda obj: obj.label)
    category = factory.Faker('random_element', elements=['ministry', 'region', 'municipality'])
    status = 'ACTIVE'


class AFMEntityFactory(DjangoModelFactory):
    """Factory for AFMEntity model"""
    
    class Meta:
        model = 'core.AFMEntity'
        django_get_or_create = ('afm',)
    
    afm = factory.Sequence(lambda n: f"{100000000 + n}")
    name = factory.Faker('company')
    entity_type = factory.Faker('random_element', elements=['company', 'person', 'organization'])


class SignerFactory(DjangoModelFactory):
    """Factory for Signer model"""
    
    class Meta:
        model = 'core.Signer'
    
    uid = factory.Sequence(lambda n: f"SIGNER{n:06d}")
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    active = True
    organization = factory.SubFactory(OrganizationFactory)
    has_organization_sign_rights = True


class DecisionTypeFactory(DjangoModelFactory):
    """Factory for ActType model (referenced as decision_type in Decision)"""
    
    class Meta:
        model = 'core.ActType'
        django_get_or_create = ('uid',)
    
    uid = factory.Sequence(lambda n: f"Δ{n}")
    label = factory.Faker('catch_phrase')
    allowed_in_decisions = True


class DecisionFactory(DjangoModelFactory):
    """Factory for Decision model"""
    
    class Meta:
        model = 'core.Decision'
    
    ada = factory.Sequence(lambda n: f"ADA{n:06d}")
    subject = factory.Faker('sentence', nb_words=10)
    protocol_number = factory.Sequence(lambda n: f"PROT-{n}")
    organization = factory.SubFactory(OrganizationFactory)
    decision_type = factory.SubFactory(DecisionTypeFactory)
    
    # Dates
    issue_date = factory.LazyFunction(
        lambda: timezone.now() - timedelta(days=7)
    )
    submission_timestamp = factory.LazyFunction(
        lambda: timezone.now() - timedelta(days=6)
    )
    publish_timestamp = factory.LazyFunction(
        lambda: timezone.now() - timedelta(days=5)
    )
    
    # Status and URLs
    status = 'PUBLISHED'
    document_url = factory.LazyAttribute(
        lambda obj: f"https://diavgeia.gov.gr/doc/{obj.ada}.pdf"
    )
    url = factory.LazyAttribute(
        lambda obj: f"https://diavgeia.gov.gr/decision/view/{obj.ada}"
    )
    
    version_id = "1"
    has_private_data = False


class DocumentExtractionFactory(DjangoModelFactory):
    """Factory for DocumentExtraction model"""
    
    class Meta:
        model = 'core.DocumentExtraction'
    
    decision = factory.SubFactory(DecisionFactory)
    extraction_status = 'COMPLETED'
    extraction_provider = 'PYMUPDF'
    extraction_date = factory.LazyFunction(timezone.now)
    raw_text = factory.Faker('text', max_nb_chars=500)
    page_count = 1
    character_count = factory.LazyAttribute(lambda obj: len(obj.raw_text) if obj.raw_text else 0)
    is_scanned_document = False
    processing_time_ms = 100


# ============================================================================
# Notification Factories
# ============================================================================

class NotificationSubscriptionFactory(DjangoModelFactory):
    """Factory for NotificationSubscription model"""
    
    class Meta:
        model = 'notifications.NotificationSubscription'
    
    user = factory.SubFactory(UserFactory)
    is_active = True
    check_frequency = 'daily'
    
    # Most subscriptions are for organizations
    organization = factory.SubFactory(OrganizationFactory)
    
    # List fields - default to empty but can be overridden
    # Using LazyFunction to ensure each instance gets its own list
    keywords = factory.LazyFunction(list)
    decision_types = factory.LazyFunction(list)


class EntitySubscriptionFactory(NotificationSubscriptionFactory):
    """Factory for entity-based subscriptions"""
    organization = None
    entity = factory.SubFactory(AFMEntityFactory)


class RelationshipSubscriptionFactory(NotificationSubscriptionFactory):
    """Factory for relationship-based subscriptions"""
    organization = None
    relationship_org = factory.SubFactory(OrganizationFactory)
    relationship_entity = factory.SubFactory(AFMEntityFactory)


class NotificationFactory(DjangoModelFactory):
    """Factory for Notification model"""
    
    class Meta:
        model = 'notifications.Notification'
    
    user = factory.SubFactory(UserFactory)
    subscription = factory.SubFactory(NotificationSubscriptionFactory)
    decision = factory.SubFactory(DecisionFactory)
    match_reason = 'organization_match'
    is_read = False
    is_dismissed = False
    match_details = factory.LazyAttribute(lambda obj: {
        'matched_on': 'organization',
        'organization_uid': obj.decision.organization.uid if obj.decision and obj.decision.organization else None
    })


# ============================================================================
# Pytest Fixtures (wrapping factories for easier use)
# ============================================================================

@pytest.fixture
def user():
    """Create a regular test user"""
    return UserFactory()


@pytest.fixture
def admin_user():
    """Create an admin test user"""
    return AdminUserFactory()


@pytest.fixture
def organization():
    """Create a test organization"""
    return OrganizationFactory()


@pytest.fixture
def afm_entity():
    """Create a test AFM entity"""
    return AFMEntityFactory()


@pytest.fixture
def decision_type():
    """Create a test decision type"""
    return DecisionTypeFactory()


@pytest.fixture
def signer(organization):
    """Create a test signer"""
    return SignerFactory(organization=organization)


@pytest.fixture
def decision(organization, decision_type):
    """Create a test decision"""
    return DecisionFactory(
        organization=organization,
        decision_type=decision_type
    )


@pytest.fixture
def notification_subscription(user, organization):
    """Create a test notification subscription"""
    return NotificationSubscriptionFactory(
        user=user,
        organization=organization
    )


@pytest.fixture
def notification(user, notification_subscription, decision):
    """Create a test notification"""
    return NotificationFactory(
        user=user,
        subscription=notification_subscription,
        decision=decision
    )


# ============================================================================
# API Client Fixtures
# ============================================================================

@pytest.fixture
def api_client():
    """Unauthenticated API client"""
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def authenticated_client(user):
    """API client authenticated with a regular user"""
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin_client(admin_user):
    """API client authenticated with an admin user"""
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture
def db_with_sample_data(db):
    """
    Database populated with sample test data.
    Useful for integration tests that need realistic data.
    """
    # Create some organizations
    orgs = OrganizationFactory.create_batch(5)
    
    # Create some entities
    entities = AFMEntityFactory.create_batch(10)
    
    # Create some decision types
    types = DecisionTypeFactory.create_batch(3)
    
    # Create decisions for each org
    decisions = []
    for org in orgs:
        for dt in types[:2]:  # 2 decisions per org per type
            decisions.extend(
                DecisionFactory.create_batch(
                    2,
                    organization=org,
                    decision_type=dt
                )
            )
    
    return {
        'organizations': orgs,
        'entities': entities,
        'decision_types': types,
        'decisions': decisions
    }


# ============================================================================
# Mock Celery for Integration Tests
# ============================================================================

@pytest.fixture
def celery_eager_mode(settings):
    """
    Make Celery execute tasks synchronously for tests.
    This allows testing task logic without needing a Celery worker.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
    return settings
