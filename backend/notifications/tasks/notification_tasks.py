from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from notifications.models import NotificationSubscription, Notification
from core.models.decisions import Decision
from loguru import logger
from django.db import models


def build_keyword_q_filter(keyword, field_name='subject'):
    """
    Build a Q filter for keyword matching that handles Greek word inflections.
    
    For Greek (and other inflected languages), we need to match word stems
    since the same word can have different endings based on grammatical case.
    
    Examples:
        - διαγωνισμός (nominative) should match διαγωνισμού (genitive)
        - σύμβαση should match Σύμβαση (case-insensitive)
    
    Strategy:
        1. First try exact substring match (handles most cases)
        2. For longer keywords (>5 chars), also match word stems by removing
           last 1-2 characters to handle case endings
    
    Args:
        keyword: The keyword to match
        field_name: The field name to search in (default: 'subject')
    
    Returns:
        Q object with the appropriate filter conditions
    """
    q_filter = models.Q()
    
    # Always include exact substring match (case-insensitive)
    q_filter |= models.Q(**{f'{field_name}__icontains': keyword})
    
    # For longer keywords, also try stem matching to handle inflections
    # This is especially important for Greek where word endings change based on case
    if len(keyword) > 5:
        # Create stems by removing last 1-2 characters
        # This handles most Greek case endings (ός/ού/ό, ση/σης/ση, ια/ιας, etc.)
        stem_variants = []
        
        # Try removing last 2 chars (handles ός->ού/ό, ση->σης, ια->ιας, etc.)
        if len(keyword) > 6:
            stem = keyword[:-2]
            if len(stem) >= 4:  # Minimum stem length to avoid false positives
                stem_variants.append(stem)
        
        # Try removing last 1 char (handles η->ης, ο->ου, etc.)
        if len(keyword) > 5:
            stem = keyword[:-1]
            if len(stem) >= 4:
                stem_variants.append(stem)
        
        # Add stem variants as case-insensitive substring matches
        # Don't use word boundaries as they don't work reliably with Unicode
        for stem in stem_variants:
            q_filter |= models.Q(**{f'{field_name}__icontains': stem})
    
    return q_filter


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
        # Check if entity appears in any decision through entity_relationships
        entity_afm = subscription.entity.afm
        queryset = queryset.filter(
            entity_relationships__entity__afm=entity_afm
        )
    
    elif subscription.subscription_type == 'relationship':
        # Check for relationship between org and entity
        entity_afm = subscription.relationship_entity.afm
        queryset = queryset.filter(
            organization=subscription.relationship_org,
            entity_relationships__entity__afm=entity_afm
        )
    
    elif subscription.subscription_type == 'person':
        # Find companies where this person is associated
        from core.models.companies import CompanyPerson
        
        # Get AFMs of companies where this person appears
        company_afms = CompanyPerson.objects.filter(
            person_name__icontains=subscription.person_name
        ).values_list('company__afm', flat=True).distinct()
        
        # Find decisions involving entities with those AFMs
        queryset = queryset.filter(
            entity_relationships__entity__afm__in=company_afms
        )
    
    elif subscription.subscription_type == 'signer':
        # Find decisions signed by this person
        # Build a query that matches first_name + last_name against signer_name
        # The signer_name might be "FirstName LastName" or similar
        signer_name_parts = subscription.signer_name.split()
        
        if len(signer_name_parts) >= 2:
            # Try to match by building full name from first_name and last_name
            signer_query = models.Q()
            
            # Try different combinations in case name is in different order
            for i in range(len(signer_name_parts)):
                for j in range(i+1, len(signer_name_parts) + 1):
                    name_part = ' '.join(signer_name_parts[i:j])
                    signer_query |= models.Q(signers__first_name__icontains=name_part)
                    signer_query |= models.Q(signers__last_name__icontains=name_part)
            
            queryset = queryset.filter(signer_query)
        else:
            # Single name part - search in both first and last name
            queryset = queryset.filter(
                models.Q(signers__first_name__icontains=subscription.signer_name) |
                models.Q(signers__last_name__icontains=subscription.signer_name)
            )
    
    elif subscription.subscription_type == 'filter':
        # Filter-only subscription - no target restrictions
        # queryset already filtered by publish_timestamp, will apply filters below
        pass
    
    # Apply optional filters (keywords, amounts, decision types, signer)
    # These apply to ALL subscription types
    
    # Signer filter - can be used with any subscription type
    # (e.g., org + signer means "decisions from this org signed by this person")
    if subscription.signer_name:
        signer_name_parts = subscription.signer_name.split()
        
        if len(signer_name_parts) >= 2:
            # Try to match by building full name from first_name and last_name
            signer_query = models.Q()
            
            # Try different combinations in case name is in different order
            for i in range(len(signer_name_parts)):
                for j in range(i+1, len(signer_name_parts) + 1):
                    name_part = ' '.join(signer_name_parts[i:j])
                    signer_query |= models.Q(signers__first_name__icontains=name_part)
                    signer_query |= models.Q(signers__last_name__icontains=name_part)
            
            queryset = queryset.filter(signer_query)
        else:
            # Single name part - search in both first and last name
            queryset = queryset.filter(
                models.Q(signers__first_name__icontains=subscription.signer_name) |
                models.Q(signers__last_name__icontains=subscription.signer_name)
            )
    
    # Keyword filter
    if subscription.keywords:
        # Check keywords in subject (case-insensitive)
        # Support both AND and OR operators
        # Uses stem matching to handle Greek word inflections
        operator = getattr(subscription, 'keyword_match_operator', 'AND')  # Default to AND
        
        if operator == 'OR':
            # OR logic: any keyword matches (at least one keyword must be present)
            keyword_filter = models.Q()
            for keyword in subscription.keywords:
                keyword_filter |= build_keyword_q_filter(keyword, 'subject')
            queryset = queryset.filter(keyword_filter)
        else:  # AND logic
            # AND logic: all keywords must match (every keyword must be present)
            for keyword in subscription.keywords:
                queryset = queryset.filter(build_keyword_q_filter(keyword, 'subject'))
    
    if subscription.amount_min is not None or subscription.amount_max is not None:
        # Filter by amount
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
    
    # Determine primary match reason based on subscription type
    subscription_type = subscription.subscription_type
    
    # Add subscription type to match details
    match_details['subscription_type'] = subscription_type
    
    # Check keyword matches
    if subscription.keywords:
        found_keywords = []
        for keyword in subscription.keywords:
            if keyword.lower() in (decision.subject or '').lower():
                found_keywords.append(keyword)
        
        if found_keywords:
            match_details['keywords_found'] = list(set(found_keywords))
            match_details['keyword_match_operator'] = getattr(subscription, 'keyword_match_operator', 'AND')
    
    # Check amount match
    if subscription.amount_min or subscription.amount_max:
        if hasattr(decision, 'amount') and decision.amount:
            match_details['amount'] = str(decision.amount)
            match_details['amount_in_range'] = True
    
    # Check decision type match
    if subscription.decision_types:
        if decision.decision_type_id in subscription.decision_types:
            match_details['decision_type_matched'] = decision.decision_type_id
    
    # Determine primary match reason based on subscription type and filters
    # Priority: subscription type first, then specific filters
    if subscription_type == 'organization':
        match_reason = 'organization'
        match_details['organization_uid'] = subscription.organization.uid if subscription.organization else None
    elif subscription_type == 'entity':
        match_reason = 'entity'
        match_details['entity_afm'] = subscription.entity.afm if subscription.entity else None
    elif subscription_type == 'relationship':
        match_reason = 'relationship'
        match_details['relationship_org_uid'] = subscription.relationship_org.uid if subscription.relationship_org else None
        match_details['relationship_entity_afm'] = subscription.relationship_entity.afm if subscription.relationship_entity else None
    elif subscription_type == 'person':
        match_reason = 'person'
        match_details['person_name'] = subscription.person_name
    elif subscription_type == 'signer':
        match_reason = 'signer'
        match_details['signer_name'] = subscription.signer_name
    elif subscription_type == 'filter':
        # For filter-only subscriptions, determine match reason by what matched
        if match_details.get('keywords_found'):
            match_reason = 'keyword_match'
        elif match_details.get('amount_in_range'):
            match_reason = 'amount_match'
        elif match_details.get('decision_type_matched'):
            match_reason = 'filter'
        else:
            match_reason = 'filter'
    else:
        # Fallback
        match_reason = 'filter'
    
    return match_reason, match_details

