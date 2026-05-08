# Personal Search History System

## Overview

The personal search history system tracks user searches in Redis for fast retrieval and provides privacy-friendly history features. It complements the existing `SearchAnalytics` database model by providing real-time access to recent searches.

## Architecture

### Components

1. **SearchHistoryService** (`core/services/search_history_service.py`)
   - Redis-based service for tracking and retrieving search history
   - Uses sorted sets for chronological ordering
   - Supports both authenticated users and anonymous IPs
   - Auto-expires after 90 days

2. **Redis Keys** (`api/redis_keys.py`)
   - `search_history:user:<user_id>` - User's search history
   - `search_history:ip:<ip_address>` - IP's search history

3. **API Endpoints** (`api/views/search/entity_search.py`)
   - `GET /api/search/history/` - Get personal history
   - `GET /api/search/history/recent-queries/` - Get recent query strings
   - `POST /api/search/history/clear/` - Clear history (privacy feature)

4. **SearchAnalytics Model** (`core/models/search_analytics.py`)
   - Database persistence for long-term analytics
   - Tracks clicks, CTR, response times
   - Used by `SearchAnalyticsService`

## Data Flow

```
User Search
    ↓
Search Endpoint (e.g., universal_search_api)
    ↓
get_search_data_for_api(query, ..., request=request)
    ↓
SearchHistoryService.track_search()  ← Stores in Redis
    ↓
Redis Sorted Set (sorted by timestamp)
```

## Usage Examples

### Track a Search (Automatic)

All search endpoints automatically track searches when they call `get_search_data_for_api` with `request=request`:

```python
return Response(get_search_data_for_api(
    query,
    entity_types=['organization', 'signer'],
    limit=20,
    request=request  # ← This enables automatic tracking
))
```

### Get User's History

```bash
# Authenticated users
GET /api/search/history/?limit=20

# Response:
{
  "history": [
    {
      "query": "Δημοτικό Συμβούλιο Αθηναίων",
      "normalized_query": "δημοτικό συμβούλιο αθηναίων",
      "timestamp": 1715518800.123,
      "results_count": 45,
      "search_types": ["organization", "signer"],
      "entity_type": "organization"
    },
    ...
  ],
  "count": 20,
  "stats": {
    "total_searches": 150,
    "unique_queries": 87,
    "top_search_types": [["organization", 95], ["signer", 55]]
  }
}
```

### Get Recent Query Strings (for Autocomplete)

```bash
GET /api/search/history/recent-queries/?limit=5

# Response:
{
  "queries": [
    "Δημοτικό Συμβούλιο Αθηναίων",
    "Υπουργείο Οικονομικών",
    "Γιάννης Παπαδόπουλος"
  ],
  "count": 3
}
```

### Clear History (Privacy)

```bash
POST /api/search/history/clear/

# Response:
{
  "success": true,
  "message": "Search history cleared successfully"
}
```

## Frontend Integration

### Display Default Suggestions on Focus

```javascript
// When user focuses on search box (before typing)
const response = await fetch('/api/search/suggestions/');
const { results } = await response.json();
// Display: results.organizations, results.signers, etc.
```

### Display Personal History on Focus

```javascript
// Show user's recent searches alongside defaults
const historyResponse = await fetch('/api/search/history/recent-queries/?limit=5');
const { queries } = await historyResponse.json();

// Display in dropdown:
// "Recent searches"
//   - Δημοτικό Συμβούλιο
//   - Υπουργείο Οικονομικών
// "Popular"
//   - [from default_suggestions_api]
```

### Autocomplete with History

```javascript
async function getAutocomplete(query) {
  if (!query) {
    // Empty query: show recent searches
    return await fetch('/api/search/history/recent-queries/?limit=5');
  } else {
    // Has query: show entity matches
    return await fetch(`/api/search/autocomplete/?q=${query}`);
  }
}
```

## Privacy Features

1. **Automatic Expiration**: All search history automatically expires after 90 days
2. **Manual Clearing**: Users can clear their history via the API
3. **Separate Storage**: User history is separate from system-wide analytics
4. **No Cross-Contamination**: Each user/IP has isolated history

## Comparison: SearchSuggestion vs SearchHistory

| Feature | SearchSuggestion | SearchHistory |
|---------|------------------|---------------|
| **Purpose** | Admin-configured popular entities | User's personal search history |
| **Storage** | Database (PostgreSQL) | Redis (temporary) |
| **Scope** | Global (all users see same) | Personal (per user/IP) |
| **Curation** | Manually curated by admins | Automatically tracked |
| **Expiration** | Never (unless deleted) | 90 days |
| **API Endpoint** | `/api/search/suggestions/` | `/api/search/history/` |
| **Use Case** | "Trending topics" | "Continue where you left off" |

## Configuration

### Redis Keys

All keys are centralized in `api/redis_keys.py`:

```python
SEARCH_HISTORY_NS = "search_history"
SEARCH_HISTORY_USER_PREFIX = f"{SEARCH_HISTORY_NS}:user:"
SEARCH_HISTORY_IP_PREFIX = f"{SEARCH_HISTORY_NS}:ip:"
SEARCH_HISTORY_EXPIRE = 60 * 60 * 24 * 90  # 90 days
```

### Limits

- **Max history per user/IP**: 100 most recent searches
- **History retention**: 90 days (auto-expiring)
- **Deduplication**: Same query searched multiple times only appears once (with latest timestamp)

## Monitoring

### Check Redis Storage

```bash
# Connect to Redis
redis-cli

# View user's history
ZREVRANGE search_history:user:123 0 10 WITHSCORES

# Count total history entries
KEYS search_history:* | wc -l

# Check memory usage
MEMORY USAGE search_history:user:123
```

### Database Analytics

Long-term analytics are still stored in the database via `SearchAnalytics` model:

```python
from core.models import SearchAnalytics

# Get search stats for last 30 days
stats = SearchAnalytics.objects.filter(
    created_at__gte=timezone.now() - timedelta(days=30)
).aggregate(
    total_searches=Count('id'),
    avg_results=Avg('results_count'),
    searches_with_clicks=Count('id', filter=Q(user_clicked_result=True))
)
```

## API Analytics Persistence

The `persist_analytics` management command has been modernized to use centralized Redis keys:

```bash
# Run manually
python manage.py persist_analytics

# Output:
✅ Successfully persisted analytics data (ID: 42)
  - 125 endpoints
  - 30 days of traffic
  - 1,234 IP journeys
```

This command reads from Redis using the centralized key patterns and persists to the `APIAnalytics`, `EndpointStats`, `DailyTraffic`, and `IPJourney` models.

## Best Practices

1. **Always pass `request` to tracking**: Ensure all search endpoints pass `request=request` to `get_search_data_for_api`
2. **Don't over-fetch**: Use reasonable limits (e.g., 20 for history, 5 for autocomplete)
3. **Respect privacy**: Implement the clear history feature prominently
4. **Monitor Redis memory**: Track growth of history keys
5. **Combine sources**: Show both personal history and admin suggestions for best UX

## Future Enhancements

- [ ] Search history analytics per user (most searched types, time patterns)
- [ ] Export history feature (GDPR compliance)
- [ ] Search history sharing/saving (bookmarks)
- [ ] Smart suggestions based on history + popularity
- [ ] Cross-device history sync (requires user accounts)
