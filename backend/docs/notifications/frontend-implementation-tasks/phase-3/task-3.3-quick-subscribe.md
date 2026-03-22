# Task 3.3: Quick Subscribe Flow

**Status:** ⬜ Not Started  
**Priority:** 🟡 High Priority  
**Estimated Effort:** 2 days  
**Assignee:** _TBD_

---

## Description

Implement a streamlined "quick subscribe" flow that allows users to create a basic subscription with one or two clicks from a context-aware page. This provides an express path for users who want immediate notifications without configuring advanced filters.

## Goals

- Enable one-click subscription creation from context pages
- Provide optional quick filter selection (keywords, amount range)
- Skip full wizard for common use cases
- Show immediate feedback and confirmation
- Allow easy upgrade to full wizard if needed

## Technical Requirements

### Quick Subscribe Modal

When user clicks the bell button to subscribe on a subscribable page, show a simplified modal before the full wizard:

```
┌─────────────────────────────────────────────────┐
│  Quick Subscribe                            ✕   │
├─────────────────────────────────────────────────┤
│                                                  │
│  🏢 Subscribe to ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ                 │
│                                                  │
│  Get notified about new decisions from this     │
│  organization.                                   │
│                                                  │
│  ┌────────────────────────────────────────────┐ │
│  │ Add filters (optional):                    │ │
│  │                                             │ │
│  │ Keywords: [                           ]    │ │
│  │           e.g., procurement, contract      │ │
│  │                                             │ │
│  │ Amount range:                              │ │
│  │ Min: [€         ] Max: [€         ]       │ │
│  └────────────────────────────────────────────┘ │
│                                                  │
│  ☑️ Check for existing decisions (last 30 days) │
│                                                  │
├─────────────────────────────────────────────────┤
│                                                  │
│  [Advanced Options ↗]   [Cancel]  [Subscribe]   │
│                                                  │
└─────────────────────────────────────────────────┘
```

### Component Interface

```typescript
interface QuickSubscribeModalProps {
  isOpen: boolean;
  onClose: () => void;
  context: NotificationContext;
  onComplete?: (subscription: Subscription) => void;
  onAdvanced?: () => void; // Switch to full wizard
}

export function QuickSubscribeModal({
  isOpen,
  onClose,
  context,
  onComplete,
  onAdvanced
}: QuickSubscribeModalProps): JSX.Element;
```

### Quick Subscribe Flow States

```typescript
type QuickSubscribeState =
  | { status: 'idle' }
  | { status: 'collecting-input' }  // User adding optional filters
  | { status: 'submitting'; progress?: number }
  | { status: 'success'; subscription: Subscription }
  | { status: 'error'; error: Error };
```

### Form State

```typescript
interface QuickSubscribeFormData {
  keywords: string[]; // Optional
  amountMin?: number; // Optional
  amountMax?: number; // Optional
  checkExisting: boolean; // Default: true
}

function useQuickSubscribeForm(context: NotificationContext) {
  const [formData, setFormData] = useState<QuickSubscribeFormData>({
    keywords: [],
    checkExisting: true
  });
  
  const [errors, setErrors] = useState<Record<string, string>>({});
  
  const validate = useCallback(() => {
    const newErrors: Record<string, string> = {};
    
    // Validate amount range
    if (formData.amountMin && formData.amountMax) {
      if (formData.amountMin > formData.amountMax) {
        newErrors.amountMin = 'Min must be less than max';
      }
    }
    
    // Validate keywords
    if (formData.keywords.length > 10) {
      newErrors.keywords = 'Maximum 10 keywords allowed';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [formData]);
  
  return { formData, setFormData, errors, validate };
}
```

### Submission Logic

```typescript
async function handleQuickSubscribe(
  context: NotificationContext,
  formData: QuickSubscribeFormData,
  api: NotificationsAPI
): Promise<Subscription> {
  // Build subscription payload based on context
  const payload: CreateSubscriptionPayload = {
    ...extractTargetFields(context),
    check_frequency: 'daily', // Default
  };
  
  // Add optional filters
  if (formData.keywords.length > 0) {
    payload.keywords = formData.keywords;
  }
  if (formData.amountMin) {
    payload.amount_min = formData.amountMin.toString();
  }
  if (formData.amountMax) {
    payload.amount_max = formData.amountMax.toString();
  }
  
  // Create subscription
  const subscription = await api.createSubscription(payload);
  
  return subscription;
}

function extractTargetFields(context: NotificationContext): Partial<CreateSubscriptionPayload> {
  switch (context.type) {
    case 'organization':
      return { organization_uid: context.organizationUid };
    case 'entity':
      return { entity_afm: context.afm };
    case 'relationship':
      return {
        relationship_org_uid: context.organizationUid,
        relationship_entity_afm: context.afm
      };
    case 'signer':
      return { signer_name: context.signerName };
    case 'person':
      return { person_name: context.personName };
    default:
      return {};
  }
}
```

### Success Feedback

After successful subscription, show toast notification and update UI:

```typescript
const handleSuccess = useCallback((subscription: Subscription) => {
  // Show toast
  showToast(
    `Subscribed! You'll receive notifications about new decisions.`,
    'success',
    {
      action: {
        label: 'View Subscription',
        onClick: () => openSubscriptionsTab(subscription.id)
      }
    }
  );
  
  // Refresh subscription status
  refetchSubscriptionStatus();
  
  // Update bell icon to filled state
  // (handled automatically by status refetch)
  
  // Close modal
  onClose();
  
  // Call completion callback if provided
  onComplete?.(subscription);
}, [onClose, onComplete, refetchSubscriptionStatus]);
```

## Dependencies

- Task 1.1 (API Client)
- Task 1.2 (Context Detection)
- Task 3.1 (Subscription Status)
- Task 3.2 (Bell Click Behavior)

## Acceptance Criteria

- [ ] Quick subscribe modal opens with context-aware title
- [ ] Modal shows appropriate icon and description for subscription type
- [ ] Keywords input accepts multiple keywords (comma or enter separated)
- [ ] Amount range inputs accept numeric values with currency formatting
- [ ] "Check existing" checkbox defaults to checked
- [ ] Form validation works (min < max, keyword limits)
- [ ] "Subscribe" button disabled during submission
- [ ] Loading spinner shown during submission
- [ ] Success toast appears after successful subscription
- [ ] Bell icon updates to filled state after subscription
- [ ] Modal closes after successful subscription
- [ ] Error messages displayed if submission fails
- [ ] "Advanced Options" button opens full wizard with pre-filled data
- [ ] "Cancel" button closes modal without creating subscription
- [ ] Modal is accessible (keyboard navigation, ARIA labels)
- [ ] Works for all subscription types (org, entity, signer, relationship)

## Testing Requirements

### Unit Tests

```typescript
describe('QuickSubscribeModal', () => {
  it('should render with context-aware title', () => {
    render(
      <QuickSubscribeModal
        isOpen={true}
        onClose={jest.fn()}
        context={{
          type: 'organization',
          organizationUid: '99221718',
          organizationName: 'ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ'
        }}
      />
    );
    
    expect(screen.getByText(/Subscribe to ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ/)).toBeInTheDocument();
  });

  it('should allow adding keywords', async () => {
    render(
      <QuickSubscribeModal
        isOpen={true}
        onClose={jest.fn()}
        context={{ type: 'organization', organizationUid: '99221718' }}
      />
    );
    
    const keywordInput = screen.getByPlaceholderText(/e.g., procurement/);
    
    // Type and press Enter
    await userEvent.type(keywordInput, 'procurement{enter}');
    await userEvent.type(keywordInput, 'contract{enter}');
    
    // Keywords should appear as chips/tags
    expect(screen.getByText('procurement')).toBeInTheDocument();
    expect(screen.getByText('contract')).toBeInTheDocument();
  });

  it('should validate amount range', async () => {
    render(
      <QuickSubscribeModal
        isOpen={true}
        onClose={jest.fn()}
        context={{ type: 'organization', organizationUid: '99221718' }}
      />
    );
    
    // Enter min > max
    await userEvent.type(screen.getByLabelText('Min'), '10000');
    await userEvent.type(screen.getByLabelText('Max'), '5000');
    
    // Try to submit
    fireEvent.click(screen.getByText('Subscribe'));
    
    // Error should appear
    await waitFor(() => {
      expect(screen.getByText(/Min must be less than max/)).toBeInTheDocument();
    });
  });

  it('should submit subscription successfully', async () => {
    const mockSubscription = { id: 1, organization_uid: '99221718' };
    mockAPI.createSubscription.mockResolvedValue(mockSubscription);
    
    const onComplete = jest.fn();
    
    render(
      <QuickSubscribeModal
        isOpen={true}
        onClose={jest.fn()}
        context={{ type: 'organization', organizationUid: '99221718' }}
        onComplete={onComplete}
      />
    );
    
    // Click subscribe without adding filters
    fireEvent.click(screen.getByText('Subscribe'));
    
    await waitFor(() => {
      expect(mockAPI.createSubscription).toHaveBeenCalledWith({
        organization_uid: '99221718',
        check_frequency: 'daily'
      });
    });
    
    expect(onComplete).toHaveBeenCalledWith(mockSubscription);
  });

  it('should include filters when provided', async () => {
    mockAPI.createSubscription.mockResolvedValue({ id: 1 });
    
    render(
      <QuickSubscribeModal
        isOpen={true}
        onClose={jest.fn()}
        context={{ type: 'organization', organizationUid: '99221718' }}
      />
    );
    
    // Add keyword
    await userEvent.type(
      screen.getByPlaceholderText(/e.g., procurement/),
      'procurement{enter}'
    );
    
    // Add amount
    await userEvent.type(screen.getByLabelText('Min'), '10000');
    
    // Submit
    fireEvent.click(screen.getByText('Subscribe'));
    
    await waitFor(() => {
      expect(mockAPI.createSubscription).toHaveBeenCalledWith({
        organization_uid: '99221718',
        keywords: ['procurement'],
        amount_min: '10000',
        check_frequency: 'daily'
      });
    });
  });

  it('should handle API errors', async () => {
    mockAPI.createSubscription.mockRejectedValue(
      new Error('Organization does not exist')
    );
    
    render(
      <QuickSubscribeModal
        isOpen={true}
        onClose={jest.fn()}
        context={{ type: 'organization', organizationUid: 'INVALID' }}
      />
    );
    
    fireEvent.click(screen.getByText('Subscribe'));
    
    await waitFor(() => {
      expect(screen.getByText(/Organization does not exist/)).toBeInTheDocument();
    });
  });

  it('should switch to advanced mode', () => {
    const onAdvanced = jest.fn();
    
    render(
      <QuickSubscribeModal
        isOpen={true}
        onClose={jest.fn()}
        context={{ type: 'organization', organizationUid: '99221718' }}
        onAdvanced={onAdvanced}
      />
    );
    
    fireEvent.click(screen.getByText('Advanced Options'));
    
    expect(onAdvanced).toHaveBeenCalled();
  });

  it('should close on cancel', () => {
    const onClose = jest.fn();
    
    render(
      <QuickSubscribeModal
        isOpen={true}
        onClose={onClose}
        context={{ type: 'organization', organizationUid: '99221718' }}
      />
    );
    
    fireEvent.click(screen.getByText('Cancel'));
    
    expect(onClose).toHaveBeenCalled();
  });
});

describe('useQuickSubscribeForm', () => {
  it('should initialize with defaults', () => {
    const { result } = renderHook(() =>
      useQuickSubscribeForm({ type: 'organization', organizationUid: '99221718' })
    );
    
    expect(result.current.formData).toEqual({
      keywords: [],
      checkExisting: true
    });
  });

  it('should validate amount range', () => {
    const { result } = renderHook(() =>
      useQuickSubscribeForm({ type: 'organization', organizationUid: '99221718' })
    );
    
    act(() => {
      result.current.setFormData({
        keywords: [],
        amountMin: 10000,
        amountMax: 5000,
        checkExisting: true
      });
    });
    
    const isValid = result.current.validate();
    
    expect(isValid).toBe(false);
    expect(result.current.errors.amountMin).toBeTruthy();
  });

  it('should validate keyword limit', () => {
    const { result } = renderHook(() =>
      useQuickSubscribeForm({ type: 'organization', organizationUid: '99221718' })
    );
    
    act(() => {
      result.current.setFormData({
        keywords: Array(15).fill('keyword'),
        checkExisting: true
      });
    });
    
    const isValid = result.current.validate();
    
    expect(isValid).toBe(false);
    expect(result.current.errors.keywords).toBeTruthy();
  });
});
```

### Integration Tests

```typescript
describe('Quick Subscribe Flow Integration', () => {
  it('should complete full quick subscribe flow', async () => {
    mockAPI.createSubscription.mockResolvedValue({
      id: 1,
      organization_uid: '99221718',
      is_active: true
    });
    
    render(<App />, { route: '/entity/organization/99221718' });
    
    // Click bell to open quick subscribe
    fireEvent.click(screen.getByTestId('bell-button-left'));
    
    await waitFor(() => {
      expect(screen.getByText('Quick Subscribe')).toBeInTheDocument();
    });
    
    // Add a keyword
    await userEvent.type(
      screen.getByPlaceholderText(/e.g., procurement/),
      'procurement{enter}'
    );
    
    // Click subscribe
    fireEvent.click(screen.getByText('Subscribe'));
    
    // Success toast should appear
    await waitFor(() => {
      expect(screen.getByText(/Subscribed!/)).toBeInTheDocument();
    });
    
    // Bell should be filled
    expect(screen.getByTestId('bell-icon')).toHaveClass('bell-filled');
    
    // Modal should be closed
    expect(screen.queryByText('Quick Subscribe')).not.toBeInTheDocument();
  });

  it('should switch to advanced wizard', async () => {
    render(<App />, { route: '/entity/organization/99221718' });
    
    // Open quick subscribe
    fireEvent.click(screen.getByTestId('bell-button-left'));
    
    await waitFor(() => {
      expect(screen.getByText('Quick Subscribe')).toBeInTheDocument();
    });
    
    // Click advanced options
    fireEvent.click(screen.getByText('Advanced Options'));
    
    // Full wizard should open
    await waitFor(() => {
      expect(screen.getByText('Create Subscription')).toBeInTheDocument();
      expect(screen.getByText('Type Selection')).toBeInTheDocument();
    });
  });
});
```

## Implementation Notes

### Keyword Input Component

Use a tag/chip input component for keywords:

```typescript
function KeywordInput({
  value,
  onChange,
  placeholder,
  error
}: {
  value: string[];
  onChange: (keywords: string[]) => void;
  placeholder?: string;
  error?: string;
}) {
  const [inputValue, setInputValue] = useState('');
  
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && inputValue.trim()) {
      e.preventDefault();
      const newKeyword = inputValue.trim().toLowerCase();
      if (!value.includes(newKeyword)) {
        onChange([...value, newKeyword]);
      }
      setInputValue('');
    }
  };
  
  const handleRemove = (keyword: string) => {
    onChange(value.filter(k => k !== keyword));
  };
  
  return (
    <div className="keyword-input">
      <div className="keywords-list">
        {value.map(keyword => (
          <Chip
            key={keyword}
            label={keyword}
            onDelete={() => handleRemove(keyword)}
          />
        ))}
      </div>
      <input
        type="text"
        value={inputValue}
        onChange={e => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
      />
      {error && <div className="error">{error}</div>}
    </div>
  );
}
```

### Amount Input with Currency Formatting

```typescript
function AmountInput({
  value,
  onChange,
  label,
  error
}: {
  value?: number;
  onChange: (value?: number) => void;
  label: string;
  error?: string;
}) {
  const [displayValue, setDisplayValue] = useState('');
  
  useEffect(() => {
    if (value !== undefined) {
      setDisplayValue(value.toLocaleString('el-GR'));
    }
  }, [value]);
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/[^0-9]/g, '');
    if (raw === '') {
      onChange(undefined);
      setDisplayValue('');
    } else {
      const num = parseInt(raw, 10);
      onChange(num);
      setDisplayValue(num.toLocaleString('el-GR'));
    }
  };
  
  return (
    <div className="amount-input">
      <label>{label}</label>
      <div className="input-wrapper">
        <span className="currency">€</span>
        <input
          type="text"
          value={displayValue}
          onChange={handleChange}
          placeholder="0"
        />
      </div>
      {error && <div className="error">{error}</div>}
    </div>
  );
}
```

### Transition to Full Wizard

When user clicks "Advanced Options", transfer data to full wizard:

```typescript
const handleAdvancedClick = useCallback(() => {
  // Close quick subscribe modal
  onClose();
  
  // Open full wizard with pre-filled data
  openSubscriptionWizard({
    prefill: {
      type: context.type,
      ...extractTargetFields(context),
      keywords: formData.keywords,
      amountMin: formData.amountMin,
      amountMax: formData.amountMax
    },
    skipTypeSelection: true, // Jump directly to filters
    skipTargetSelection: true
  });
}, [context, formData, onClose]);
```

## Related Files

- `frontend/src/components/QuickSubscribeModal.tsx` (new)
- `frontend/src/hooks/useQuickSubscribeForm.ts` (new)
- `frontend/src/components/KeywordInput.tsx` (new)
- `frontend/src/components/AmountInput.tsx` (new)
- `frontend/src/hooks/useBellClickHandler.ts` (Task 3.2 - integration)
- `frontend/src/api/NotificationsAPI.ts` (Task 1.1)

## Definition of Done

- [ ] All code written and reviewed
- [ ] All unit tests passing (>95% coverage)
- [ ] Integration tests passing
- [ ] UI design matches mockups
- [ ] Form validation working correctly
- [ ] Success/error feedback working
- [ ] "Advanced Options" transition working
- [ ] Works for all subscription types
- [ ] Accessibility verified
- [ ] Mobile responsive
- [ ] Performance validated (smooth animations)
- [ ] Code merged to feature branch

## Additional Resources

- [UI Specification - Quick Subscribe Flow](../../FRONTEND_UI_SPECIFICATION.md#step-3-filters-optional)
- Material-UI Chip component
- React Hook Form (if using for validation)

---

**Notes:**
- Consider showing estimated notification frequency based on historical data
- May want to add "Or choose specific decision types" option
- Consider A/B testing quick subscribe vs. always showing full wizard
- Add analytics to track conversion rate of quick subscribe vs. advanced
- Consider pre-populating common keywords based on page content or entity type
