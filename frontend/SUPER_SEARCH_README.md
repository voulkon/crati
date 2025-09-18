# Super Search Feature

A powerful, unified search component that allows users to search across all entity types (organizations, documents, companies, signers, etc.) with real-time autocomplete and intelligent result categorization.

## Features

### 🔍 **Unified Search Experience**
- Single search box for all data types
- Real-time autocomplete suggestions
- Intelligent result categorization
- Keyboard navigation support

### 📊 **Multi-Entity Search**
Search across:
- **Organizations** - Government bodies, departments
- **Signers** - Decision signers and officials  
- **Units** - Organizational units and departments
- **Companies** - Private companies and entities
- **Company Persons** - Company representatives
- **Documents** - Full-text search with highlighted excerpts

### 🎯 **Smart Results Display**
- **Categorized results** grouped by entity type
- **Highlighted matching text** with `<em>` and `<mark>` tags
- **Rich document excerpts** with context from OpenSearch
- **Metadata display** for documents (dates, amounts, signers)
- **Relevance scoring** for search results

### ⚡ **Performance Optimized**
- **Debounced search** (300ms) to reduce API calls
- **Intelligent caching** via API client
- **Lazy loading** of full results
- **Rate limiting aware** with graceful degradation

## Usage

### Basic Implementation

```jsx
import SuperSearch from '../components/SuperSearch';

function MyPage() {
  return (
    <SuperSearch
      placeholder="Search organizations, documents, companies..."
      onResultClick={(item) => {
        console.log('User clicked:', item);
        // Handle navigation or custom action
      }}
    />
  );
}
```

### Advanced Configuration

```jsx
<SuperSearch
  placeholder="Custom placeholder text..."
  showFullResults={true}        // Include document search
  autoFocus={false}            // Auto-focus on mount
  className="my-custom-class"   // Additional CSS class
  onResultClick={(item) => {
    // Custom click handler
    if (item.type === 'document') {
      navigate(`/decision/${item.details.decision_id}`);
    }
  }}
/>
```

## Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `placeholder` | `string` | `"Search organizations, documents, companies..."` | Input placeholder text |
| `onResultClick` | `function` | `undefined` | Custom click handler for results |
| `showFullResults` | `boolean` | `true` | Whether to include document search |
| `autoFocus` | `boolean` | `false` | Auto-focus the input on mount |
| `className` | `string` | `""` | Additional CSS class for container |

## API Integration

The component uses the `/api/search/super/` endpoint which returns:

```json
{
  "query": "ΚΑΡΤΑ ΣΗΜΑΝΣΗΣ",
  "results": {
    "organizations": [...],
    "signers": [...],
    "units": [...], 
    "companies": [...],
    "company_persons": [...],
    "documents": [
      {
        "id": 7018,
        "type": "document",
        "title": "ΠΡΟΜΗΘΕΙΑ <em>ΚΑΡΤΩΝ</em> <em>ΣΗΜΑΝΣΗΣ</em>...",
        "subtitle": "By ΗΛΕΚΤΡΟΝΙΚΟΣ ΕΘΝΙΚΟΣ ΦΟΡΕΑΣ...",
        "description": "Document excerpt with highlights...",
        "details": {
          "decision_id": 136831,
          "ada": "ΨΛΔΣ46ΜΑΠΣ-Γ4Γ",
          "organization": "ΗΛΕΚΤΡΟΝΙΚΟΣ ΕΘΝΙΚΟΣ ΦΟΡΕΑΣ...",
          "issue_date": "2025-05-05T21:00:00+00:00",
          "signers": ["ΕΥΓΕΝΙΑ ΤΖΑΚΑ"]
        },
        "highlights": {
          "title": ["ΠΡΟΜΗΘΕΙΑ <em>ΚΑΡΤΩΝ</em> <em>ΣΗΜΑΝΣΗΣ</em>..."],
          "content": ["...highlighted content excerpts..."]
        }
      }
    ]
  },
  "total_count": 1
}
```

## Styling

The component uses CSS variables for theming and follows the existing design system:

```css
/* Key CSS variables used */
--primary-blue
--border-color
--card-bg
--text-color
--muted-text
--hover-bg
--spacing-* (xs, sm, md, lg, xl)
--radius-* (sm, md, lg)
--font-* (xs, sm, md, lg, xl)
--transition-fast
```

### Custom Styling

```css
.my-custom-search {
  max-width: 500px;
}

.my-custom-search .super-search-input {
  font-size: 18px;
}
```

## Keyboard Navigation

- **↑/↓ Arrow Keys** - Navigate through results
- **Enter** - Select highlighted result  
- **Escape** - Close results dropdown
- **Tab** - Move focus to next element

## Accessibility

- Full keyboard navigation support
- ARIA labels and roles
- Focus indicators
- Screen reader friendly
- High contrast support

## Examples

### Homepage Integration
```jsx
// In HomePage.js
<div className="hero-search">
  <SuperSearch
    placeholder="Search organizations, documents, companies, signers..."
    autoFocus={false}
    showFullResults={true}
    className="homepage-super-search"
  />
</div>
```

### Quick Entity Search
```jsx
// For autocomplete-style search without documents
<SuperSearch
  placeholder="Quick entity search..."
  showFullResults={false}
  onResultClick={(item) => navigate(`/entity/${item.type}/${item.id}`)}
/>
```

### Custom Result Handling
```jsx
<SuperSearch
  onResultClick={(item) => {
    switch (item.type) {
      case 'organization':
        navigate(`/entity/organization/${item.id}`);
        break;
      case 'document':
        navigate(`/decision/${item.details.decision_id}`);
        break;
      case 'company':
        window.open(`/entity/company/${item.id}`, '_blank');
        break;
      default:
        console.log('Unknown type:', item.type);
    }
  }}
/>
```

## Files Structure

```
src/
├── api/
│   └── searchApi.js           # API service functions
├── components/
│   ├── SuperSearch.js         # Main component
│   └── SuperSearch.css        # Component styles
├── pages/
│   ├── SearchResults.js       # Full search results page
│   ├── SearchResults.css      # Results page styles
│   ├── SuperSearchExample.js  # Example/demo page
│   └── SuperSearchExample.css # Example page styles
```

## Test Examples

Visit `/search-example` to see the component in action with different configurations.

### Test Queries
Try these Greek government data searches:
- `ΚΑΡΤΑ ΣΗΜΑΝΣΗΣ` - Returns documents about ID cards
- `ΚΟΙΝΟΠΡΑΞΙΑ ΠΛΟΙΩΝ` - Returns companies and documents about ship consortiums  
- `ΟΡΓΑΝΙΣΜΟΣ ΤΗΛΕΠΙΚΟΙΝΩΝΙΩΝ` - Returns OTE (telecom organization) data
- `ΠΕΡΙΦΕΡΕΙΑ` - Returns regional government entities

## Backend Requirements

Ensure the backend has:
- `/api/search/super/` endpoint implemented
- OpenSearch integration for document full-text search
- Proper highlighting in search results
- Rate limiting configured
- CORS headers for frontend requests

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Performance Notes

- Debounced search reduces API calls
- Results are cached by the API client
- Large result sets are paginated
- Images and heavy assets are lazy-loaded
