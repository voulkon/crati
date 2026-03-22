# Task 4.1: Subscriptions List (Read-Only)

**Status:** ⬜ Not Started  
**Priority:** 🔴 Critical (MVP)  
**Estimated Effort:** 2-3 days  
**Assignee:** _TBD_

---

## Description

Implement the Subscriptions tab in the Notification Center sidebar that displays all user subscriptions in a read-only list view. This includes rendering subscription cards with complete details, status indicators, and metadata.

## Goals

- Display all user subscriptions in an organized, scannable format
- Show subscription type, target, filters, and status at a glance
- Provide visual indicators for active/inactive subscriptions
- Show notification counts and last check timestamps
- Support empty states and loading states

## Technical Requirements

### Component Structure

```
SubscriptionsTab
├── SubscriptionsHeader
│   ├── Title
│   ├── NewSubscriptionButton
│   └── FilterControls (search, status filter, type filter, sort)
├── SubscriptionsList
│   ├── LoadingState
│   ├── EmptyState
│   └── SubscriptionCard[] (multiple)
│       ├── TypeIcon
│       ├── UserAlias
│       ├── TargetInfo
│       ├── FiltersDisplay
│       ├── StatusBadge
│       ├── MetadataRow (notification count, last checked)
│       └── ActionButtons (stub - implemented in 4.2)
```

### Subscription Card Layout

```typescript
interface SubscriptionCardProps {
  subscription: NotificationSubscription;
  onEdit?: (id: number) => void;  // Stub for now
  onDelete?: (id: number) => void; // Stub for now
  onPause?: (id: number) => void;  // Stub for now
  onCheckNow?: (id: number) => void; // Stub for now
}
```

**Card Display Elements:**
1. **Type Icon & Label** - Organization 🏢, Entity 🏭, Relationship 🔗, Person 👤, Signer ✍️, Filter Only 🔍
2. **User Alias** - Large, bold custom name (or auto-generated)
3. **Target Information** - Name, UID/AFM, category (if applicable)
4. **Filters Summary** - Compact display of keywords, amount range, decision types
5. **Status Indicator** - ⚡ Active (green) / ⏸️ Paused (gray)
6. **Metadata Row** - 📊 X notifications, 🕐 Last checked: X hours ago
7. **Action Buttons** - Edit, Check Now, Pause/Resume, Delete (placeholder only)

### API Integration

```typescript
// Fetch subscriptions on mount
const { data, loading, error, refetch } = useQuery(
  ['subscriptions'],
  () => notificationAPI.listSubscriptions()
);

// Data structure from API
type NotificationSubscription = {
  id: number;
  subscription_type: 'organization' | 'entity' | 'relationship' | 'person' | 'signer' | 'filter_only';
  user_alias?: string;
  organization_uid?: string;
  organization_details?: { name: string; category: string };
  entity_afm?: string;
  entity_details?: { name: string; vat_number: string };
  relationship_org_uid?: string;
  relationship_entity_afm?: string;
  signer_name?: string;
  keywords: string[];
  amount_min?: string;
  amount_max?: string;
  decision_types: string[];
  is_active: boolean;
  check_frequency: 'realtime' | 'hourly' | 'daily' | 'weekly';
  notification_count: number;
  last_checked_at?: string;
  created_at: string;
  updated_at: string;
};
```

### Visual States

1. **Loading State**
   ```
   ┌─────────────────────────────────────┐
   │  [Skeleton Card]                    │
   │  [Skeleton Card]                    │
   │  [Skeleton Card]                    │
   └─────────────────────────────────────┘
   ```

2. **Empty State**
   ```
   ┌─────────────────────────────────────┐
   │            📭                         │
   │      No subscriptions yet            │
   │                                      │
   │  Create your first subscription to   │
   │  receive notifications about         │
   │  decisions that matter to you.       │
   │                                      │
   │     [Create Subscription]            │
   └─────────────────────────────────────┘
   ```

3. **Loaded with Data**
   ```
   ┌─────────────────────────────────────┐
   │ 🏢 Organization Subscription         │
   │ "Athens Municipality Procurement"    │
   │                                      │
   │ Target: ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ              │
   │ Filters:                             │
   │   • Keywords: procurement, contract  │
   │   • Amount: €10,000+                 │
   │   • Frequency: Daily                 │
   │                                      │
   │ ⚡ Active  📊 5 notifications         │
   │ Last checked: 2 hours ago            │
   │                                      │
   │ [Edit] [Check Now] [Pause] [Delete]  │
   └─────────────────────────────────────┘
   ```

### Filtering & Sorting

**Filter Controls:**
- **Search** - Filter by user alias or target name (client-side)
- **Status** - All / Active / Paused
- **Type** - All / Organization / Entity / Relationship / Person / Signer / Filter Only
- **Sort** - Recent / Alphabetical / Type / Notification Count

```typescript
interface SubscriptionFilters {
  search: string;
  status: 'all' | 'active' | 'paused';
  type: 'all' | SubscriptionType;
  sortBy: 'recent' | 'alphabetical' | 'type' | 'notifications';
}

// Client-side filtering logic
const filteredSubscriptions = useMemo(() => {
  return subscriptions
    .filter(sub => {
      if (filters.search) {
        const searchLower = filters.search.toLowerCase();
        return (
          sub.user_alias?.toLowerCase().includes(searchLower) ||
          sub.organization_details?.name.toLowerCase().includes(searchLower) ||
          sub.entity_details?.name.toLowerCase().includes(searchLower)
        );
      }
      return true;
    })
    .filter(sub => {
      if (filters.status === 'active') return sub.is_active;
      if (filters.status === 'paused') return !sub.is_active;
      return true;
    })
    .filter(sub => {
      if (filters.type !== 'all') return sub.subscription_type === filters.type;
      return true;
    })
    .sort((a, b) => {
      switch (filters.sortBy) {
        case 'recent':
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        case 'alphabetical':
          return (a.user_alias || '').localeCompare(b.user_alias || '');
        case 'type':
          return a.subscription_type.localeCompare(b.subscription_type);
        case 'notifications':
          return b.notification_count - a.notification_count;
        default:
          return 0;
      }
    });
}, [subscriptions, filters]);
```

### Type-Specific Rendering

```typescript
function getSubscriptionTypeLabel(type: SubscriptionType): string {
  const labels = {
    organization: 'Organization Subscription',
    entity: 'Entity Subscription',
    relationship: 'Relationship Subscription',
    person: 'Person Subscription',
    signer: 'Signer Subscription',
    filter_only: 'Custom Filter Subscription'
  };
  return labels[type];
}

function getSubscriptionTypeIcon(type: SubscriptionType): string {
  const icons = {
    organization: '🏢',
    entity: '🏭',
    relationship: '🔗',
    person: '👤',
    signer: '✍️',
    filter_only: '🔍'
  };
  return icons[type];
}

function getTargetDisplay(subscription: NotificationSubscription): string {
  switch (subscription.subscription_type) {
    case 'organization':
      return subscription.organization_details?.name || `UID: ${subscription.organization_uid}`;
    case 'entity':
      return subscription.entity_details?.name || `AFM: ${subscription.entity_afm}`;
    case 'relationship':
      return `${subscription.organization_details?.name} + ${subscription.entity_details?.name}`;
    case 'signer':
      return subscription.signer_name || 'Unknown Signer';
    case 'filter_only':
      return 'Custom filters';
    default:
      return 'Unknown';
  }
}
```

### Filters Display Component

```typescript
interface FiltersDisplayProps {
  keywords: string[];
  amountMin?: string;
  amountMax?: string;
  decisionTypes: string[];
  checkFrequency: string;
}

function FiltersDisplay({ keywords, amountMin, amountMax, decisionTypes, checkFrequency }: FiltersDisplayProps) {
  return (
    <div className="filters-display">
      {keywords.length > 0 && (
        <div className="filter-item">
          <span className="filter-label">Keywords:</span>
          <span className="filter-value">{keywords.join(', ')}</span>
        </div>
      )}
      
      {(amountMin || amountMax) && (
        <div className="filter-item">
          <span className="filter-label">Amount:</span>
          <span className="filter-value">
            {amountMin && `€${parseFloat(amountMin).toLocaleString()}+`}
            {amountMin && amountMax && ' - '}
            {amountMax && `€${parseFloat(amountMax).toLocaleString()}`}
          </span>
        </div>
      )}
      
      {decisionTypes.length > 0 && (
        <div className="filter-item">
          <span className="filter-label">Decision Types:</span>
          <span className="filter-value">{decisionTypes.length} selected</span>
        </div>
      )}
      
      <div className="filter-item">
        <span className="filter-label">Frequency:</span>
        <span className="filter-value">{checkFrequency}</span>
      </div>
    </div>
  );
}
```

## Dependencies

- Task 1.1: API Client & Type Definitions (completed)
- Task 2.1: Sidebar Shell & Tab Navigation (completed)
- Existing UI component library (buttons, cards, badges, icons)

## Acceptance Criteria

- [ ] Subscriptions tab displays all user subscriptions from API
- [ ] Each subscription card shows all required information clearly
- [ ] Type-specific icons and labels are displayed correctly
- [ ] Active/paused status is visually distinct
- [ ] Filters summary is readable and compact
- [ ] Notification count and last checked timestamp are displayed
- [ ] Loading state shows skeleton cards
- [ ] Empty state with "Create Subscription" button is displayed when no subscriptions exist
- [ ] Search/filter controls work correctly
- [ ] Client-side filtering by search, status, and type works
- [ ] Sorting by all criteria works correctly
- [ ] Action buttons are present but disabled/stubbed (functionality in 4.2)
- [ ] Responsive layout works on mobile and desktop
- [ ] Accessibility: keyboard navigation, screen reader support, ARIA labels

## Testing Requirements

### Unit Tests

```typescript
describe('SubscriptionCard', () => {
  it('should render organization subscription with all details', () => {
    const subscription = {
      id: 1,
      subscription_type: 'organization',
      user_alias: 'My Org Watch',
      organization_uid: '99221718',
      organization_details: { name: 'ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ', category: 'Δήμος' },
      keywords: ['procurement'],
      amount_min: '10000.00',
      decision_types: ['Β.1.1'],
      is_active: true,
      check_frequency: 'daily',
      notification_count: 5,
      last_checked_at: '2024-01-15T10:00:00Z',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-15T10:00:00Z'
    };
    
    const { getByText } = render(<SubscriptionCard subscription={subscription} />);
    
    expect(getByText('My Org Watch')).toBeInTheDocument();
    expect(getByText('ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ')).toBeInTheDocument();
    expect(getByText(/procurement/)).toBeInTheDocument();
    expect(getByText(/€10,000/)).toBeInTheDocument();
    expect(getByText(/5 notifications/)).toBeInTheDocument();
    expect(getByText('⚡ Active')).toBeInTheDocument();
  });

  it('should render paused subscription with correct styling', () => {
    const subscription = {
      ...mockSubscription,
      is_active: false
    };
    
    const { container } = render(<SubscriptionCard subscription={subscription} />);
    
    expect(container.querySelector('.subscription-card--paused')).toBeInTheDocument();
    expect(getByText('⏸️ Paused')).toBeInTheDocument();
  });

  it('should render relationship subscription with both targets', () => {
    const subscription = {
      subscription_type: 'relationship',
      organization_details: { name: 'Org A' },
      entity_details: { name: 'Company B' },
      // ... other fields
    };
    
    const { getByText } = render(<SubscriptionCard subscription={subscription} />);
    
    expect(getByText(/Org A.*Company B/)).toBeInTheDocument();
  });
});

describe('SubscriptionsList', () => {
  it('should display loading state while fetching', () => {
    const { container } = render(<SubscriptionsList loading={true} subscriptions={[]} />);
    
    expect(container.querySelectorAll('.skeleton-card')).toHaveLength(3);
  });

  it('should display empty state when no subscriptions exist', () => {
    const { getByText } = render(<SubscriptionsList loading={false} subscriptions={[]} />);
    
    expect(getByText('No subscriptions yet')).toBeInTheDocument();
    expect(getByText('Create Subscription')).toBeInTheDocument();
  });

  it('should display all subscriptions', () => {
    const subscriptions = [
      { id: 1, user_alias: 'Sub 1', /* ... */ },
      { id: 2, user_alias: 'Sub 2', /* ... */ },
    ];
    
    const { getByText } = render(<SubscriptionsList subscriptions={subscriptions} />);
    
    expect(getByText('Sub 1')).toBeInTheDocument();
    expect(getByText('Sub 2')).toBeInTheDocument();
  });
});

describe('Subscription Filtering', () => {
  it('should filter by search query', () => {
    // Test search functionality
  });

  it('should filter by active status', () => {
    // Test status filtering
  });

  it('should filter by subscription type', () => {
    // Test type filtering
  });

  it('should sort by notification count', () => {
    // Test sorting
  });
});
```

### Integration Tests

```typescript
describe('Subscriptions Tab Integration', () => {
  it('should fetch and display subscriptions on mount', async () => {
    mockAPI.listSubscriptions.mockResolvedValue([...subscriptions]);
    
    render(<NotificationSidebar initialTab="subscriptions" />);
    
    await waitFor(() => {
      expect(screen.getByText('Sub 1')).toBeInTheDocument();
    });
    
    expect(mockAPI.listSubscriptions).toHaveBeenCalledTimes(1);
  });

  it('should handle API errors gracefully', async () => {
    mockAPI.listSubscriptions.mockRejectedValue(new Error('API Error'));
    
    render(<SubscriptionsTab />);
    
    await waitFor(() => {
      expect(screen.getByText(/error loading subscriptions/i)).toBeInTheDocument();
    });
  });
});
```

### Visual Tests

```typescript
describe('SubscriptionCard Visual Tests', () => {
  it('should match snapshot for organization subscription', () => {
    const { container } = render(<SubscriptionCard subscription={orgSubscription} />);
    expect(container).toMatchSnapshot();
  });

  it('should match snapshot for paused subscription', () => {
    const { container } = render(<SubscriptionCard subscription={pausedSubscription} />);
    expect(container).toMatchSnapshot();
  });
});
```

## Implementation Notes

### Performance Considerations

- Use React.memo for SubscriptionCard to prevent unnecessary re-renders
- Implement virtual scrolling if user has >50 subscriptions
- Debounce search input (300ms)
- Cache filtered results with useMemo

### Accessibility

- Use semantic HTML (`<article>` for cards, `<button>` for actions)
- Provide ARIA labels for icon-only buttons
- Ensure keyboard navigation works (Tab, Enter, Space)
- Use proper heading hierarchy (h2 for section, h3 for subscription names)
- Provide screen reader text for status indicators
- Ensure color contrast meets WCAG AA standards (4.5:1 for text)

### Styling Approach

- Use existing design system colors and typography
- Subscription cards should match the visual style of notification cards
- Active subscriptions: subtle green accent border
- Paused subscriptions: gray/muted appearance
- Hover states: subtle elevation/shadow
- Responsive: stack filters vertically on mobile

### Edge Cases

1. **Subscription with no alias** - Generate default: "[Type] Subscription #[ID]"
2. **Very long keywords list** - Show first 3, then "+ X more"
3. **Missing target details** - Fallback to UID/AFM display
4. **Never checked subscription** - Show "Never checked" instead of timestamp
5. **Zero notifications** - Show "No notifications yet"
6. **Future timestamps** - Handle gracefully (shouldn't happen but defensive)

### Data Freshness

- Refetch subscriptions when tab becomes active
- Expose refetch function for use by action handlers in 4.2
- Consider polling or websocket updates (Phase 8)

## Related Files

**To Create:**
- `frontend/src/components/notifications/SubscriptionsTab.tsx`
- `frontend/src/components/notifications/SubscriptionCard.tsx`
- `frontend/src/components/notifications/FiltersDisplay.tsx`
- `frontend/src/components/notifications/SubscriptionsHeader.tsx`
- `frontend/src/components/notifications/SubscriptionEmptyState.tsx`

**To Reference:**
- `frontend/src/api/notifications/client.ts` (Task 1.1)
- `frontend/src/api/notifications/types.ts` (Task 1.1)
- `frontend/src/components/notifications/NotificationSidebar.tsx` (Task 2.1)
- Backend serializers: `backend/notifications/serializers/subscription_serializer.py`

## Definition of Done

- [ ] SubscriptionsTab component renders correctly
- [ ] All subscription cards display complete information
- [ ] Type-specific icons and labels work
- [ ] Loading state implemented
- [ ] Empty state implemented
- [ ] Search/filter/sort functionality works
- [ ] Action buttons present (stubbed)
- [ ] Unit tests written and passing (>85% coverage)
- [ ] Integration tests written and passing
- [ ] Visual/snapshot tests created
- [ ] Accessibility audit passed (keyboard nav, screen readers, ARIA)
- [ ] Responsive design works on mobile/tablet/desktop
- [ ] Code reviewed and approved
- [ ] Documentation updated
- [ ] Merged to feature branch

## Future Enhancements (Out of Scope)

- Bulk actions (select multiple, delete/pause all)
- Export subscriptions as JSON
- Duplicate subscription feature
- Subscription templates/presets
- Drag-and-drop reordering

---

**Notes:**
- Action button functionality will be implemented in Task 4.2
- Edit flow will be implemented in Task 5.5
- Focus on read-only display and organization in this task
- Ensure consistent styling with NotificationsList from Task 2.2
