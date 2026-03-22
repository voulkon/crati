# Task 1.2: Context Detection System

**Status:** ⬜ Not Started  
**Priority:** 🔴 Critical (MVP)  
**Estimated Effort:** 2 days  
**Assignee:** _TBD_

---

## Description

Implement a context detection system that determines the appropriate notification subscription type and target based on the current route/page. This powers the context-aware bell button behavior.

## Goals

- Automatically detect which entity/page the user is viewing
- Map page context to subscription types and targets
- Provide a clean API via React hook
- Enable pre-filled subscription creation from any page

## Technical Requirements

### Context Types

```typescript
type NotificationContext =
  | { type: 'organization'; organizationUid: string; organizationName?: string }
  | { type: 'entity'; afm: string; entityName?: string }
  | { type: 'signer'; signerName: string }
  | { type: 'relationship'; organizationUid: string; afm: string }
  | { type: 'person'; personName: string }
  | { type: 'passive' }  // Home, search, library - no specific target
  | { type: 'disabled' };  // Decision detail, units - not subscribable

type ContextCapabilities = {
  canSubscribe: boolean;
  subscriptionType: SubscriptionType | null;
  suggestedName?: string;
};
```

### Hook Interface

```typescript
function useNotificationContext(): {
  context: NotificationContext;
  capabilities: ContextCapabilities;
  isLoading: boolean;
  targetData?: {
    id: string;
    name: string;
    type: string;
    [key: string]: any;
  };
}
```

### Route Mapping

| Route Pattern | Context Type | Extract From |
|--------------|--------------|-------------|
| `/entity/organization/:uid` | organization | URL param + page data |
| `/entity/signer/:name` | signer | URL param + page data |
| `/entity/afm/:afm` | entity | URL param + page data |
| `/entity/unit/:id` | disabled | N/A |
| `/decision/:ada` | disabled | N/A |
| `/relationship/entity/:afm/org/:uid` | relationship | URL params + page data |
| `/person/:name` | person | URL param + page data |
| `/`, `/search`, `/library` | passive | N/A |

## Dependencies

- React Router for route matching
- Existing page data/state (entity details loaded on page)
- Task 1.1 (Type definitions)

## Acceptance Criteria

- [ ] Hook correctly identifies context on all route types
- [ ] Hook returns correct `canSubscribe` flag for each route
- [ ] Hook extracts entity IDs from URL params correctly
- [ ] Hook provides entity name/details when available from page state
- [ ] Hook returns `isLoading: true` while entity data is being fetched
- [ ] Hook handles missing or invalid URL params gracefully
- [ ] Hook updates when route changes
- [ ] Hook is memoized to prevent unnecessary re-renders
- [ ] Documentation includes examples for each route type

## Testing Requirements

### Unit Tests

```typescript
describe('useNotificationContext', () => {
  it('should detect organization context', () => {
    const { result } = renderHookWithRouter(
      () => useNotificationContext(),
      { route: '/entity/organization/99221718' }
    );
    
    expect(result.current.context).toEqual({
      type: 'organization',
      organizationUid: '99221718'
    });
    expect(result.current.capabilities.canSubscribe).toBe(true);
  });

  it('should detect disabled context on decision page', () => {
    const { result } = renderHookWithRouter(
      () => useNotificationContext(),
      { route: '/decision/ABC123' }
    );
    
    expect(result.current.context.type).toBe('disabled');
    expect(result.current.capabilities.canSubscribe).toBe(false);
  });

  it('should detect relationship context', () => {
    const { result } = renderHookWithRouter(
      () => useNotificationContext(),
      { route: '/relationship/entity/123456789/org/99221718' }
    );
    
    expect(result.current.context).toEqual({
      type: 'relationship',
      organizationUid: '99221718',
      afm: '123456789'
    });
  });

  it('should detect passive context on home page', () => {
    const { result } = renderHookWithRouter(
      () => useNotificationContext(),
      { route: '/' }
    );
    
    expect(result.current.context.type).toBe('passive');
    expect(result.current.capabilities.canSubscribe).toBe(false);
  });

  it('should update when route changes', () => {
    const { result, rerender } = renderHookWithRouter(
      () => useNotificationContext(),
      { route: '/' }
    );
    
    expect(result.current.context.type).toBe('passive');
    
    // Navigate to organization page
    act(() => {
      navigate('/entity/organization/99221718');
    });
    
    rerender();
    
    expect(result.current.context.type).toBe('organization');
  });

  it('should include entity name when available from page state', () => {
    const { result } = renderHookWithRouter(
      () => useNotificationContext(),
      {
        route: '/entity/organization/99221718',
        providerProps: {
          entityData: { uid: '99221718', label: 'ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ' }
        }
      }
    );
    
    expect(result.current.targetData?.name).toBe('ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ');
  });
});
```

### Integration Tests

```typescript
describe('Context Detection Integration', () => {
  it('should work with real router navigation', () => {
    const { result } = renderWithRouter(<TestComponent />);
    
    // Navigate through different pages
    userEvent.click(screen.getByText('View Organization'));
    expect(result.current.context.type).toBe('organization');
    
    userEvent.click(screen.getByText('View Decision'));
    expect(result.current.context.type).toBe('disabled');
  });
});
```

## Implementation Notes

### Hook Implementation Structure

```typescript
export function useNotificationContext() {
  const location = useLocation();
  const params = useParams();
  
  // Get entity data from page context if available
  const entityData = useEntityPageData(); // Or whatever hook provides page data
  
  const context = useMemo(() => {
    return detectContextFromRoute(location.pathname, params, entityData);
  }, [location.pathname, params, entityData]);
  
  const capabilities = useMemo(() => {
    return getContextCapabilities(context);
  }, [context]);
  
  return { context, capabilities, targetData: entityData };
}
```

### Route Detection Logic

```typescript
function detectContextFromRoute(
  pathname: string,
  params: Record<string, string>,
  entityData?: any
): NotificationContext {
  // Match patterns in order of specificity
  if (pathname.startsWith('/entity/organization/')) {
    return {
      type: 'organization',
      organizationUid: params.uid!,
      organizationName: entityData?.label
    };
  }
  
  if (pathname.startsWith('/entity/signer/')) {
    return {
      type: 'signer',
      signerName: decodeURIComponent(params.name!)
    };
  }
  
  // ... more patterns
  
  // Default cases
  if (pathname.startsWith('/decision/')) {
    return { type: 'disabled' };
  }
  
  return { type: 'passive' };
}
```

### Capability Calculation

```typescript
function getContextCapabilities(context: NotificationContext): ContextCapabilities {
  switch (context.type) {
    case 'organization':
    case 'entity':
    case 'signer':
    case 'relationship':
    case 'person':
      return {
        canSubscribe: true,
        subscriptionType: context.type,
        suggestedName: context.organizationName || context.entityName || context.signerName
      };
    
    case 'passive':
      return {
        canSubscribe: false,
        subscriptionType: null
      };
    
    case 'disabled':
      return {
        canSubscribe: false,
        subscriptionType: null
      };
  }
}
```

## Related Files

- `frontend/src/hooks/useNotificationContext.ts` (new)
- `frontend/src/pages/EntityPage.tsx` (integration)
- UI Specification: Context-Aware Bell Button section

## Definition of Done

- [ ] All code written and reviewed
- [ ] All unit tests passing (>95% coverage)
- [ ] Integration tests with router passing
- [ ] Hook documented with JSDoc
- [ ] Example usage documented in README
- [ ] Works with existing routing setup
- [ ] Performance validated (no excessive re-renders)
- [ ] Code merged to feature branch

## Additional Resources

- React Router documentation
- [UI Specification - Context-Aware Bell Button](../../FRONTEND_UI_SPECIFICATION.md#context-aware-bell-button)

---

**Notes:**
- Consider edge cases like URL encoding for names with special characters
- Ensure hook is stable across re-renders (use useMemo/useCallback)
- May need to handle async entity data loading states
