# Notification System Architecture - Current State

**Date:** March 11, 2026  
**Status:** ⚠️ DUAL SYSTEM IN PRODUCTION - NEEDS RECONCILIATION

---

## Executive Summary

There are **TWO PARALLEL NOTIFICATION SYSTEMS** currently implemented:

1. **Individual Notifications** (Legacy/Old) - One notification per matching decision
2. **Batch Notifications** (New) - Groups multiple decisions into one notification

**CRITICAL ISSUE:** Both systems exist simultaneously, and the default behavior is inconsistent across the codebase.

---

## System 1: Individual Notifications (Legacy)

### Models

#### `Notification` Model
Location: `/code/notifications/models/notification.py`

```python
class Notification(models.Model):
    user = ForeignKey('users.CustomUser')
    subscription = ForeignKey('NotificationSubscription')
    decision = ForeignKey('core.Decision')  # ONE decision per notification
    match_reason = CharField(choices=MATCH_REASONS)
    match_details = JSONField()
    is_read = BooleanField(default=False)
    is_dismissed = BooleanField(default=False)
    created_at = DateTimeField(auto_now_add=True)
    read_at = DateTimeField(null=True)
```

**Unique Constraint:** `(user, subscription, decision)` - Prevents duplicate notifications for same decision

### API Endpoints

- `GET /api/notifications/` - List all notifications
- `GET /api/notifications/unread-count/` - Count unread notifications
- `POST /api/notifications/{id}/mark-read/` - Mark as read
- `POST /api/notifications/{id}/dismiss/` - Dismiss notification

### Data Flow

```
User creates subscription
         ↓
Celery task: check_single_subscription(sub_id, use_batch=False)  ← DEFAULT
         ↓
find_matching_decisions()
         ↓
create_notifications_for_matches()  ← Creates individual Notifications
         ↓
For EACH matching decision:
    → Create ONE Notification object
    → User sees: "New decision from Organization X"
         ↓
Frontend shows list of individual notifications
```

### Problem: NOTIFICATION SPAM

If a subscription matches 50 decisions:
- ✗ Creates 50 separate Notification objects
- ✗ User sees 50 separate notification items
- ✗ User must mark 50 items as read
- ✗ Database bloat

---

## System 2: Batch Notifications (New/Preferred)

### Models

#### `NotificationBatch` Model
Location: `/code/notifications/models/notification_batch.py`

```python
class NotificationBatch(models.Model):
    """The notification that users see in their notification list"""
    user = ForeignKey('users.CustomUser')
    subscription = ForeignKey('NotificationSubscription')
    check_window_start = DateTimeField()  # Time range checked
    check_window_end = DateTimeField()
    match_count = IntegerField()  # How many decisions matched
    aggregate_stats = JSONField()  # Pre-computed statistics
    is_read = BooleanField(default=False)
    is_dismissed = BooleanField(default=False)
    created_at = DateTimeField(auto_now_add=True)
```

**Unique Constraint:** `(subscription, check_window_start, check_window_end)` - One batch per time window

#### `NotificationBatchDecision` Model

```python
class NotificationBatchDecision(models.Model):
    """Junction table - the individual decisions within a batch"""
    batch = ForeignKey('NotificationBatch')
    decision = ForeignKey('core.Decision')
    match_reason = CharField()
    match_details = JSONField()
    is_viewed = BooleanField(default=False)
    added_at = DateTimeField(auto_now_add=True)
```

**Unique Constraint:** `(batch, decision)` - Prevents duplicate decisions in same batch

### API Endpoints

- `GET /api/notifications/batches/` - List all batch notifications
- `GET /api/notifications/batches/unread-count/` - Count unread batches
- `GET /api/notifications/batches/{id}/` - Get batch details
- `GET /api/notifications/batches/{id}/decisions/` - **List decisions within batch (paginated)**
- `POST /api/notifications/batches/{id}/mark-read/` - Mark batch as read
- `POST /api/notifications/batches/{id}/dismiss/` - Dismiss batch

### Data Flow

```
User creates subscription
         ↓
Celery task: check_single_subscription(sub_id, use_batch=True)
         ↓
find_matching_decisions()
         ↓
create_batch_for_matches()  ← Creates ONE batch with multiple decisions
         ↓
Create ONE NotificationBatch object
    ↓
    match_count = 50
    aggregate_stats = {
        total_amount: 1500000.00,
        avg_amount: 30000.00,
        decision_types: {"Α.1": 30, "Β.2": 20}
    }
    ↓
    For EACH matching decision:
        → Create NotificationBatchDecision (linking record)
         ↓
Frontend shows: "5 new decisions match your subscription 'Organization X + Keywords'"
    User clicks to expand
         ↓
    Frontend calls: GET /api/notifications/batches/{id}/decisions/
         ↓
    Shows paginated list of 50 individual decisions
```

### Benefits: ANTI-SPAM

If a subscription matches 50 decisions:
- ✓ Creates 1 NotificationBatch object
- ✓ User sees 1 notification item showing "50 new matches"
- ✓ User can expand to see individual decisions
- ✓ User marks 1 batch as read (all decisions marked viewed)
- ✓ Cleaner database structure

---

## Current Implementation Status

### Task Functions
Location: `/code/notifications/tasks/notification_tasks.py`

```python
@shared_task
def check_single_subscription(subscription_id, lookback_days=30, use_batch=False):
    """
    CURRENT DEFAULT: use_batch=False (Individual Notifications)
    ⚠️ PROBLEM: This creates spam by default!
    """
    if use_batch:
        # Create NotificationBatch (NEW SYSTEM)
        batch_result = create_batch_for_matches(...)
        return {
            'batch_id': ...,
            'decisions_added': ...
        }
    else:
        # Create individual Notifications (LEGACY SYSTEM)
        notifications_created = create_notifications_for_matches(...)
        return {
            'notifications_created': ...
        }

@shared_task
def check_subscriptions_for_new_decisions():
    """
    Scheduled daily task - checks all active subscriptions
    CURRENTLY USES: Individual Notifications (Legacy System)
    ⚠️ PROBLEM: Scheduled checks create spam!
    """
    for subscription in active_subscriptions:
        matching_decisions = find_matching_decisions(...)
        
        # Uses legacy system - creates individual notifications
        notifications_count = create_notifications_for_matches(...)
```

### Test Coverage

**Tests using Individual Notifications (Legacy):**
- ✓ `/code/notifications/tests/integration/test_keyword_matching.py` (38 tests)
- ✓ `/code/notifications/tests/integration/test_subscription_types_comprehensive.py` (30+ tests)
- ✓ `/code/notifications/tests/integration/test_notification_flow.py` (partial)
- ✓ `/code/notifications/tests/unit/test_models.py` (partial)

**Tests using Batch Notifications (New):**
- ✓ `/code/notifications/tests/integration/test_notification_batch_api.py` (must pass `use_batch=True`)

---

## The Discrepancy - What's Wrong

### Issue 1: Inconsistent Default Behavior

```python
# Manual check from "Check Now" button
check_single_subscription(sub.id)  
# → Creates individual Notifications (SPAM)
# → Should create NotificationBatch

# Scheduled daily check
check_subscriptions_for_new_decisions()
# → Creates individual Notifications (SPAM) 
# → Should create NotificationBatch
```

### Issue 2: Frontend Integration Unclear

**Which API should the frontend use?**

- Option A: `/api/notifications/` (Individual system - causes spam)
- Option B: `/api/notifications/batches/` (Batch system - preferred)

**Current state:** Both APIs exist, unclear which is "production"

### Issue 3: Test Suite Mismatch

- 95% of tests expect individual Notifications
- 5% of tests expect NotificationBatch
- Tests pass, but don't reflect desired production behavior

---

## Frontend Integration Guide

### Recommended Approach (Batch System)

#### 1. Notification List View

```typescript
// GET /api/notifications/batches/?is_read=false
{
  results: [
    {
      id: 123,
      subscription: {
        id: 456,
        alias: "Organization X + Keywords",
        organization_name: "Ministry of Health"
      },
      match_count: 50,
      aggregate_stats: {
        total_amount: 1500000.00,
        avg_amount: 30000.00,
        decision_types: {"Α.1": 30, "Β.2": 20}
      },
      check_window_start: "2026-03-10T00:00:00Z",
      check_window_end: "2026-03-11T18:00:00Z",
      is_read: false,
      created_at: "2026-03-11T18:00:00Z"
    }
  ]
}
```

**Display:**
```
🔔 50 new decisions from "Ministry of Health + Keywords"
   Total value: €1,500,000 • Avg: €30,000
   Decision types: Α.1 (30), Β.2 (20)
   2 hours ago
   [View Details] [Mark Read] [Dismiss]
```

#### 2. Notification Details View (Expandable)

```typescript
// GET /api/notifications/batches/123/decisions/?page=1&page_size=20
{
  count: 50,
  next: "...?page=2",
  results: [
    {
      id: 789,
      decision: {
        ada: "ΩΨ9Ξ46ΨΖ3Υ-ΓΡΛ",
        subject: "Προμήθεια ιατρικού εξοπλισμού",
        organization_label: "Ministry of Health",
        decision_type_label: "Σύμβαση",
        amount: 45000.00,
        publish_timestamp: "2026-03-11T10:00:00Z"
      },
      match_reason: "keyword_match",
      match_details: {
        matched_keywords: ["εξοπλισμός", "προμήθεια"]
      },
      is_viewed: false
    },
    // ... 19 more decisions
  ]
}
```

**Display:**
```
📄 50 matching decisions

[Search/Filter within batch]

1. ΩΨ9Ξ46ΨΖ3Υ-ΓΡΛ
   Προμήθεια ιατρικού εξοπλισμού
   €45,000 • Σύμβαση • 8 hours ago
   Matched: εξοπλισμός, προμήθεια
   [View Decision]

2. [Next decision...]
...

[Load More] [1 of 3 pages]
```

#### 3. Mark as Read

```typescript
// POST /api/notifications/batches/123/mark-read/
// Marks the entire batch as read
// User doesn't need to mark each decision individually
```

---

## Decision Matrix - What Needs To Happen

### Option 1: Full Migration to Batch System (RECOMMENDED)

**Changes needed:**

1. **Update default behavior:**
   ```python
   def check_single_subscription(subscription_id, lookback_days=30, use_batch=True):  # ← Change default
   ```

2. **Update scheduled task:**
   ```python
   def check_subscriptions_for_new_decisions():
       # Use batches instead of individual notifications
       batch_result = create_batch_for_matches(...)
   ```

3. **Update all tests** to expect NotificationBatch

4. **Deprecate old API:**
   - Keep `/api/notifications/` for backward compatibility (read-only)
   - Document `/api/notifications/batches/` as primary API
   - Frontend uses batch API exclusively

5. **Data migration:**
   - Migrate existing Notification objects to NotificationBatch format
   - Or keep old notifications and stop creating new ones

**Pros:**
- ✓ Solves spam problem
- ✓ Better UX (grouped notifications)
- ✓ Cleaner architecture
- ✓ Scalable for high-volume subscriptions

**Cons:**
- ✗ Need to update ~70 tests
- ✗ Need frontend changes
- ✗ Need data migration plan

### Option 2: Hybrid System (CURRENT - NOT RECOMMENDED)

Keep both systems, let frontend choose:
- Manual checks → Batches
- Scheduled checks → Individual
- Frontend supports both APIs

**Pros:**
- ✓ No test changes needed
- ✓ Gradual migration possible

**Cons:**
- ✗ Complex to maintain
- ✗ Confusing for developers
- ✗ Still creates spam on scheduled checks
- ✗ Frontend complexity (two notification types)

### Option 3: Revert to Individual Only (NOT RECOMMENDED)

Remove NotificationBatch, keep only individual Notifications

**Pros:**
- ✓ Tests already pass

**Cons:**
- ✗ Spam problem remains
- ✗ Loses batching work already done
- ✗ Poor UX for users with active subscriptions

---

## Recommended Action Plan

### Phase 1: Code Alignment (Immediate)

1. ✅ **DONE:** Fixed `bulk_create` counting bug
2. ⏳ **TODO:** Change `use_batch` default to `True` in `check_single_subscription`
3. ⏳ **TODO:** Update `check_subscriptions_for_new_decisions` to use batches
4. ⏳ **TODO:** Document batch API as primary in API docs

### Phase 2: Test Migration (Sprint 1)

1. Update test factories to create batches by default
2. Update ~70 integration tests to use batch API
3. Keep a few tests for individual notifications (backward compatibility)
4. Add integration tests for batch → individual decision flow

### Phase 3: Frontend Integration (Sprint 2)

1. Frontend implements batch notification list
2. Frontend implements expandable decision details
3. Frontend uses `/api/notifications/batches/` exclusively
4. Add telemetry to ensure old API is not used

### Phase 4: Data Migration (Sprint 3)

1. Script to convert existing Notifications to NotificationBatch format
2. Soft-delete old individual Notification table (keep for rollback)
3. Monitor for issues
4. Hard delete after 30 days if no issues

### Phase 5: Cleanup (Sprint 4)

1. Remove `use_batch` parameter (always batch)
2. Deprecate `/api/notifications/` endpoints
3. Remove old Notification model
4. Archive legacy tests

---

## Current File Locations

### Models
- Individual: `/code/notifications/models/notification.py`
- Batch: `/code/notifications/models/notification_batch.py`
- Exports: `/code/notifications/models/__init__.py`

### Tasks
- Main logic: `/code/notifications/tasks/notification_tasks.py`
- Exports: `/code/notifications/tasks/__init__.py`

### API Views
- Individual: Search for "notification" views in `/code/notifications/views/`
- Batch: Search for "batch" views in `/code/notifications/views/`

### Serializers
- Check `/code/notifications/serializers/`

### Tests
- Integration: `/code/notifications/tests/integration/`
- Unit: `/code/notifications/tests/unit/`

---

## Questions for Product/Architecture Decision

1. **Should we fully migrate to batch system?** (Recommended: YES)

2. **Timeline for frontend changes?** (Needed to know migration urgency)

3. **Existing user data?** (Convert old notifications to batches? Keep separate?)

4. **Rollback plan?** (If users hate batched notifications, how to revert?)

5. **Analytics impact?** (Are we tracking notification metrics that depend on individual counts?)

---

## Contact

For questions about this architecture:
- Backend: See `/code/notifications/` codebase
- Tests: See `/code/notifications/tests/`
- API Docs: Check OpenAPI/Swagger docs
- This document: `/code/docs/notifications/notification_system_architecture.md`

**Last Updated:** March 11, 2026
