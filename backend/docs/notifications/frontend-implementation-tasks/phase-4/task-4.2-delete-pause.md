# Task 4.2: Delete & Pause Subscriptions

**Status:** ⬜ Not Started  
**Priority:** 🔴 Critical (MVP)  
**Estimated Effort:** 2 days  
**Assignee:** _TBD_

---

## Description

Implement the delete and pause/resume functionality for subscriptions in the Subscriptions tab. This includes confirmation dialogs, optimistic updates, error handling, and UI state management.

## Goals

- Enable users to pause/resume subscriptions without deleting them
- Provide safe deletion with confirmation dialog
- Implement optimistic UI updates for immediate feedback
- Handle errors gracefully with rollback
- Update subscription list automatically after actions

## Technical Requirements

### Action Buttons Implementation

Update the `SubscriptionCard` component from Task 4.1 to make action buttons functional:

```typescript
interface SubscriptionCardProps {
  subscription: NotificationSubscription;
  onEdit?: (id: number) => void;  // Still stub (Task 5.5)
  onDelete: (id: number) => void;  // Implement in this task
  onPause: (id: number) => void;   // Implement in this task
  onCheckNow?: (id: number) => void; // Stub (Task 4.3)
}

function SubscriptionCard({ subscription, onDelete, onPause }: SubscriptionCardProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const [isPausing, setIsPausing] = useState(false);

  return (
    <div className="subscription-card">
      {/* ... existing card content ... */}
      
      <div className="subscription-actions">
        <button onClick={() => onEdit?.(subscription.id)} disabled>
          ✏️ Edit
        </button>
        
        <button onClick={() => onCheckNow?.(subscription.id)} disabled>
          🔄 Check Now
        </button>
        
        <button
          onClick={() => onPause(subscription.id)}
          disabled={isPausing}
          className={subscription.is_active ? 'btn-pause' : 'btn-resume'}
        >
          {isPausing ? (
            <Spinner size="small" />
          ) : subscription.is_active ? (
            <>⏸️ Pause</>
          ) : (
            <>▶️ Resume</>
          )}
        </button>
        
        <button
          onClick={() => onDelete(subscription.id)}
          disabled={isDeleting}
          className="btn-delete"
        >
          {isDeleting ? <Spinner size="small" /> : <>🗑️ Delete</>}
        </button>
      </div>
    </div>
  );
}
```

### Pause/Resume Functionality

```typescript
function SubscriptionsTab() {
  const queryClient = useQueryClient();
  
  const pauseMutation = useMutation({
    mutationFn: async ({ id, newStatus }: { id: number; newStatus: boolean }) => {
      return await notificationAPI.updateSubscription(id, { is_active: newStatus });
    },
    
    // Optimistic update
    onMutate: async ({ id, newStatus }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries(['subscriptions']);
      
      // Snapshot previous value
      const previousSubscriptions = queryClient.getQueryData<NotificationSubscription[]>(['subscriptions']);
      
      // Optimistically update
      queryClient.setQueryData<NotificationSubscription[]>(['subscriptions'], (old) =>
        old?.map(sub => sub.id === id ? { ...sub, is_active: newStatus } : sub) || []
      );
      
      return { previousSubscriptions };
    },
    
    // On error, rollback
    onError: (err, variables, context) => {
      if (context?.previousSubscriptions) {
        queryClient.setQueryData(['subscriptions'], context.previousSubscriptions);
      }
      
      toast.error('Failed to update subscription. Please try again.');
      console.error('Pause/Resume error:', err);
    },
    
    // Always refetch after success or error
    onSettled: () => {
      queryClient.invalidateQueries(['subscriptions']);
    },
    
    onSuccess: (data, variables) => {
      toast.success(
        variables.newStatus
          ? 'Subscription activated'
          : 'Subscription paused'
      );
    }
  });
  
  const handlePauseToggle = (id: number, currentStatus: boolean) => {
    pauseMutation.mutate({ id, newStatus: !currentStatus });
  };
  
  // ... rest of component
}
```

### Delete Functionality with Confirmation

```typescript
function SubscriptionsTab() {
  const [deleteConfirmation, setDeleteConfirmation] = useState<{
    show: boolean;
    subscriptionId: number | null;
    subscriptionName: string;
  }>({
    show: false,
    subscriptionId: null,
    subscriptionName: ''
  });
  
  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      return await notificationAPI.deleteSubscription(id);
    },
    
    // Optimistic update
    onMutate: async (id) => {
      await queryClient.cancelQueries(['subscriptions']);
      
      const previousSubscriptions = queryClient.getQueryData<NotificationSubscription[]>(['subscriptions']);
      
      // Remove from list immediately
      queryClient.setQueryData<NotificationSubscription[]>(['subscriptions'], (old) =>
        old?.filter(sub => sub.id !== id) || []
      );
      
      return { previousSubscriptions };
    },
    
    onError: (err, id, context) => {
      if (context?.previousSubscriptions) {
        queryClient.setQueryData(['subscriptions'], context.previousSubscriptions);
      }
      
      toast.error('Failed to delete subscription. Please try again.');
      console.error('Delete error:', err);
    },
    
    onSuccess: () => {
      toast.success('Subscription deleted successfully');
      setDeleteConfirmation({ show: false, subscriptionId: null, subscriptionName: '' });
    },
    
    onSettled: () => {
      queryClient.invalidateQueries(['subscriptions']);
    }
  });
  
  const handleDeleteClick = (subscription: NotificationSubscription) => {
    setDeleteConfirmation({
      show: true,
      subscriptionId: subscription.id,
      subscriptionName: subscription.user_alias || getDefaultAlias(subscription)
    });
  };
  
  const handleDeleteConfirm = () => {
    if (deleteConfirmation.subscriptionId) {
      deleteMutation.mutate(deleteConfirmation.subscriptionId);
    }
  };
  
  const handleDeleteCancel = () => {
    setDeleteConfirmation({ show: false, subscriptionId: null, subscriptionName: '' });
  };
  
  return (
    <>
      {/* Subscription list */}
      <SubscriptionsList
        subscriptions={subscriptions}
        onDelete={handleDeleteClick}
        onPause={(id, status) => handlePauseToggle(id, status)}
      />
      
      {/* Delete confirmation modal */}
      <DeleteConfirmationModal
        show={deleteConfirmation.show}
        subscriptionName={deleteConfirmation.subscriptionName}
        onConfirm={handleDeleteConfirm}
        onCancel={handleDeleteCancel}
        isDeleting={deleteMutation.isLoading}
      />
    </>
  );
}
```

### Delete Confirmation Modal

```typescript
interface DeleteConfirmationModalProps {
  show: boolean;
  subscriptionName: string;
  onConfirm: () => void;
  onCancel: () => void;
  isDeleting: boolean;
}

function DeleteConfirmationModal({
  show,
  subscriptionName,
  onConfirm,
  onCancel,
  isDeleting
}: DeleteConfirmationModalProps) {
  if (!show) return null;
  
  return (
    <Modal onClose={onCancel} size="small">
      <ModalHeader>
        <h3>Delete Subscription</h3>
      </ModalHeader>
      
      <ModalBody>
        <div className="delete-confirmation">
          <div className="warning-icon">⚠️</div>
          
          <p>
            Are you sure you want to delete the subscription{' '}
            <strong>"{subscriptionName}"</strong>?
          </p>
          
          <div className="warning-message">
            <ul>
              <li>All notifications for this subscription will remain</li>
              <li>You can create a new subscription with the same settings later</li>
              <li>This action cannot be undone</li>
            </ul>
          </div>
        </div>
      </ModalBody>
      
      <ModalFooter>
        <button
          onClick={onCancel}
          disabled={isDeleting}
          className="btn-secondary"
        >
          Cancel
        </button>
        
        <button
          onClick={onConfirm}
          disabled={isDeleting}
          className="btn-danger"
        >
          {isDeleting ? (
            <>
              <Spinner size="small" /> Deleting...
            </>
          ) : (
            'Delete Subscription'
          )}
        </button>
      </ModalFooter>
    </Modal>
  );
}
```

### Keyboard Shortcuts

```typescript
function SubscriptionCard({ subscription, onDelete, onPause }: SubscriptionCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Check if this card is focused
      if (!cardRef.current?.contains(document.activeElement)) return;
      
      switch (e.key) {
        case 'Delete':
        case 'Backspace':
          if (e.shiftKey) {
            e.preventDefault();
            onDelete(subscription.id);
          }
          break;
        case 'p':
        case 'P':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            onPause(subscription.id, subscription.is_active);
          }
          break;
      }
    };
    
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [subscription, onDelete, onPause]);
  
  return (
    <div ref={cardRef} className="subscription-card" tabIndex={0}>
      {/* ... card content ... */}
    </div>
  );
}
```

### Error Handling

```typescript
interface SubscriptionError extends Error {
  status?: number;
  field_errors?: Record<string, string[]>;
  non_field_errors?: string[];
}

function handleSubscriptionError(error: SubscriptionError, action: 'delete' | 'pause' | 'resume') {
  let message = `Failed to ${action} subscription.`;
  
  if (error.status === 404) {
    message = 'Subscription not found. It may have been deleted.';
  } else if (error.status === 403) {
    message = 'You do not have permission to modify this subscription.';
  } else if (error.status === 400 && error.non_field_errors) {
    message = error.non_field_errors[0];
  } else if (error.status >= 500) {
    message = 'Server error. Please try again later.';
  }
  
  return message;
}
```

### Batch Operations (Future Enhancement - Out of Scope)

Prepare component structure for future batch operations:

```typescript
// Placeholder for future implementation
interface SubscriptionsTabState {
  selectedIds: Set<number>;
  isBatchMode: boolean;
}

// Add checkbox to each card for selection (hidden by default)
// Add "Select All", "Delete Selected", "Pause Selected" buttons
```

## Dependencies

- Task 4.1: Subscriptions List (Read-Only) - must be completed
- Task 1.1: API Client & Type Definitions - completed
- React Query or similar state management library
- Toast/notification library for user feedback
- Modal component from design system

## Acceptance Criteria

- [ ] Pause button toggles subscription active status
- [ ] Resume button activates paused subscriptions
- [ ] Delete button opens confirmation modal
- [ ] Confirmation modal shows subscription name and warning
- [ ] Delete confirmation removes subscription from list
- [ ] Optimistic updates provide immediate UI feedback
- [ ] Failed operations rollback optimistic changes
- [ ] Error messages are user-friendly and specific
- [ ] Success toasts confirm actions
- [ ] Deletion updates the subscription count in the sidebar
- [ ] Paused subscriptions are visually distinct in the list
- [ ] Loading states shown during API calls
- [ ] Keyboard shortcuts work (Shift+Delete, Cmd/Ctrl+P)
- [ ] Actions are disabled during loading
- [ ] Cancel button in modal works correctly
- [ ] Clicking outside modal closes it (with cancel behavior)

## Testing Requirements

### Unit Tests

```typescript
describe('Delete Functionality', () => {
  it('should show confirmation modal when delete clicked', () => {
    const subscription = mockSubscription;
    const { getByText } = render(
      <SubscriptionCard subscription={subscription} onDelete={jest.fn()} />
    );
    
    fireEvent.click(getByText('Delete'));
    
    expect(getByText(/delete the subscription/i)).toBeInTheDocument();
    expect(getByText(subscription.user_alias)).toBeInTheDocument();
  });
  
  it('should call delete API when confirmed', async () => {
    const onDelete = jest.fn();
    const { getByText } = render(
      <DeleteConfirmationModal
        show={true}
        subscriptionName="Test Sub"
        onConfirm={onDelete}
        onCancel={jest.fn()}
        isDeleting={false}
      />
    );
    
    fireEvent.click(getByText('Delete Subscription'));
    
    expect(onDelete).toHaveBeenCalledTimes(1);
  });
  
  it('should cancel deletion when cancel clicked', () => {
    const onCancel = jest.fn();
    const { getByText } = render(
      <DeleteConfirmationModal
        show={true}
        subscriptionName="Test"
        onConfirm={jest.fn()}
        onCancel={onCancel}
        isDeleting={false}
      />
    );
    
    fireEvent.click(getByText('Cancel'));
    
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
  
  it('should disable buttons while deleting', () => {
    const { getByText } = render(
      <DeleteConfirmationModal
        show={true}
        subscriptionName="Test"
        onConfirm={jest.fn()}
        onCancel={jest.fn()}
        isDeleting={true}
      />
    );
    
    expect(getByText('Delete Subscription')).toBeDisabled();
    expect(getByText('Cancel')).toBeDisabled();
  });
});

describe('Pause/Resume Functionality', () => {
  it('should show pause button for active subscriptions', () => {
    const subscription = { ...mockSubscription, is_active: true };
    const { getByText } = render(
      <SubscriptionCard subscription={subscription} onPause={jest.fn()} />
    );
    
    expect(getByText('Pause')).toBeInTheDocument();
  });
  
  it('should show resume button for paused subscriptions', () => {
    const subscription = { ...mockSubscription, is_active: false };
    const { getByText } = render(
      <SubscriptionCard subscription={subscription} onPause={jest.fn()} />
    );
    
    expect(getByText('Resume')).toBeInTheDocument();
  });
  
  it('should call pause API with correct parameters', async () => {
    const onPause = jest.fn();
    const subscription = { ...mockSubscription, is_active: true };
    const { getByText } = render(
      <SubscriptionCard subscription={subscription} onPause={onPause} />
    );
    
    fireEvent.click(getByText('Pause'));
    
    expect(onPause).toHaveBeenCalledWith(subscription.id, true);
  });
});
```

### Integration Tests

```typescript
describe('Subscription Actions Integration', () => {
  it('should delete subscription and update list', async () => {
    mockAPI.deleteSubscription.mockResolvedValue(undefined);
    
    const { getByText, queryByText } = render(<SubscriptionsTab />);
    
    // Wait for subscriptions to load
    await waitFor(() => expect(getByText('Test Subscription')).toBeInTheDocument());
    
    // Click delete
    fireEvent.click(getByText('Delete'));
    
    // Confirm deletion
    fireEvent.click(getByText('Delete Subscription'));
    
    // Wait for API call and list update
    await waitFor(() => {
      expect(mockAPI.deleteSubscription).toHaveBeenCalledWith(1);
      expect(queryByText('Test Subscription')).not.toBeInTheDocument();
    });
    
    // Check success toast
    expect(getByText(/deleted successfully/i)).toBeInTheDocument();
  });
  
  it('should handle delete error and rollback', async () => {
    mockAPI.deleteSubscription.mockRejectedValue(new Error('API Error'));
    
    const { getByText } = render(<SubscriptionsTab />);
    
    await waitFor(() => expect(getByText('Test Subscription')).toBeInTheDocument());
    
    fireEvent.click(getByText('Delete'));
    fireEvent.click(getByText('Delete Subscription'));
    
    // Subscription should still be there after error
    await waitFor(() => {
      expect(getByText('Test Subscription')).toBeInTheDocument();
      expect(getByText(/failed to delete/i)).toBeInTheDocument();
    });
  });
  
  it('should pause subscription optimistically', async () => {
    mockAPI.updateSubscription.mockResolvedValue({
      ...mockSubscription,
      is_active: false
    });
    
    const { getByText, queryByText } = render(<SubscriptionsTab />);
    
    await waitFor(() => expect(getByText('Pause')).toBeInTheDocument());
    
    fireEvent.click(getByText('Pause'));
    
    // Should immediately show Resume button (optimistic)
    expect(queryByText('Pause')).not.toBeInTheDocument();
    expect(getByText('Resume')).toBeInTheDocument();
    
    // Wait for API confirmation
    await waitFor(() => {
      expect(mockAPI.updateSubscription).toHaveBeenCalledWith(1, { is_active: false });
    });
  });
});
```

### Accessibility Tests

```typescript
describe('Accessibility', () => {
  it('should support keyboard navigation for delete', () => {
    const onDelete = jest.fn();
    const { getByText } = render(
      <SubscriptionCard subscription={mockSubscription} onDelete={onDelete} />
    );
    
    const deleteButton = getByText('Delete');
    deleteButton.focus();
    
    fireEvent.keyDown(deleteButton, { key: 'Enter' });
    
    expect(onDelete).toHaveBeenCalled();
  });
  
  it('should trap focus in confirmation modal', () => {
    const { getByText } = render(
      <DeleteConfirmationModal
        show={true}
        subscriptionName="Test"
        onConfirm={jest.fn()}
        onCancel={jest.fn()}
        isDeleting={false}
      />
    );
    
    const cancelButton = getByText('Cancel');
    const deleteButton = getByText('Delete Subscription');
    
    // First tab goes to cancel
    cancelButton.focus();
    expect(document.activeElement).toBe(cancelButton);
    
    // Tab should move to delete
    fireEvent.keyDown(cancelButton, { key: 'Tab' });
    expect(document.activeElement).toBe(deleteButton);
    
    // Tab should wrap back to cancel
    fireEvent.keyDown(deleteButton, { key: 'Tab' });
    expect(document.activeElement).toBe(cancelButton);
  });
  
  it('should have proper ARIA labels', () => {
    const { getByLabelText } = render(
      <DeleteConfirmationModal
        show={true}
        subscriptionName="Test"
        onConfirm={jest.fn()}
        onCancel={jest.fn()}
        isDeleting={false}
      />
    );
    
    expect(getByLabelText(/delete subscription/i)).toBeInTheDocument();
  });
});
```

## Implementation Notes

### Optimistic Updates Best Practices

1. **Always provide rollback** - Store previous state in context
2. **Show loading indicators** - Even with optimistic updates, show that action is processing
3. **Invalidate queries on settled** - Always refetch to ensure consistency
4. **Handle race conditions** - Cancel pending queries before optimistic update

### UX Considerations

1. **Delete is permanent** - Make this clear in the modal
2. **Pause is reversible** - No confirmation needed for pause/resume
3. **Provide undo option** (future) - Toast with undo button for 5 seconds
4. **Disable rapid clicks** - Prevent double-clicking actions
5. **Show deletion in progress** - Fade out card or show spinner overlay

### Performance

- Debounce rapid pause/resume toggles (prevent API spam)
- Use optimistic updates to make UI feel instant
- Batch delete operations (future enhancement)

### Error Recovery

If delete fails:
1. Rollback optimistic update
2. Show error toast with reason
3. Keep subscription in list
4. Optional: Offer retry button

If pause/resume fails:
1. Rollback optimistic update
2. Show error toast
3. Log error for debugging

## Related Files

**To Modify:**
- `frontend/src/components/notifications/SubscriptionCard.tsx` (from 4.1)
- `frontend/src/components/notifications/SubscriptionsTab.tsx` (from 4.1)

**To Create:**
- `frontend/src/components/notifications/DeleteConfirmationModal.tsx`
- `frontend/src/hooks/useDeleteSubscription.ts` (optional - extracted hook)
- `frontend/src/hooks/usePauseSubscription.ts` (optional - extracted hook)

**To Reference:**
- `frontend/src/api/notifications/client.ts` (Task 1.1)
- Modal component from design system
- Toast component from design system

## Definition of Done

- [ ] Pause/resume functionality implemented and working
- [ ] Delete confirmation modal implemented
- [ ] Delete functionality working with confirmation
- [ ] Optimistic updates working for both pause and delete
- [ ] Error handling with rollback working
- [ ] Success/error toasts showing
- [ ] Loading states displayed correctly
- [ ] Unit tests written and passing (>85% coverage)
- [ ] Integration tests written and passing
- [ ] Accessibility tests passing
- [ ] Keyboard shortcuts working
- [ ] Code reviewed and approved
- [ ] User testing completed
- [ ] Documentation updated
- [ ] Merged to feature branch

## Future Enhancements (Out of Scope)

- Undo deletion within 5 seconds (toast with undo button)
- Bulk operations (select multiple, delete/pause all)
- Confirmation preferences (skip confirmation for experienced users)
- Archive subscriptions instead of delete (soft delete)
- Subscription templates (save deleted subscription as template)

---

**Notes:**
- Keep confirmation modal simple and clear
- Use danger color (red) for delete actions
- Use neutral color for pause/resume
- Test edge cases thoroughly (401, 404, 500 errors)
