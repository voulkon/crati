# Notification System - Frontend UI Specification

## Overview

This document provides comprehensive UI/UX specifications for implementing the notification subscription system in the frontend. It covers component structure, context-aware behavior, user interactions, and edge cases.

**Related Documents:**
- [FRONTEND_INTEGRATION_GUIDE.md](./FRONTEND_INTEGRATION_GUIDE.md) - API endpoints and data structures

---

## Table of Contents

1. [Component Architecture](#component-architecture)
2. [Context-Aware Bell Button](#context-aware-bell-button)
3. [Notification Center Sidebar](#notification-center-sidebar)
4. [Subscription Management](#subscription-management)
5. [User Flows](#user-flows)
6. [States & Edge Cases](#states--edge-cases)
7. [Real-time Updates](#real-time-updates)

---

## Component Architecture

### Component Hierarchy

```
NotificationButton (in TopControls, similar to BookmarkButton)
├─ BellIcon (with unread count badge)
└─ ChevronIcon (toggle sidebar)

NotificationSidebar (similar to LibrarySidebar)
├─ Tabs
│  ├─ Notifications Tab
│  └─ Subscriptions Tab
├─ NotificationList (when Notifications tab active)
│  └─ NotificationItem[]
│     ├─ DecisionPreview
│     ├─ MatchReason
│     └─ Actions (mark read/unread, dismiss, navigate)
└─ SubscriptionList (when Subscriptions tab active)
   └─ SubscriptionItem[]
      ├─ SubscriptionDetails
      ├─ EditButton
      ├─ ToggleActive
      ├─ CheckNowButton
      └─ DeleteButton

CreateSubscriptionModal (launched from various contexts)
├─ Step 1: Type Selection (conditional - may be skipped if context-aware)
├─ Step 2: Target Selection (conditional - may be pre-filled)
├─ Step 3: Filters (optional)
└─ Step 4: Name & Review
```

---

## Context-Aware Bell Button

### Core Concept

The bell button behavior **changes based on the current page context**. This is more sophisticated than the bookmark button.

### Button States

**Visual States:**
- **Default:** Bell icon + chevron (like bookmark button)
- **Active:** Bell icon changes when subscription exists for current context
- **Badge:** Shows unread notification count
- **Disabled:** Grayed out on pages where subscriptions don't apply

### Context Mapping

| Page Route | Entity Type | Bell Button Behavior | Subscription Type |
|------------|-------------|----------------------|-------------------|
| `/entity/organization/:uid` | Organization | **Active** - Create/manage org subscription | `organization` |
| `/entity/signer/:name` | Signer | **Active** - Create/manage signer subscription | `signer` |
| `/entity/unit/:id` | Unit | **Disabled** - Units not supported | N/A |
| `/entity/afm/:afm` | AFM Entity | **Active** - Create/manage entity subscription | `entity` |
| `/decision/:ada` | Decision | **Disabled** - Single decisions not supported | N/A |
| `/relationship/entity/:afm/org/:uid` | Relationship | **Active** - Create/manage relationship subscription | `relationship` |
| `/` (Home) | N/A | **Passive** - Only opens notification center | N/A |
| `/search` | N/A | **Passive** - Only opens notification center | N/A |
| `/library` | N/A | **Passive** - Only opens notification center | N/A |

### Implementation Logic

```javascript
// Pseudo-code for context detection
function getNotificationContext() {
  const location = useLocation();
  const params = useParams();
  
  // Organization page
  if (location.pathname.startsWith('/entity/organization/')) {
    return {
      type: 'organization',
      target: { organization_uid: params.entityId },
      canSubscribe: true,
      label: 'Subscribe to this organization'
    };
  }
  
  // Signer page
  if (location.pathname.startsWith('/entity/signer/')) {
    return {
      type: 'signer',
      target: { signer_name: decodeURIComponent(params.entityId) },
      canSubscribe: true,
      label: 'Subscribe to this signer'
    };
  }
  
  // AFM Entity page
  if (location.pathname.startsWith('/entity/afm/')) {
    return {
      type: 'entity',
      target: { entity_afm: params.afm },
      canSubscribe: true,
      label: 'Subscribe to this entity'
    };
  }
  
  // Relationship page
  if (location.pathname.startsWith('/relationship/')) {
    return {
      type: 'relationship',
      target: {
        relationship_org_uid: params.orgUid,
        relationship_entity_afm: params.afm
      },
      canSubscribe: true,
      label: 'Subscribe to this relationship'
    };
  }
  
  // Decision page - not applicable
  if (location.pathname.startsWith('/decision/')) {
    return {
      type: null,
      canSubscribe: false,
      disabledReason: 'Notifications for individual decisions are not supported. Subscribe to the organization or entities instead.'
    };
  }
  
  // Default - passive mode (just open notification center)
  return {
    type: null,
    canSubscribe: false,
    passiveMode: true
  };
}
```

### Button Interaction Behavior

**Split Button Design (like BookmarkButton):**

```
┌──────────────────────────┐
│  🔔3  │  ▾               │
└──────────────────────────┘
 ↑        ↑
 Bell     Chevron
 Half     Half
```

**Bell Half (Left):**
1. **On subscribable pages:**
   - **If NOT subscribed:** Click → Open subscription modal (pre-filled with context)
   - **If subscribed:** Click → Show toast "Already subscribed" + highlight subscription in sidebar
   - **Badge count:** Always shows total unread count (not context-specific)

2. **On passive pages:**
   - Click → Open notification center (same as chevron)

3. **On disabled pages (e.g., decision detail):**
   - Grayed out
   - Hover tooltip: "Notifications for individual decisions are not supported."

**Chevron Half (Right):**
- Always opens/closes the notification sidebar
- Works on all pages (never disabled)

### Visual Feedback

**Subscription Status Indicator:**
```javascript
// When user is on an organization page
const isSubscribed = checkSubscription(context);

// Bell icon appearance:
if (isSubscribed) {
  // Filled bell, primary color
  icon = '🔔'; // or <BellIconFilled />
  className = 'notification-btn-subscribed';
} else {
  // Outline bell, neutral color
  icon = '🔕'; // or <BellIconOutline />
  className = 'notification-btn-not-subscribed';
}
```

---

## Notification Center Sidebar

### Layout

Similar to LibrarySidebar, but with two tabs.

```
┌─────────────────────────────────────────┐
│  🔔 Notifications               ✕       │ ← Header
├─────────────────────────────────────────┤
│  [ Notifications ] [ Subscriptions ]     │ ← Tabs
├─────────────────────────────────────────┤
│                                          │
│  TAB CONTENT HERE                        │
│  (see sections below)                    │
│                                          │
│                                          │
└─────────────────────────────────────────┘
```

### Tab 1: Notifications

**Header Actions:**
- Search/filter input
- "Mark all as read" button
- View filter dropdown (All / Unread Only / By Type)

**Notification Item Card:**
```
┌───────────────────────────────────────┐
│ ⭐ [Organization Name]                │ ← Subscription indicator + target
│ New decision: [Decision Subject]       │ ← Decision title
│ ADA: ΩΑΒΓ123456                       │ ← ADA
│ Amount: €50,000                        │ ← Key info
│ Matched: "procurement" keyword         │ ← Match reason
│                                        │
│ [👁️ View] [✓ Mark Read] [✖ Dismiss]   │ ← Actions
│ 2 hours ago                            │ ← Timestamp
└───────────────────────────────────────┘
```

**Notification States:**
- **Unread:** Bold text, colored border
- **Read:** Normal text, muted
- **Dismissed:** Hidden (or show in "Show dismissed" option)

**Actions:**
- **View:** Navigate to decision + mark as read automatically
- **Mark Read/Unread:** Toggle read status
- **Dismiss:** Remove from list (can be recovered via API if needed)

**Empty State:**
```
┌───────────────────────────────────────┐
│                                        │
│            🔕                          │
│      No new notifications              │
│                                        │
│  You'll be notified when decisions     │
│  matching your subscriptions appear.   │
│                                        │
│         [Create Subscription]          │
│                                        │
└───────────────────────────────────────┘
```

### Tab 2: Subscriptions

**Header Actions:**
- Search/filter input
- "+ New Subscription" button
- Filter: Active / Inactive / All
- Sort: Recent / Alphabetical / Type

**Subscription Item Card:**
```
┌───────────────────────────────────────┐
│ 🏢 Organization Subscription           │ ← Type icon + label
│ "My Custom Name for This"              │ ← User's alias
│                                        │
│ Target: [Organization Name]            │ ← Target details
│ Filters:                               │ ← Applied filters
│   • Keywords: procurement, contract    │
│   • Amount: €10,000+                   │
│   • Frequency: Daily                   │
│                                        │
│ ⚡ Active  📊 5 notifications           │ ← Status + count
│ Last checked: 2 hours ago              │ ← Last check time
│                                        │
│ [✏️ Edit] [🔄 Check Now] [⏸️ Pause] [🗑️ Delete] │ ← Actions
└───────────────────────────────────────┘
```

**Type Icons:**
- 🏢 Organization
- 🏭 Entity (AFM)
- 🔗 Relationship
- 👤 Person
- ✍️ Signer
- 🔍 Filter-only

**Actions:**
- **Edit:** Open edit modal (same as create, but pre-filled)
- **Check Now:** Trigger immediate check, show spinner, toast on completion
- **Pause/Resume:** Toggle `is_active` status
- **Delete:** Confirm dialog → Delete subscription

**Empty State:**
```
┌───────────────────────────────────────┐
│                                        │
│            📭                          │
│      No subscriptions yet              │
│                                        │
│  Create your first subscription to     │
│  receive notifications about decisions │
│  that matter to you.                   │
│                                        │
│         [Create Subscription]          │
│                                        │
└───────────────────────────────────────┘
```

---

## Subscription Management

### Create/Edit Subscription Modal

**Modal Structure:**

```
┌─────────────────────────────────────────────────────┐
│  Create Subscription                            ✕   │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Step indicators: ○ → ○ → ○ → ○                    │
│                   Type  Target  Filters  Review     │
│                                                      │
│  [STEP CONTENT HERE]                                │
│                                                      │
├─────────────────────────────────────────────────────┤
│              [< Back]         [Next >]              │
└─────────────────────────────────────────────────────┘
```

### Step 1: Subscription Type Selection

**When to Show:**
- Always show when launched from "+ New Subscription" button
- **Skip** when context-aware (launched from bell button on specific page)

**UI Layout:**
```
Choose what you want to watch:

┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   🏢         │  │   🏭         │  │   🔗         │
│ Organization │  │   Entity     │  │ Relationship │
│              │  │   (AFM)      │  │   (Org+AFM)  │
│ Watch all... │  │ Watch a...   │  │ Watch when.. │
└──────────────┘  └──────────────┘  └──────────────┘

┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   👤         │  │   ✍️         │  │   🔍         │
│   Person     │  │   Signer     │  │  Filter Only │
│              │  │              │  │              │
│ Companies... │  │ Decisions... │  │ Custom...    │
└──────────────┘  └──────────────┘  └──────────────┘
```

**Card Details:**
Each card shows:
- Icon
- Type name
- Short description
- Example use case

### Step 2: Target Selection

**When to Show:**
- For types: organization, entity, relationship, person, signer
- **Skip** for "filter-only" type
- **Pre-fill** when context-aware (from bell button)

**UI for Organization/Entity/Signer:**
```
Select the organization to watch:

┌────────────────────────────────────────────────┐
│ 🔍  Search for organization...                │
└────────────────────────────────────────────────┘

Suggestions:     [or] Recent:

┌─────────────────────────────────┐
│ 🏢 ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ               │
│    UID: 99221718                 │
│    Category: Δήμος               │
└─────────────────────────────────┘
┌─────────────────────────────────┐
│ 🏢 ΥΠΟΥΡΓΕΙΟ ΟΙΚΟΝΟΜΙΚΩΝ        │
│    UID: 99001234                 │
│    Category: Υπουργείο           │
└─────────────────────────────────┘
```

**Search Behavior:**
- Debounced autocomplete (300ms)
- Uses `/api/search/entities-fast/`
- Shows top 5 results
- Display: Name, UID/AFM, Category/Type
- Click to select

**If Context-Aware:**
```
┌─────────────────────────────────┐
│ ✓ Selected Organization:         │
│                                  │
│ 🏢 ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ               │
│    UID: 99221718                 │
│    Category: Δήμος               │
│                                  │
│    [Change Selection]            │
└─────────────────────────────────┘
```

**UI for Relationship:**
```
Select organization and entity:

Organization:
┌────────────────────────────────────────────────┐
│ 🔍  Search for organization...                │
└────────────────────────────────────────────────┘
[Selected: ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ]

Entity (AFM):
┌────────────────────────────────────────────────┐
│ 🔍  Search for company/person...               │
└────────────────────────────────────────────────┘
[Selected: ACME Corp - AFM: 123456789]
```

### Step 3: Filters (Optional)

**Always shown for all types.** Filters are optional but can narrow results.

```
Add filters to narrow your notifications (optional):

┌────────────────────────────────────────────────┐
│ Keywords (match any):                          │
│                                                 │
│ [procurement] [contract] [tender]  + Add       │
│                                                 │
└────────────────────────────────────────────────┘
Enter keyword and press Enter or click +

┌────────────────────────────────────────────────┐
│ Amount Range:                                  │
│                                                 │
│ Min: [€ 10,000    ] Max: [€ 100,000    ]      │
│                                                 │
│ ├────────●──────────────────●──────────┤       │
│ €0                              €1,000,000     │
└────────────────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│ Decision Types:                                │
│                                                 │
│ [▼ Select decision types...]                   │
│                                                 │
│ Selected: Β.1.1 (Προμήθειες), Β.2.4 (Διαγω...) │
└────────────────────────────────────────────────┘
Multi-select dropdown with search

┌────────────────────────────────────────────────┐
│ Check Frequency:                               │
│                                                 │
│ ○ Daily    ● Weekly    ○ Manual Only          │
└────────────────────────────────────────────────┘
```

**Decision Type Selector:**
- Dropdown with search
- Multi-select checkboxes
- Show popular types first (from `/api/notifications-meta/metadata/popular-decision-types/`)
- Search as you type
- Display hierarchy if applicable

### Step 4: Name & Review

```
Name your subscription:

┌────────────────────────────────────────────────┐
│ Custom Name (optional):                        │
│                                                 │
│ [My ACME Company Procurement Alerts     ]      │
│                                                 │
└────────────────────────────────────────────────┘
Leave blank to use default name

─────────────────────────────────────────────────

Review your subscription:

┌────────────────────────────────────────────────┐
│ Type:         🏢 Organization                   │
│ Target:       ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ (99221718)        │
│ Alias:        My Athens Procurement Alerts     │
│                                                 │
│ Filters:                                        │
│   • Keywords: procurement, contract            │
│   • Amount: €10,000 - €100,000                │
│   • Types: Β.1.1, Β.2.4                       │
│   • Frequency: Weekly                          │
│                                                 │
│ ☑️ Check for existing matching decisions       │
│   (last 30 days)                               │
└────────────────────────────────────────────────┘

[< Back]                        [Create Subscription]
```

**Validation:**
- At least one target OR at least one filter must be set
- If relationship: both org and entity required
- Amount min <= amount max
- All fields sanitized

### Quick Subscribe (Context-Aware)

**When bell button is clicked on subscribable page:**

**Option A: One-Click Subscribe (Minimal)**
- Check if subscribed: No → Create with defaults (no filters, daily frequency)
- Show toast: "Subscribed to [Organization Name]! ✓"
- Option in toast: "Customize" → Opens edit modal

**Option B: Quick Modal (Recommended)**
```
┌──────────────────────────────────────────┐
│  Subscribe to ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ        ✕   │
├──────────────────────────────────────────┤
│                                           │
│  You'll receive notifications when       │
│  this organization publishes decisions.  │
│                                           │
│  Custom name (optional):                 │
│  [Athens City Hall Watch          ]      │
│                                           │
│  ☐ Add filters (keywords, amounts...)    │
│                                           │
│  Check frequency: ● Daily  ○ Weekly      │
│                                           │
├──────────────────────────────────────────┤
│           [Cancel]  [Subscribe]          │
└──────────────────────────────────────────┘
```

If "Add filters" is checked → Expand to show filter UI (Step 3)

---

## User Flows

### Flow 1: Context-Aware Subscribe from Organization Page

1. User is viewing organization detail page (`/entity/organization/99221718`)
2. User sees bell button (outline, not subscribed)
3. User clicks **bell half** → Quick subscribe modal opens
4. Modal shows: "Subscribe to ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ" (pre-filled)
5. User optionally adds custom name
6. User clicks "Subscribe" button
7. API call: `POST /api/notifications/subscriptions/` with `organization_uid=99221718`
8. Backend creates subscription + triggers immediate check
9. Modal closes, toast appears: "Subscribed! ✓"
10. Bell icon changes to filled (subscribed state)
11. User opens sidebar (chevron) → Sees new subscription in list

### Flow 2: Create Filter-Only Subscription

1. User opens notification sidebar (chevron)
2. User clicks "Subscriptions" tab
3. User clicks "+ New Subscription" button
4. Modal opens → Step 1: Type Selection
5. User selects "🔍 Filter Only"
6. Modal skips to Step 3: Filters
7. User adds:
   - Keywords: "emergency", "urgent"
   - Amount min: €50,000
   - Types: Β.1.1
   - Frequency: Daily
8. Step 4: Review & Name
9. User names it "High-Value Emergency Decisions"
10. User clicks "Create Subscription"
11. API call: `POST /api/notifications/subscriptions/` with filters only
12. Subscription created, appears in list
13. Toast: "Subscription created! Checking for matches..."

### Flow 3: Receiving and Viewing Notification

1. Backend check runs (daily cron or manual trigger)
2. Matching decision found → Notification created
3. User opens app (or is already in app)
4. Bell badge updates: Shows "1" (unread count)
5. User clicks **chevron half** → Sidebar opens
6. User is on "Notifications" tab
7. Notification card shows at top (unread, bold):
   ```
   🏢 Athens City Hall Watch
   New decision: Προμήθεια Ηλεκτρονικού Εξοπλισμού
   ADA: ΩΑΒΓ123456 | €45,000
   Matched: "procurement" keyword
   [View] [Mark Read] [Dismiss]
   5 minutes ago
   ```
8. User clicks "View" button
9. Navigate to `/decision/ΩΑΒΓ123456`
10. Notification automatically marked as read
11. Badge count decreases

### Flow 4: Managing Subscription

1. User opens sidebar → "Subscriptions" tab
2. User finds subscription: "Athens City Hall Watch"
3. User clicks "✏️ Edit" button
4. Edit modal opens (same as create, pre-filled)
5. User changes:
   - Adds keyword: "tender"
   - Changes frequency: Weekly → Daily
6. User clicks "Save"
7. API call: `PATCH /api/notifications/subscriptions/{id}/`
8. Subscription updated
9. Toast: "Subscription updated! ✓"

### Flow 5: Manual Check Now

1. User in "Subscriptions" tab
2. User clicks "🔄 Check Now" button on a subscription
3. Button shows spinner
4. API call: `POST /api/notifications/subscriptions/{id}/check-now/`
5. Backend task queued
6. Toast: "Checking for new matches..."
7. After task completes (poll or websocket):
   - If matches found: "Found 3 new matches! 🎉"
   - If no matches: "No new matches found."

---

## States & Edge Cases

### Loading States

**Initial Load:**
```
┌───────────────────────────────────────┐
│            ⏳                          │
│      Loading notifications...          │
└───────────────────────────────────────┘
```

**Check Now Loading:**
```
[🔄 Check Now]  →  [⏳ Checking...]  →  [🔄 Check Now]
```

**Infinite Scroll Loading:**
```
[Notification cards...]

⏳ Loading more...

[More notification cards...]
```

### Error States

**API Error:**
```
┌───────────────────────────────────────┐
│            ⚠️                          │
│   Failed to load notifications         │
│                                        │
│   [Retry]                              │
└───────────────────────────────────────┘
```

**Validation Error (Create/Edit):**
```
❌ At least one target or filter is required.
```
Display inline near relevant field.

### Edge Cases

**1. Already Subscribed**
- User clicks bell on org page they're already subscribed to
- Show toast: "You're already subscribed to this organization."
- Option: "View Subscription" → Opens sidebar + highlights subscription

**2. Entity No Longer Exists**
- Organization/Entity deleted in backend
- Subscription still exists but shows warning:
  ```
  ⚠️ Target organization no longer exists
  [Delete Subscription]
  ```

**3. No Permissions**
- User not authenticated
- Bell button hidden or grayed out
- Tooltip: "Sign in to subscribe"

**4. Rate Limiting**
- User spams "Check Now" button
- API returns 429 Too Many Requests
- Show toast: "Please wait before checking again. (30s cooldown)"

**5. Decision Page Bell Button**
- User on `/decision/ΩΑΒΓ123456`
- Bell button is grayed out (left half)
- Hover tooltip: "Notifications for individual decisions are not supported. Subscribe to the organization or entities instead."
- Chevron still works (opens sidebar)

**6. Subscription with No Matches Yet**
- Subscription created, no notifications yet
- Show in subscription card:
  ```
  📊 0 notifications
  Last checked: Never
  [Check Now] button prominent
  ```

**7. Large Number of Notifications**
- Use virtual scrolling or pagination
- Show count: "Showing 20 of 150 notifications"
- Load more as user scrolls

**8. Conflicting Subscriptions**
- User creates org subscription + entity subscription
- Entity works for same org → Duplicate notifications possible
- Consider: Deduplicate notifications (same decision_ada + user)
- Or: Show which subscriptions matched in notification details

---

## Real-time Updates

### Polling Strategy

**Unread Count:**
- Poll `/api/notifications/unread-count/` every 30 seconds
- Update badge count
- Only when user is active (tab is visible)

**Notification List:**
- Refresh when sidebar is opened
- Auto-refresh every 60 seconds if sidebar is open
- Show "New notifications available" banner if updates detected while viewing

**Subscription Status:**
- Check current page subscription status on page load
- Update bell icon state

### WebSocket Alternative (Future Enhancement)

If WebSockets are implemented:
```javascript
// Connect to WebSocket
ws.on('notification.created', (data) => {
  // Update badge count
  // Show browser notification (if permission granted)
  // Add to notification list if sidebar is open
});

ws.on('subscription.checked', (data) => {
  // Update "last checked" timestamp
  // Show toast if manual check
});
```

### Browser Notifications (Future Enhancement)

**Request Permission:**
- After first subscription created
- Show prompt: "Get notified about new decisions?"
- If granted: Send browser notification when new notification created

**Notification Content:**
```
Title: New Decision - [Organization Name]
Body: [Decision Subject]
Icon: Bell icon
Click: Navigate to decision + mark as read
```

---

## Styling & Design Tokens

### Colors

```css
/* Bell Button */
.notification-btn {
  --bell-default: #6b7280;
  --bell-subscribed: #3b82f6;
  --bell-active: #2563eb;
  --badge-bg: #ef4444;
  --badge-text: #ffffff;
}

/* Notification Card */
.notification-card {
  --unread-border: #3b82f6;
  --read-border: #e5e7eb;
  --unread-bg: #eff6ff;
  --read-bg: #ffffff;
}

/* Subscription Card */
.subscription-card {
  --active-indicator: #10b981;
  --inactive-indicator: #6b7280;
}
```

### Animations

**Badge Pulse (when new notification):**
```css
@keyframes badge-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}
```

**Toast Slide-In:**
```css
@keyframes toast-slide-in {
  from { transform: translateY(-100%); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
```

**Check Now Spinner:**
```css
@keyframes spinner-rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
```

---

## Accessibility

### Keyboard Navigation

- Bell button: `Tab` to focus, `Enter` or `Space` to activate
- Sidebar: `Esc` to close
- Notification cards: `Tab` through actions, `Enter` to activate
- Modal: `Tab` through fields, `Esc` to cancel

### Screen Reader Support

```html
<button 
  aria-label="Notifications"
  aria-describedby="notification-count"
  aria-expanded="false"
>
  <span aria-hidden="true">🔔</span>
  <span id="notification-count" className="sr-only">
    You have 3 unread notifications
  </span>
  <span className="badge">3</span>
</button>
```

### Focus Management

- When modal opens: Focus first input field
- When sidebar opens: Focus search input
- After notification action: Return focus to notification card

---

## Performance Considerations

### Optimization Strategies

1. **Lazy Load Components:**
   - Load modal only when needed
   - Virtual scroll for large lists

2. **Debounce Search:**
   - 300ms delay for autocomplete
   - Cancel previous requests

3. **Cache API Responses:**
   - Cache decision types list (rarely changes)
   - Cache organization searches (5 min TTL)
   - Invalidate on mutations

4. **Optimistic UI:**
   - Mark as read: Update UI immediately, API in background
   - Toggle subscription: Update UI, revert on error

5. **Batch API Calls:**
   - When checking multiple subscriptions
   - When marking multiple as read

---

## Testing Checklist

### Functional Testing

- [ ] Bell button appears on correct pages
- [ ] Bell button disabled on decision pages
- [ ] Context-aware subscription pre-fills correctly
- [ ] Can create all 6 subscription types
- [ ] Filters work correctly (keywords, amount, types)
- [ ] Can edit existing subscriptions
- [ ] Can delete subscriptions
- [ ] Manual "Check Now" triggers correctly
- [ ] Notifications appear in list
- [ ] Mark read/unread works
- [ ] Dismiss works
- [ ] Navigation to decision works
- [ ] Badge count updates correctly
- [ ] Sidebar opens/closes correctly
- [ ] Tabs switch correctly

### Edge Case Testing

- [ ] Already subscribed handling
- [ ] No notifications empty state
- [ ] No subscriptions empty state
- [ ] API error handling
- [ ] Validation error display
- [ ] Rate limiting handling
- [ ] Long organization names (truncation)
- [ ] Missing entity handling
- [ ] Conflicting filters (amount min > max)

### Cross-Browser Testing

- [ ] Chrome/Edge
- [ ] Firefox
- [ ] Safari
- [ ] Mobile Safari
- [ ] Mobile Chrome

### Accessibility Testing

- [ ] Keyboard navigation
- [ ] Screen reader support
- [ ] Focus management
- [ ] Color contrast (WCAG AA)
- [ ] Reduced motion support

---

## Future Enhancements

1. **Notification Grouping**
   - Group multiple notifications from same subscription
   - "5 new decisions from Athens City Hall"

2. **Smart Suggestions**
   - Suggest subscriptions based on browsing history
   - "You've viewed this organization 5 times. Subscribe?"

3. **Notification Digest**
   - Daily/weekly email digest option
   - Summary of notifications

4. **Advanced Filters**
   - Date range filters
   - Exclude keywords
   - Complex boolean logic

5. **Subscription Templates**
   - Save commonly used filter combinations
   - Share subscription templates

6. **Notification Actions**
   - Snooze notification
   - Share notification
   - Add to folder/collection

7. **Analytics**
   - Show subscription performance
   - "This subscription generated 50 notifications (20% matched your interests)"

---

## Related Files

**Frontend:**
- `/frontend/src/components/NotificationButton.js` (to be created)
- `/frontend/src/components/NotificationSidebar.js` (to be created)
- `/frontend/src/components/CreateSubscriptionModal.js` (to be created)

**Backend:**
- `/backend/notifications/views.py`
- `/backend/notifications/views_metadata.py`
- `/backend/notifications/models/notification_subscription.py`

**Documentation:**
- [FRONTEND_INTEGRATION_GUIDE.md](./FRONTEND_INTEGRATION_GUIDE.md)
- `/backend/notifications/tests/` (comprehensive test examples)

---

## Questions for Product/Design Team

1. **Browser Notifications:** Do we want to implement browser push notifications?
2. **Email Notifications:** Should users receive email notifications as well?
3. **Notification Retention:** How long should notifications be kept? (30 days? Forever?)
4. **Subscription Limits:** Should there be a limit on subscriptions per user?
5. **Sharing:** Should users be able to share subscriptions with teammates?
6. **Export:** Should users be able to export notification history?

---

## Implementation Priority

### Phase 1: MVP (Minimum Viable Product)
- ✅ NotificationButton component (split button)
- ✅ Context detection logic
- ✅ NotificationSidebar with tabs
- ✅ Basic notification list (view, mark read, dismiss)
- ✅ Basic subscription list (view, delete)
- ✅ Context-aware quick subscribe (pre-filled modal)
- ✅ Badge count + polling

### Phase 2: Full Features
- ⏳ Full create subscription modal (all 6 types)
- ⏳ Edit subscription
- ⏳ Advanced filters (decision types, amount ranges)
- ⏳ Manual "Check Now" feature
- ⏳ Search/filter in sidebar
- ⏳ Custom subscription names (alias)

### Phase 3: Enhancements
- ⏳ WebSocket real-time updates
- ⏳ Browser notifications
- ⏳ Email digest
- ⏳ Subscription templates
- ⏳ Analytics/insights

---

**Document Version:** 1.0  
**Last Updated:** 2026-03-07  
**Maintained By:** Backend + Frontend Teams
