from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from notifications.models import NotificationSubscription, Notification, NotificationBatch, NotificationBatchDecision
from notifications.utils import find_matching_decisions, determine_match_reason
from notifications.constants import CHECK_FREQUENCY_DAILY, CHECK_FREQUENCY_WEEKLY
from loguru import logger


@shared_task
def check_single_subscription(subscription_id, lookback_days=30, use_batch=False):
    """
    Check a single subscription for matching decisions.
    Used for on-demand checks triggered by users via the "check now" button.
    
    Args:
        subscription_id: ID of the subscription to check
        lookback_days: How many days back to check for matching decisions (default: 30)
        use_batch: If True, create NotificationBatch; if False, create individual Notifications (default: False)
    
    Returns:
        dict with subscription_id and either batch_id/decisions_added or notifications_created
    """
    try:
        subscription = NotificationSubscription.objects.select_related(
            'organization', 'entity', 'relationship_org', 'relationship_entity'
        ).get(id=subscription_id)
        
        logger.info(f"Checking subscription {subscription_id} (manual check, lookback: {lookback_days} days)")
        
        # For manual checks, use the lookback_days parameter
        check_window_end = timezone.now()
        check_window_start = check_window_end - timedelta(days=lookback_days)
        
        # Find matching decisions
        matching_decisions = find_matching_decisions(subscription, check_window_start)
        
        if use_batch:
            # Create batch for matches (prevents notification spam)
            batch_result = create_batch_for_matches(
                subscription, 
                matching_decisions,
                check_window_start,
                check_window_end
            )
            
            # Update last_checked
            subscription.last_checked = timezone.now()
            subscription.save(update_fields=['last_checked'])
            
            logger.info(
                f"Subscription {subscription_id}: Created batch {batch_result.get('batch_id')} "
                f"with {batch_result.get('decisions_added', 0)} decisions"
            )
            
            return {
                'subscription_id': subscription_id,
                'batch_id': batch_result.get('batch_id'),
                'decisions_added': batch_result.get('decisions_added', 0),
                'batch_created': batch_result.get('batch_created', False),
                'lookback_days': lookback_days,
                # For backwards compatibility with tests expecting 'notifications_created'
                'notifications_created': batch_result.get('decisions_added', 0)
            }
        else:
            # Create individual notifications
            notifications_created = create_notifications_for_matches(subscription, matching_decisions)
            
            # Update last_checked
            subscription.last_checked = timezone.now()
            subscription.save(update_fields=['last_checked'])
            
            logger.info(
                f"Subscription {subscription_id}: Created {notifications_created} notifications"
            )
            
            return {
                'subscription_id': subscription_id,
                'notifications_created': notifications_created,
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
        check_frequency__in=[CHECK_FREQUENCY_DAILY, CHECK_FREQUENCY_WEEKLY]
    ).select_related('organization', 'entity', 'relationship_org', 'relationship_entity')
    
    logger.info(f"Found {active_subscriptions.count()} active subscriptions with automatic checking enabled")
    
    notifications_created = 0
    checked_count = 0
    
    for subscription in active_subscriptions:
        try:
            # Determine if we should check this subscription
            should_check = False
            
            if subscription.check_frequency == CHECK_FREQUENCY_DAILY:
                should_check = True
                # For daily checks, look back 1 day (or since last_checked if more recent)
                default_check_since = now - timedelta(days=1)
            elif subscription.check_frequency == CHECK_FREQUENCY_WEEKLY:
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
            check_window_start = subscription.last_checked or default_check_since
            check_window_end = now
            
            # Find matching decisions
            matching_decisions = find_matching_decisions(subscription, check_window_start)
            
            # Create notifications for matches
            notifications_count = create_notifications_for_matches(subscription, matching_decisions)
            
            notifications_created += notifications_count
            checked_count += 1
            
            # Update last_checked
            subscription.last_checked = now
            subscription.save(update_fields=['last_checked'])
            
            logger.info(
                f"Subscription {subscription.id} ({subscription.check_frequency}): "
                f"created {notifications_count} notifications"
            )
            
        except Exception as e:
            logger.error(f"Error processing subscription {subscription.id}: {e}", exc_info=True)
            continue
    
    logger.info(f"Checked {checked_count} subscriptions, created {notifications_created} notifications")
    return {"notifications_created": notifications_created, "checked_count": checked_count}


def create_notifications_for_matches(subscription, matching_decisions):
    """
    Create Notification objects for each matching decision.
    Uses bulk_create with ignore_conflicts to avoid duplicates.
    
    This is the current approach used by check tasks to create individual
    notifications for each matching decision.
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
    # Note: bulk_create with ignore_conflicts=True returns an empty list,
    # so we count before creating rather than after
    count = len(notifications_to_create)
    
    Notification.objects.bulk_create(
        notifications_to_create,
        ignore_conflicts=True
    )
    
    return count


def create_batch_for_matches(subscription, matching_decisions, check_window_start, check_window_end):
    """
    Create a NotificationBatch and NotificationBatchDecision objects for matching decisions.
    
    This is the preferred approach for manual checks (check_single_subscription),
    grouping multiple matches into a single batch to prevent notification spam.
    
    Args:
        subscription: NotificationSubscription instance
        matching_decisions: QuerySet or list of Decision instances that matched
        check_window_start: datetime when check started
        check_window_end: datetime when check ended
    
    Returns:
        dict with batch_id and decisions_added count
    """
    from decimal import Decimal
    from django.db import transaction
    
    # Convert to list if it's a QuerySet
    decisions_list = list(matching_decisions)
    
    if not decisions_list:
        logger.info(f"No decisions to batch for subscription {subscription.id}")
        return {'batch_id': None, 'decisions_added': 0}
    
    # Calculate aggregate statistics
    aggregate_stats = {}
    
    # Amount statistics (if decisions have amounts)
    amounts = []
    for decision in decisions_list:
        if hasattr(decision, 'amount') and decision.amount:
            amounts.append(float(decision.amount))
    
    if amounts:
        aggregate_stats['total_amount'] = sum(amounts)
        aggregate_stats['avg_amount'] = sum(amounts) / len(amounts)
        aggregate_stats['min_amount'] = min(amounts)
        aggregate_stats['max_amount'] = max(amounts)
    
    # Decision type breakdown
    decision_types = {}
    for decision in decisions_list:
        if decision.decision_type:
            type_uid = decision.decision_type.uid
            decision_types[type_uid] = decision_types.get(type_uid, 0) + 1
    
    if decision_types:
        aggregate_stats['decision_types'] = decision_types
    
    try:
        with transaction.atomic():
            # Create or get existing batch for this time window
            batch, created = NotificationBatch.objects.get_or_create(
                subscription=subscription,
                check_window_start=check_window_start,
                check_window_end=check_window_end,
                defaults={
                    'user': subscription.user,
                    'match_count': len(decisions_list),
                    'aggregate_stats': aggregate_stats,
                }
            )
            
            if not created:
                # Batch already exists - update match count and stats
                batch.match_count = len(decisions_list)
                batch.aggregate_stats = aggregate_stats
                batch.save(update_fields=['match_count', 'aggregate_stats'])
                logger.info(f"Updated existing batch {batch.id} for subscription {subscription.id}")
            else:
                logger.info(f"Created new batch {batch.id} for subscription {subscription.id}")
            
            # Create batch decisions
            batch_decisions_to_create = []
            for decision in decisions_list:
                match_reason, match_details = determine_match_reason(subscription, decision)
                
                batch_decisions_to_create.append(
                    NotificationBatchDecision(
                        batch=batch,
                        decision=decision,
                        match_reason=match_reason,
                        match_details=match_details
                    )
                )
            
            # Bulk create with ignore_conflicts to handle duplicates
            # Note: bulk_create with ignore_conflicts=True returns an empty list,
            # so we count before creating rather than after
            decisions_added = len(batch_decisions_to_create)
            
            NotificationBatchDecision.objects.bulk_create(
                batch_decisions_to_create,
                ignore_conflicts=True
            )
            
            logger.info(
                f"Batch {batch.id}: Added {decisions_added} decisions "
                f"(total in batch: {batch.match_count})"
            )
            
            return {
                'batch_id': batch.id,
                'decisions_added': decisions_added,
                'batch_created': created
            }
            
    except Exception as e:
        logger.error(f"Error creating batch for subscription {subscription.id}: {e}", exc_info=True)
        return {'batch_id': None, 'decisions_added': 0, 'error': str(e)}

