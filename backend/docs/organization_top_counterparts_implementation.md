# Organization Top Counterparts Implementation

## Overview

This implementation adds a new endpoint to get top entities (counterparts) by total amount for an organization in a date range. This is optimized for pagination and designed to handle the use case where users want to see which vendors/entities received the most money from an organization.

## Architecture Decisions

### Why On-the-Fly Calculations (Not Pre-Calculation)

1. **Data is mostly static** - Vendors typically don't have many interactions per day, so query results don't change frequently
2. **High cache hit rate** - With 5-minute TTL, most requests will hit cache
3. **Avoids complexity** - No need for backfill jobs, stale data handling, or additional tables
4. **Future flexibility** - Easy to add filters (decision types, KAE codes, etc.)

### When to Consider Pre-Calculation

Only if monitoring shows:
- Query times consistently > 300ms
- Database CPU > 70% during peak traffic
- Specific date ranges (e.g., "last 30 days") queried repeatedly

## Implementation Details

### 1. Service Method: `FinancialCalculationService.get_top_counterparts_for_organization()`

**Location:** `core/services/financial_calculation_service.py`

**Features:**
- Single optimized query with pagination support
- Returns total count for pagination UI
- Filters by roles (defaults to MONEY_RECEIVED_ROLES)
- Only includes entities with actual amounts (> 0)
- Performance monitoring built-in

**Parameters:**
- `organization`: Organization to analyze
- `start_date`: Start of date range
- `end_date`: End of date range
- `limit`: Number of results to return (default: 5)
- `offset`: Pagination offset (default: 0)
- `roles`: Optional list of roles to filter by

**Returns:**
```python
{
    'results': [
        {
            'entity__afm': '094079101',
            'entity__name': 'Ε.ΥΔ.Α.Π. Α.Ε.',
            'entity__entity_type': 'company',
            'total_amount': 5587643.46,
            'decision_count': 12
        },
        ...
    ],
    'total_count': 47,
    'has_more': True
}
```

### 2. API Endpoint: `organization_top_counterparts_api`

**Location:** `api/views/organization_entity_relationships/__init__.py`

**URL:** `/api/organizations/<organization_uid>/top-counterparts/`

**Parameters:**
- `organization_uid` (required): Organization UID
- `start_date` (required): Start date (YYYY-MM-DD)
- `end_date` (required): End date (YYYY-MM-DD)
- `limit` (optional): Number of results (default: 5)
- `offset` (optional): Pagination offset (default: 0)

**Response:**
```json
{
    "organization": {
        "uid": "MINISTRY_UID",
        "label": "Ministry Name"
    },
    "date_range": {
        "start": "2025-12-01",
        "end": "2026-01-06"
    },
    "results": [...],
    "pagination": {
        "limit": 5,
        "offset": 0,
        "total_count": 47,
        "has_more": true
    }
}
```

**Validation:**
- Required parameters checked
- Date format validated
- Date range validated (start <= end)
- Organization existence checked
- Warning logged for large date ranges (> 365 days)

### 3. URL Configuration

**Location:** `api/urls.py`

**Added:**
```python
path('explore/organizations/<str:organization_uid>/top-counterparts/', 
     search.organization_top_counterparts_api, 
     name='organization_top_counterparts')
```

## Performance Considerations

### Current Approach (On-the-Fly + Caching)

**Pros:**
- ✅ Simple implementation
- ✅ No additional tables to maintain
- ✅ Data is always fresh (5-minute cache)
- ✅ Easy to extend with new filters
- ✅ Works well with "few thousand decisions per day" scale

**Cons:**
- ⚠️ Database query on cache miss (acceptable with proper indexes)
- ⚠️ Cache invalidation not implemented (acceptable with short TTL)

### Recommended Database Indexes

**Add these indexes for optimal performance:**

```sql
-- Index for org-entity-date queries (main use case)
CREATE INDEX CONCURRENTLY IF NOT EXISTS 
idx_org_entity_date_amount ON core_decisionentityrelationship 
(decision__organization_id, entity_id, decision__issue_date DESC) 
WHERE role IN ('sponsorAFMName', 'grantee', 'grantor');

-- Index for amount lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS 
idx_amount_rel_amount ON core_decisionamountfield 
(associated_relationship_id, amount DESC) 
WHERE associated_relationship_id IS NOT NULL;

-- Composite index for decision date + org
CREATE INDEX CONCURRENTLY IF NOT EXISTS 
idx_decision_org_date ON core_decision 
(organization_id, issue_date DESC);
```

**Create a migration file:** `backend/core/migrations/XXXX_add_counterparts_indexes.py`

### Caching Strategy

**Current:** No caching implemented yet (can be added if needed)

**Recommended (if queries are slow):**
```python
from django.core.cache import cache

def get_top_counterparts_for_organization(...):
    cache_key = f"top_counterparts:{org_uid}:{start_date}:{end_date}:{limit}:{offset}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    result = # ... query ...
    cache.set(cache_key, result, timeout=300)  # 5 minutes
    return result
```

**Cache invalidation:** Not needed with 5-minute TTL for now. Can add later if stale data becomes an issue.

## Testing

### Test Script

**Location:** `backend/test_top_counterparts.py`

**Run:**
```bash
cd backend
python test_top_counterparts.py
```

**What it tests:**
- Service method execution
- Pagination (page 1 and page 2)
- Data structure and formatting
- Error handling

### Manual API Testing

```bash
# Test with specific organization
curl "http://localhost:8000/api/explore/organizations/MINISTRY_UID/top-counterparts/?start_date=2025-12-01&end_date=2026-01-06&limit=5"

# Test pagination
curl "http://localhost:8000/api/explore/organizations/MINISTRY_UID/top-counterparts/?start_date=2025-12-01&end_date=2026-01-06&limit=5&offset=5"

# Test with larger limit
curl "http://localhost:8000/api/explore/organizations/MINISTRY_UID/top-counterparts/?start_date=2025-12-01&end_date=2026-01-06&limit=20"
```

## Monitoring

### Performance Monitoring

The endpoint includes `@monitor_query_performance(operation="organization_top_counterparts")` which will log:
- Query execution time
- Database query details
- Cache hit/miss (when caching is added)

### Metrics to Watch

1. **Query latency:** p50, p95, p99
2. **Cache hit rate:** (when caching is added)
3. **Database CPU:** During peak traffic
4. **Slow query log:** Any queries > 500ms

### Grafana/Loki Integration

Logs are already structured with context, so you can query:
```
{operation="organization_top_counterparts"} |>= 5m
```

## Next Steps

### Phase 1: Current Implementation ✅
- [x] Add service method
- [x] Add API endpoint
- [x] Add URL configuration
- [x] Create test script
- [ ] Add database indexes
- [ ] Deploy to staging
- [ ] Test with real data

### Phase 2: Performance Optimization (If Needed)
- [ ] Add Redis caching
- [ ] Monitor query performance
- [ ] Add cache invalidation (if needed)

### Phase 3: Pre-Calculation (If Needed)
- [ ] Measure query times in production
- [ ] Identify hot date ranges
- [ ] Implement monthly aggregates (if queries > 300ms)
- [ ] Add backfill job for aggregates

### Phase 4: Frontend Integration
- [ ] Create organization page component
- [ ] Implement infinite scroll or pagination
- [ ] Add date range picker
- [ ] Create entity-organization detail page
- [ ] Add loading states and error handling

## Frontend Integration Notes

### Expected API Response Structure

```typescript
interface TopCounterpartsResponse {
    organization: {
        uid: string;
        label: string;
    };
    date_range: {
        start: string;  // YYYY-MM-DD
        end: string;    // YYYY-MM-DD
    };
    results: Array<{
        entity__afm: string;
        entity__name: string;
        entity__entity_type: string;
        total_amount: number;
        decision_count: number;
    }>;
    pagination: {
        limit: number;
        offset: number;
        total_count: number;
        has_more: boolean;
    };
}
```

### UX Recommendations

1. **Show skeleton loaders** while fetching
2. **Handle empty states** gracefully (no counterparts found)
3. **Use infinite scroll** for better UX than traditional pagination
4. **Show decision count** alongside amount (helps users understand significance)
5. **Link to entity-organization page** when user clicks on a counterpart
6. **Cache results** in frontend state to avoid refetching on back navigation

### Example Frontend Flow

```
User visits organization page
  ↓
Selects date range (e.g., "Last 30 days")
  ↓
Frontend calls: /api/explore/organizations/{uid}/top-counterparts/?start_date=...&end_date=...
  ↓
Shows top 5 counterparts with amounts
  ↓
User scrolls down
  ↓
Frontend calls: ...&offset=5
  ↓
Shows next 5 counterparts
  ↓
User clicks on a counterpart
  ↓
Navigates to entity-organization page (to be implemented)
```

## Troubleshooting

### Common Issues

**Issue:** Query is slow (> 1 second)
**Solution:** Add the recommended database indexes

**Issue:** Results don't update after new decisions
**Solution:** Reduce cache TTL or add cache invalidation

**Issue:** Pagination shows wrong total_count
**Solution:** Check if `distinct()` is working correctly for your data

**Issue:** Organization not found error
**Solution:** Verify organization UID is correct and organization exists in database

## Summary

This implementation provides a solid foundation for showing top counterparts between organizations and entities. It's designed to:

1. **Perform well** at your scale (few thousand decisions/day)
2. **Scale easily** with proper database indexes
3. **Stay fresh** with short cache TTL (or add invalidation later)
4. **Be flexible** for future enhancements (filters, pre-calculation, etc.)

**Next action:** Add database indexes, deploy to staging, and observe performance before adding caching or pre-calculation.

## Sample Requests

------------------------------------------------------

curl -X 'GET' \
  'http://localhost/api/entities/094079101/top-organizations/?start_date=2025-12-20&end_date=2025-12-31&limit=4' \
  -H 'accept: application/json' \
  -H 'X-CSRFTOKEN: iTsMp4ce37HwbGFBU123tgmW6W9BaadFY5OaxxJolGONfsOwcCvJ694oTyrvkHhE'

  {
  "entity": {
    "afm": "094079101",
    "name": "ΕΤΑΙΡΙΑ ΥΔΡΕΥΣΕΩΣ ΚΑΙ ΑΠΟΧΕΤΕΥΣΕΩΣ ΠΡΩΤΕΥΟΥΣΗΣ ΑΝΩΝΥΜΗ ΕΤΑΙΡΕΙΑ",
    "entity_type": "company"
  },
  "date_range": {
    "start": "2025-12-20",
    "end": "2025-12-31"
  },
  "results": [
    {
      "decision__organization__uid": "99201057",
      "decision__organization__label": "ΕΤΑΙΡΕΙΑ ΠΑΓΙΩΝ ΕΥΔΑΠ",
      "total_amount": 5587643.46,
      "decision_count": 1
    },
    {
      "decision__organization__uid": "6026",
      "decision__organization__label": "ΔΗΜΟΣ ΑΜΑΡΟΥΣΙΟΥ",
      "total_amount": 75935.25,
      "decision_count": 1
    },
    {
      "decision__organization__uid": "6243",
      "decision__organization__label": "ΔΗΜΟΣ ΠΕΙΡΑΙΩΣ",
      "total_amount": 45430.25,
      "decision_count": 9
    },
    {
      "decision__organization__uid": "99221632",
      "decision__organization__label": "ΚΕΝΤΡΟ ΕΚΠ/ΣΗΣ ΚΑΙ ΑΠΟΚΑΤΑΣΤΑΣΗΣ ΤΥΦΛΩΝ (ΚΕΑΤ)",
      "total_amount": 629.91,
      "decision_count": 15
    }
  ],
  "pagination": {
    "limit": 4,
    "offset": 0,
    "total_count": 6,
    "has_more": true
  }
}

------------------------------------------------------

curl -X 'GET' \
  'http://localhost/api/organizations/99201057/top-counterparts/?start_date=2025-12-20&end_date=2025-12-31' \
  -H 'accept: application/json' \
  -H 'X-CSRFTOKEN: iTsMp4ce37HwbGFBU123tgmW6W9BaadFY5OaxxJolGONfsOwcCvJ694oTyrvkHhE'

{
  "organization": {
    "uid": "99201057",
    "label": "ΕΤΑΙΡΕΙΑ ΠΑΓΙΩΝ ΕΥΔΑΠ"
  },
  "date_range": {
    "start": "2025-12-20",
    "end": "2025-12-31"
  },
  "results": [
    {
      "entity__afm": "094079101",
      "entity__name": "ΕΤΑΙΡΙΑ ΥΔΡΕΥΣΕΩΣ ΚΑΙ ΑΠΟΧΕΤΕΥΣΕΩΣ ΠΡΩΤΕΥΟΥΣΗΣ ΑΝΩΝΥΜΗ ΕΤΑΙΡΕΙΑ",
      "entity__entity_type": "company",
      "total_amount": 5587643.46,
      "decision_count": 1
    },
    {
      "entity__afm": "090165560",
      "entity__name": "ΦΟΡΟΣ 4% ΛΟΙΠΩΝ ΠΡΟΜΗΘΕΙΩΝ",
      "entity__entity_type": "person",
      "total_amount": 366107.77,
      "decision_count": 4
    },
    {
      "entity__afm": "997072577",
      "entity__name": "ΕΦΚΑ (ΕΝΙΑΙΟΣ ΦΟΡΕΑΣ ΚΟΙΝΩΝΙΚΗΣ ΑΣΦΑΛΙΣΗΣ)",
      "entity__entity_type": "person",
      "total_amount": 7409.16,
      "decision_count": 1
    },
    {
      "entity__afm": "999456372",
      "entity__name": "Β. ΚΟΚΚΩΝΗΣ & ΣΙΑ ΕΕ",
      "entity__entity_type": "person",
      "total_amount": 1736,
      "decision_count": 1
    },
    {
      "entity__afm": "998406137",
      "entity__name": "CLEAN LEVEL Μ.ΕΠΕ ΚΑΘΑΡΙΣΜΟΙ ΚΤΙΡΙΩΝ",
      "entity__entity_type": "company",
      "total_amount": 1577.35,
      "decision_count": 2
    }
  ],
  "pagination": {
    "limit": 5,
    "offset": 0,
    "total_count": 7,
    "has_more": true
  }
}