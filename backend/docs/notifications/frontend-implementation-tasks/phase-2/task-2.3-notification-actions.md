# Task 2.3: Notification Actions

**Status:** ⬜ Not Started  
**Priority:** 🔴 Critical (MVP)  
**Estimated Effort:** 2 days  
**Assignee:** _TBD_

---

## Description

Implement action buttons and handlers for notifications: mark as read/unread, dismiss, navigate to decision, and mark all as read.

## Goals

- Enable users to manage notification read status
- Allow dismissing notifications
- Navigate to decision from notification (with auto-mark-read)
- Provide "mark all as read" bulk action
- Optimistic UI updates for responsiveness

## Technical Requirements

### Action Buttons

```typescript
interface NotificationActionsProps {
  notification: Notification;
  onMarkRead: (id: number) => Promise<void>;
  onMarkUnread: (id: number) => Promise<void>;
  onDismiss: (id: number) => Promise<void>;
  onNavigate: (notification: Notification) => void;
}
```

### Actions Required

1. **View** - Navigate to decision + mark as read
2. **Mark Read** - Toggle read status
3. **Dismiss** - Remove from list
4. **Mark All Read** - Bulk action in header

## Dependencies

- Task 1.1 (API client - notification actions)
- Task 2.2 (Notifications list)
- React Router for navigation

## Acceptance Criteria

- [ ] "View" button navigates to decision page
- [ ] Clicking "View" marks notification as read automatically
- [ ] "Mark Read" toggles to "Mark Unread" based on state
- [ ] Read/unread toggle updates UI immediately (optimistic)
- [ ] "Dismiss" removes notification from list with confirmation
- [ ] "Mark All Read" button in header works
- [ ] "Mark All Read" confirms if count > 10
- [ ] Toast notifications for successful actions
- [ ] Error handling with retry option
- [ ] Optimistic updates roll back on error
- [ ] Action buttons disabled during API call
- [ ] Keyboard shortcuts work (Enter to view, D to dismiss)

## Testing Requirements

### Unit Tests

```typescript
describe('Notification Actions', () => {
  it('should navigate to decision and mark as read when clicking View', async () => {
    const notification = createMockNotification({ id: 1, is_read: false });
    const navigate = jest.fn();
    const markRead = jest.fn().mockResolvedValue(undefined);
    
    render(
      <NotificationCard 
        notification={notification}
        onNavigate={navigate}
        onMarkRead={markRead}
      />
    );
    
    const viewButton = screen.getByRole('button', { name: /view/i });
    fireEvent.click(viewButton);
    
    expect(markRead).toHaveBeenCalledWith(1);
    await waitFor(() => {
      expect(navigate).toHaveBeenCalledWith('/decision/ABC123');
    });
  });

  it('should toggle read status when clicking Mark Read', async () => {
    const notification = createMockNotification({ id: 1, is_read: false });
    const markRead = jest.fn().mockResolvedValue(undefined);
    
    render(
      <NotificationCard
        notification={notification}
        onMarkRead={markRead}
      />
    );
    
    const markReadButton = screen.getByRole('button', { name: /mark read/i });
    fireEvent.click(markReadButton);
    
    expect(markReadButton).toBeDisabled();
    await waitFor(() => {
      expect(markRead).toHaveBeenCalledWith(1);
    });
  });

  it('should optimistically update UI before API responds', async () => {
    const notification = createMockNotification({ id: 1, is_read: false });
    let resolveMarkRead: () => void;
    const markReadPromise = new Promise<void>(resolve => {
      resolveMarkRead = resolve;
    });
    
    const markRead = jest.fn().mockReturnValue(markReadPromise);
    
    const { rerender } = render(
      <NotificationCard notification={notification} onMarkRead={markRead} />
    );
    
    // Initially unread
    expect(screen.getByTestId('notification-card')).toHaveClass('notification-card-unread');
    
    // Click mark read
    fireEvent.click(screen.getByRole('button', { name: /mark read/i }));
    
    // Should update immediately
    expect(screen.getByTestId('notification-card')).not.toHaveClass('notification-card-unread');
    
    // Resolve API call
    resolveMarkRead!();
  });

  it('should rollback optimistic update on error', async () => {
    const notification = createMockNotification({ id: 1, is_read: false });
    const markRead = jest.fn().mockRejectedValue(new Error('Network error'));
    
    render(
      <NotificationCard notification={notification} onMarkRead={markRead} />
    );
    
    fireEvent.click(screen.getByRole('button', { name: /mark read/i }));
    
    await waitFor(() => {
      // Should revert to unread
      expect(screen.getByTestId('notification-card')).toHaveClass('notification-card-unread');
      expect(screen.getByText(/failed to mark as read/i)).toBeInTheDocument();
    });
  });

  it('should confirm before dismissing notification', async () => {
    const notification = createMockNotification({ id: 1 });
    const dismiss = jest.fn().mockResolvedValue(undefined);
    
    window.confirm = jest.fn().mockReturnValue(false);
    
    render(
      <NotificationCard notification={notification} onDismiss={dismiss} />
    );
    
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }));
    
    expect(window.confirm).toHaveBeenCalled();
    expect(dismiss).not.toHaveBeenCalled();
  });

  it('should dismiss notification when confirmed', async () => {
    const notification = createMockNotification({ id: 1 });
    const dismiss = jest.fn().mockResolvedValue(undefined);
    
    window.confirm = jest.fn().mockReturnValue(true);
    
    render(
      <NotificationCard notification={notification} onDismiss={dismiss} />
    );
    
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }));
    
    await waitFor(() => {
      expect(dismiss).toHaveBeenCalledWith(1);
    });
  });
});

describe('Mark All Read', () => {
  it('should mark all notifications as read', async () => {
    const markAllRead = jest.fn().mockResolvedValue({ marked_read: 5 });
    mockAPI.markAllNotificationsRead = markAllRead;
    
    render(<NotificationsList />);
    
    await waitFor(() => {
      expect(screen.getAllByTestId('notification-card-unread')).toHaveLength(5);
    });
    
    const markAllButton = screen.getByRole('button', { name: /mark all read/i });
    fireEvent.click(markAllButton);
    
    await waitFor(() => {
      expect(markAllRead).toHaveBeenCalled();
      expect(screen.queryByTestId('notification-card-unread')).not.toBeInTheDocument();
    });
  });

  it('should confirm before marking all read if count > 10', async () => {
    const notifications = Array.from({ length: 15 }, (_, i) => 
      createMockNotification({ id: i, is_read: false })
    );
    mockAPI.listNotifications.mockResolvedValue(notifications);
    
    window.confirm = jest.fn().mockReturnValue(false);
    
    render(<NotificationsList />);
    
    await waitFor(() => {
      expect(screen.getAllByTestId('notification-card')).toHaveLength(15);
    });
    
    fireEvent.click(screen.getByRole('button', { name: /mark all read/i }));
    
    expect(window.confirm).toHaveBeenCalledWith(
      expect.stringContaining('15 notifications')
    );
  });

  it('should show toast on successful mark all read', async () => {
    mockAPI.markAllNotificationsRead.mockResolvedValue({ marked_read: 5 });
    
    render(<NotificationsList />);
    
    await waitFor(() => screen.getByRole('button', { name: /mark all read/i }));
    
    fireEvent.click(screen.getByRole('button', { name: /mark all read/i }));
    
    await waitFor(() => {
      expect(screen.getByText(/5 notifications marked as read/i)).toBeInTheDocument();
    });
  });
});
```

### Integration Tests

```typescript
describe('Notification Actions Integration', () => {
  it('should handle complete flow: view → navigate → auto mark read', async () => {
    const notification = createMockNotification({
      id: 1,
      decision_ada: 'ABC123',
      is_read: false
    });
    
    mockAPI.listNotifications.mockResolvedValue([notification]);
    mockAPI.markNotificationRead.mockResolvedValue(undefined);
    
    const { history } = renderWithRouter(<NotificationsList />);
    
    await waitFor(() => {
      expect(screen.getByText(/test decision/i)).toBeInTheDocument();
    });
    
    fireEvent.click(screen.getByRole('button', { name: /view/i }));
    
    await waitFor(() => {
      expect(mockAPI.markNotificationRead).toHaveBeenCalledWith(1);
      expect(history.location.pathname).toBe('/decision/ABC123');
    });
  });
});
```

## Implementation Notes

### Optimistic Updates Pattern

```typescript
function useNotificationActions(notificationId: number) {
  const queryClient = useQueryClient();
  
  const markRead = useMutation({
    mutationFn: () => notificationAPI.markNotificationRead(notificationId),
    onMutate: async () => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries(['notifications']);
      
      // Snapshot previous value
      const previous = queryClient.getQueryData(['notifications']);
      
      // Optimistically update
      queryClient.setQueryData(['notifications'], (old: Notification[]) => 
        old.map(n => n.id === notificationId ? { ...n, is_read: true } : n)
      );
      
      return { previous };
    },
    onError: (err, variables, context) => {
      // Rollback
      if (context?.previous) {
        queryClient.setQueryData(['notifications'], context.previous);
      }
      toast.error('Failed to mark as read');
    },
    onSuccess: () => {
      toast.success('Marked as read');
    }
  });
  
  return { markRead };
}
```

### Navigation with Auto Mark Read

```typescript
async function handleViewNotification(notification: Notification) {
  try {
    // Mark as read first
    if (!notification.is_read) {
      await notificationAPI.markNotificationRead(notification.id);
    }
    
    // Then navigate
    navigate(`/decision/${notification.decision_ada}`);
    
    // Close sidebar
    onCloseSidebar();
  } catch (error) {
    toast.error('Failed to open decision');
  }
}
```

### Action Buttons Component

```typescript
function NotificationActions({ notification, ...handlers }: NotificationActionsProps) {
  const [isActing, setIsActing] = useState(false);
  
  const handleMarkReadToggle = async () => {
    setIsActing(true);
    try {
      if (notification.is_read) {
        await handlers.onMarkUnread(notification.id);
      } else {
        await handlers.onMarkRead(notification.id);
      }
    } finally {
      setIsActing(false);
    }
  };
  
  const handleDismiss = async () => {
    const confirmed = window.confirm('Dismiss this notification?');
    if (!confirmed) return;
    
    setIsActing(true);
    try {
      await handlers.onDismiss(notification.id);
    } finally {
      setIsActing(false);
    }
  };
  
  return (
    <div className="notification-actions">
      <button
        onClick={() => handlers.onNavigate(notification)}
        className="btn-primary"
        disabled={isActing}
      >
        👁️ View
      </button>
      
      <button
        onClick={handleMarkReadToggle}
        className="btn-secondary"
        disabled={isActing}
      >
        {notification.is_read ? '✉️ Mark Unread' : '✓ Mark Read'}
      </button>
      
      <button
        onClick={handleDismiss}
        className="btn-danger"
        disabled={isActing}
      >
        ✖ Dismiss
      </button>
    </div>
  );
}
```

## Related Files

- `frontend/src/components/NotificationSidebar/NotificationActions.tsx` (new)
- `frontend/src/hooks/useNotificationActions.ts` (new)
- Task 2.2 components (NotificationCard, NotificationsList)

## Definition of Done

- [ ] All code written and reviewed
- [ ] All unit tests passing (>90% coverage)
- [ ] Integration tests passing
- [ ] Optimistic updates working correctly
- [ ] Error handling with rollback tested
- [ ] Toast notifications appear appropriately
- [ ] Keyboard shortcuts implemented
- [ ] Navigation works correctly
- [ ] Code merged to feature branch

## Additional Resources

- [UI Specification - Notification Actions](../../FRONTEND_UI_SPECIFICATION.md#notification-item-card)
- [Integration Guide - Notification Management](../../FRONTEND_INTEGRATION_GUIDE.md#notification-management)
- React Query: [Optimistic Updates](https://tanstack.com/query/latest/docs/react/guides/optimistic-updates)

---

**Notes:**
- Consider rate limiting on action buttons (debounce rapid clicks)
- May want undo functionality for dismiss action
- Consider batch actions for selecting multiple notifications
