# Daily Decision Analysis - Performance Optimization Plan

## Current Performance Issues

The `daily_decision_analysis` view is slow because it executes **15+ database queries** on every page load:

1. `_analyze_by_type` - Aggregation with subquery
2. `_analyze_by_organization` - Aggregation  
3. `_analyze_by_signer` - Many-to-many join + aggregation
4. `_analyze_by_hour` - Aggregation
5. `_get_timing_stats` - Aggregation
6. `_get_content_stats` - Multiple count queries
7. `_get_document_stats` - Multiple queries to DocumentExtraction
8. `_get_top_organizations` - Aggregation
9. `_get_top_signers` - Aggregation  
10. `_get_top_types` - Aggregation
11. `_get_quality_indicators` - 5 separate count queries
12. `_get_financial_summary` - Complex aggregations with relationships
13. `get_daily_decisions_with_details` - Paginated query with prefetch
14. Company lookups in the loop (potential N+1 problem)

## Optimization Strategy (Priority Order)

### 🥇 **Priority 1: Add Redis Caching (Immediate Impact)**

Past dates never change - cache the entire analysis result for 24 hours:

**Benefits:**
- First load: slow (as now)
- Subsequent loads: < 50ms (from cache)
- 90%+ of admin views hit cache

**Implementation:** 5-10 minutes
**Impact:** 95% faster for 90% of requests

### 🥈 **Priority 2: Optimize Query Count (Reduce DB Load)**

Combine related queries to reduce round trips:

**Current:** 15+ queries
**After:** 5-7 queries  
**Benefits:** 50-60% faster initial load, less DB connection overhead

**Implementation:** 30-60 minutes
**Impact:** 50-60% faster uncached requests

### 🥉 **Priority 3: Add Database Indexes (Remote DB)**

Add compound indexes for common patterns:

**Benefits:** 
- Each aggregation query 2-5x faster
- Especially important for remote DB (network latency)

**Implementation:** 15 minutes
**Impact:** 40-50% faster on large datasets

### 💡 **Priority 4: Fix N+1 in Company Lookups**

The `get_daily_decisions_with_details` queries Company for each decision in a loop.

**Current:** 1 + N queries (N = decisions per page)
**After:** 2 queries total
**Implementation:** 10 minutes
**Impact:** Faster pagination, especially with 50+ decisions per page

## Detailed Implementation Plans

### Implementation 1: Add Caching

```python
# backend/core/services/decision_analysis_service.py

from django.core.cache import cache
from datetime import date, timedelta

class DecisionAnalysisService:
    
    def get_daily_decision_analysis(self, target_date: date) -> Dict[str, Any]:
        """Get comprehensive analysis with caching for past dates"""
        
        # Generate cache key
        cache_key = f"daily_analysis:{target_date.isoformat()}"
        
        # For dates in the past (won't change), cache for 24 hours
        # For today (still being updated), cache for 5 minutes only
        is_past_date = target_date < date.today()
        cache_timeout = 86400 if is_past_date else 300  # 24 hours vs 5 minutes
        
        # Try cache first
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            logger.info(f"Cache HIT for {target_date}")
            return cached_result
        
        logger.info(f"Cache MISS for {target_date} - computing...")
        
        # ... existing analysis code ...
        analysis = {
            'date': target_date,
            # ... rest of your current code ...
        }
        
        # Cache the result
        cache.set(cache_key, analysis, cache_timeout)
        
        return analysis
    
    def get_daily_decisions_with_details(self, target_date, offset, limit, decision_type_uid=None):
        """Get paginated decisions with caching"""
        
        # Cache key includes all filter parameters
        cache_key = f"daily_decisions:{target_date.isoformat()}:{offset}:{limit}:{decision_type_uid or 'all'}"
        
        is_past_date = target_date < date.today()
        cache_timeout = 86400 if is_past_date else 300
        
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        # ... existing query code ...
        
        result = {
            'decisions': decision_details,
            'total_count': total_count,
            # ... rest of result ...
        }
        
        cache.set(cache_key, result, cache_timeout)
        return result
```

**Cache Invalidation:**
When new decisions are imported for a date, invalidate its cache:

```python
# In your import command/view after importing decisions
from django.core.cache import cache

def invalidate_daily_analysis_cache(target_date: date):
    """Invalidate cache when new decisions are added"""
    cache_key = f"daily_analysis:{target_date.isoformat()}"
    cache.delete(cache_key)
    
    # Also invalidate pagination caches
    # This is a simple approach - delete pattern matching keys
    # For production, consider using cache.delete_pattern() with django-redis
```

### Implementation 2: Optimize Query Count

Instead of 15 separate queries, do 1 master query and extract different views:

```python
def get_daily_decision_analysis_optimized(self, target_date: date) -> Dict[str, Any]:
    """Optimized version with fewer queries"""
    
    # ONE comprehensive query with all needed annotations
    decisions_qs = Decision.objects.filter(
        issue_date__date=target_date
    ).select_related(
        'organization', 'decision_type'
    ).prefetch_related(
        'signers'
    ).annotate(
        effective_amt=Coalesce('amount', Subquery(
            DecisionAmountField.objects.filter(
                decision=OuterRef('pk')
            ).values('decision').annotate(
                total=Sum('amount')
            ).values('total')
        )),
        hour=TruncHour('publish_timestamp')
    )
    
    # Fetch all decisions into memory ONCE
    # For a single day (typically 100-2000 decisions), this is manageable
    all_decisions = list(decisions_qs)
    
    if not all_decisions:
        return {'has_data': False, ...}
    
    # Now compute all stats from the in-memory list
    # This eliminates 10+ database round trips
    
    analysis = {
        'total_count': len(all_decisions),
        'by_type': self._compute_by_type(all_decisions),
        'by_organization': self._compute_by_organization(all_decisions),
        # ... etc, all computed from all_decisions list
    }
    
    return analysis

def _compute_by_type(self, decisions: List[Decision]) -> List[Dict]:
    """Compute type distribution from in-memory list"""
    from collections import defaultdict
    
    type_stats = defaultdict(lambda: {'count': 0, 'total_amount': 0})
    
    for decision in decisions:
        if decision.decision_type:
            key = decision.decision_type.uid
            type_stats[key]['label'] = decision.decision_type.label
            type_stats[key]['uid'] = decision.decision_type.uid
            type_stats[key]['count'] += 1
            type_stats[key]['total_amount'] += float(decision.effective_amt or 0)
    
    return sorted(type_stats.values(), key=lambda x: x['count'], reverse=True)
```

### Implementation 3: Add Database Indexes

```python
# Add migration: python manage.py makemigrations --empty core --name add_daily_analysis_indexes

from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('core', 'XXXX_previous_migration'),  # Update this
    ]

    operations = [
        # Composite index for daily analysis queries
        migrations.AddIndex(
            model_name='decision',
            index=models.Index(
                fields=['issue_date', 'decision_type', 'organization'],
                name='daily_analysis_idx'
            ),
        ),
        
        # Index for signer aggregations (many-to-many relationship)
        migrations.AddIndex(
            model_name='signer',
            index=models.Index(
                fields=['uid'],
                name='signer_uid_idx'
            ),
        ),
        
        # Index for document extraction lookups
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS doc_extract_decision_status_idx "
            "ON core_documentextraction (decision_id, extraction_status);",
            
            reverse_sql="DROP INDEX IF EXISTS doc_extract_decision_status_idx;"
        ),
    ]
```

### Implementation 4: Fix Company N+1 Query

```python
def get_daily_decisions_with_details(self, target_date, offset, limit, decision_type_uid=None):
    """Optimized version without N+1 queries"""
    
    # ... existing query setup ...
    
    decisions = decisions_qs[offset:offset + limit]
    
    # BEFORE: Company lookup inside the loop (N+1 problem)
    # AFTER: Collect all AFMs, then query companies ONCE
    
    # Collect all unique AFMs from all decisions' relationships
    all_afms = set()
    for decision in decisions:
        for rel in decision.entity_relationships.all():
            if rel.entity.afm:
                all_afms.add(rel.entity.afm)
    
    # Single query for all companies with prefetch
    companies_by_afm = {}
    if all_afms:
        from core.models.companies import Company
        companies = Company.objects.filter(
            afm__in=all_afms
        ).prefetch_related('persons')
        
        # Index by AFM for O(1) lookup
        for company in companies:
            if company.afm not in companies_by_afm:
                companies_by_afm[company.afm] = []
            companies_by_afm[company.afm].append(company)
    
    # Now build decision details using the pre-fetched companies
    decision_details = []
    for decision in decisions:
        counterparts = []
        
        for rel in decision.entity_relationships.all():
            entity = rel.entity
            counterpart = {
                'afm': entity.afm,
                'name': entity.name,
                'type': entity.entity_type,
                'role': rel.get_role_display(),
                'companies': []
            }
            
            # Lookup from pre-fetched dict (O(1)) instead of querying DB (N queries)
            if entity.afm and entity.afm in companies_by_afm:
                for company in companies_by_afm[entity.afm]:
                    company_info = {
                        'name': company.co_name_el,
                        'gemi': company.ar_gemi,
                        'status': company.status_name,
                        'persons': [
                            {'name': p.person_name, 'role': p.role}
                            for p in company.persons.all()  # Already prefetched
                        ]
                    }
                    counterpart['companies'].append(company_info)
            
            counterparts.append(counterpart)
        
        # ... rest of decision detail building ...
```

## Expected Performance Improvements

| Scenario | Before | After (All Optimizations) | Improvement |
|----------|--------|---------------------------|-------------|
| Past date (cache hit) | 5-10s | 20-50ms | **99% faster** |
| Past date (cache miss) | 5-10s | 1-2s | **70-80% faster** |
| Today (5min cache) | 5-10s | 50ms (cached) / 1-2s (uncached) | **70-99% faster** |
| Remote DB | 10-20s | 50ms (cached) / 2-4s (uncached) | **80-99% faster** |

## Implementation Order

1. **Week 1:** Add caching (Implementation 1) - Biggest immediate impact
2. **Week 2:** Fix N+1 queries (Implementation 4) - Quick win  
3. **Week 3:** Add indexes (Implementation 3) - Helps uncached queries
4. **Week 4:** Optimize query count (Implementation 2) - Most complex, defer if caching is enough

## Monitoring

Add timing logs to track improvements:

```python
import time
from loguru import logger

def get_daily_decision_analysis(self, target_date: date):
    start_time = time.time()
    
    # ... your code ...
    
    elapsed = time.time() - start_time
    logger.info(f"Daily analysis for {target_date} took {elapsed:.2f}s (cached: {cached_result is not None})")
    
    return analysis
```

## Quick Start: 5-Minute Cache Implementation

Just add this decorator to your existing service methods:

```python
from functools import wraps
from django.core.cache import cache

def cache_daily_analysis(timeout_past=86400, timeout_today=300):
    """Decorator to cache daily analysis results"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, target_date, *args, **kwargs):
            # Build cache key from function name and all arguments
            cache_key = f"{func.__name__}:{target_date.isoformat()}:{args}:{kwargs}"
            
            # Check cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Compute result
            result = func(self, target_date, *args, **kwargs)
            
            # Cache with appropriate timeout
            from datetime import date
            is_past = target_date < date.today()
            timeout = timeout_past if is_past else timeout_today
            cache.set(cache_key, result, timeout)
            
            return result
        return wrapper
    return decorator

# Usage:
@cache_daily_analysis()
def get_daily_decision_analysis(self, target_date: date) -> Dict[str, Any]:
    # ... existing code unchanged ...
```
