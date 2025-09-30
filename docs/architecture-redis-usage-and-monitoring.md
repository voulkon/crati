# Redis Analytics - The One Guide You Need

**Quick nav**: [What it does](#what-it-tracks) • [Architecture](#architecture--data-flow) • [Dashboard](#view-dashboard) • [Quick commands](#quick-commands) • [Database queries](#database-queries) • [Troubleshooting](#troubleshooting)

---

## What It Tracks

```
✅ Every API request → Redis counter
✅ Which IPs visit which endpoints → Redis sets  
✅ Search terms & filters → Redis sorted sets (last 1000/endpoint)
✅ Hourly/daily traffic → Time-series data
✅ All persisted to PostgreSQL for historical analysis
```

**What gets tracked automatically:**
- `/api/search?q=corruption` → Saves search term "corruption"
- `/api/decisions?year=2024` → Saves filter "year=2024"
- Every endpoint hit by every IP → Bidirectional tracking

---

## Architecture & Data Flow

### 🔄 Complete Analytics Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        EVERY API REQUEST                                │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  RateLimitMiddleware (backend/api/middleware/rate_limit.py)             │
│  ├─ process_request() - runs BEFORE view                                │
│  │  └─ Checks rate limits only                                          │
│  └─ process_response() - runs AFTER view (if status < 400)              │
│     └─ record_api_request() - THIS WRITES TO REDIS                      │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    REDIS WRITES (Real-time)                             │
│                                                                         │
│  Stats Keys (30-day TTL):                                               │
│  ├─ stats:total_requests              ← cache.incr()                    │
│  ├─ stats:unique_ips                  ← redis.sadd()                    │
│  ├─ stats:hourly                      ← redis.zincrby()                 │
│  ├─ stats:daily                       ← redis.zincrby()                 │
│  ├─ stats:endpoint:/api/search/       ← cache.incr()                    │
│  ├─ stats:method:GET                  ← cache.incr()                    │
│  ├─ stats:ip:192.168.1.1:endpoints    ← redis.sadd() ⭐ NEW             │
│  ├─ stats:endpoint_ips:/api/search    ← redis.sadd() ⭐ NEW             │
│  └─ stats:query_logs:/api/search      ← redis.zadd() ⭐ NEW             │
│                                                                         │
│  Query Logs (only for trackable endpoints):                             │
│  └─ Stores: {ip, endpoint, method, get_params, post_params, timestamp}  │
│     Retention: Last 1000 per endpoint, 30-day TTL                       │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           │ ⏰ Manual or Scheduled
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  persist_analytics Management Command                                   │
│  (backend/api/management/commands/persist_analytics.py)                 │
│                                                                         │
│  Triggered by:                                                          │
│  ├─ Manual: python manage.py persist_analytics                          │
│  └─ Celery Beat (if configured): Daily at 2 AM                          │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   POSTGRESQL WRITES (Historical)                        │
│                                                                         │
│  api_apianalytics (Snapshot)                                            │
│  ├─ total_requests                                                      │
│  ├─ unique_ips                                                          │
│  └─ created_at                                                          │
│                                                                         │
│  api_endpointstats (Per-Endpoint Stats)                                 │
│  ├─ analytics (FK to APIAnalytics)                                      │
│  ├─ endpoint                                                            │
│  └─ count                                                               │
│                                                                         │
│  api_dailytraffic (Time-Series)                                         │
│  ├─ analytics (FK to APIAnalytics)                                      │
│  ├─ date                                                                │
│  └─ count                                                               │
│                                                                         │
│  api_ipjourney (User Journeys) ⭐ NEW                                   │
│  ├─ analytics (FK to APIAnalytics)                                      │
│  ├─ ip_address                                                          │
│  ├─ endpoints_visited (JSON)                                            │
│  ├─ journey_length                                                      │
│  ├─ first_seen                                                          │
│  └─ last_seen                                                           │
│                                                                         │
│  api_endpointaccesslog (Detailed Logs) ⭐ NEW                           │
│  ├─ ip_address                                                          │
│  ├─ endpoint                                                            │
│  ├─ method                                                              │
│  ├─ query_params (JSON) ⭐ Search terms, filters                        │
│  ├─ timestamp                                                           │
│  └─ user_agent                                                          │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      ADMIN DASHBOARD                                    │
│  (backend/admin_custom/views/analytics/redis.py)                        │
│                                                                         │
│  Reads from Redis (Real-time):                                          │
│  ├─ Summary stats (total requests, unique IPs)                          │
│  ├─ Popular endpoints                                                   │
│  ├─ Hourly/daily traffic (with pagination)                              │
│  └─ IP journeys ⭐ NEW                                                  │
│                                                                         │
│  Template: backend/templates/admin/redis_analytics.html                 │
│  URL: http://localhost:8000/api/admin/analytics/                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 🔧 Component Interactions

#### 1. Request Recording Flow

```python
# File: backend/api/middleware/rate_limit.py

class RateLimitMiddleware:
    def process_response(self, request, response):
        if response.status_code < 400:
            self.record_api_request(request)  # ← Main entry point
        return response
    
    def record_api_request(self, request):
        ip = get_client_ip(request)
        endpoint = request.path
        
        # Basic stats
        safe_incr(TOTAL_REQUESTS, 1)           # Counter
        self.redis.sadd(UNIQUE_IPS, ip)         # Set
        self.redis.zincrby(HOURLY_STATS, ...)   # Sorted Set
        
        # IP → Endpoint tracking ⭐ NEW
        ip_endpoints_key = get_ip_endpoints_key(ip)
        self.redis.sadd(ip_endpoints_key, endpoint)
        
        # Endpoint → IPs tracking (reverse) ⭐ NEW
        endpoint_ips_key = get_endpoint_ips_key(endpoint)
        self.redis.sadd(endpoint_ips_key, ip)
        
        # Query parameter logging ⭐ NEW
        if self._is_trackable_endpoint(endpoint):
            query_log_key = f"stats:query_logs:{endpoint}"
            log_entry = json.dumps({
                'ip': ip,
                'endpoint': endpoint,
                'method': request.method,
                'get_params': dict(request.GET),
                'post_params': self._get_safe_post_params(request),
                'timestamp': datetime.now().isoformat()
            })
            self.redis.zadd(query_log_key, {log_entry: time.time()})
```

**Key Points:**
- ✅ Runs on **every successful API response** (status < 400)
- ✅ Writes are **atomic** (no transactions needed)
- ✅ All keys have **30-day TTL** (auto-cleanup)
- ✅ Query params logged **only for trackable endpoints**

#### 2. Persistence Flow

```python
# File: backend/api/management/commands/persist_analytics.py

class Command(BaseCommand):
    def handle(self, *args, **options):
        redis = get_redis_connection('default')
        
        # 1. Create snapshot
        analytics = APIAnalytics.objects.create(
            total_requests=cache.get(TOTAL_REQUESTS, 0),
            unique_ips=redis.scard(UNIQUE_IPS)
        )
        
        # 2. Save endpoint stats
        endpoint_keys = redis.keys(f"{ENDPOINT_PREFIX}*")
        for key in endpoint_keys:
            endpoint = key.decode().replace(ENDPOINT_PREFIX, "")
            count = cache.get(key.decode(), 0)
            EndpointStats.objects.create(
                analytics=analytics,
                endpoint=endpoint,
                count=count
            )
        
        # 3. Save daily traffic
        daily_data = redis.zrange(DAILY_STATS, 0, -1, withscores=True)
        for day_key, count in daily_data:
            DailyTraffic.objects.create(
                analytics=analytics,
                date=datetime.fromtimestamp(int(day_key) * 86400),
                count=int(count)
            )
        
        # 4. Save IP journeys ⭐ NEW
        ip_keys = redis.keys("stats:ip:*:endpoints")
        for ip_key in ip_keys:
            ip = ip_key.decode().split(':')[2]
            endpoints = redis.smembers(ip_key)
            
            IPJourney.objects.create(
                analytics=analytics,
                ip_address=ip,
                endpoints_visited=list(endpoints),
                journey_length=len(endpoints)
            )
```

**Key Points:**
- ✅ Creates **immutable snapshot** in database
- ✅ All data linked to **single APIAnalytics record**
- ✅ Can be run **multiple times** (creates new snapshots)
- ✅ Old Redis data **remains** (not deleted after persist)

#### 3. Dashboard Reading Flow

```python
# File: backend/admin_custom/views/analytics/redis.py

@staff_member_required
def redis_analytics(request):
    redis = get_redis_connection('default')
    
    # Pagination parameters
    daily_offset = int(request.GET.get('daily_offset', 0))
    hourly_offset = int(request.GET.get('hourly_offset', 0))
    
    # Read from Redis (NOT from database)
    total_requests = cache.get(TOTAL_REQUESTS, 0)
    unique_ips = redis.scard(UNIQUE_IPS)
    
    # Popular endpoints
    endpoint_keys = redis.keys(f"{ENDPOINT_PREFIX}*")
    endpoints = [...]  # Build list with counts
    
    # IP Journeys ⭐ NEW
    ip_journeys = []
    ip_keys = redis.keys("stats:ip:*:endpoints")
    for ip_key in ip_keys:
        ip = ip_key.decode().split(':')[2]
        ip_endpoints_set = redis.smembers(ip_key)
        ip_journeys.append({
            'ip': ip,
            'endpoints': list(ip_endpoints_set),
            'count': len(ip_endpoints_set)
        })
    
    return render(request, 'admin/redis_analytics.html', {...})
```

**Key Points:**
- ✅ Reads **directly from Redis** (real-time)
- ✅ Does **NOT query database** (fast!)
- ✅ Pagination via **time windows** (offset parameters)
- ✅ Top N results only (endpoints[:10])

---

## View Dashboard

```
http://localhost:8000/api/admin/analytics/
```

**Features:**
- Total requests & unique IPs
- Daily traffic chart (7-day windows, navigate with ◀ ▶)
- Hourly traffic chart (24-hour windows, navigate with ◀ ▶)
- Top 10 endpoints by popularity
- IP Journey table (which IPs visited which endpoints)

---

## Quick Commands

### Check What's in Redis

```bash
# All IPs being tracked
docker exec diavgeia_redis redis-cli -n 1 KEYS "stats:ip:*:endpoints"

# Specific IP's journey
docker exec diavgeia_redis redis-cli -n 1 SMEMBERS "stats:ip:172.18.0.1:endpoints"

# Search logs
docker exec diavgeia_redis redis-cli -n 1 ZRANGE "stats:query_logs:/api/search" 0 -1

# Total requests
docker exec diavgeia_redis redis-cli -n 1 GET "stats:total_requests"
```

### Save Redis Data to Database

```bash
# Manual persist
docker exec diavgeia_backend python manage.py persist_analytics

# Check what got saved
docker exec diavgeia_backend python manage.py shell -c "
from api.models import IPJourney, APIAnalytics
print(f'Snapshots: {APIAnalytics.objects.count()}')
print(f'IP journeys: {IPJourney.objects.count()}')
"
```

### Test It

```bash
# Make a search request
curl "http://localhost:8000/api/search?q=test&year=2024"

# Verify it was logged
docker exec diavgeia_backend python manage.py shell -c "
from django_redis import get_redis_connection
import json
redis = get_redis_connection('default')
logs = redis.zrange('stats:query_logs:/api/search', -1, -1)
if logs:
    print('Latest search:', json.loads(logs[0])['get_params'])
"
```

---

## Database Queries

### Find Popular Search Terms

```python
from api.models import EndpointAccessLog
from collections import Counter

searches = EndpointAccessLog.objects.filter(
    endpoint__contains='/search'
).values_list('query_params', flat=True)

terms = [s.get('q', [''])[0] for s in searches if s]
popular = Counter(terms).most_common(10)

for term, count in popular:
    print(f"{term}: {count} searches")
```

### Find Most Active IPs

```python
from api.models import IPJourney

power_users = IPJourney.objects.order_by('-journey_length')[:10]
for u in power_users:
    print(f"{u.ip_address}: visited {u.journey_length} different endpoints")
    print(f"  Endpoints: {u.endpoints_visited}")
```

### User Journey Analysis

```python
from api.models import IPJourney

# Find users who searched and then viewed decisions
searchers = IPJourney.objects.filter(
    endpoints_visited__contains='/api/search'
).filter(
    endpoints_visited__contains='/api/decisions'
)

print(f"{searchers.count()} users searched then viewed decisions")
```

---

## How It Works

### Real-Time (Redis)

Every API request → **Middleware** → Records in Redis:

```python
# In rate_limit.py middleware:
stats:total_requests              # Increment counter
stats:unique_ips                  # Add IP to set
stats:ip:<ip>:endpoints          # Add endpoint to IP's set
stats:endpoint_ips:<endpoint>    # Add IP to endpoint's set (reverse)
stats:query_logs:<endpoint>      # Add request with params (if trackable)
```

**Trackable endpoints** (query params logged):
- `/api/search` - Search queries
- `/api/decisions` - Decision filters
- `/api/organizations` - Org filters
- `/api/filters` - Custom filters

### Persistent (PostgreSQL)

Run `persist_analytics` command → Saves to database:

```
APIAnalytics (snapshot)
  ├─ EndpointStats (which endpoints, how many hits)
  ├─ DailyTraffic (traffic per day)
  └─ IPJourney (which IPs visited which endpoints)

EndpointAccessLog (detailed logs with query params)
```

---

## Critical Failure Points & Debugging

### 🚨 If Dashboard Shows No Data

**Check each layer:**

```bash
# 1. Is middleware running?
docker logs diavgeia_backend | grep "record_api_request"

# 2. Is Redis receiving writes?
docker exec diavgeia_redis redis-cli -n 1 KEYS "stats:*"

# 3. Make a test request
curl http://localhost:8000/api/health/

# 4. Check if it was recorded
docker exec diavgeia_redis redis-cli -n 1 GET "stats:total_requests"
```

**Common causes:**
- ❌ Middleware not in `MIDDLEWARE` list (settings.py)
- ❌ Redis connection failed (check `REDIS_HOST`)
- ❌ All requests returning errors (status >= 400)
- ❌ Wrong Redis database (check `REDIS_DB=1`)

### 🚨 If Persistence Not Working

**Check each layer:**

```bash
# 1. Can command connect to Redis?
docker exec diavgeia_backend python manage.py shell -c "
from django.core.cache import cache
print('Redis OK:', cache.get('stats:total_requests', 'NOT FOUND'))
"

# 2. Run persist command manually
docker exec diavgeia_backend python manage.py persist_analytics

# 3. Check if data saved
docker exec diavgeia_backend python manage.py shell -c "
from api.models import APIAnalytics
print('Snapshots:', APIAnalytics.objects.count())
"
```

**Common causes:**
- ❌ Redis empty (no data to persist)
- ❌ Database migration not applied
- ❌ Import error in persist_analytics.py
- ❌ Celery task scheduled but not running

### 🚨 If Query Params Not Tracked

**Debug flow:**

```python
# 1. Check if endpoint is trackable
from api.middleware.rate_limit import RateLimitMiddleware
middleware = RateLimitMiddleware(None)

endpoint = "/api/search"
print(f"Trackable: {middleware._is_trackable_endpoint(endpoint)}")

# 2. Check if logs exist in Redis
from django_redis import get_redis_connection
redis = get_redis_connection('default')
keys = redis.keys("stats:query_logs:*")
print(f"Query log keys: {[k.decode() for k in keys]}")

# 3. Check log contents
logs = redis.zrange("stats:query_logs:/api/search", 0, -1)
import json
for log in logs:
    print(json.loads(log))
```

**Common causes:**
- ❌ Endpoint not in `trackable_patterns` list
- ❌ Request has no GET/POST parameters
- ❌ Redis sorted set hit size limit (1000)

### 🚨 If IP Journeys Empty

**Debug flow:**

```bash
# 1. Check if IP tracking keys exist
docker exec diavgeia_redis redis-cli -n 1 KEYS "stats:ip:*:endpoints"

# 2. Check specific IP
docker exec diavgeia_redis redis-cli -n 1 SMEMBERS "stats:ip:172.18.0.1:endpoints"

# 3. Check reverse lookup
docker exec diavgeia_redis redis-cli -n 1 SMEMBERS "stats:endpoint_ips:/api/search"
```

**Common causes:**
- ❌ IP extraction failing (check `get_client_ip()`)
- ❌ Keys expired (check TTL)
- ❌ Wrong Redis database

---

## Component Health Checks

### Quick System Verification

```bash
# Run all checks at once
docker exec diavgeia_backend python manage.py shell << 'EOF'
from django.core.cache import cache
from django_redis import get_redis_connection
from api.models import APIAnalytics

print("=== REDIS HEALTH ===")
try:
    redis = get_redis_connection('default')
    print(f"✓ Redis connected: {redis.ping()}")
    print(f"✓ Total keys: {redis.dbsize()}")
    print(f"✓ Stats keys: {len(redis.keys('stats:*'))}")
except Exception as e:
    print(f"✗ Redis error: {e}")

print("\n=== MIDDLEWARE HEALTH ===")
total = cache.get('stats:total_requests', 0)
print(f"{'✓' if total > 0 else '✗'} Total requests: {total}")

unique_ips = redis.scard('stats:unique_ips')
print(f"{'✓' if unique_ips > 0 else '✗'} Unique IPs: {unique_ips}")

print("\n=== DATABASE HEALTH ===")
snapshots = APIAnalytics.objects.count()
print(f"{'✓' if snapshots > 0 else '○'} Snapshots persisted: {snapshots}")

print("\n=== NEW FEATURES ===")
ip_keys = redis.keys('stats:ip:*:endpoints')
print(f"{'✓' if ip_keys else '○'} IP tracking: {len(ip_keys)} IPs")

query_keys = redis.keys('stats:query_logs:*')
print(f"{'✓' if query_keys else '○'} Query logs: {len(query_keys)} endpoints")
EOF
```

Expected output:
```
=== REDIS HEALTH ===
✓ Redis connected: True
✓ Total keys: 142
✓ Stats keys: 76

=== MIDDLEWARE HEALTH ===
✓ Total requests: 1523
✓ Unique IPs: 12

=== DATABASE HEALTH ===
✓ Snapshots persisted: 3

=== NEW FEATURES ===
✓ IP tracking: 8 IPs
✓ Query logs: 2 endpoints
```

---

## Troubleshooting

### Dashboard not loading?

```bash
# Restart backend
docker restart diavgeia_backend

# Check logs
docker logs diavgeia_backend --tail 50
```

### No data showing?

```bash
# Make some requests
curl http://localhost:8000/api/health/

# Verify Redis has data
docker exec diavgeia_redis redis-cli -n 1 KEYS "stats:*"
```

### Query params not tracked?

Check if endpoint is in trackable list:
```python
# In rate_limit.py line ~180
trackable_patterns = [
    '/api/search',
    '/api/decisions',
    '/api/organizations',
    '/api/filters',
]
```

### Need to clear everything?

```bash
# WARNING: Deletes all analytics!
docker exec diavgeia_redis redis-cli -n 1 FLUSHDB
```

---

## Configuration Files

| File | What It Does | When It Runs |
|------|--------------|--------------|
| `backend/api/redis_keys.py` | All Redis key patterns | N/A (constants) |
| `backend/api/middleware/rate_limit.py` | Records requests | Every API response |
| `backend/api/models.py` | Database models | N/A (schema) |
| `backend/api/management/commands/persist_analytics.py` | Saves Redis → DB | Manual or scheduled |
| `backend/admin_custom/views/analytics/redis.py` | Dashboard view | When admin visits URL |
| `backend/templates/admin/redis_analytics.html` | Dashboard UI | Rendered by view |

### Data Flow Summary

```
Request → Middleware (writes Redis) → Dashboard (reads Redis)
                ↓
         persist_analytics
                ↓
         Database (historical)
```

**Critical paths:**
1. **Request recording**: MUST happen in middleware `process_response()`
2. **Redis writes**: MUST complete before response sent
3. **Persistence**: CAN fail without breaking real-time analytics
4. **Dashboard**: Reads Redis directly (no DB dependency)

---

## Remember

- **Redis = Real-time**: Data expires after 30 days
- **Database = Historical**: Keeps forever (run persist command)
- **Middleware tracks everything**: No setup needed, just works
- **Search terms captured**: Only for trackable endpoints
- **IP journeys saved**: Which endpoints each IP visited

---

## That's It!

**View analytics**: http://localhost:8000/api/admin/analytics/  
**Persist data**: `docker exec diavgeia_backend python manage.py persist_analytics`  
**Check Redis**: http://localhost:8081 (Redis Commander)

Everything else is automatic. 🎉
