# Task 2.2: Notifications List (Read-Only)

**Status:** ⬜ Not Started  
**Priority:** 🔴 Critical (MVP)  
**Estimated Effort:** 3 days  
**Assignee:** _TBD_

---

## Description

Implement the notifications list component that displays user's notifications in a scrollable list. This is read-only view only - actions (mark read, dismiss) come in Task 2.3.

## Goals

- Display list of notifications with all relevant information
- Show read/unread visual states
- Handle loading, empty, and error states
- Implement pagination or infinite scroll
- Provide good performance with large lists

## Technical Requirements

### Component Interface

```typescript
interface NotificationsListProps {
  className?: string;
}

interface NotificationCardProps {
  notification: Notification;
  onClick?: (notification: Notification) => void;
}
```

### Data Fetching

```typescript
function useNotifications(filters?: NotificationFilters) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [hasMore, setHasMore] = useState(true);
  
  const loadMore = async () => {
    // Fetch next page
  };
  
  const refresh = async () => {
    // Reload from start
  };
  
  return { notifications, isLoading, error, hasMore, loadMore, refresh };
}
```

### Notification Card Layout

```
┌───────────────────────────────────────┐
│ ⭐ ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ                      │ ← Organization/target name
│ New decision: Ανάθεση σύμβασης...     │ ← Decision subject (truncated)
│ ADA: ΩΑΒΓ1234567-ΨΣΘ                 │ ← ADA
│ Amount: €50,000.00                     │ ← Amount (if present)
│ Matched: "procurement" keyword         │ ← Match reason
│                                        │
│ 2 hours ago                            │ ← Relative timestamp
└───────────────────────────────────────┘
```

### Visual States

- **Unread:** Bold text, colored left border (e.g., blue 4px), slight background highlight
- **Read:** Normal text, no border, muted colors
- **Dismissed:** Not shown (filtered out by default)
- **Hover:** Subtle background change, pointer cursor

## Dependencies

- Task 1.1 (API client - listNotifications)
- Task 2.1 (Sidebar shell)
- Notification types from API client

## Acceptance Criteria

- [ ] Displays list of notifications fetched from API
- [ ] Each notification card shows all required information
- [ ] Unread notifications visually distinct from read
- [ ] Clicking notification is possible (handler prop)
- [ ] Loading state shows skeleton cards (3-5)
- [ ] Empty state shows helpful message and CTA
- [ ] Error state shows error message and retry button
- [ ] Infinite scroll loads more notifications
- [ ] Loading indicator appears at bottom during load more
- [ ] Timestamps are relative and human-readable ("2 hours ago")
- [ ] Long text (subject, match reason) is truncated with ellipsis
- [ ] Decision amount formatted as currency
- [ ] Subscription type icon displayed correctly
- [ ] List is scrollable within sidebar
- [ ] Performance: smooth scrolling with 100+ items

## Testing Requirements

### Unit Tests

```typescript
describe('NotificationsList', () => {
  it('should display notifications when loaded', async () => {
    const mockNotifications = [
      createMockNotification({ id: 1, decision_subject: 'Test Decision 1' }),
      createMockNotification({ id: 2, decision_subject: 'Test Decision 2' }),
    ];
    
    mockAPI.listNotifications.mockResolvedValue(mockNotifications);
    
    render(<NotificationsList />);
    
    await waitFor(() => {
      expect(screen.getByText('Test Decision 1')).toBeInTheDocument();
      expect(screen.getByText('Test Decision 2')).toBeInTheDocument();
    });
  });

  it('should show loading skeleton while fetching', () => {
    mockAPI.listNotifications.mockReturnValue(new Promise(() => {})); // Never resolves
    
    render(<NotificationsList />);
    
    expect(screen.getAllByTestId('notification-skeleton')).toHaveLength(5);
  });

  it('should show empty state when no notifications', async () => {
    mockAPI.listNotifications.mockResolvedValue([]);
    
    render(<NotificationsList />);
    
    await waitFor(() => {
      expect(screen.getByText(/no new notifications/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /create subscription/i })).toBeInTheDocument();
    });
  });

  it('should show error state on API failure', async () => {
    mockAPI.listNotifications.mockRejectedValue(new Error('Network error'));
    
    render(<NotificationsList />);
    
    await waitFor(() => {
      expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });
  });

  it('should retry loading on retry button click', async () => {
    mockAPI.listNotifications
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce([createMockNotification({ id: 1 })]);
    
    render(<NotificationsList />);
    
    await waitFor(() => {
      expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
    });
    
    const retryButton = screen.getByRole('button', { name: /retry/i });
    fireEvent.click(retryButton);
    
    await waitFor(() => {
      expect(screen.getByText(/Test Decision/i)).toBeInTheDocument();
    });
  });
});

describe('NotificationCard', () => {
  it('should display unread notification with distinct styling', () => {
    const notification = createMockNotification({ is_read: false });
    
    const { container } = render(<NotificationCard notification={notification} />);
    
    const card = container.firstChild;
    expect(card).toHaveClass('notification-card-unread');
    expect(screen.getByText(/test decision/i)).toHaveStyle({ fontWeight: 'bold' });
  });

  it('should display read notification with muted styling', () => {
    const notification = createMockNotification({ is_read: true });
    
    const { container } = render(<NotificationCard notification={notification} />);
    
    const card = container.firstChild;
    expect(card).not.toHaveClass('notification-card-unread');
  });

  it('should display all notification details', () => {
    const notification = createMockNotification({
      organization_label: 'ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ',
      decision_subject: 'Ανάθεση σύμβασης προμηθειών',
      decision_ada: 'ΩΑΒΓ1234567-ΨΣΘ',
      decision_amount: '50000.00',
      match_reason: 'Matched keywords: procurement, contract',
      created_at: '2026-03-07T10:00:00Z'
    });
    
    render(<NotificationCard notification={notification} />);
    
    expect(screen.getByText('ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ')).toBeInTheDocument();
    expect(screen.getByText(/Ανάθεση σύμβασης/i)).toBeInTheDocument();
    expect(screen.getByText('ΩΑΒΓ1234567-ΨΣΘ')).toBeInTheDocument();
    expect(screen.getByText('€50,000.00')).toBeInTheDocument();
    expect(screen.getByText(/Matched keywords/)).toBeInTheDocument();
    expect(screen.getByText(/hours ago/i)).toBeInTheDocument();
  });

  it('should truncate long decision subjects', () => {
    const longSubject = 'A'.repeat(200);
    const notification = createMockNotification({ decision_subject: longSubject });
    
    render(<NotificationCard notification={notification} />);
    
    const subjectElement = screen.getByTestId('decision-subject');
    expect(subjectElement).toHaveTextContent(/A+\.\.\./);
    expect(subjectElement.textContent).toHaveLength(103); // 100 chars + '...'
  });

  it('should format relative timestamps correctly', () => {
    const notification = createMockNotification({
      created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString() // 2 hours ago
    });
    
    render(<NotificationCard notification={notification} />);
    
    expect(screen.getByText('2 hours ago')).toBeInTheDocument();
  });

  it('should call onClick when card is clicked', () => {
    const notification = createMockNotification({ id: 1 });
    const onClick = jest.fn();
    
    render(<NotificationCard notification={notification} onClick={onClick} />);
    
    const card = screen.getByTestId('notification-card');
    fireEvent.click(card);
    
    expect(onClick).toHaveBeenCalledWith(notification);
  });

  it('should display subscription type icon', () => {
    const notification = createMockNotification({ subscription_type: 'organization' });
    
    render(<NotificationCard notification={notification} />);
    
    expect(screen.getByTestId('subscription-icon-organization')).toBeInTheDocument();
  });
});

describe('Infinite Scroll', () => {
  it('should load more notifications when scrolling to bottom', async () => {
    const page1 = [createMockNotification({ id: 1 }), createMockNotification({ id: 2 })];
    const page2 = [createMockNotification({ id: 3 }), createMockNotification({ id: 4 })];
    
    mockAPI.listNotifications
      .mockResolvedValueOnce(page1)
      .mockResolvedValueOnce(page2);
    
    const { container } = render(<NotificationsList />);
    
    await waitFor(() => {
      expect(screen.getAllByTestId('notification-card')).toHaveLength(2);
    });
    
    // Scroll to bottom
    const scrollContainer = container.querySelector('.notifications-list');
    fireEvent.scroll(scrollContainer!, { target: { scrollTop: 1000 } });
    
    await waitFor(() => {
      expect(screen.getAllByTestId('notification-card')).toHaveLength(4);
    });
  });

  it('should show loading indicator when loading more', async () => {
    mockAPI.listNotifications.mockResolvedValue([createMockNotification({ id: 1 })]);
    
    render(<NotificationsList />);
    
    await waitFor(() => {
      expect(screen.getByTestId('notification-card')).toBeInTheDocument();
    });
    
    // Trigger load more
    mockAPI.listNotifications.mockReturnValue(new Promise(() => {})); // Pending
    fireEvent.scroll(screen.getByTestId('notifications-list'), { target: { scrollTop: 1000 } });
    
    expect(screen.getByTestId('load-more-spinner')).toBeInTheDocument();
  });
});
```

## Implementation Notes

### Component Structure

```typescript
export function NotificationsList({ className }: NotificationsListProps) {
  const { 
    notifications, 
    isLoading, 
    error, 
    hasMore, 
    loadMore 
  } = useNotifications();
  
  const listRef = useRef<HTMLDivElement>(null);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  
  // Infinite scroll handler
  const handleScroll = useCallback(async () => {
    if (!listRef.current || !hasMore || isLoadingMore) return;
    
    const { scrollTop, scrollHeight, clientHeight } = listRef.current;
    const bottomReached = scrollHeight - scrollTop - clientHeight < 100;
    
    if (bottomReached) {
      setIsLoadingMore(true);
      await loadMore();
      setIsLoadingMore(false);
    }
  }, [hasMore, isLoadingMore, loadMore]);
  
  useEffect(() => {
    const list = listRef.current;
    if (list) {
      list.addEventListener('scroll', handleScroll);
      return () => list.removeEventListener('scroll', handleScroll);
    }
  }, [handleScroll]);
  
  if (isLoading) {
    return <NotificationListSkeleton />;
  }
  
  if (error) {
    return <NotificationListError error={error} onRetry={() => window.location.reload()} />;
  }
  
  if (notifications.length === 0) {
    return <NotificationListEmpty />;
  }
  
  return (
    <div ref={listRef} className={cn('notifications-list', className)} data-testid="notifications-list">
      {notifications.map(notification => (
        <NotificationCard
          key={notification.id}
          notification={notification}
          onClick={handleNotificationClick}
        />
      ))}
      {isLoadingMore && <div className="load-more-spinner" data-testid="load-more-spinner" />}
    </div>
  );
}

export function NotificationCard({ notification, onClick }: NotificationCardProps) {
  const isUnread = !notification.is_read;
  
  return (
    <div
      className={cn('notification-card', {
        'notification-card-unread': isUnread
      })}
      onClick={() => onClick?.(notification)}
      data-testid="notification-card"
    >
      <div className="notification-header">
        <SubscriptionTypeIcon type={notification.subscription_type} />
        <span className="notification-target">
          {notification.organization_label || notification.entity_name || notification.signer_name}
        </span>
      </div>
      
      <div className="notification-body">
        <p className="decision-subject" data-testid="decision-subject">
          {truncate(notification.decision_subject, 100)}
        </p>
        <p className="decision-ada">ADA: {notification.decision_ada}</p>
        {notification.decision_amount && (
          <p className="decision-amount">
            {formatCurrency(notification.decision_amount)}
          </p>
        )}
        <p className="match-reason">{notification.match_reason}</p>
      </div>
      
      <div className="notification-footer">
        <time dateTime={notification.created_at}>
          {formatRelativeTime(notification.created_at)}
        </time>
      </div>
    </div>
  );
}
```

### Empty State Component

```typescript
function NotificationListEmpty() {
  return (
    <div className="notification-list-empty">
      <div className="empty-icon">🔕</div>
      <h3>No new notifications</h3>
      <p>You'll be notified when decisions matching your subscriptions appear.</p>
      <button onClick={handleCreateSubscription}>
        Create Subscription
      </button>
    </div>
  );
}
```

## Related Files

- `frontend/src/components/NotificationSidebar/NotificationsList.tsx` (new)
- `frontend/src/components/NotificationSidebar/NotificationCard.tsx` (new)
- `frontend/src/hooks/useNotifications.ts` (new)
- `frontend/src/utils/formatters.ts` (currency, time formatting)

##Definition of Done

- [ ] All code written and reviewed
- [ ] All unit tests passing (>85% coverage)
- [ ] Infinite scroll working smoothly
- [ ] All states (loading, empty, error) implemented
- [ ] Performance tested with 100+ items
- [ ] Responsive layout works on all screen sizes
- [ ] Timestamps update when component stays mounted
- [ ] Code merged to feature branch

## Additional Resources

- [UI Specification - Notification Center](../../FRONTEND_UI_SPECIFICATION.md#tab-1-notifications)
- [Integration Guide - Notification List Endpoint](../../FRONTEND_INTEGRATION_GUIDE.md#1-list-notifications)

---

**Notes:**
- Use `react-window` or `react-virtualized` if performance issues with large lists
- Consider pull-to-refresh on mobile
- Timestamps should update every minute for "X minutes ago" accuracy
