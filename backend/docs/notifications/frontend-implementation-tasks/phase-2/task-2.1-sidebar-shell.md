# Task 2.1: Sidebar Shell & Tab Navigation

**Status:** ⬜ Not Started  
**Priority:** 🔴 Critical (MVP)  
**Estimated Effort:** 2 days  
**Assignee:** _TBD_

---

## Description

Create the notification sidebar container component with tab navigation, similar to LibrarySidebar. This provides the shell for displaying notifications and managing subscriptions.

## Goals

- Create reusable sidebar layout component
- Implement tab switching between Notifications and Subscriptions
- Handle open/close animations
- Integrate with bell button toggle
- Maintain responsive behavior across screen sizes

## Technical Requirements

### Component Interface

```typescript
interface NotificationSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  initialTab?: 'notifications' | 'subscriptions';
  className?: string;
}

export function NotificationSidebar({
  isOpen,
  onClose,
  initialTab = 'notifications',
  className
}: NotificationSidebarProps): JSX.Element;
```

### Tab Structure

```typescript
type TabType = 'notifications' | 'subscriptions';

interface TabDefinition {
  id: TabType;
  label: string;
  icon: React.ComponentType;
  badge?: number;
  component: React.ComponentType;
}

const TABS: TabDefinition[] = [
  {
    id: 'notifications',
    label: 'Notifications',
    icon: BellIcon,
    component: NotificationsList,  // Task 2.2
  },
  {
    id: 'subscriptions',
    label: 'Subscriptions',
    icon: SubscriptionIcon,
    component: SubscriptionsList,  // Task 4.1
  },
];
```

### Layout Structure

```
┌─────────────────────────────────────────┐
│  🔔 Notifications               ✕       │ Header
├─────────────────────────────────────────┤
│  [ Notifications ] [ Subscriptions ]     │ Tabs
├─────────────────────────────────────────┤
│                                          │
│                                          │
│           TAB CONTENT                    │
│        (Dynamic component)               │
│                                          │
│                                          │
└─────────────────────────────────────────┘
```

### Responsive Behavior

- **Desktop (>1024px):** Sidebar width 400px, slides from right
- **Tablet (768-1023px):** Sidebar width 360px, slides from right
- **Mobile (<768px):** Full screen overlay, slides from bottom

## Dependencies

- Task 1.3 (Bell button integration)
- Existing sidebar patterns (LibrarySidebar)
- React Portal for overlay rendering

## Acceptance Criteria

- [ ] Sidebar opens/closes smoothly with animation
- [ ] Tab switching works without losing scroll position
- [ ] Active tab visually highlighted
- [ ] Close button (X) closes sidebar
- [ ] Click outside sidebar closes it (desktop/tablet)
- [ ] Escape key closes sidebar
- [ ] Sidebar maintains state when re-opened (same tab)
- [ ] Header shows correct title based on active tab
- [ ] Responsive layout works on all screen sizes
- [ ] Sidebar doesn't block page scrolling when open
- [ ] Animations are smooth (60fps)
- [ ] Sidebar content is scrollable independently
- [ ] Focus trap: keyboard navigation stays within sidebar when open
- [ ] Accessible: proper ARIA attributes

## Testing Requirements

### Unit Tests

```typescript
describe('NotificationSidebar', () => {
  it('should render with notifications tab active by default', () => {
    render(<NotificationSidebar isOpen={true} onClose={jest.fn()} />);
    
    expect(screen.getByRole('tab', { name: 'Notifications' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel')).toBeInTheDocument();
  });

  it('should switch tabs when clicking tab button', () => {
    render(<NotificationSidebar isOpen={true} onClose={jest.fn()} />);
    
    const subscriptionsTab = screen.getByRole('tab', { name: 'Subscriptions' });
    fireEvent.click(subscriptionsTab);
    
    expect(subscriptionsTab).toHaveAttribute('aria-selected', 'true');
    // Content should change
  });

  it('should call onClose when close button clicked', () => {
    const onClose = jest.fn();
    render(<NotificationSidebar isOpen={true} onClose={onClose} />);
    
    const closeButton = screen.getByLabelText('Close notification sidebar');
    fireEvent.click(closeButton);
    
    expect(onClose).toHaveBeenCalled();
  });

  it('should call onClose when clicking outside sidebar', () => {
    const onClose = jest.fn();
    render(<NotificationSidebar isOpen={true} onClose={onClose} />);
    
    const overlay = screen.getByTestId('sidebar-overlay');
    fireEvent.click(overlay);
    
    expect(onClose).toHaveBeenCalled();
  });

  it('should call onClose when pressing Escape key', () => {
    const onClose = jest.fn();
    render(<NotificationSidebar isOpen={true} onClose={onClose} />);
    
    fireEvent.keyDown(document, { key: 'Escape' });
    
    expect(onClose).toHaveBeenCalled();
  });

  it('should not render when isOpen is false', () => {
    const { container } = render(
      <NotificationSidebar isOpen={false} onClose={jest.fn()} />
    );
    
    expect(container.querySelector('.notification-sidebar')).not.toBeInTheDocument();
  });

  it('should remember active tab when re-opened', () => {
    const { rerender } = render(
      <NotificationSidebar isOpen={true} onClose={jest.fn()} />
    );
    
    // Switch to subscriptions tab
    fireEvent.click(screen.getByRole('tab', { name: 'Subscriptions' }));
    
    // Close sidebar
    rerender(<NotificationSidebar isOpen={false} onClose={jest.fn()} />);
    
    // Re-open sidebar
    rerender(<NotificationSidebar isOpen={true} onClose={jest.fn()} />);
    
    // Should still be on subscriptions tab
    expect(screen.getByRole('tab', { name: 'Subscriptions' })).toHaveAttribute('aria-selected', 'true');
  });

  it('should start with specified initial tab', () => {
    render(
      <NotificationSidebar 
        isOpen={true} 
        onClose={jest.fn()} 
        initialTab="subscriptions" 
      />
    );
    
    expect(screen.getByRole('tab', { name: 'Subscriptions' })).toHaveAttribute('aria-selected', 'true');
  });
});
```

### Accessibility Tests

```typescript
describe('NotificationSidebar Accessibility', () => {
  it('should trap focus within sidebar when open', () => {
    render(<NotificationSidebar isOpen={true} onClose={jest.fn()} />);
    
    const sidebar = screen.getByRole('dialog');
    const focusableElements = sidebar.querySelectorAll('button, a, input, [tabindex="0"]');
    
    expect(focusableElements.length).toBeGreaterThan(0);
    
    // Tab through elements
    focusableElements[0].focus();
    expect(document.activeElement).toBe(focusableElements[0]);
    
    // Tab beyond last element should cycle back
    userEvent.tab({ shift: false });
    // Assert focus management
  });

  it('should have proper ARIA attributes', () => {
    render(<NotificationSidebar isOpen={true} onClose={jest.fn()} />);
    
    const sidebar = screen.getByRole('dialog');
    expect(sidebar).toHaveAttribute('aria-label', 'Notification center');
    expect(sidebar).toHaveAttribute('aria-modal', 'true');
    
    const tabList = screen.getByRole('tablist');
    expect(tabList).toBeInTheDocument();
  });

  it('should announce tab changes to screen readers', () => {
    render(<NotificationSidebar isOpen={true} onClose={jest.fn()} />);
    
    const subscriptionsTab = screen.getByRole('tab', { name: 'Subscriptions' });
    fireEvent.click(subscriptionsTab);
    
    const tabPanel = screen.getByRole('tabpanel');
    expect(tabPanel).toHaveAttribute('aria-labelledby');
  });
});
```

### Visual Tests

```typescript
describe('NotificationSidebar Visual', () => {
  it('should match snapshot - notifications tab', () => {
    const { container } = render(
      <NotificationSidebar isOpen={true} onClose={jest.fn()} />
    );
    expect(container).toMatchSnapshot();
  });

  it('should match snapshot - subscriptions tab', () => {
    const { container } = render(
      <NotificationSidebar isOpen={true} onClose={jest.fn()} initialTab="subscriptions" />
    );
    expect(container).toMatchSnapshot();
  });
});
```

## Implementation Notes

### Component Structure

```typescript
export function NotificationSidebar({
  isOpen,
  onClose,
  initialTab = 'notifications',
  className
}: NotificationSidebarProps) {
  const [activeTab, setActiveTab] = useState<TabType>(initialTab);
  const sidebarRef = useRef<HTMLDivElement>(null);
  
  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);
  
  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (sidebarRef.current && !sidebarRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen, onClose]);
  
  // Focus trap
  useFocusTrap(sidebarRef, isOpen);
  
  // Prevent body scroll when open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = '';
      };
    }
  }, [isOpen]);
  
  if (!isOpen) return null;
  
  const ActiveComponent = TABS.find(t => t.id === activeTab)?.component;
  
  return createPortal(
    <div className="sidebar-overlay" data-testid="sidebar-overlay">
      <aside
        ref={sidebarRef}
        className={cn('notification-sidebar', className)}
        role="dialog"
        aria-label="Notification center"
        aria-modal="true"
      >
        {/* Header */}
        <header className="sidebar-header">
          <h2>🔔 Notifications</h2>
          <button
            onClick={onClose}
            aria-label="Close notification sidebar"
            className="close-button"
          >
            ✕
          </button>
        </header>
        
        {/* Tabs */}
        <div role="tablist" className="sidebar-tabs">
          {TABS.map(tab => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-controls={`${tab.id}-panel`}
              id={`${tab.id}-tab`}
              onClick={() => setActiveTab(tab.id)}
              className={cn('tab-button', {
                'tab-active': activeTab === tab.id
              })}
            >
              <tab.icon />
              {tab.label}
              {tab.badge && <span className="tab-badge">{tab.badge}</span>}
            </button>
          ))}
        </div>
        
        {/* Content */}
        <div
          role="tabpanel"
          id={`${activeTab}-panel`}
          aria-labelledby={`${activeTab}-tab`}
          className="sidebar-content"
        >
          {ActiveComponent && <ActiveComponent />}
        </div>
      </aside>
    </div>,
    document.body
  );
}
```

### Animation CSS

```css
.sidebar-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1000;
  animation: fadeIn 0.2s ease-out;
}

.notification-sidebar {
  position: fixed;
  right: 0;
  top: 0;
  bottom: 0;
  width: 400px;
  background: white;
  box-shadow: -2px 0 8px rgba(0, 0, 0, 0.1);
  animation: slideInRight 0.3s ease-out;
  display: flex;
  flex-direction: column;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideInRight {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

@media (max-width: 768px) {
  .notification-sidebar {
    width: 100%;
    animation: slideInBottom 0.3s ease-out;
  }
  
  @keyframes slideInBottom {
    from { transform: translateY(100%); }
    to { transform: translateY(0); }
  }
}
```

## Related Files

- `frontend/src/components/NotificationSidebar/NotificationSidebar.tsx` (new)
- `frontend/src/components/NotificationSidebar/index.ts` (new)
- `frontend/src/components/LibrarySidebar.tsx` (reference)
- `frontend/src/hooks/useFocusTrap.ts` (utility, may need to create)

## Definition of Done

- [ ] All code written and reviewed
- [ ] All unit tests passing (>85% coverage)
- [ ] Accessibility tests passing
- [ ] Visual tests passing
- [ ] Focus trap working correctly
- [ ] Keyboard navigation complete
- [ ] Animations smooth on all devices
- [ ] Responsive behavior verified
- [ ] Screen reader tested
- [ ] Code merged to feature branch

## Additional Resources

- [UI Specification - Notification Center Sidebar](../../FRONTEND_UI_SPECIFICATION.md#notification-center-sidebar)
- [WAI-ARIA: Dialog Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/)
- [WAI-ARIA: Tabs Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/)

---

**Notes:**
- Consider using existing modal/dialog utilities if available
- Test animation performance on low-end devices
- Ensure tab content doesn't re-mount unnecessarily (preserve state)
- Consider adding URL query param for deep linking to specific tab
