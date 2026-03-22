# Task 3.2: Bell Click Context Behavior

**Status:** ⬜ Not Started  
**Priority:** 🔴 Critical (MVP)  
**Estimated Effort:** 2-3 days  
**Assignee:** _TBD_

---

## Description

Implement intelligent click behavior for the bell half of the notification button. The button should respond differently based on the current page context and subscription status, providing quick access to subscribe/unsubscribe or view existing subscriptions.

## Goals

- Implement context-aware click handlers for bell button
- Show different UI based on subscription status
- Provide quick subscribe/unsubscribe actions
- Open subscription modal with pre-filled context
- Handle edge cases and error states gracefully

## Technical Requirements

### Split Button Behavior

The notification button has two clickable areas:

```
┌──────────────────────────┐
│  🔔3  │  ▾               │
└──────────────────────────┘
 ↑        ↑
 Bell     Chevron
 Half     Half
```

**This task focuses on the BELL HALF (left side).**

### Click Behavior Matrix

| Page Context | Subscription Status | Bell Click Action |
|-------------|---------------------|-------------------|
| Organization page | Not subscribed | Open subscription modal (pre-filled) |
| Organization page | Subscribed | Show subscription menu/popover |
| Entity (AFM) page | Not subscribed | Open subscription modal (pre-filled) |
| Entity (AFM) page | Subscribed | Show subscription menu/popover |
| Signer page | Not subscribed | Open subscription modal (pre-filled) |
| Signer page | Subscribed | Show subscription menu/popover |
| Relationship page | Not subscribed | Open subscription modal (pre-filled) |
| Relationship page | Subscribed | Show subscription menu/popover |
| Home/Search/Library | N/A | Open notification sidebar (same as chevron) |
| Decision detail | N/A | Disabled (no action) |
| Unit page | N/A | Disabled (no action) |

### Subscription Menu/Popover

When user is subscribed, clicking the bell shows a popover with:

```
┌─────────────────────────────────┐
│ 📋 Active Subscription          │
│                                  │
│ "My Custom Name"                 │
│ Organization: ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ    │
│                                  │
│ Filters:                         │
│  • Keywords: procurement         │
│  • Amount: €10,000+              │
│                                  │
│ ─────────────────────────────── │
│                                  │
│ [✏️ Edit]  [View All]  [Delete] │
└─────────────────────────────────┘
```

### Component Interface

```typescript
interface BellButtonClickHandler {
  onClick: (event: React.MouseEvent) => void;
  isDisabled: boolean;
  tooltip?: string;
  className?: string;
}

function useBellClickHandler(): BellButtonClickHandler;
```

### Implementation Logic

```typescript
export function useBellClickHandler(): BellButtonClickHandler {
  const { context, capabilities } = useNotificationContext();
  const { isSubscribed, subscription } = useSubscriptionStatus();
  const [showPopover, setShowPopover] = useState(false);
  const { openModal: openSubscriptionModal } = useSubscriptionModal();
  const { openSidebar } = useNotificationSidebar();

  const onClick = useCallback((event: React.MouseEvent) => {
    event.stopPropagation();
    
    // Handle disabled contexts
    if (context.type === 'disabled') {
      return; // No action
    }
    
    // Handle passive contexts (home, search, library)
    if (context.type === 'passive') {
      openSidebar('notifications');
      return;
    }
    
    // Handle subscribable contexts
    if (capabilities.canSubscribe) {
      if (isSubscribed && subscription) {
        // Show subscription menu/popover
        setShowPopover(true);
      } else {
        // Open subscription modal with pre-filled context
        openSubscriptionModal({
          prefill: {
            type: context.type,
            ...extractTargetData(context)
          }
        });
      }
    }
  }, [context, capabilities, isSubscribed, subscription]);

  const isDisabled = context.type === 'disabled';
  
  const tooltip = useMemo(() => {
    if (context.type === 'disabled') {
      return 'Notifications for individual decisions are not supported';
    }
    if (context.type === 'passive') {
      return 'View notifications';
    }
    if (isSubscribed) {
      return 'Manage subscription';
    }
    return 'Subscribe to notifications';
  }, [context, isSubscribed]);

  return { onClick, isDisabled, tooltip };
}
```

### Subscription Popover Component

```typescript
interface SubscriptionPopoverProps {
  subscription: Subscription;
  isOpen: boolean;
  onClose: () => void;
  anchorEl: HTMLElement | null;
  onEdit: () => void;
  onDelete: () => void;
  onViewAll: () => void;
}

export function SubscriptionPopover({
  subscription,
  isOpen,
  onClose,
  anchorEl,
  onEdit,
  onDelete,
  onViewAll
}: SubscriptionPopoverProps): JSX.Element {
  return (
    <Popover
      open={isOpen}
      anchorEl={anchorEl}
      onClose={onClose}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      transformOrigin={{ vertical: 'top', horizontal: 'right' }}
    >
      <div className="subscription-popover">
        <div className="popover-header">
          <Icon type={subscription.subscription_type} />
          <span>Active Subscription</span>
        </div>
        
        <div className="popover-content">
          {subscription.user_alias && (
            <div className="subscription-name">"{subscription.user_alias}"</div>
          )}
          
          <SubscriptionTargetDisplay subscription={subscription} />
          
          {(subscription.keywords?.length > 0 || 
            subscription.amount_min || 
            subscription.decision_types?.length > 0) && (
            <div className="filters-section">
              <div className="section-label">Filters:</div>
              <FiltersList subscription={subscription} />
            </div>
          )}
          
          <div className="metadata">
            <span className={subscription.is_active ? 'active' : 'paused'}>
              {subscription.is_active ? '⚡ Active' : '⏸️ Paused'}
            </span>
            <span>Created {formatRelativeTime(subscription.created_at)}</span>
          </div>
        </div>
        
        <div className="popover-actions">
          <Button variant="text" onClick={onEdit}>
            ✏️ Edit
          </Button>
          <Button variant="text" onClick={onViewAll}>
            View All
          </Button>
          <Button variant="text" color="danger" onClick={onDelete}>
            Delete
          </Button>
        </div>
      </div>
    </Popover>
  );
}
```

## Dependencies

- Task 1.2 (Context Detection)
- Task 1.3 (Bell Button Component)
- Task 3.1 (Subscription Status)
- Task 5.1-5.4 (Subscription Modal - may need coordination)

## Acceptance Criteria

- [ ] Bell half click opens modal when not subscribed on subscribable pages
- [ ] Bell half click shows popover when subscribed on subscribable pages
- [ ] Bell half click opens sidebar on passive pages (home, search)
- [ ] Bell half is disabled and shows tooltip on disabled pages (decisions)
- [ ] Popover displays correct subscription details
- [ ] Popover "Edit" opens subscription edit modal
- [ ] Popover "Delete" shows confirmation and deletes subscription
- [ ] Popover "View All" opens subscriptions tab in sidebar
- [ ] Click outside popover closes it
- [ ] Escape key closes popover
- [ ] Subscription modal opens with correct pre-filled data
- [ ] Visual feedback on hover (cursor pointer vs not-allowed)
- [ ] Tooltip accurately describes action
- [ ] Loading state shown while checking subscription status
- [ ] Error state handled gracefully (e.g., network error)
- [ ] Multiple rapid clicks don't cause issues (debounced/prevented)

## Testing Requirements

### Unit Tests

```typescript
describe('useBellClickHandler', () => {
  it('should open modal when not subscribed on organization page', () => {
    const { result } = renderHookWithContext(
      () => useBellClickHandler(),
      {
        context: { type: 'organization', organizationUid: '99221718' },
        isSubscribed: false
      }
    );
    
    const mockEvent = { stopPropagation: jest.fn() };
    result.current.onClick(mockEvent as any);
    
    expect(mockOpenModal).toHaveBeenCalledWith({
      prefill: {
        type: 'organization',
        organizationUid: '99221718'
      }
    });
  });

  it('should show popover when subscribed', () => {
    const mockSubscription = { id: 1, organization_uid: '99221718' };
    
    const { result } = renderHookWithContext(
      () => useBellClickHandler(),
      {
        context: { type: 'organization', organizationUid: '99221718' },
        isSubscribed: true,
        subscription: mockSubscription
      }
    );
    
    const mockEvent = { stopPropagation: jest.fn() };
    result.current.onClick(mockEvent as any);
    
    // Popover should be shown (test via state or callback)
    expect(mockShowPopover).toHaveBeenCalled();
  });

  it('should open sidebar on passive page', () => {
    const { result } = renderHookWithContext(
      () => useBellClickHandler(),
      { context: { type: 'passive' } }
    );
    
    const mockEvent = { stopPropagation: jest.fn() };
    result.current.onClick(mockEvent as any);
    
    expect(mockOpenSidebar).toHaveBeenCalledWith('notifications');
  });

  it('should be disabled on decision page', () => {
    const { result } = renderHookWithContext(
      () => useBellClickHandler(),
      { context: { type: 'disabled' } }
    );
    
    expect(result.current.isDisabled).toBe(true);
    expect(result.current.tooltip).toBe(
      'Notifications for individual decisions are not supported'
    );
  });

  it('should provide correct tooltip based on context', () => {
    // Not subscribed
    const { result: result1 } = renderHookWithContext(
      () => useBellClickHandler(),
      {
        context: { type: 'organization', organizationUid: '99221718' },
        isSubscribed: false
      }
    );
    expect(result1.current.tooltip).toBe('Subscribe to notifications');
    
    // Subscribed
    const { result: result2 } = renderHookWithContext(
      () => useBellClickHandler(),
      {
        context: { type: 'organization', organizationUid: '99221718' },
        isSubscribed: true
      }
    );
    expect(result2.current.tooltip).toBe('Manage subscription');
  });

  it('should stop event propagation', () => {
    const { result } = renderHookWithContext(
      () => useBellClickHandler(),
      { context: { type: 'passive' } }
    );
    
    const mockEvent = { stopPropagation: jest.fn() };
    result.current.onClick(mockEvent as any);
    
    expect(mockEvent.stopPropagation).toHaveBeenCalled();
  });
});

describe('SubscriptionPopover', () => {
  const mockSubscription = {
    id: 1,
    organization_uid: '99221718',
    user_alias: 'My Custom Name',
    keywords: ['procurement', 'contract'],
    amount_min: '10000.00',
    is_active: true,
    created_at: '2026-03-01T10:00:00Z'
  };

  it('should render subscription details', () => {
    render(
      <SubscriptionPopover
        subscription={mockSubscription}
        isOpen={true}
        onClose={jest.fn()}
        anchorEl={document.body}
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        onViewAll={jest.fn()}
      />
    );
    
    expect(screen.getByText('My Custom Name')).toBeInTheDocument();
    expect(screen.getByText(/procurement/)).toBeInTheDocument();
    expect(screen.getByText(/€10,000/)).toBeInTheDocument();
  });

  it('should call onEdit when edit button clicked', () => {
    const onEdit = jest.fn();
    
    render(
      <SubscriptionPopover
        subscription={mockSubscription}
        isOpen={true}
        onClose={jest.fn()}
        anchorEl={document.body}
        onEdit={onEdit}
        onDelete={jest.fn()}
        onViewAll={jest.fn()}
      />
    );
    
    fireEvent.click(screen.getByText('Edit'));
    expect(onEdit).toHaveBeenCalled();
  });

  it('should call onDelete when delete button clicked', () => {
    const onDelete = jest.fn();
    
    render(
      <SubscriptionPopover
        subscription={mockSubscription}
        isOpen={true}
        onClose={jest.fn()}
        anchorEl={document.body}
        onEdit={jest.fn()}
        onDelete={onDelete}
        onViewAll={jest.fn()}
      />
    );
    
    fireEvent.click(screen.getByText('Delete'));
    expect(onDelete).toHaveBeenCalled();
  });

  it('should close when clicking outside', () => {
    const onClose = jest.fn();
    
    render(
      <SubscriptionPopover
        subscription={mockSubscription}
        isOpen={true}
        onClose={onClose}
        anchorEl={document.body}
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        onViewAll={jest.fn()}
      />
    );
    
    fireEvent.click(document.body);
    expect(onClose).toHaveBeenCalled();
  });
});
```

### Integration Tests

```typescript
describe('Bell Click Behavior Integration', () => {
  it('should complete full subscribe flow from bell click', async () => {
    render(<App />, { route: '/entity/organization/99221718' });
    
    // Click bell button
    const bellButton = screen.getByTestId('bell-button-left');
    fireEvent.click(bellButton);
    
    // Subscription modal should open
    await waitFor(() => {
      expect(screen.getByText('Create Subscription')).toBeInTheDocument();
    });
    
    // Organization should be pre-filled
    expect(screen.getByText('ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ')).toBeInTheDocument();
  });

  it('should show popover when already subscribed', async () => {
    // Setup: user has subscription
    mockAPI.checkOrganizationSubscription.mockResolvedValue({
      subscribed: true,
      subscription: { id: 1, organization_uid: '99221718' }
    });
    
    render(<App />, { route: '/entity/organization/99221718' });
    
    await waitFor(() => {
      expect(screen.getByTestId('bell-icon')).toHaveClass('bell-filled');
    });
    
    // Click bell
    fireEvent.click(screen.getByTestId('bell-button-left'));
    
    // Popover should appear
    await waitFor(() => {
      expect(screen.getByText('Active Subscription')).toBeInTheDocument();
    });
  });

  it('should delete subscription from popover', async () => {
    mockAPI.checkOrganizationSubscription.mockResolvedValue({
      subscribed: true,
      subscription: { id: 1, organization_uid: '99221718' }
    });
    
    render(<App />, { route: '/entity/organization/99221718' });
    
    // Open popover
    fireEvent.click(screen.getByTestId('bell-button-left'));
    
    await waitFor(() => {
      expect(screen.getByText('Delete')).toBeInTheDocument();
    });
    
    // Click delete
    fireEvent.click(screen.getByText('Delete'));
    
    // Confirm deletion
    fireEvent.click(screen.getByText('Confirm'));
    
    // Subscription should be deleted
    await waitFor(() => {
      expect(mockAPI.deleteSubscription).toHaveBeenCalledWith(1);
    });
    
    // Bell should return to unfilled state
    expect(screen.getByTestId('bell-icon')).toHaveClass('bell-outline');
  });
});
```

## Implementation Notes

### Prevent Double-Click Issues

```typescript
// Add debouncing or click protection
const [isProcessing, setIsProcessing] = useState(false);

const onClick = useCallback(async (event: React.MouseEvent) => {
  if (isProcessing) return;
  
  setIsProcessing(true);
  try {
    // Handle click logic
  } finally {
    setIsProcessing(false);
  }
}, [isProcessing, /* other deps */]);
```

### Pre-fill Modal Data

```typescript
function extractTargetData(context: NotificationContext) {
  switch (context.type) {
    case 'organization':
      return {
        organizationUid: context.organizationUid,
        organizationName: context.organizationName
      };
    case 'entity':
      return {
        afm: context.afm,
        entityName: context.entityName
      };
    case 'relationship':
      return {
        organizationUid: context.organizationUid,
        afm: context.afm
      };
    case 'signer':
      return {
        signerName: context.signerName
      };
    default:
      return {};
  }
}
```

### Delete Confirmation

```typescript
const handleDelete = useCallback(async () => {
  const confirmed = await showConfirmDialog({
    title: 'Delete Subscription?',
    message: 'You will stop receiving notifications. This action cannot be undone.',
    confirmText: 'Delete',
    confirmColor: 'danger'
  });
  
  if (confirmed && subscription) {
    await api.deleteSubscription(subscription.id);
    await refetchStatus(); // Refresh subscription status
    showToast('Subscription deleted', 'success');
    onClose();
  }
}, [subscription, api, refetchStatus]);
```

### Popover Positioning

- Use Material-UI Popover or similar for positioning
- Position below and to the right of bell button
- Ensure popover stays on screen (responsive positioning)
- Add arrow/pointer to indicate anchor

## Related Files

- `frontend/src/hooks/useBellClickHandler.ts` (new)
- `frontend/src/components/SubscriptionPopover.tsx` (new)
- `frontend/src/components/NotificationButton.tsx` (Task 1.3 - integrate handler)
- `frontend/src/hooks/useNotificationContext.ts` (Task 1.2)
- `frontend/src/hooks/useSubscriptionStatus.ts` (Task 3.1)

## Definition of Done

- [ ] All code written and reviewed
- [ ] All unit tests passing (>95% coverage)
- [ ] Integration tests passing
- [ ] Popover component implemented and tested
- [ ] Click handler hook implemented and tested
- [ ] Integrated with bell button component
- [ ] Modal opening with pre-filled data working
- [ ] Delete subscription flow working
- [ ] Tooltips accurate and helpful
- [ ] Accessibility verified (keyboard navigation, screen readers)
- [ ] Visual design approved
- [ ] Code merged to feature branch

## Additional Resources

- [UI Specification - Button Interaction Behavior](../../FRONTEND_UI_SPECIFICATION.md#button-interaction-behavior)
- [UI Specification - Subscription Menu/Popover](../../FRONTEND_UI_SPECIFICATION.md#subscription-menupopover)
- Material-UI Popover documentation

---

**Notes:**
- Consider animation/transition for popover appearance
- Ensure popover doesn't block important UI elements
- Test with long subscription names and many filters
- Consider adding "Quick filters" or "Recent notifications" to popover
- May want to show notification count for this specific subscription in popover
