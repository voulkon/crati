# Task 7.2: Validation & Error Display

**Status:** ⬜ Not Started  
**Priority:** 🟡 High Priority  
**Estimated Effort:** 2-3 days  
**Assignee:** _TBD_

---

## Description

Implement comprehensive client-side validation for all subscription forms and provide clear, user-friendly error messages with inline field feedback and recovery options.

## Goals

- Validate all form inputs before submission
- Display field-specific error messages
- Show API validation errors returned from backend
- Provide clear recovery paths for errors
- Prevent invalid submissions
- Maintain good UX with non-intrusive error display

## Technical Requirements

### Validation Rules

```typescript
interface ValidationRules {
  // Keywords
  keywords?: {
    minItems?: number;      // Default: 0 (optional)
    maxItems?: number;      // Default: 20
    minLength?: number;     // Per keyword, default: 2
    maxLength?: number;     // Per keyword, default: 100
  };
  
  // Amount range
  amount?: {
    min?: number;           // Default: 0
    max?: number;           // Default: unlimited
    mustBePositive?: boolean;
    minMustBeLessThanMax?: boolean;
  };
  
  // Decision types
  decisionTypes?: {
    minItems?: number;      // Default: 0 (optional)
    maxItems?: number;      // Default: 50
  };
  
  // Required fields (varies by subscription type)
  required?: string[];      // e.g., ['organization_uid'], ['entity_afm']
}
```

### Validation Messages

```typescript
const VALIDATION_MESSAGES = {
  required: (field: string) => `${field} is required`,
  minLength: (field: string, min: number) => `${field} must be at least ${min} characters`,
  maxLength: (field: string, max: number) => `${field} must not exceed ${max} characters`,
  minItems: (field: string, min: number) => `Select at least ${min} ${field}`,
  maxItems: (field: string, max: number) => `Cannot select more than ${max} ${field}`,
  invalidFormat: (field: string) => `Invalid ${field} format`,
  amountRange: 'Minimum amount must be less than maximum amount',
  atLeastOneFilter: 'At least one target OR one filter must be set',
  invalidNumber: 'Please enter a valid number',
  positiveNumber: 'Amount must be a positive number'
};
```

### Error Display Patterns

1. **Field-level errors** - Inline below input
2. **Form-level errors** - Alert box at top of step
3. **API errors** - Toast + inline (if field-specific)
4. **Non-field errors** - Callout box with explanation

## Dependencies

- Task 5.1-5.4 (Subscription wizard steps)
- Task 1.1 (API client with typed errors)
- Form library (React Hook Form or similar)

## Acceptance Criteria

- [ ] Real-time validation on blur (not on every keystroke)
- [ ] Submit button disabled if form invalid
- [ ] Field errors displayed inline below input
- [ ] Error colors/icons used consistently (red, ⚠️)
- [ ] API validation errors mapped to fields correctly
- [ ] Non-field API errors shown in alert box
- [ ] Error messages are clear and actionable
- [ ] Required fields marked with asterisk (*)
- [ ] Validation feedback is immediate (< 100ms)
- [ ] Successful submission clears all errors
- [ ] Form can be corrected and re-submitted
- [ ] Async validation for entity existence (if needed)
- [ ] Accessibility: errors announced to screen readers
- [ ] Error summary for screen readers at form top

## Testing Requirements

### Unit Tests

```typescript
describe('Subscription Form Validation', () => {
  it('should require organization_uid for organization subscriptions', async () => {
    render(<SubscriptionWizard initialType="organization" />);
    
    // Skip to review step without selecting organization
    goToStep(4);
    
    const submitButton = screen.getByRole('button', { name: /create/i });
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(screen.getByText(/organization is required/i)).toBeInTheDocument();
    });
    expect(submitButton).toBeDisabled();
  });

  it('should validate amount_min <= amount_max', async () => {
    render(<FiltersStep />);
    
    const minInput = screen.getByLabelText(/minimum amount/i);
    const maxInput = screen.getByLabelText(/maximum amount/i);
    
    fireEvent.change(minInput, { target: { value: '100000' } });
    fireEvent.change(maxInput, { target: { value: '50000' } });
    fireEvent.blur(maxInput);
    
    await waitFor(() => {
      expect(screen.getByText(/minimum must be less than maximum/i)).toBeInTheDocument();
    });
  });

  it('should validate keyword length', async () => {
    render(<FiltersStep />);
    
    const keywordInput = screen.getByLabelText(/keywords/i);
    
    fireEvent.change(keywordInput, { target: { value: 'a' } }); // Too short
    fireEvent.blur(keywordInput);
    
    await waitFor(() => {
      expect(screen.getByText(/at least 2 characters/i)).toBeInTheDocument();
    });
  });

  it('should limit number of keywords', async () => {
    const keywords = Array.from({ length: 21 }, (_, i) => `keyword${i}`);
    
    render(<FiltersStep initialKeywords={keywords} />);
    
    await waitFor(() => {
      expect(screen.getByText(/cannot select more than 20/i)).toBeInTheDocument();
    });
  });

  it('should validate at least one target or filter required', async () => {
    render(<SubscriptionWizard initialType="filter_only" />);
    
    // Skip to review without adding any filters
    goToStep(4);
    
    const submitButton = screen.getByRole('button', { name: /create/i });
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(screen.getByText(/at least one filter must be set/i)).toBeInTheDocument();
    });
  });

  it('should display API validation errors on fields', async () => {
    mockAPI.createSubscription.mockRejectedValue({
      status: 400,
      field_errors: {
        organization_uid: ['Organization with uid "INVALID" does not exist.']
      }
    });
    
    render(<SubscriptionWizard />);
    
    // Fill form and submit
    fillForm({ organization_uid: 'INVALID' });
    fireEvent.click(screen.getByRole('button', { name: /create/i }));
    
    await waitFor(() => {
      expect(screen.getByText(/organization.*does not exist/i)).toBeInTheDocument();
    });
    
    // Error should be near the organization_uid field
    const orgField = screen.getByLabelText(/organization/i);
    const orgError = screen.getByText(/does not exist/i);
    expect(orgError).toBeInTheDocument();
  });

  it('should display non-field API errors in alert box', async () => {
    mockAPI.createSubscription.mockRejectedValue({
      status: 400,
      non_field_errors: ['Duplicate subscription already exists.']
    });
    
    render(<SubscriptionWizard />);
    
    fillFormAndSubmit();
    
    await waitFor(() => {
      const alert = screen.getByRole('alert');
      expect(alert).toHaveTextContent(/duplicate subscription/i);
    });
  });

  it('should clear errors when correcting input', async () => {
    render(<FiltersStep />);
    
    const minInput = screen.getByLabelText(/minimum amount/i);
    const maxInput = screen.getByLabelText(/maximum amount/i);
    
    // Trigger error
    fireEvent.change(minInput, { target: { value: '100000' } });
    fireEvent.change(maxInput, { target: { value: '50000' } });
    fireEvent.blur(maxInput);
    
    await waitFor(() => {
      expect(screen.getByText(/minimum must be less than maximum/i)).toBeInTheDocument();
    });
    
    // Correct input
    fireEvent.change(minInput, { target: { value: '40000' } });
    fireEvent.blur(minInput);
    
    await waitFor(() => {
      expect(screen.queryByText(/minimum must be less than maximum/i)).not.toBeInTheDocument();
    });
  });

  it('should validate positive numbers for amounts', async () => {
    render(<FiltersStep />);
    
    const minInput = screen.getByLabelText(/minimum amount/i);
    
    fireEvent.change(minInput, { target: { value: '-100' } });
    fireEvent.blur(minInput);
    
    await waitFor(() => {
      expect(screen.getByText(/must be a positive number/i)).toBeInTheDocument();
    });
  });
});

describe('Error Accessibility', () => {
  it('should associate error messages with fields using aria-describedby', async () => {
    render(<FiltersStep />);
    
    const minInput = screen.getByLabelText(/minimum amount/i);
    
    fireEvent.change(minInput, { target: { value: '-100' } });
    fireEvent.blur(minInput);
    
    await waitFor(() => {
      const errorId = minInput.getAttribute('aria-describedby');
      expect(errorId).toBeTruthy();
      expect(document.getElementById(errorId!)).toHaveTextContent(/positive number/i);
    });
  });

  it('should announce errors to screen readers', async () => {
    render(<SubscriptionWizard />);
    
    fillFormAndSubmit({ invalid: true });
    
    await waitFor(() => {
      const liveRegion = screen.getByRole('alert');
      expect(liveRegion).toHaveAttribute('aria-live', 'polite');
      expect(liveRegion).toHaveTextContent(/error/i);
    });
  });

  it('should provide error summary for screen readers', async () => {
    render(<SubscriptionWizard />);
    
    // Trigger multiple errors
    fillFormAndSubmit({ 
      organization_uid: '',
      amount_min: '100000',
      amount_max: '50000'
    });
    
    await waitFor(() => {
      const errorSummary = screen.getByRole('alert');
      expect(errorSummary).toHaveTextContent('2 errors');
      expect(errorSummary).toHaveTextContent('Organization is required');
      expect(errorSummary).toHaveTextContent('Minimum must be less than maximum');
    });
  });
});
```

## Implementation Notes

### Validation Hook

```typescript
function useSubscriptionValidation(subscriptionType: SubscriptionType) {
  const validate = useCallback((values: Partial<NotificationSubscription>) => {
    const errors: Record<string, string> = {};
    
    // Type-specific required fields
    if (subscriptionType === 'organization' && !values.organization_uid) {
      errors.organization_uid = 'Organization is required';
    }
    
    if (subscriptionType === 'entity' && !values.entity_afm) {
      errors.entity_afm = 'Entity AFM is required';
    }
    
    // Amount range validation
    if (values.amount_min && values.amount_max) {
      if (parseFloat(values.amount_min) > parseFloat(values.amount_max)) {
        errors.amount_max = 'Maximum amount must be greater than minimum';
      }
    }
    
    if (values.amount_min && parseFloat(values.amount_min) < 0) {
      errors.amount_min = 'Amount must be positive';
    }
    
    // Keywords validation
    if (values.keywords && values.keywords.length > 20) {
      errors.keywords = 'Cannot have more than 20 keywords';
    }
    
    if (values.keywords) {
      for (const keyword of values.keywords) {
        if (keyword.length < 2) {
          errors.keywords = 'Each keyword must be at least 2 characters';
          break;
        }
      }
    }
    
    // At least one target or filter
    const hasTarget = values.organization_uid || values.entity_afm || 
                      values.signer_name || values.person_name;
    const hasFilters = values.keywords?.length || values.amount_min || 
                       values.amount_max || values.decision_types?.length;
    
    if (!hasTarget && !hasFilters) {
      errors._form = 'At least one target or filter must be set';
    }
    
    return errors;
  }, [subscriptionType]);
  
  return { validate };
}
```

### Error Display Component

```typescript
function FieldError({ error }: { error?: string }) {
  if (!error) return null;
  
  return (
    <div 
      className="field-error" 
      role="alert" 
      aria-live="polite"
      id={`error-${Date.now()}`}
    >
      <span className="error-icon" aria-hidden="true">⚠️</span>
      <span className="error-message">{error}</span>
    </div>
  );
}

function FormError({ errors }: { errors: string[] }) {
  if (errors.length === 0) return null;
  
  return (
    <div className="form-error-summary" role="alert" aria-live="polite">
      <h3>Please fix the following errors:</h3>
      <ul>
        {errors.map((error, i) => (
          <li key={i}>{error}</li>
        ))}
      </ul>
    </div>
  );
}
```

### API Error Handling

```typescript
async function handleSubmit(values: CreateSubscriptionRequest) {
  try {
    await createSubscription(values);
    toast.success('Subscription created!');
    onSuccess();
  } catch (error) {
    if (error instanceof NotificationAPIError) {
      // Field-specific errors
      if (error.field_errors) {
        Object.entries(error.field_errors).forEach(([field, messages]) => {
          setError(field, { message: messages[0] });
        });
      }
      
      // Non-field errors
      if (error.non_field_errors) {
        setFormError(error.non_field_errors);
      }
    } else {
      toast.error('An unexpected error occurred');
      console.error(error);
    }
  }
}
```

### Styling

```css
.field-error {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.25rem;
  color: var(--error-color);
  font-size: 0.875rem;
}

.error-icon {
  font-size: 1rem;
}

.form-error-summary {
  background-color: var(--error-bg);
  border: 1px solid var(--error-color);
  border-radius: 4px;
  padding: 1rem;
  margin-bottom: 1rem;
}

.field-with-error input,
.field-with-error select {
  border-color: var(--error-color);
}

.field-with-error input:focus {
  outline-color: var(--error-color);
  box-shadow: 0 0 0 2px var(--error-color-transparent);
}
```

## Related Files

- All wizard step components (Tasks 5.1-5.4)
- `frontend/src/hooks/useSubscriptionValidation.ts` (new)
- `frontend/src/components/Form/FieldError.tsx` (new)
- `frontend/src/components/Form/FormErrorSummary.tsx` (new)

## Definition of Done

- [ ] All code written and reviewed
- [ ] All unit tests passing (>90% coverage)
- [ ] Accessibility tests passing
- [ ] All validation rules implemented
- [ ] API error handling complete
- [ ] Error messages are clear and helpful
- [ ] Screen reader announcements working
- [ ] Visual design approved
- [ ] Code merged to feature branch

## Additional Resources

- [UI Specification - Validation & Error Handling](../../FRONTEND_UI_SPECIFICATION.md#validation--error-handling)
- [Integration Guide - Error Handling](../../FRONTEND_INTEGRATION_GUIDE.md#validation--error-handling)
- [WAI-ARIA: Form Validation](https://www.w3.org/WAI/WCAG21/Techniques/aria/ARIA21)

---

**Notes:**
- Consider using a validation library like Yup or Zod for complex rules
- May want to add warning states (yellow) vs error states (red)
- Consider showing validation on submit vs on blur (UX preference)
