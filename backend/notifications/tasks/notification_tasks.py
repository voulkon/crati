from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from notifications.models import NotificationSubscription, Notification
from core.models.decisions import Decision
from loguru import logger
from django.db import models


@shared_task
def check_single_subscription(subscription_id, lookback_days=30):
    """
    Check a single subscription for matching decisions.
    Used for on-demand checks triggered by users via the "check now" button.
    
    Args:
        subscription_id: ID of the subscription to check
        lookback_days: How many days back to check for matching decisions (default: 30)
    
    Returns:
        dict with subscription_id and notifications_created count
    """
    try:
        subscription = NotificationSubscription.objects.select_related(
            'organization', 'entity', 'relationship_org', 'relationship_entity'
        ).get(id=subscription_id)
        
        logger.info(f"Checking subscription {subscription_id} (manual check, lookback: {lookback_days} days)")
        
        # For manual checks, use the lookback_days parameter
        check_since = timezone.now() - timedelta(days=lookback_days)
        
        # Find matching decisions
        matching_decisions = find_matching_decisions(subscription, check_since)
        
        # Create notifications
        created_count = create_notifications_for_matches(subscription, matching_decisions)
        
        # Update last_checked
        subscription.last_checked = timezone.now()
        subscription.save(update_fields=['last_checked'])
        
        logger.info(f"Subscription {subscription_id}: Created {created_count} notifications")
        
        return {
            'subscription_id': subscription_id,
            'notifications_created': created_count,
            'lookback_days': lookback_days
        }
        
    except NotificationSubscription.DoesNotExist:
        logger.error(f"Subscription {subscription_id} not found")
        return {'error': 'Subscription not found', 'subscription_id': subscription_id}
    except Exception as e:
        logger.error(f"Error checking subscription {subscription_id}: {e}", exc_info=True)
        return {'error': str(e), 'subscription_id': subscription_id}


@shared_task
def check_subscriptions_for_new_decisions():
    """
    Main scheduled task - checks all active subscriptions with automatic check frequency
    for new matching decisions since last check.
    
    Runs daily. Only checks subscriptions with check_frequency='daily' or 'weekly'
    (weekly subscriptions are checked if last_checked was more than 7 days ago).
    """
    logger.info("Starting scheduled subscription check for new decisions")
    
    now = timezone.now()
    
    # Get active subscriptions that should be checked
    active_subscriptions = NotificationSubscription.objects.filter(
        is_active=True,
        check_frequency__in=['daily', 'weekly']
    ).select_related('organization', 'entity', 'relationship_org', 'relationship_entity')
    
    logger.info(f"Found {active_subscriptions.count()} active subscriptions with automatic checking enabled")
    
    notifications_created = 0
    checked_count = 0
    
    for subscription in active_subscriptions:
        try:
            # Determine if we should check this subscription
            should_check = False
            
            if subscription.check_frequency == 'daily':
                should_check = True
                # For daily checks, look back 1 day (or since last_checked if more recent)
                default_check_since = now - timedelta(days=1)
            elif subscription.check_frequency == 'weekly':
                # Check weekly subscriptions only if last_checked was more than 7 days ago
                if subscription.last_checked is None:
                    should_check = True
                    default_check_since = now - timedelta(days=7)
                elif (now - subscription.last_checked).days >= 7:
                    should_check = True
                    default_check_since = now - timedelta(days=7)
            
            if not should_check:
                continue
            
            # Determine actual check window
            check_since = subscription.last_checked or default_check_since
            
            # Find matching decisions
            matching_decisions = find_matching_decisions(subscription, check_since)
            
            # Create notifications
            created_count = create_notifications_for_matches(subscription, matching_decisions)
            notifications_created += created_count
            checked_count += 1
            
            # Update last_checked
            subscription.last_checked = now
            subscription.save(update_fields=['last_checked'])
            
            logger.info(f"Subscription {subscription.id} ({subscription.check_frequency}): created {created_count} notifications")
            
        except Exception as e:
            logger.error(f"Error processing subscription {subscription.id}: {e}", exc_info=True)
            continue
    
    logger.info(f"Checked {checked_count} subscriptions, created {notifications_created} new notifications")
    return {"notifications_created": notifications_created}

def find_matching_decisions(subscription, check_since):
    """
    Find decisions that match the subscription criteria
    since the last check.
    """
    queryset = Decision.objects.filter(
        publish_timestamp__gte=check_since
    )
    
    # Apply subscription type filters
    if subscription.subscription_type == 'organization':
        queryset = queryset.filter(organization=subscription.organization)
    
    elif subscription.subscription_type == 'entity':
        # Check if entity appears in signer, buyer, or extra_fields
        entity_afm = subscription.entity.afm
        queryset = queryset.filter(
            models.Q(signer__afm=entity_afm) |
            models.Q(buyer__afm=entity_afm) |
            models.Q(seller__afm=entity_afm)
        )
    
    elif subscription.subscription_type == 'relationship':
        # Check for relationship between org and entity
        entity_afm = subscription.relationship_entity.afm
        queryset = queryset.filter(
            organization=subscription.relationship_org
        ).filter(
            models.Q(signer__afm=entity_afm) |
            models.Q(buyer__afm=entity_afm) |
            models.Q(seller__afm=entity_afm)
        )
    
    # Apply optional filters
    if subscription.keywords:
        # Check keywords in subject
        keyword_filter = models.Q()
        for keyword in subscription.keywords:
            keyword_filter |= models.Q(subject__icontains=keyword)
        queryset = queryset.filter(keyword_filter)
    
    if subscription.amount_min is not None or subscription.amount_max is not None:
        # Filter by amount (check where amounts are stored in your model)
        if subscription.amount_min:
            queryset = queryset.filter(amount__gte=subscription.amount_min)
        if subscription.amount_max:
            queryset = queryset.filter(amount__lte=subscription.amount_max)
    
    if subscription.decision_types:
        queryset = queryset.filter(decision_type_id__in=subscription.decision_types)
    
    return queryset.distinct()

def create_notifications_for_matches(subscription, matching_decisions):
    """
    Create Notification objects for each matching decision.
    Uses bulk_create with ignore_conflicts to avoid duplicates.
    """
    notifications_to_create = []
    
    for decision in matching_decisions:
        # Determine match reason and details
        match_reason, match_details = determine_match_reason(subscription, decision)
        
        notifications_to_create.append(
            Notification(
                user=subscription.user,
                subscription=subscription,
                decision=decision,
                match_reason=match_reason,
                match_details=match_details
            )
        )
    
    # Use bulk_create with ignore_conflicts to handle unique constraint
    created = Notification.objects.bulk_create(
        notifications_to_create,
        ignore_conflicts=True
    )
    
    return len(created)

def determine_match_reason(subscription, decision):
    """
    Determine why this decision matched and provide details.
    """
    match_details = {}
    
    # Check keyword matches
    if subscription.keywords:
        found_keywords = []
        for keyword in subscription.keywords:
            if keyword.lower() in (decision.subject or '').lower():
                found_keywords.append(keyword)
        
        if found_keywords:
            match_details['keywords_found'] = list(set(found_keywords))
    
    # Check amount match
    if subscription.amount_min or subscription.amount_max:
        if hasattr(decision, 'amount') and decision.amount:
            match_details['amount'] = str(decision.amount)
            match_details['amount_in_range'] = True
    
    # Determine primary match reason
    if match_details.get('keywords_found'):
        match_reason = 'keyword_match'
    elif match_details.get('amount_in_range'):
        match_reason = 'amount_match'
    else:
        match_reason = 'new_decision'
    
    return match_reason, match_details

