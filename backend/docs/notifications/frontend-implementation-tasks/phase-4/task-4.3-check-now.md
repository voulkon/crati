# Task 4.3: Manual Check Now Action

**Status:** ⬜ Not Started  
**Priority:** 🟡 High Priority  
**Estimated Effort:** 1-2 days  
**Assignee:** _TBD_

---

## Description

Implement the "Check Now" functionality that allows users to manually trigger an immediate check for new matching decisions for a specific subscription. This includes UI feedback, progress indication, and result notification.

## Goals

- Allow users to manually trigger subscription checks on-demand
- Provide real-time feedback during the check process
- Show results (new notifications found or none)
- Handle errors gracefully
- Prevent abuse with rate limiting feedback

## Technical Requirements

### API Integration

```typescript
// API call with optional lookback period
async function triggerCheckNow(
  subscriptionId: number,
  lookbackDays: number = 30
): Promise<CheckNowResponse> {
  const response = await notificationAPI.triggerCheckNow(subscriptionId, lookbackDays);
  return response;
}

interface CheckNowResponse {
  status: 'check started' | 'already checking' | 'rate limited';
  subscription_id: number;
  estimated_duration_seconds?: number;
  lookback_days: number;
  message?: string;
  retry_after?: number; // For rate limiting
}
```

### Check Now Button Implementation

```typescript
interface CheckNowButtonProps {
  subscriptionId: number;
  isActive: boolean;
  lastChecked?: string;
  onCheckStarted?: () => void;
  onCheckCompleted?: (notificationsCount: number) => void;
}

function CheckNowButton({
  subscriptionId,
  isActive,
  lastChecked,
  onCheckStarted,
  onCheckCompleted
}: CheckNowButtonProps) {
  const [isChecking, setIsChecking] = useState(false);
  const [checkProgress, setCheckProgress] = useState(0);
  const queryClient = useQueryClient();
  
  const checkNowMutation = useMutation({
    mutationFn: ({ id, lookback }: { id: number; lookback?: number }) =>
      notificationAPI.triggerCheckNow(id, lookback),
    
    onMutate: () => {
      setIsChecking(true);
      setCheckProgress(0);
      onCheckStarted?.();
    },
    
    onSuccess: async (data) => {
      if (data.status === 'already checking') {
        toast.info('This subscription is already being checked. Please wait.');
        setIsChecking(false);
        return;
      }
      
      if (data.status === 'rate limited') {
        toast.warning(
          `Please wait ${data.retry_after} seconds before checking again.`,
          { duration: 5000 }
        );
        setIsChecking(false);
        return;
      }
      
      // Start polling for completion
      await pollForCheckCompletion(subscriptionId);
    },
    
    onError: (error: any) => {
      setIsChecking(false);
      setCheckProgress(0);
      
      if (error.status === 429) {
        toast.error('Too many requests. Please wait before trying again.');
      } else {
        toast.error('Failed to start check. Please try again.');
      }
    }
  });
  
  const pollForCheckCompletion = async (id: number) => {
    const maxPolls = 30; // 30 seconds max
    const pollInterval = 1000; // 1 second
    let pollCount = 0;
    
    const poll = async () => {
      pollCount++;
      
      // Simulate progress (real implementation would get actual progress from API)
      setCheckProgress((pollCount / maxPolls) * 100);
      
      // Get updated subscription
      const subscription = await queryClient.fetchQuery(
        ['subscription', id],
        () => notificationAPI.getSubscription(id)
      );
      
      // Check if last_checked_at has been updated
      const wasRecentlyChecked = subscription.last_checked_at &&
        new Date(subscription.last_checked_at).getTime() > Date.now() - 60000; // Within last minute
      
      if (wasRecentlyChecked || pollCount >= maxPolls) {
        setIsChecking(false);
        setCheckProgress(100);
        
        // Refetch notifications and subscriptions
        await queryClient.invalidateQueries(['notifications']);
        await queryClient.invalidateQueries(['subscriptions']);
        await queryClient.invalidateQueries(['unread-count']);
        
        // Get notification count (simplified - actual may need endpoint)
        const notifications = queryClient.getQueryData<Notification[]>(['notifications']);
        const newNotifications = notifications?.filter(
          n => n.subscription_id === id &&
          new Date(n.created_at).getTime() > Date.now() - 60000
        ) || [];
        
        if (newNotifications.length > 0) {
          toast.success(
            `Check complete! Found ${newNotifications.length} new ${
              newNotifications.length === 1 ? 'notification' : 'notifications'
            }.`,
            { duration: 5000 }
          );
        } else {
          toast.info('Check complete. No new matching decisions found.');
        }
        
        onCheckCompleted?.(newNotifications.length);
        return;
      }
      
      // Continue polling
      setTimeout(poll, pollInterval);
    };
    
    poll();
  };
  
  const handleCheckNow = () => {
    if (!isActive) {
      toast.warning('This subscription is paused. Activate it to check for new decisions.');
      return;
    }
    
    checkNowMutation.mutate({ id: subscriptionId, lookback: 30 });
  };
  
  return (
    <button
      onClick={handleCheckNow}
      disabled={isChecking || !isActive}
      className={`btn-check-now ${!isActive ? 'disabled' : ''}`}
      title={!isActive ? 'Activate subscription to check' : 'Check for new matching decisions'}
    >
      {isChecking ? (
        <span className="checking-state">
          <Spinner size="small" />
          <span>Checking... {Math.round(checkProgress)}%</span>
        </span>
      ) : (
        <>
          <span className="icon">🔄</span>
          <span>Check Now</span>
        </>
      )}
    </button>
  );
}
```

### Check Now Modal (Advanced Option)

For more control, provide a modal with options:

```typescript
interface CheckNowModalProps {
  show: boolean;
  subscription: NotificationSubscription;
  onClose: () => void;
  onCheckStarted: () => void;
}

function CheckNowModal({ show, subscription, onClose, onCheckStarted }: CheckNowModalProps) {
  const [lookbackDays, setLookbackDays] = useState(30);
  const [isChecking, setIsChecking] = useState(false);
  
  if (!show) return null;
  
  return (
    <Modal onClose={onClose} size="medium">
      <ModalHeader>
        <h3>Check for New Decisions</h3>
      </ModalHeader>
      
      <ModalBody>
        <div className="check-now-options">
          <p>
            Manually check for decisions matching:{' '}
            <strong>{subscription.user_alias || 'this subscription'}</strong>
          </p>
          
          <div className="form-group">
            <label htmlFor="lookback-days">
              Look back how many days?
            </label>
            
            <select
              id="lookback-days"
              value={lookbackDays}
              onChange={(e) => setLookbackDays(Number(e.target.value))}
              disabled={isChecking}
            >
              <option value={7}>Past 7 days</option>
              <option value={14}>Past 2 weeks</option>
              <option value={30}>Past 30 days (default)</option>
              <option value={60}>Past 60 days</option>
              <option value={90}>Past 90 days</option>
            </select>
            
            <small className="help-text">
              Checking longer periods may take more time
            </small>
          </div>
          
          <div className="info-box">
            <strong>Note:</strong> This will only find new decisions that haven't
            been checked before. Already-notified decisions won't create duplicate
            notifications.
          </div>
          
          {subscription.last_checked_at && (
            <div className="last-checked">
              Last checked: {formatDistanceToNow(new Date(subscription.last_checked_at))} ago
            </div>
          )}
        </div>
      </ModalBody>
      
      <ModalFooter>
        <button
          onClick={onClose}
          disabled={isChecking}
          className="btn-secondary"
        >
          Cancel
        </button>
        
        <button
          onClick={() => {
            setIsChecking(true);
            onCheckStarted();
            // Trigger check with selected lookback
            // (actual implementation in parent component)
          }}
          disabled={isChecking}
          className="btn-primary"
        >
          {isChecking ? (
            <>
              <Spinner size="small" /> Checking...
            </>
          ) : (
            'Start Check'
          )}
        </button>
      </ModalFooter>
    </Modal>
  );
}
```

### Progress Indicator in Subscription Card

Update the subscription card to show check-in-progress state:

```typescript
function SubscriptionCard({ subscription, onCheckNow }: SubscriptionCardProps) {
  const [isChecking, setIsChecking] = useState(false);
  
  return (
    <div className={`subscription-card ${isChecking ? 'checking' : ''}`}>
      {/* Existing card content */}
      
      {isChecking && (
        <div className="check-progress-overlay">
          <Spinner />
          <span>Checking for new decisions...</span>
        </div>
      )}
      
      {/* Last checked timestamp */}
      <div className="subscription-meta">
        <span className="last-checked">
          {subscription.last_checked_at ? (
            <>
              🕐 Last checked: {formatDistanceToNow(new Date(subscription.last_checked_at))} ago
            </>
          ) : (
            <>🕐 Never checked</>
          )}
        </span>
      </div>
      
      {/* Action buttons */}
      <div className="subscription-actions">
        <CheckNowButton
          subscriptionId={subscription.id}
          isActive={subscription.is_active}
          lastChecked={subscription.last_checked_at}
          onCheckStarted={() => setIsChecking(true)}
          onCheckCompleted={() => setIsChecking(false)}
        />
        {/* Other buttons... */}
      </div>
    </div>
  );
}
```

### Rate Limiting Feedback

```typescript
function useCheckNowRateLimit(subscriptionId: number) {
  const [rateLimitUntil, setRateLimitUntil] = useState<Date | null>(null);
  const [canCheck, setCanCheck] = useState(true);
  
  useEffect(() => {
    const checkRateLimit = () => {
      if (rateLimitUntil && rateLimitUntil > new Date()) {
        setCanCheck(false);
      } else {
        setCanCheck(true);
        setRateLimitUntil(null);
      }
    };
    
    const interval = setInterval(checkRateLimit, 1000);
    checkRateLimit();
    
    return () => clearInterval(interval);
  }, [rateLimitUntil]);
  
  const recordCheck = (retryAfter?: number) => {
    if (retryAfter) {
      const now = new Date();
      setRateLimitUntil(new Date(now.getTime() + retryAfter * 1000));
    }
  };
  
  const getRemainingTime = () => {
    if (!rateLimitUntil) return 0;
    return Math.max(0, Math.ceil((rateLimitUntil.getTime() - Date.now()) / 1000));
  };
  
  return { canCheck, recordCheck, remainingTime: getRemainingTime() };
}
```

### Notification After Check Completion

```typescript
function NotificationCheckResult({ notificationCount }: { notificationCount: number }) {
  return (
    <div className="check-result-toast">
      {notificationCount > 0 ? (
        <>
          <span className="icon">✅</span>
          <div>
            <strong>Check Complete!</strong>
            <p>Found {notificationCount} new {notificationCount === 1 ? 'notification' : 'notifications'}</p>
          </div>
          <button onClick={() => {/* Navigate to notifications tab */}}>
            View
          </button>
        </>
      ) : (
        <>
          <span className="icon">ℹ️</span>
          <div>
            <strong>Check Complete</strong>
            <p>No new matching decisions found</p>
          </div>
        </>
      )}
    </div>
  );
}
```

## Dependencies

- Task 4.1: Subscriptions List (Read-Only) - completed
- Task 4.2: Delete & Pause Subscriptions - completed
- Task 1.1: API Client & Type Definitions - completed
- Polling/long-polling mechanism or WebSocket (optional)
- Toast notification library

## Acceptance Criteria

- [ ] Check Now button triggers immediate check via API
- [ ] Button shows loading state during check
- [ ] Progress indicator shows check in progress
- [ ] Poll for completion or detect when check finishes
- [ ] Notification count updates after check completes
- [ ] Success toast shows number of new notifications found
- [ ] Info toast shows when no new notifications found
- [ ] Rate limiting is handled gracefully with countdown
- [ ] Button is disabled for paused subscriptions
- [ ] Last checked timestamp updates after successful check
- [ ] Error handling shows appropriate messages
- [ ] Notification list refreshes automatically after check
- [ ] Unread count updates if new notifications found
- [ ] Button state resets after completion
- [ ] Multiple simultaneous checks are prevented

## Testing Requirements

### Unit Tests

```typescript
describe('CheckNowButton', () => {
  it('should be disabled for paused subscriptions', () => {
    const { getByText } = render(
      <CheckNowButton subscriptionId={1} isActive={false} />
    );
    
    const button = getByText('Check Now');
    expect(button).toBeDisabled();
  });
  
  it('should show loading state when checking', async () => {
    mockAPI.triggerCheckNow.mockResolvedValue({ status: 'check started' });
    
    const { getByText } = render(
      <CheckNowButton subscriptionId={1} isActive={true} />
    );
    
    fireEvent.click(getByText('Check Now'));
    
    await waitFor(() => {
      expect(getByText(/checking/i)).toBeInTheDocument();
    });
  });
  
  it('should show toast when rate limited', async () => {
    mockAPI.triggerCheckNow.mockResolvedValue({
      status: 'rate limited',
      retry_after: 60
    });
    
    const { getByText } = render(
      <CheckNowButton subscriptionId={1} isActive={true} />
    );
    
    fireEvent.click(getByText('Check Now'));
    
    await waitFor(() => {
      expect(toast.warning).toHaveBeenCalledWith(
        expect.stringContaining('60 seconds'),
        expect.anything()
      );
    });
  });
  
  it('should call onCheckCompleted with notification count', async () => {
    const onCheckCompleted = jest.fn();
    mockAPI.triggerCheckNow.mockResolvedValue({ status: 'check started' });
    
    // Mock polling to return immediately with updated subscription
    mockAPI.getSubscription.mockResolvedValue({
      ...mockSubscription,
      last_checked_at: new Date().toISOString()
    });
    
    const { getByText } = render(
      <CheckNowButton
        subscriptionId={1}
        isActive={true}
        onCheckCompleted={onCheckCompleted}
      />
    );
    
    fireEvent.click(getByText('Check Now'));
    
    await waitFor(() => {
      expect(onCheckCompleted).toHaveBeenCalledWith(expect.any(Number));
    }, { timeout: 5000 });
  });
});
```

### Integration Tests

```typescript
describe('Check Now Integration', () => {
  it('should complete full check flow', async () => {
    mockAPI.triggerCheckNow.mockResolvedValue({
      status: 'check started',
      subscription_id: 1,
      lookback_days: 30
    });
    
    mockAPI.getSubscription.mockResolvedValue({
      ...mockSubscription,
      last_checked_at: new Date().toISOString(),
      notification_count: 7
    });
    
    const { getByText } = render(<SubscriptionsTab />);
    
    // Wait for subscriptions to load
    await waitFor(() => expect(getByText('Check Now')).toBeInTheDocument());
    
    // Click check now
    fireEvent.click(getByText('Check Now'));
    
    // Should show checking state
    await waitFor(() => {
      expect(getByText(/checking/i)).toBeInTheDocument();
    });
    
    // Wait for completion
    await waitFor(() => {
      expect(mockAPI.getSubscription).toHaveBeenCalled();
      expect(getByText(/complete/i)).toBeInTheDocument();
    }, { timeout: 5000 });
    
    // Verify notifications were refetched
    expect(mockAPI.listNotifications).toHaveBeenCalled();
  });
  
  it('should handle check error gracefully', async () => {
    mockAPI.triggerCheckNow.mockRejectedValue(new Error('API Error'));
    
    const { getByText } = render(<SubscriptionsTab />);
    
    await waitFor(() => expect(getByText('Check Now')).toBeInTheDocument());
    
    fireEvent.click(getByText('Check Now'));
    
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        expect.stringContaining('failed'),
        expect.anything()
      );
    });
    
    // Button should be re-enabled
    expect(getByText('Check Now')).not.toBeDisabled();
  });
});
```

### E2E Tests

```typescript
describe('Check Now E2E', () => {
  it('should complete check and show new notifications', async () => {
    // Create subscription
    // Click check now
    // Wait for completion
    // Verify new notifications appear in notifications tab
    // Verify unread count updates
  });
});
```

## Implementation Notes

### Backend Behavior

The backend `/api/notifications/subscriptions/{id}/check-now/` endpoint:
- Triggers an async check (Celery task)
- Returns immediately with `status: 'check started'`
- Updates `last_checked_at` when complete
- Creates new notifications for matching decisions
- Prevents duplicate notifications

### Polling Strategy

Since checks are async, frontend must poll to detect completion:

1. **Simple Polling** - Check subscription every 1-2 seconds for updated `last_checked_at`
2. **Exponential Backoff** - Start at 1s, increase to 2s, 4s, etc. (more efficient)
3. **WebSocket** (Phase 8) - Backend pushes completion event

For MVP, use simple polling with 30-second timeout.

### Progress Indication

Backend doesn't provide real-time progress, so:
- Show indeterminate spinner, OR
- Fake progress bar (increase 10% every second up to 80%, then wait for completion)

### Rate Limiting

Backend may rate limit checks (e.g., once per minute per subscription):
- Show countdown "Can check again in 45 seconds"
- Disable button during countdown
- Store rate limit in local state

### Performance

- Don't poll too frequently (1-2 seconds is fine)
- Use single subscription query, not full list
- Cancel polling if component unmounts
- Abort ongoing checks if user navigates away

### UX Considerations

1. **Feedback is critical** - User must know check is happening
2. **Show results** - Clearly indicate if new notifications were found
3. **Make it easy** - Single click, no complicated options (for basic version)
4. **Prevent spam** - Rate limiting prevents abuse
5. **Handle paused subscriptions** - Disable check for paused subs

## Related Files

**To Modify:**
- `frontend/src/components/notifications/SubscriptionCard.tsx` (from 4.1)
- `frontend/src/components/notifications/SubscriptionsTab.tsx` (from 4.1)

**To Create:**
- `frontend/src/components/notifications/CheckNowButton.tsx`
- `frontend/src/components/notifications/CheckNowModal.tsx` (optional)
- `frontend/src/hooks/useCheckNow.ts` (optional - extracted hook)
- `frontend/src/hooks/useCheckNowPoll.ts` (polling logic)

**To Reference:**
- `frontend/src/api/notifications/client.ts` (Task 1.1)
- Toast library for notifications

## Definition of Done

- [ ] Check Now button implemented and functional
- [ ] Loading state shows during check
- [ ] Polling detects check completion
- [ ] Success/failure toasts display
- [ ] Notification count updates after check
- [ ] Last checked timestamp updates
- [ ] Rate limiting handled with feedback
- [ ] Paused subscriptions can't be checked
- [ ] Unit tests written and passing (>85% coverage)
- [ ] Integration tests written and passing
- [ ] E2E test for full flow passing
- [ ] Error states handled gracefully
- [ ] Code reviewed and approved
- [ ] User testing completed
- [ ] Documentation updated
- [ ] Merged to feature branch

## Future Enhancements (Out of Scope)

- Real-time progress updates via WebSocket
- Cancel ongoing check
- Schedule automatic checks
- Batch check all subscriptions
- Check history log
- Custom lookback period in UI
- Notification preview before creating

---

**Notes:**
- Keep check flow simple for MVP
- Advanced options (lookback period) can be added later
- Focus on clear feedback and error handling
- Test with slow/failing API responses
