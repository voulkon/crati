# Notification Subscription Frontend Integration Guide

## Overview

This guide explains how to build a frontend UI for the notification subscription system. The system allows users to subscribe to government decisions based on various criteria and receive notifications when matching decisions are published.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Metadata Endpoints](#metadata-endpoints)
3. [Search Endpoints](#search-endpoints)
4. [Subscription CRUD](#subscription-crud)
5. [Notification Management](#notification-management)
6. [Complete Flow Examples](#complete-flow-examples)

---

## Getting Started

### Core Concepts

The notification system supports **6 subscription types**:

1. **Organization** - Watch all decisions from a specific organization
2. **Entity (AFM)** - Watch decisions involving a specific company/person
3. **Relationship** - Watch decisions involving a specific org + entity pair
4. **Person** - Watch companies where a specific person is associated
5. **Signer** - Watch decisions signed by a specific person
6. **Filter Only** - Watch decisions matching criteria (no specific target)

Each subscription type can be combined with **filters**:
- `keywords` - List of keywords (case-insensitive, OR logic)
- `amount_min` / `amount_max` - Amount range filters
- `decision_types` - List of decision type UIDs

---

## Metadata Endpoints

### 1. Get Subscription System Metadata

**Endpoint:** `GET /api/notifications-meta/metadata/`

**Purpose:** Get complete information about available subscription types, filter parameters, and validation rules.

**Response:**
```json
{
  "subscription_types": [
    {
      "type": "organization",
      "label": "Organization",
      "description": "Watch all decisions from a specific organization",
      "icon": "building",
      "required_fields": ["organization_uid"],
      "optional_filters": ["keywords", "amount_min", "amount_max", "decision_types"],
      "example": {
        "organization_uid": "99221718",
        "keywords": ["contract"],
        "check_frequency": "daily"
      }
    }
  ],
  "filter_parameters": {
    "keywords": {
      "type": "array",
      "item_type": "string",
      "description": "List of keywords to match...",
      "validation": {
        "min_items": 1,
        "max_items": 20
      },
      "example": ["procurement", "contract"]
    }
  },
  "check_frequency_options": [
    {"value": "daily", "label": "Daily"},
    {"value": "weekly", "label": "Weekly"},
    {"value": "manual", "label": "Manual Only"}
  ],
  "endpoints": {
    "search_organizations": "/api/search/entities-fast/?q={query}&types=organization",
    "decision_types": "/api/notifications-meta/metadata/decision-types/",
    "create_subscription": "/api/notifications/subscriptions/"
  }
}
```

**Use Cases:**
- Build dynamic subscription creation UI
- Show available options in dropdowns/selects
- Display field descriptions and validation rules
- Generate form validation logic

---

### 2. Get Available Decision Types

**Endpoint:** `GET /api/notifications-meta/metadata/decision-types/`

**Query Parameters:**
- `search` (optional) - Filter by label text
- `allowed_only` (optional, default: true) - Only return types usable in decisions
- `limit` (optional, default: 100, max: 500) - Results limit

**Response:**
```json
{
  "count": 150,
  "total_count": 245,
  "decision_types": [
    {
      "uid": "Β.1.1",
      "label": "Προμήθειες - Υπηρεσίες",
      "allowed_in_decisions": true,
      "has_children": false,
      "parent_uid": null
    }
  ]
}
```

**Use Cases:**
- Populate decision type dropdown in subscription form
- Show searchable/filterable type picker
- Display hierarchical type structure

---

### 3. Get Popular Decision Types

**Endpoint:** `GET /api/notifications-meta/metadata/popular-decision-types/`

**Query Parameters:**
- `limit` (optional, default: 20) - Number of top types

**Response:**
```json
{
  "popular_types": [
    {
      "uid": "Β.1.1",
      "label": "Προμήθειες - Υπηρεσίες",
      "decision_count": 15420,
      "percentage": 12.5
    }
  ],
  "total_decisions": 123456
}
```

**Use Cases:**
- Show frequently used types first in dropdowns
- Display "popular choices" section in UI
- Provide usage statistics to users

---

## Search Endpoints

### Fast Entity Search

**Endpoint:** `GET /api/search/entities-fast/`

**Query Parameters:**
- `q` (required) - Search query
- `types` (optional) - Comma-separated: `organization,signer,unit,company,company_person`
- `limit` (optional, default: 5) - Results per type

**Response:**
```json
{
  "query": "ΔΗΜΟΣ",
  "results": {
    "organizations": [
      {
        "id": "99221718",
        "text": "ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ",
        "type": "organization",
        "title": "<mark>ΔΗΜΟΣ</mark> ΑΘΗΝΑΙΩΝ",
        "subtitle": "Οργανισμός Τοπικής Αυτοδιοίκησης...",
        "details": {
          "vat_number": "090025537",
          "category": "Δήμος"
        }
      }
    ],
    "signers": [...],
    "companies": [...]
  },
  "total_count": 23
}
```

**Use Cases:**
- Real-time search-as-you-type
- Autocomplete for organization/entity selection
- Type selector with previews

---

## Subscription CRUD

### 1. Create Subscription

**Endpoint:** `POST /api/notifications/subscriptions/`

**Request Body Examples:**

**Organization subscription:**
```json
{
  "organization_uid": "99221718",
  "keywords": ["procurement", "contract"],
  "amount_min": "10000.00",
  "check_frequency": "daily"
}
```

**Entity subscription:**
```json
{
  "entity_afm": "123456789",
  "keywords": ["tender"],
  "decision_types": ["Β.1.1", "Β.1.2"]
}
```

**Relationship subscription:**
```json
{
  "relationship_org_uid": "99221718",
  "relationship_entity_afm": "123456789",
  "amount_min": "5000.00"
}
```

**Signer subscription:**
```json
{
  "signer_name": "Γεώργιος Παπαδόπουλος",
  "organization_uid": "99221718",
  "keywords": ["appointment"]
}
```

**Filter-only subscription:**
```json
{
  "keywords": ["urgent", "emergency"],
  "amount_min": "50000.00",
  "decision_types": ["Β.1.1"]
}
```

**Response:** Full subscription object with nested details

**Note:** Backend automatically triggers immediate check for matching decisions after creation.

---

### 2. List User's Subscriptions

**Endpoint:** `GET /api/notifications/subscriptions/`

**Response:**
```json
[
  {
    "id": 1,
    "subscription_type": "organization",
    "organization_label": "ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ",
    "entity_name": null,
    "person_name": null,
    "signer_name": null,
    "is_active": true,
    "check_frequency": "daily",
    "created_at": "2026-03-01T10:00:00Z"
  }
]
```

---

### 3. Get Subscription Details

**Endpoint:** `GET /api/notifications/subscriptions/{id}/`

**Response:** Full subscription with all filters and nested details

---

### 4. Update Subscription

**Endpoint:** `PATCH /api/notifications/subscriptions/{id}/`

**Request Body (partial updates allowed):**
```json
{
  "keywords": ["updated", "keywords"],
  "is_active": false,
  "check_frequency": "weekly"
}
```

**Note:** You cannot change the subscription type (organization/entity/etc). Delete and create new instead.

---

### 5. Delete Subscription

**Endpoint:** `DELETE /api/notifications/subscriptions/{id}/`

**Response:** `204 No Content`

---

### 6. Check if User is Subscribed

**Organization:**
```
GET /api/notifications/subscriptions/check-organization/{org_uid}/
```

**Entity:**
```
GET /api/notifications/subscriptions/check-entity/{afm}/
```

**Relationship:**
```
GET /api/notifications/subscriptions/check-relationship/?org_uid={uid}&entity_afm={afm}
```

**Signer:**
```
GET /api/notifications/subscriptions/check-signer/{signer_name}/
```

**Response:**
```json
{
  "subscribed": true,
  "subscription": {
    "id": 1,
    "keywords": ["contract"],
    ...
  }
}
```

**Use Cases:**
- Show "Subscribe" vs "Unsubscribe" button
- Display existing subscription settings
- Prevent duplicate subscriptions

---

### 7. Manually Trigger Subscription Check

**Endpoint:** `POST /api/notifications/subscriptions/{id}/check-now/`

**Query Parameters:**
- `lookback_days` (optional, default: 30) - How far back to check

**Response:**
```json
{
  "status": "check started",
  "task_id": "abc-123-def",
  "subscription_id": 1,
  "lookback_days": 30
}
```

---

## Notification Management

### 1. List Notifications

**Endpoint:** `GET /api/notifications/`

**Query Parameters:**
- `is_read` (optional) - Filter by read status (true/false)
- `is_dismissed` (optional) - Filter by dismissed status
- `subscription_type` (optional) - Filter by subscription type

**Response:**
```json
[
  {
    "id": 1,
    "subscription_type": "organization",
    "decision_ada": "ΩΛΜΘ465ΧΘΞ-ΨΣΘ",
    "decision_subject": "Απόφαση ανάθεσης σύμβασης",
    "match_reason": "Matched keywords: contract",
    "is_read": false,
    "is_dismissed": false,
    "created_at": "2026-03-07T09:00:00Z"
  }
]
```

---

### 2. Get Notification Details

**Endpoint:** `GET /api/notifications/{id}/`

**Response:** Full notification with complete decision and subscription details

---

### 3. Mark as Read

**Endpoint:** `POST /api/notifications/{id}/mark-read/`

---

### 4. Mark as Unread

**Endpoint:** `POST /api/notifications/{id}/mark-unread/`

---

### 5. Dismiss Notification

**Endpoint:** `POST /api/notifications/{id}/dismiss/`

---

### 6. Mark All as Read

**Endpoint:** `POST /api/notifications/mark-all-read/`

**Response:**
```json
{
  "marked_read": 15
}
```

---

### 7. Get Unread Count

**Endpoint:** `GET /api/notifications/unread-count/`

**Response:**
```json
{
  "unread_count": 5
}
```

**Use Case:** Display notification badge counter

---

## Complete Flow Examples

### Example 1: Organization Subscription with Keyword Filter

```javascript
// 1. Get metadata to build UI
const metadata = await fetch('/api/notifications-meta/metadata/').then(r => r.json());

// 2. User searches for organization
const searchResults = await fetch(
  '/api/search/entities-fast/?q=ΔΗΜΟΣ&types=organization&limit=5'
).then(r => r.json());

// Display results, user selects: id="99221718"

// 3. Check if already subscribed
const checkResult = await fetch(
  '/api/notifications/subscriptions/check-organization/99221718/'
).then(r => r.json());

if (checkResult.subscribed) {
  // Show existing subscription
  console.log('Already subscribed:', checkResult.subscription);
} else {
  // 4. Create new subscription
  const subscription = await fetch('/api/notifications/subscriptions/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      organization_uid: '99221718',
      keywords: ['contract', 'procurement'],
      amount_min: '10000.00',
      check_frequency: 'daily'
    })
  }).then(r => r.json());
  
  console.log('Subscription created:', subscription);
}
```

---

### Example 2: Entity Subscription with Decision Type Filter

```javascript
// 1. Get decision types
const decisionTypes = await fetch(
  '/api/notifications-meta/metadata/decision-types/?search=προμήθ&limit=20'
).then(r => r.json());

// Display in dropdown, user selects: uid="Β.1.1"

// 2. Search for company/entity
const companies = await fetch(
  '/api/search/entities-fast/?q=ACME&types=company&limit=10'
).then(r => r.json());

// User selects company with AFM: "123456789"

// 3. Create subscription
const subscription = await fetch('/api/notifications/subscriptions/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    entity_afm: '123456789',
    decision_types: ['Β.1.1', 'Β.1.2'],
    check_frequency: 'daily'
  })
}).then(r => r.json());
```

---

### Example 3: Filter-Only Subscription

```javascript
// No target selection needed - just filters
const subscription = await fetch('/api/notifications/subscriptions/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    keywords: ['urgent', 'emergency', 'critical'],
    amount_min: '100000.00',
    decision_types: ['Β.1.1'],
    check_frequency: 'daily'
  })
}).then(r => r.json());
```

---

### Example 4: Display Notifications

```javascript
// Get unread count for badge
const { unread_count } = await fetch('/api/notifications/unread-count/')
  .then(r => r.json());

// Display badge: <span class="badge">{unread_count}</span>

// Get notification list
const notifications = await fetch('/api/notifications/?is_read=false')
  .then(r => r.json());

// Display notifications
notifications.forEach(notif => {
  console.log({
    id: notif.id,
    type: notif.subscription_type,
    decision: notif.decision_subject,
    reason: notif.match_reason
  });
});

// User clicks notification
await fetch(`/api/notifications/${notif.id}/mark-read/`, { method: 'POST' });

// Navigate to decision details
window.location.href = `/decisions/${notif.decision_ada}`;
```

---

## UI Component Suggestions

### 1. Subscription Creation Wizard

**Step 1: Choose Type**
- Radio buttons or cards for 6 subscription types
- Show icon, title, description for each

**Step 2: Select Target (if applicable)**
- Autocomplete search input
- Show results with details (VAT, category, etc.)
- Skip for filter-only subscriptions

**Step 3: Add Filters (optional)**
- Keyword input (tags/chips UI)
- Amount range sliders or inputs
- Decision type multi-select dropdown
- Check frequency radio buttons

**Step 4: Review & Create**
- Summary card showing all selected options
- Validation errors display
- "Create Subscription" button

---

### 2. Subscription Management Dashboard

**List View:**
- Card or table layout
- Show: type, target name, active status, created date
- Actions: Edit, Deactivate, Delete, Check Now
- Filter: by type, active status

**Detail View:**
- Full subscription info
- Edit filters inline
- Notification history for this subscription
- Activity log (last checked, notifications created)

---

### 3. Notification Center

**Layout:**
- Bell icon with unread count badge
- Dropdown or sidebar panel
- List of recent notifications
- "Mark all as read" button
- Filter: Unread only, By subscription type
- Click notification → navigate to decision + mark as read

---

## Validation & Error Handling

### Common Validation Errors

```json
{
  "non_field_errors": [
    "At least one target (organization, entity, relationship, person, or signer) OR at least one filter (keywords, amounts, decision types) must be set."
  ]
}
```

```json
{
  "amount_min": ["Ensure this value is less than or equal to amount_max."]
}
```

```json
{
  "organization_uid": ["Organization with uid 'INVALID' does not exist."]
}
```

### Handle Errors in UI

```javascript
try {
  const subscription = await createSubscription(data);
  showSuccess('Subscription created!');
} catch (error) {
  const errors = await error.json();
  if (errors.non_field_errors) {
    showError(errors.non_field_errors[0]);
  } else {
    // Field-specific errors
    Object.entries(errors).forEach(([field, messages]) => {
      showFieldError(field, messages[0]);
    });
  }
}
```

---

## Testing & Development

### Sample Data

Use the factories in `/code/conftest.py`:
- `OrganizationFactory`
- `DecisionFactory`
- `SignerFactory`
- `NotificationSubscriptionFactory`

### API Testing

```bash
# Get metadata
curl http://localhost:8000/api/notifications-meta/metadata/

# Get decision types
curl http://localhost:8000/api/notifications-meta/metadata/decision-types/?search=προμήθ

# Create subscription (requires authentication)
curl -X POST http://localhost:8000/api/notifications/subscriptions/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "organization_uid": "99221718",
    "keywords": ["test"],
    "check_frequency": "daily"
  }'
```

---

## Performance Considerations

1. **Autocomplete Search**
   - Use debouncing (300-500ms) for search input
   - Show "Searching..." indicator
   - Cache recent searches

2. **Notification List**
   - Implement pagination
   - Use virtual scrolling for large lists
   - Load unread count separately (lightweight endpoint)

3. **Subscription Management**
   - Cache subscription list
   - Invalidate cache on create/update/delete
   - Use optimistic UI updates

---

## Security Considerations

1. **Authentication Required**
   - All endpoints require authentication
   - Users can only see/manage their own subscriptions/notifications

2. **Input Validation**
   - Validate on frontend AND backend
   - Sanitize keyword inputs
   - Limit array sizes (keywords, decision_types)

3. **Rate Limiting**
   - "Check Now" action may have rate limits
   - Search endpoints may be throttled

---

## Additional Resources

- **Comprehensive Test Suite:** `/code/notifications/tests/integration/test_subscription_types_comprehensive.py`
- **API Tests:** `/code/notifications/tests/integration/test_notification_flow.py`
- **Model Definition:** `/code/notifications/models/notification_subscription.py`
- **Backend Logic:** `/code/notifications/tasks.py`

---

## Support

For questions or issues, refer to:
- API documentation: `/api/docs/` (Swagger UI)
- Test cases for usage examples
- Backend team for complex subscription logic
