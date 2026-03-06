# Task 5.1: Type Selection Step

**Status:** ⬜ Not Started  
**Priority:** 🔴 Critical (MVP)  
**Estimated Effort:** 2 days  
**Assignee:** _TBD_

---

## Description

Implement the first step of the subscription creation wizard: selecting the subscription type (organization, entity, relationship, person, signer, or filter-only).

## Goals

- Present all 6 subscription types clearly
- Enable user to select one type
- Skip this step when context pre-determines type (context-aware)
- Provide examples and descriptions for each type
- Set up wizard navigation structure

## Technical Requirements

### Component Interface

```typescript
interface TypeSelectionStepProps {
  selectedType?: SubscriptionType;
  onSelectType: (type: SubscriptionType) => void;
  onNext: () => void;
  onCancel: () => void;
  contextType?: SubscriptionType; // Pre-selected from context
}

type SubscriptionType = 
  | 'organization'
  | 'entity'
  | 'relationship'
  | 'person'
  | 'signer'
  | 'filter_only';
```

### Type Cards Content

```typescript
const SUBSCRIPTION_TYPES: TypeCardDefinition[] = [
  {
    type: 'organization',
    icon: '🏢',
    label: 'Organization',
    description: 'Watch all decisions from a specific organization',
    example: 'e.g., Monitor all decisions from ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ',
    color: 'blue'
  },
  {
    type: 'entity',
    icon: '🏭',
    label: 'Entity (AFM)',
    description: 'Watch decisions involving a specific company or person',
    example: 'e.g., Track when ACME Corp appears in decisions',
    color: 'green'
  },
  {
    type: 'relationship',
    icon: '🔗',
    label: 'Relationship',
    description: 'Watch decisions involving a specific organization + entity pair',
    example: 'e.g., When ΔΗΜΟΣ contracts with specific company',
    color: 'purple'
  },
  {
    type: 'person',
    icon: '👤',
    label: 'Person',
    description: 'Watch companies where a specific person is associated',
    example: 'e.g., Decisions involving Γεώργιος Παπαδόπουλος',
    color: 'orange'
  },
  {
    type: 'signer',
    icon: '✍️',
    label: 'Signer',
    description: 'Watch decisions signed by a specific person',
    example: 'e.g., Appointments signed by specific official',
    color: 'red'
  },
  {
    type: 'filter_only',
    icon: '🔍',
    label: 'Filter Only',
    description: 'Watch decisions matching custom criteria',
    example: 'e.g., High-value emergency decisions',
    color: 'gray'
  }
];
```

### UI Layout

```
Choose what you want to watch:

┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   🏢         │  │   🏭         │  │   🔗         │
│ Organization │  │   Entity     │  │ Relationship │
│              │  │   (AFM)      │  │   (Org+AFM)  │
│ Watch all    │  │ Watch a      │  │ Watch when   │
│ decisions... │  │ specific...  │  │ pairing...   │
│              │  │              │  │              │
│ e.g., Monitor│  │ e.g., Track  │  │ e.g., When   │
│ ΔΗΜΟΣ...     │  │ ACME Corp... │  │ ΔΗΜΟΣ + ...  │
└──────────────┘  └──────────────┘  └──────────────┘

┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   👤         │  │   ✍️         │  │   🔍         │
│   Person     │  │   Signer     │  │  Filter Only │
│              │  │              │  │              │
│ Watch        │  │ Watch        │  │ Custom       │
│ companies... │  │ decisions... │  │ criteria...  │
└──────────────┘  └──────────────┘  └──────────────┘

                    [Next →]
```

## Dependencies

- Task 1.1 (Type definitions)
- Task 1.2 (Context detection for auto-selection)
- Wizard container component

## Acceptance Criteria

- [ ] All 6 subscription types displayed as cards
- [ ] Each card shows icon, label, description, and example
- [ ] Cards are keyboard navigable (tab, arrow keys)
- [ ] Clicking card selects it (visual highlight)
- [ ] Only one type can be selected at a time
- [ ] Next button disabled until type selected
- [ ] Next button proceeds to step 2
- [ ] Cancel button closes wizard with confirmation
- [ ] Step indicator shows "Step 1 of 4"
- [ ] When context-aware: step is skipped OR pre-selected
- [ ] Cards are responsive (grid layout adjusts)
- [ ] Hover state shows more information
- [ ] Accessible: screen reader announces selection

## Testing Requirements

### Unit Tests

```typescript
describe('TypeSelectionStep', () => {
  it('should render all subscription type cards', () => {
    render(<TypeSelectionStep onSelectType={jest.fn()} onNext={jest.fn()} onCancel={jest.fn()} />);
    
    expect(screen.getByText('Organization')).toBeInTheDocument();
    expect(screen.getByText('Entity (AFM)')).toBeInTheDocument();
    expect(screen.getByText('Relationship')).toBeInTheDocument();
    expect(screen.getByText('Person')).toBeInTheDocument();
    expect(screen.getByText('Signer')).toBeInTheDocument();
    expect(screen.getByText('Filter Only')).toBeInTheDocument();
  });

  it('should call onSelectType when card is clicked', () => {
    const onSelectType = jest.fn();
    render(<TypeSelectionStep onSelectType={onSelectType} onNext={jest.fn()} onCancel={jest.fn()} />);
    
    const organizationCard = screen.getByTestId('type-card-organization');
    fireEvent.click(organizationCard);
    
    expect(onSelectType).toHaveBeenCalledWith('organization');
  });

  it('should highlight selected card', () => {
    const { rerender } = render(
      <TypeSelectionStep 
        selectedType={undefined}
        onSelectType={jest.fn()} 
        onNext={jest.fn()} 
        onCancel={jest.fn()} 
      />
    );
    
    const organizationCard = screen.getByTestId('type-card-organization');
    expect(organizationCard).not.toHaveClass('type-card-selected');
    
    rerender(
      <TypeSelectionStep 
        selectedType="organization"
        onSelectType={jest.fn()} 
        onNext={jest.fn()} 
        onCancel={jest.fn()} 
      />
    );
    
    expect(organizationCard).toHaveClass('type-card-selected');
  });

  it('should disable Next button when no type selected', () => {
    render(<TypeSelectionStep onSelectType={jest.fn()} onNext={jest.fn()} onCancel={jest.fn()} />);
    
    const nextButton = screen.getByRole('button', { name: /next/i });
    expect(nextButton).toBeDisabled();
  });

  it('should enable Next button when type selected', () => {
    render(
      <TypeSelectionStep 
        selectedType="organization"
        onSelectType={jest.fn()} 
        onNext={jest.fn()} 
        onCancel={jest.fn()} 
      />
    );
    
    const nextButton = screen.getByRole('button', { name: /next/i });
    expect(nextButton).not.toBeDisabled();
  });

  it('should call onNext when Next button clicked', () => {
    const onNext = jest.fn();
    render(
      <TypeSelectionStep 
        selectedType="organization"
        onSelectType={jest.fn()} 
        onNext={onNext} 
        onCancel={jest.fn()} 
      />
    );
    
    fireEvent.click(screen.getByRole('button', { name: /next/i }));
    expect(onNext).toHaveBeenCalled();
  });

  it('should pre-select type when contextType provided', () => {
    render(
      <TypeSelectionStep 
        contextType="organization"
        onSelectType={jest.fn()} 
        onNext={jest.fn()} 
        onCancel={jest.fn()} 
      />
    );
    
    const organizationCard = screen.getByTestId('type-card-organization');
    expect(organizationCard).toHaveClass('type-card-selected');
  });

  it('should show confirmation before canceling if type selected', () => {
    window.confirm = jest.fn().mockReturnValue(false);
    const onCancel = jest.fn();
    
    render(
      <TypeSelectionStep 
        selectedType="organization"
        onSelectType={jest.fn()} 
        onNext={jest.fn()} 
        onCancel={onCancel} 
      />
    );
    
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    
    expect(window.confirm).toHaveBeenCalled();
    expect(onCancel).not.toHaveBeenCalled();
  });
});

describe('TypeSelectionStep Accessibility', () => {
  it('should be keyboard navigable', () => {
    render(<TypeSelectionStep onSelectType={jest.fn()} onNext={jest.fn()} onCancel={jest.fn()} />);
    
    const cards = screen.getAllByRole('button', { name: /subscription/i });
    
    cards[0].focus();
    expect(cards[0]).toHaveFocus();
    
    userEvent.tab();
    expect(cards[1]).toHaveFocus();
  });

  it('should allow arrow key navigation between cards', () => {
    render(<TypeSelectionStep onSelectType={jest.fn()} onNext={jest.fn()} onCancel={jest.fn()} />);
    
    const cards = screen.getAllByRole('button', { name: /subscription/i });
    cards[0].focus();
    
    fireEvent.keyDown(cards[0], { key: 'ArrowRight' });
    expect(cards[1]).toHaveFocus();
    
    fireEvent.keyDown(cards[1], { key: 'ArrowLeft' });
    expect(cards[0]).toHaveFocus();
  });

  it('should select card with Enter or Space key', () => {
    const onSelectType = jest.fn();
    render(<TypeSelectionStep onSelectType={onSelectType} onNext={jest.fn()} onCancel={jest.fn()} />);
    
    const card = screen.getByTestId('type-card-organization');
    card.focus();
    
    fireEvent.keyDown(card, { key: 'Enter' });
    expect(onSelectType).toHaveBeenCalledWith('organization');
  });

  it('should announce selection to screen readers', () => {
    render(
      <TypeSelectionStep 
        selectedType="organization"
        onSelectType={jest.fn()} 
        onNext={jest.fn()} 
        onCancel={jest.fn()} 
      />
    );
    
    const card = screen.getByTestId('type-card-organization');
    expect(card).toHaveAttribute('aria-pressed', 'true');
  });
});
```

## Implementation Notes

### Component Structure

```typescript
export function TypeSelectionStep({
  selectedType: initiallySelected,
  onSelectType,
  onNext,
  onCancel,
  contextType
}: TypeSelectionStepProps) {
  const [selectedType, setSelectedType] = useState<SubscriptionType | undefined>(
    contextType || initiallySelected
  );
  
  const handleSelectType = (type: SubscriptionType) => {
    setSelectedType(type);
    onSelectType(type);
  };
  
  const handleNext = () => {
    if (selectedType) {
      onNext();
    }
  };
  
  const handleCancel = () => {
    if (selectedType) {
      const confirmed = window.confirm('Discard subscription creation?');
      if (!confirmed) return;
    }
    onCancel();
  };
  
  return (
    <div className="type-selection-step">
      <header>
        <h2>Choose what you want to watch:</h2>
        <p className="step-indicator">Step 1 of 4</p>
      </header>
      
      <div className="type-cards-grid">
        {SUBSCRIPTION_TYPES.map(typeConfig => (
          <TypeCard
            key={typeConfig.type}
            config={typeConfig}
            isSelected={selectedType === typeConfig.type}
            onClick={() => handleSelectType(typeConfig.type)}
          />
        ))}
      </div>
      
      <footer className="wizard-footer">
        <button onClick={handleCancel} className="btn-secondary">
          Cancel
        </button>
        <button 
          onClick={handleNext} 
          className="btn-primary"
          disabled={!selectedType}
        >
          Next →
        </button>
      </footer>
    </div>
  );
}

function TypeCard({ config, isSelected, onClick }: TypeCardProps) {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick();
    }
  };
  
  return (
    <button
      className={cn('type-card', {
        'type-card-selected': isSelected,
        [`type-card-${config.color}`]: true
      })}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      data-testid={`type-card-${config.type}`}
      role="button"
      aria-pressed={isSelected}
      aria-label={`${config.label} subscription`}
    >
      <div className="type-card-icon">{config.icon}</div>
      <h3 className="type-card-label">{config.label}</h3>
      <p className="type-card-description">{config.description}</p>
      <p className="type-card-example">{config.example}</p>
      {isSelected && <div className="type-card-check">✓</div>}
    </button>
  );
}
```

### Styling Notes

```css
.type-cards-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}

@media (max-width: 768px) {
  .type-cards-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 480px) {
  .type-cards-grid {
    grid-template-columns: 1fr;
  }
}

.type-card {
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  padding: 1.5rem;
  cursor: pointer;
  transition: all 0.2s;
}

.type-card:hover {
  border-color: var(--primary-color);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.type-card-selected {
  border-color: var(--primary-color);
  background-color: var(--primary-light);
}
```

## Related Files

- `frontend/src/components/SubscriptionWizard/TypeSelectionStep.tsx` (new)
- `frontend/src/components/SubscriptionWizard/TypeCard.tsx` (new)
- `frontend/src/components/SubscriptionWizard/SubscriptionWizard.tsx` (wizard container)

## Definition of Done

- [ ] All code written and reviewed
- [ ] All unit tests passing (>90% coverage)
- [ ] Accessibility tests passing
- [ ] Keyboard navigation works
- [ ] Responsive on all screen sizes
- [ ] Visual design approved
- [ ] Context-aware pre-selection works
- [ ] Code merged to feature branch

## Additional Resources

- [UI Specification - Subscription Creation Wizard](../../FRONTEND_UI_SPECIFICATION.md#step-1-subscription-type-selection)
- [Integration Guide - Subscription Types](../../FRONTEND_INTEGRATION_GUIDE.md#core-concepts)

---

**Notes:**
- Consider adding animated illustrations for each type
- May want tooltips with more detailed explanations
- Consider allowing keyboard shortcuts (1-6 to select types)
