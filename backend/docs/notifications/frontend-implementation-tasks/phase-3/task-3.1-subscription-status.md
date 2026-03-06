# Task 3.1: Subscription Status Checking

**Status:** ⬜ Not Started  
**Priority:** 🔴 Critical (MVP)  
**Estimated Effort:** 2 days  
**Assignee:** _TBD_

---

## Description

Implement a system to check if the user has an active subscription for the current page context. This powers the bell button's visual state (filled vs outline) and enables smart behavior like showing existing subscription details instead of creating duplicates.

## Goals

- Query backend to check subscription status for current context
- Cache results to minimize API calls
- Provide loading and error states
- Integrate with context detection system
- Enable "Subscribe" vs "Unsubscribe" UI patterns

## Technical Requirements

### Hook Interface

```typescript
interface SubscriptionStatusResult {
  isSubscribed: boolean;
  subscription: Subscription | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

function useSubscriptionStatus(): SubscriptionStatusResult;
```

### API Endpoints Used

```typescript
// From backend API:
GET /api/notifications/subscriptions/check-organization/{org_uid}/
GET /api/notifications/subscriptions/check-entity/{afm}/
GET /api/notifications/subscriptions/check-relationship/?org_uid={uid}&entity_afm={afm}
GET /api/notifications/subscriptions/check-signer/{signer_name}/

// Response format:
{
  "subscribed": boolean,
  "subscription": {
    "id": number,
    "is_active": boolean,
    "created_at": string,
    // ... full subscription object
  } | null
}
```

### Cache Strategy

```typescript
// Use React Query or similar for caching
const queryKey = ['subscription-status', context.type, contextId];

// Cache config:
const CACHE_OPTIONS = {
  staleTime: 30000, // 30 seconds
  cacheTime: 300000, // 5 minutes
  refetchOnWindowFocus: true,
  retry: 2
};
```

### Integration with Context

```typescript
export function useSubscriptionStatus(): SubscriptionStatusResult {
  const { context, capabilities } = useNotificationContext();
  const api = useNotificationsAPI();
  
  // Don't fetch if context doesn't support subscriptions
  const enabled = capabilities.canSubscribe;
  
  const query = useQuery({
    queryKey: ['subscription-status', context],
    queryFn: () => fetchSubscriptionStatus(context, api),
    enabled,
    ...CACHE_OPTIONS
  });
  
  return {
    isSubscribed: query.data?.subscribed ?? false,
    subscription: query.data?.subscription ?? null,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch
  };
}
```

### Status Check Logic

```typescript
async function fetchSubscriptionStatus(
  context: NotificationContext,
  api: NotificationsAPI
): Promise<{ subscribed: boolean; subscription: Subscription | null }> {
  if (context.type === 'passive' || context.type === 'disabled') {
    return { subscribed: false, subscription: null };
  }
  
  switch (context.type) {
    case 'organization':
      return api.checkOrganizationSubscription(context.organizationUid);
    
    case 'entity':
      return api.checkEntitySubscription(context.afm);
    
    case 'relationship':
      return api.checkRelationshipSubscription(
        context.organizationUid,
        context.afm
      );
    
    case 'signer':
      return api.checkSignerSubscription(context.signerName);
    
    case 'person':
      // Person subscriptions might need custom handling
      return api.checkPersonSubscription(context.personName);
    
    default:
      return { subscribed: false, subscription: null };
  }
}
```

## Dependencies

- Task 1.1 (API Client)
- Task 1.2 (Context Detection)
- React Query or similar caching library

## Acceptance Criteria

- [ ] Hook correctly checks subscription status for all context types
- [ ] Hook returns `isSubscribed: false` for passive/disabled contexts
- [ ] Hook provides loading state while fetching
- [ ] Hook provides error state on API failure
- [ ] Hook returns full subscription object when subscribed
- [ ] Hook results are cached to prevent redundant API calls
- [ ] Hook refetches on window focus (user returns to tab)
- [ ] Hook updates when context changes (route navigation)
- [ ] `refetch()` function manually refreshes status
- [ ] Hook handles URL encoding for names with special characters
- [ ] Hook gracefully handles network errors
- [ ] Hook works offline (returns cached data if available)
- [ ] Multiple components can use hook without duplicate requests

## Testing Requirements

### Unit Tests

```typescript
describe('useSubscriptionStatus', () => {
  it('should return not subscribed for organization context with no subscription', async () => {
    mockAPI.checkOrganizationSubscription.mockResolvedValue({
      subscribed: false,
      subscription: null
    });
    
    const { result, waitFor } = renderHookWithContext(
      () => useSubscriptionStatus(),
      { context: { type: 'organization', organizationUid: '99221718' } }
    );
    
    await waitFor(() => !result.current.isLoading);
    
    expect(result.current.isSubscribed).toBe(false);
    expect(result.current.subscription).toBeNull();
  });

  it('should return subscribed with subscription details', async () => {
    const mockSubscription = {
      id: 1,
      organization_uid: '99221718',
      is_active: true,
      keywords: ['test'],
      created_at: '2026-03-01T10:00:00Z'
    };
    
    mockAPI.checkOrganizationSubscription.mockResolvedValue({
      subscribed: true,
      subscription: mockSubscription
    });
    
    const { result, waitFor } = renderHookWithContext(
      () => useSubscriptionStatus(),
      { context: { type: 'organization', organizationUid: '99221718' } }
    );
    
    await waitFor(() => !result.current.isLoading);
    
    expect(result.current.isSubscribed).toBe(true);
    expect(result.current.subscription).toEqual(mockSubscription);
  });

  it('should not fetch for passive context', () => {
    const { result } = renderHookWithContext(
      () => useSubscriptionStatus(),
      { context: { type: 'passive' } }
    );
    
    expect(result.current.isSubscribed).toBe(false);
    expect(result.current.isLoading).toBe(false);
    expect(mockAPI.checkOrganizationSubscription).not.toHaveBeenCalled();
  });

  it('should handle API errors gracefully', async () => {
    mockAPI.checkOrganizationSubscription.mockRejectedValue(
      new Error('Network error')
    );
    
    const { result, waitFor } = renderHookWithContext(
      () => useSubscriptionStatus(),
      { context: { type: 'organization', organizationUid: '99221718' } }
    );
    
    await waitFor(() => !result.current.isLoading);
    
    expect(result.current.error).toBeTruthy();
    expect(result.current.isSubscribed).toBe(false);
  });

  it('should refetch when context changes', async () => {
    mockAPI.checkOrganizationSubscription.mockResolvedValue({
      subscribed: false,
      subscription: null
    });
    
    const { result, rerender, waitFor } = renderHookWithContext(
      () => useSubscriptionStatus(),
      { context: { type: 'organization', organizationUid: '99221718' } }
    );
    
    await waitFor(() => !result.current.isLoading);
    expect(mockAPI.checkOrganizationSubscription).toHaveBeenCalledTimes(1);
    
    // Change context
    rerender({ context: { type: 'organization', organizationUid: '99221719' } });
    
    await waitFor(() => !result.current.isLoading);
    expect(mockAPI.checkOrganizationSubscription).toHaveBeenCalledTimes(2);
  });

  it('should use cached data for duplicate requests', async () => {
    mockAPI.checkOrganizationSubscription.mockResolvedValue({
      subscribed: true,
      subscription: { id: 1 }
    });
    
    const context = { type: 'organization', organizationUid: '99221718' };
    
    // First component uses hook
    const { waitFor: waitFor1 } = renderHookWithContext(
      () => useSubscriptionStatus(),
      { context }
    );
    
    await waitFor1(() => mockAPI.checkOrganizationSubscription.mock.calls.length > 0);
    
    // Second component uses same hook - should use cache
    const { result: result2, waitFor: waitFor2 } = renderHookWithContext(
      () => useSubscriptionStatus(),
      { context }
    );
    
    await waitFor2(() => !result2.current.isLoading);
    
    // API should only be called once (cached result used for second)
    expect(mockAPI.checkOrganizationSubscription).toHaveBeenCalledTimes(1);
    expect(result2.current.isSubscribed).toBe(true);
  });

  it('should manually refetch when refetch() is called', async () => {
    mockAPI.checkOrganizationSubscription.mockResolvedValue({
      subscribed: false,
      subscription: null
    });
    
    const { result, waitFor } = renderHookWithContext(
      () => useSubscriptionStatus(),
      { context: { type: 'organization', organizationUid: '99221718' } }
    );
    
    await waitFor(() => !result.current.isLoading);
    expect(mockAPI.checkOrganizationSubscription).toHaveBeenCalledTimes(1);
    
    // Manually refetch
    act(() => {
      result.current.refetch();
    });
    
    await waitFor(() => mockAPI.checkOrganizationSubscription.mock.calls.length === 2);
    expect(mockAPI.checkOrganizationSubscription).toHaveBeenCalledTimes(2);
  });

  it('should handle relationship context correctly', async () => {
    mockAPI.checkRelationshipSubscription.mockResolvedValue({
      subscribed: true,
      subscription: { id: 2 }
    });
    
    const { result, waitFor } = renderHookWithContext(
      () => useSubscriptionStatus(),
      {
        context: {
          type: 'relationship',
          organizationUid: '99221718',
          afm: '123456789'
        }
      }
    );
    
    await waitFor(() => !result.current.isLoading);
    
    expect(mockAPI.checkRelationshipSubscription).toHaveBeenCalledWith(
      '99221718',
      '123456789'
    );
    expect(result.current.isSubscribed).toBe(true);
  });
});
```

### Integration Tests

```typescript
describe('Subscription Status Integration', () => {
  it('should update bell button state when subscription status changes', async () => {
    const { rerender } = renderWithRouter(
      <NotificationButton />,
      { route: '/entity/organization/99221718' }
    );
    
    // Initially not subscribed
    await waitFor(() => {
      expect(screen.getByTestId('bell-icon')).toHaveClass('bell-outline');
    });
    
    // Create subscription
    await createSubscription({ organization_uid: '99221718' });
    
    // Refetch status
    await waitFor(() => {
      expect(screen.getByTestId('bell-icon')).toHaveClass('bell-filled');
    });
  });
});
```

## Implementation Notes

### API Client Methods

```typescript
// In NotificationsAPI class (Task 1.1)
class NotificationsAPI {
  async checkOrganizationSubscription(
    organizationUid: string
  ): Promise<{ subscribed: boolean; subscription: Subscription | null }> {
    const response = await this.client.get(
      `/api/notifications/subscriptions/check-organization/${organizationUid}/`
    );
    return response.data;
  }

  async checkEntitySubscription(
    afm: string
  ): Promise<{ subscribed: boolean; subscription: Subscription | null }> {
    const response = await this.client.get(
      `/api/notifications/subscriptions/check-entity/${afm}/`
    );
    return response.data;
  }

  async checkRelationshipSubscription(
    organizationUid: string,
    afm: string
  ): Promise<{ subscribed: boolean; subscription: Subscription | null }> {
    const response = await this.client.get(
      `/api/notifications/subscriptions/check-relationship/`,
      { params: { org_uid: organizationUid, entity_afm: afm } }
    );
    return response.data;
  }

  async checkSignerSubscription(
    signerName: string
  ): Promise<{ subscribed: boolean; subscription: Subscription | null }> {
    const encoded = encodeURIComponent(signerName);
    const response = await this.client.get(
      `/api/notifications/subscriptions/check-signer/${encoded}/`
    );
    return response.data;
  }
}
```

### Caching Considerations

- Use React Query's built-in caching to prevent duplicate requests
- Set appropriate `staleTime` to balance freshness vs performance
- Invalidate cache after subscription create/delete/update actions
- Consider using optimistic updates for better UX

### Error Handling

```typescript
// Display errors gracefully in UI
if (error) {
  // Show in tooltip or bell button
  return <BellIcon className="error" title="Could not load subscription status" />;
}
```

## Related Files

- `frontend/src/hooks/useSubscriptionStatus.ts` (new)
- `frontend/src/hooks/useNotificationContext.ts` (Task 1.2)
- `frontend/src/api/NotificationsAPI.ts` (Task 1.1)
- `frontend/src/components/NotificationButton.tsx` (Task 1.3)

## Definition of Done

- [ ] All code written and reviewed
- [ ] All unit tests passing (>95% coverage)
- [ ] Integration tests with API mocking passing
- [ ] Hook documented with JSDoc
- [ ] Caching strategy tested and validated
- [ ] Error states handled gracefully
- [ ] Works for all subscription types
- [ ] Performance validated (no excessive API calls)
- [ ] Code merged to feature branch

## Additional Resources

- [Backend API - Check Subscription Endpoints](../../FRONTEND_INTEGRATION_GUIDE.md#6-check-if-user-is-subscribed)
- React Query documentation
- [UI Specification - Context-Aware Bell Button](../../FRONTEND_UI_SPECIFICATION.md#context-aware-bell-button)

---

**Notes:**
- Consider debouncing rapid context changes (e.g., quick page navigation)
- Ensure proper cleanup of query subscriptions to prevent memory leaks
- Test with slow network conditions to validate loading states
- Consider showing stale data with background refresh for better UX
