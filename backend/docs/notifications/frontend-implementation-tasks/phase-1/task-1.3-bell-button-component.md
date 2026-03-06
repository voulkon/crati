# Task 1.3: Basic Bell Button Component

**Status:** ⬜ Not Started  
**Priority:** 🔴 Critical (MVP)  
**Estimated Effort:** 2 days  
**Assignee:** _TBD_

---

## Description

Create the notification bell button component with unread count badge and split-button behavior (similar to BookmarkButton). This serves as the primary entry point to the notification system.

## Goals

- Provide visible access to notifications from any page
- Display unread notification count
- Split button: bell half (action) + chevron half (toggle sidebar)
- Integrate with TopControls component
- Handle different visual states (active/inactive, subscribed/unsubscribed)

## Technical Requirements

### Component Interface

```typescript
interface NotificationButtonProps {
  className?: string;
  onSidebarToggle?: (open: boolean) => void;
}

export function NotificationButton({ 
  className, 
  onSidebarToggle 
}: NotificationButtonProps): JSX.Element;
```

### Visual States

1. **Default (Not Subscribed)**
   - Outline bell icon
   - Neutral color
   - Hover: highlight

2. **Subscribed**
   - Filled bell icon
   - Primary/accent color
   - Hover: darker shade

3. **With Badge**
   - Small circular badge with count
   - Position: top-right of bell icon
   - Max display: "99+" for counts > 99
   - Pulsing animation for new notifications

4. **Disabled**
   - Grayed out
   - No hover effect
   - Cursor: not-allowed
   - Tooltip explaining why disabled

5. **Loading**
   - Skeleton/shimmer effect
   - During initial data fetch

### Split Button Layout

```
┌────────────────────────┐
│  🔔 3  │  ▾            │
└────────────────────────┘
   60%        40%
   Bell     Chevron
```

### Button Behaviors

**Bell Half (Left 60%):**
- **Click handler varies by context** (see task 3.2 for full implementation)
- For this task: stub behavior
  - Subscribable pages: Log "Subscribe action"
  - Passive pages: Open sidebar (same as chevron)
  - Disabled pages: No action, show tooltip

**Chevron Half (Right 40%):**
- Always toggles notification sidebar open/closed
- Rotates chevron icon when sidebar is open

## Dependencies

- Task 1.1 (API client for unread count)
- Task 1.2 (Context detection hook)
- Existing button/icon components
- TopControls component integration point

## Acceptance Criteria

- [ ] Button renders with bell and chevron icons
- [ ] Split button: two distinct clickable areas
- [ ] Unread count badge displays correctly (1-99, 99+)
- [ ] Badge hides when count is 0
- [ ] Bell icon changes appearance based on subscription status
- [ ] Chevron rotates when sidebar is open
- [ ] Disabled state shows tooltip
- [ ] Loading state shows skeleton
- [ ] Integrates into TopControls component
- [ ] Responsive: works on mobile/tablet/desktop
- [ ] Keyboard accessible (tab, enter, space)
- [ ] Screen reader announces unread count
- [ ] Matches design system styling
- [ ] No layout shift during loading

## Testing Requirements

### Unit Tests

```typescript
describe('NotificationButton', () => {
  it('should render bell and chevron icons', () => {
    render(<NotificationButton />);
    expect(screen.getByTestId('bell-icon')).toBeInTheDocument();
    expect(screen.getByTestId('chevron-icon')).toBeInTheDocument();
  });

  it('should display unread count badge when count > 0', () => {
    mockUnreadCount(5);
    render(<NotificationButton />);
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('should display "99+" for counts over 99', () => {
    mockUnreadCount(150);
    render(<NotificationButton />);
    expect(screen.getByText('99+')).toBeInTheDocument();
  });

  it('should hide badge when count is 0', () => {
    mockUnreadCount(0);
    render(<NotificationButton />);
    expect(screen.queryByTestId('unread-badge')).not.toBeInTheDocument();
  });

  it('should call onSidebarToggle when chevron is clicked', () => {
    const onToggle = jest.fn();
    render(<NotificationButton onSidebarToggle={onToggle} />);
    
    const chevronButton = screen.getByTestId('chevron-button');
    fireEvent.click(chevronButton);
    
    expect(onToggle).toHaveBeenCalledWith(true);
  });

  it('should show filled bell icon when subscribed', () => {
    mockSubscriptionStatus({ subscribed: true });
    mockContext({ type: 'organization', organizationUid: '123' });
    
    render(<NotificationButton />);
    
    const bellIcon = screen.getByTestId('bell-icon');
    expect(bellIcon).toHaveClass('bell-filled');
  });

  it('should show outline bell icon when not subscribed', () => {
    mockSubscriptionStatus({ subscribed: false });
    mockContext({ type: 'organization', organizationUid: '123' });
    
    render(<NotificationButton />);
    
    const bellIcon = screen.getByTestId('bell-icon');
    expect(bellIcon).toHaveClass('bell-outline');
  });

  it('should be disabled on decision pages', () => {
    mockContext({ type: 'disabled' });
    
    render(<NotificationButton />);
    
    const bellButton = screen.getByTestId('bell-button');
    expect(bellButton).toBeDisabled();
  });

  it('should show tooltip when disabled', async () => {
    mockContext({ type: 'disabled' });
    
    render(<NotificationButton />);
    
    const bellButton = screen.getByTestId('bell-button');
    fireEvent.mouseOver(bellButton);
    
    await waitFor(() => {
      expect(screen.getByText(/not supported/i)).toBeInTheDocument();
    });
  });

  it('should rotate chevron when sidebar is open', () => {
    const { rerender } = render(
      <NotificationButton onSidebarToggle={jest.fn()} />
    );
    
    const chevron = screen.getByTestId('chevron-icon');
    expect(chevron).toHaveClass('chevron-down');
    
    // Simulate sidebar open state change
    rerender(<NotificationButton sidebarOpen={true} />);
    
    expect(chevron).toHaveClass('chevron-up');
  });
});
```

### Accessibility Tests

```typescript
describe('NotificationButton Accessibility', () => {
  it('should be keyboard navigable', () => {
    render(<NotificationButton />);
    
    const bellButton = screen.getByTestId('bell-button');
    bellButton.focus();
    expect(bellButton).toHaveFocus();
    
    fireEvent.keyDown(bellButton, { key: 'Enter' });
    // Assert action triggered
  });

  it('should announce unread count to screen readers', () => {
    mockUnreadCount(3);
    render(<NotificationButton />);
    
    const bellButton = screen.getByTestId('bell-button');
    expect(bellButton).toHaveAttribute('aria-label', expect.stringContaining('3 unread'));
  });

  it('should have proper ARIA attributes', () => {
    render(<NotificationButton />);
    
    const bellButton = screen.getByTestId('bell-button');
    expect(bellButton).toHaveAttribute('aria-expanded');
    expect(bellButton).toHaveAttribute('role', 'button');
  });
});
```

### Visual Regression Tests

```typescript
describe('NotificationButton Visual', () => {
  it('should match snapshot - default state', () => {
    const { container } = render(<NotificationButton />);
    expect(container).toMatchSnapshot();
  });

  it('should match snapshot - with badge', () => {
    mockUnreadCount(5);
    const { container } = render(<NotificationButton />);
    expect(container).toMatchSnapshot();
  });

  it('should match snapshot - subscribed state', () => {
    mockSubscriptionStatus({ subscribed: true });
    const { container } = render(<NotificationButton />);
    expect(container).toMatchSnapshot();
  });
});
```

## Implementation Notes

### Component Structure

```typescript
export function NotificationButton({ className, onSidebarToggle }: NotificationButtonProps) {
  const { unreadCount, isLoading } = useUnreadCount();
  const { context, capabilities } = useNotificationContext();
  const { subscribed } = useSubscriptionStatus(context);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  
  const handleBellClick = () => {
    // Stub for now - will be implemented in task 3.2
    if (!capabilities.canSubscribe) {
      if (context.type === 'passive') {
        handleToggleSidebar();
      }
      return;
    }
    
    console.log('Subscribe action:', context);
  };
  
  const handleToggleSidebar = () => {
    const newState = !sidebarOpen;
    setSidebarOpen(newState);
    onSidebarToggle?.(newState);
  };
  
  if (isLoading) {
    return <NotificationButtonSkeleton />;
  }
  
  return (
    <div className={cn('notification-button-container', className)}>
      {/* Bell half */}
      <button
        className={cn('bell-button', {
          'bell-subscribed': subscribed,
          'bell-disabled': context.type === 'disabled'
        })}
        onClick={handleBellClick}
        disabled={context.type === 'disabled'}
        aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ''}`}
        data-testid="bell-button"
      >
        <BellIcon filled={subscribed} />
        {unreadCount > 0 && (
          <span className="unread-badge" data-testid="unread-badge">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>
      
      {/* Chevron half */}
      <button
        className="chevron-button"
        onClick={handleToggleSidebar}
        aria-label="Toggle notification sidebar"
        aria-expanded={sidebarOpen}
        data-testid="chevron-button"
      >
        <ChevronIcon className={sidebarOpen ? 'chevron-up' : 'chevron-down'} />
      </button>
    </div>
  );
}
```

### Styling Notes

- Use CSS Grid or Flexbox for split button layout
- Badge position: `position: absolute; top: -4px; right: -4px;`
- Badge min-width to prevent jitter when count changes
- Smooth transitions for icon changes
- Match existing button styling from BookmarkButton

## Related Files

- `frontend/src/components/TopControls/NotificationButton.tsx` (new)
- `frontend/src/components/TopControls/TopControls.tsx` (integration)
- `frontend/src/components/TopControls/BookmarkButton.tsx` (reference)
- Design system button components

## Definition of Done

- [ ] All code written and reviewed
- [ ] All unit tests passing (>90% coverage)
- [ ] Accessibility tests passing
- [ ] Visual regression tests passing
- [ ] Integrated into TopControls
- [ ] Keyboard navigation works
- [ ] Screen reader tested
- [ ] Design review approved
- [ ] Responsive on all breakpoints
- [ ] Code merged to feature branch

## Additional Resources

- [UI Specification - Context-Aware Bell Button](../../FRONTEND_UI_SPECIFICATION.md#context-aware-bell-button)
- [Web Accessibility: Button Best Practices](https://www.w3.org/WAI/ARIA/apg/patterns/button/)
- Design system documentation

---

**Notes:**
- Bell icon: use existing icon library or add notification-specific icons
- Consider using CSS custom properties for theming
- Badge animation should be subtle, not distracting
- Test with long organization names (truncation in tooltip)
