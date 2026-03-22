# Task 1.1: API Client & Type Definitions

**Status:** ⬜ Not Started  
**Priority:** 🔴 Critical (MVP)  
**Estimated Effort:** 2-3 days  
**Assignee:** _TBD_

---

## Description

Create TypeScript type definitions for all notification system API responses and implement a centralized API client with typed methods for all notification endpoints.

## Goals

- Establish type safety for all notification-related API calls
- Create reusable API client functions
- Set up error handling patterns
- Enable autocomplete and IntelliSense for API responses

## Technical Requirements

### Type Definitions Needed

1. **NotificationSubscription**
   - `id`, `subscription_type`, `organization_uid`, `entity_afm`, etc.
   - All filter fields (`keywords`, `amount_min`, `amount_max`, `decision_types`)
   - Nested objects (`organization_details`, `entity_details`)
   
2. **Notification**
   - `id`, `subscription_type`, `decision_ada`, `decision_subject`
   - `match_reason`, `is_read`, `is_dismissed`, `created_at`
   - Nested decision and subscription details

3. **SystemMetadata**
   - `subscription_types`, `filter_parameters`, `check_frequency_options`
   - `endpoints` map

4. **DecisionType**
   - `uid`, `label`, `allowed_in_decisions`, `has_children`, `parent_uid`

5. **SearchResult**
   - Generic result type for entity searches
   - Organization, signer, company, person types

6. **API Response Wrappers**
   - Paginated response type
   - Error response type
   - Success/failure discriminated unions

### API Client Methods

```typescript
// Subscriptions
createSubscription(data: CreateSubscriptionRequest): Promise<NotificationSubscription>
listSubscriptions(): Promise<NotificationSubscription[]>
getSubscription(id: number): Promise<NotificationSubscription>
updateSubscription(id: number, data: UpdateSubscriptionRequest): Promise<NotificationSubscription>
deleteSubscription(id: number): Promise<void>
checkOrganizationSubscription(orgUid: string): Promise<SubscriptionCheckResponse>
checkEntitySubscription(afm: string): Promise<SubscriptionCheckResponse>
checkRelationshipSubscription(orgUid: string, afm: string): Promise<SubscriptionCheckResponse>
checkSignerSubscription(name: string): Promise<SubscriptionCheckResponse>
triggerCheckNow(id: number, lookbackDays?: number): Promise<CheckNowResponse>

// Notifications
listNotifications(filters?: NotificationFilters): Promise<Notification[]>
getNotification(id: number): Promise<Notification>
markNotificationRead(id: number): Promise<void>
markNotificationUnread(id: number): Promise<void>
dismissNotification(id: number): Promise<void>
markAllNotificationsRead(): Promise<{ marked_read: number }>
getUnreadCount(): Promise<{ unread_count: number }>

// Metadata
getSystemMetadata(): Promise<SystemMetadata>
getDecisionTypes(params?: DecisionTypeParams): Promise<DecisionTypesResponse>
getPopularDecisionTypes(limit?: number): Promise<PopularTypesResponse>

// Search
searchEntities(query: string, types?: string[], limit?: number): Promise<SearchResults>
```

### File Structure

```
frontend/src/
├── api/
│   ├── notifications/
│   │   ├── client.ts           # API client functions
│   │   ├── types.ts            # Type definitions
│   │   └── endpoints.ts        # API URL constants
│   └── client-base.ts          # Base HTTP client (if not exists)
└── types/
    └── notifications.ts         # Re-export types for easy import
```

## Dependencies

- Existing HTTP client (axios/fetch wrapper)
- Authentication token management
- Base API configuration

## Acceptance Criteria

- [ ] All TypeScript types match backend API responses exactly
- [ ] All API endpoints have corresponding client methods
- [ ] Client methods have proper JSDoc documentation
- [ ] Error responses are properly typed
- [ ] Request/response types are discriminated unions where applicable
- [ ] Types are exported from a central location
- [ ] No `any` types used (except where absolutely necessary with explanation)
- [ ] All methods handle authentication automatically
- [ ] Base URL and endpoints are configurable (env variables)

## Testing Requirements

### Unit Tests

```typescript
describe('Notification API Client', () => {
  describe('createSubscription', () => {
    it('should create organization subscription successfully', async () => {
      // Mock API response
      // Call createSubscription
      // Assert correct request payload
      // Assert typed response
    });

    it('should handle validation errors', async () => {
      // Mock 400 error response
      // Assert error type and fields
    });

    it('should handle network errors', async () => {
      // Mock network failure
      // Assert error handling
    });
  });

  describe('getUnreadCount', () => {
    it('should return unread count', async () => {
      // Mock response { unread_count: 5 }
      // Assert correct type and value
    });
  });

  // ... tests for each method
});
```

### Type Tests

```typescript
// Type-level tests using TypeScript's type system
type TestNotificationHasRequiredFields = Expect<
  NotificationSubscription extends { id: number; subscription_type: string }
    ? true
    : false
>;

// Or using a testing library like tsd
expectType<number>(notification.id);
expectType<'organization' | 'entity' | 'relationship' | 'person' | 'signer' | 'filter_only'>(
  subscription.subscription_type
);
```

## Implementation Notes

### Error Handling Pattern

```typescript
export class NotificationAPIError extends Error {
  constructor(
    public status: number,
    public field_errors?: Record<string, string[]>,
    public non_field_errors?: string[]
  ) {
    super('Notification API Error');
  }
}

// Usage
try {
  await createSubscription(data);
} catch (error) {
  if (error instanceof NotificationAPIError) {
    // Handle validation errors
    console.error(error.field_errors);
  }
}
```

### Type Guards

```typescript
export function isOrganizationSubscription(
  sub: NotificationSubscription
): sub is OrganizationSubscription {
  return sub.subscription_type === 'organization' && !!sub.organization_uid;
}
```

### Discriminated Unions

```typescript
type SubscriptionCheckResponse = 
  | { subscribed: true; subscription: NotificationSubscription }
  | { subscribed: false; subscription: null };
```

## Related Files

- Backend API serializers: `backend/notifications/serializers/`
- Backend API views: `backend/notifications/views/`
- Frontend integration guide: `FRONTEND_INTEGRATION_GUIDE.md`

## Definition of Done

- [ ] All code written and reviewed
- [ ] All unit tests passing (>90% coverage)
- [ ] Types validated against actual API responses
- [ ] Documentation complete (JSDoc + README)
- [ ] No TypeScript errors or warnings
- [ ] Integrated with existing auth system
- [ ] Code merged to feature branch

## Additional Resources

- [Backend API Documentation](../../FRONTEND_INTEGRATION_GUIDE.md)
- TypeScript Handbook: [Type Narrowing](https://www.typescriptlang.org/docs/handbook/2/narrowing.html)
- API Response Examples (see integration guide)

---

**Notes:**
- Use `zod` or similar for runtime validation if needed
- Consider using generated types from OpenAPI/Swagger if available
- Document any deviations from backend types with rationale
