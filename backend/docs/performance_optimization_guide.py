"""
Performance optimization recommendations and database index suggestions
for the new financial calculation approach.
"""

# =============================================================================
# CRITICAL PERFORMANCE CONSIDERATIONS
# =============================================================================

"""
1. DATABASE INDEX OPTIMIZATIONS
===============================

Add these indexes to your models for optimal performance:
"""


# In DecisionEntityRelationship model:
class Meta:
    indexes = [
        # Existing indexes...
        # CRITICAL: For entity financial queries (most common pattern)
        models.Index(fields=["entity", "role", "decision__issue_date"]),
        # CRITICAL: For organization expenditure queries
        models.Index(fields=["decision__organization", "role", "decision__issue_date"]),
        # For temporal aggregations
        models.Index(fields=["decision__issue_date", "role"]),
        # For cross-entity analysis
        models.Index(fields=["role", "decision__issue_date"]),
    ]


# In DecisionAmountField model:
class Meta:
    indexes = [
        # Existing indexes...
        # CRITICAL: For linked amount aggregations (most expensive queries)
        models.Index(
            fields=["associated_relationship", "amount"],
            condition=Q(associated_relationship__isnull=False),
        ),
        # For decision-level amount queries
        models.Index(fields=["decision", "amount", "associated_relationship"]),
        # For amount range filtering
        models.Index(fields=["amount", "associated_relationship"]),
    ]


"""
2. QUERY OPTIMIZATION PATTERNS
==============================
"""


# BAD: N+1 queries
def get_entity_amounts_bad(entity):
    relationships = DecisionEntityRelationship.objects.filter(entity=entity)
    for rel in relationships:
        # This hits the database for each relationship!
        total = sum(amount.amount for amount in rel.linked_amounts.all())


# GOOD: Database-level aggregation
def get_entity_amounts_good(entity):
    return DecisionEntityRelationship.objects.filter(
        entity=entity, role__in=["grantee", "donationReceiver", "sponsorAFMName"]
    ).aggregate(total=Sum("linked_amounts__amount"))["total"]


# BETTER: Direct amount field query (bypasses relationship table)
def get_entity_amounts_best(entity):
    return DecisionAmountField.objects.filter(
        associated_relationship__entity=entity,
        associated_relationship__role__in=[
            "grantee",
            "donationReceiver",
            "sponsorAFMName",
        ],
    ).aggregate(total=Sum("amount"))["total"]


"""
3. MEMORY USAGE OPTIMIZATION
============================
"""


# BAD: Loads all data into memory
def get_timeline_bad(entity):
    relationships = DecisionEntityRelationship.objects.filter(
        entity=entity
    ).prefetch_related(
        "linked_amounts"
    )  # Loads ALL amounts into memory

    for rel in relationships:
        total = sum(amount.amount for amount in rel.linked_amounts.all())


# GOOD: Use annotation to calculate at database level
def get_timeline_good(entity):
    return (
        DecisionEntityRelationship.objects.filter(entity=entity)
        .annotate(
            period=TruncMonth("decision__issue_date"),
            total_amount=Sum("linked_amounts__amount"),
        )
        .values("period", "total_amount")
    )


"""
4. PAGINATION FOR LARGE DATASETS
=================================
"""


# For large result sets, always paginate
def get_entity_decisions_paginated(entity, page=1, page_size=50):
    offset = (page - 1) * page_size

    # Use LIMIT/OFFSET at database level
    relationships = (
        DecisionEntityRelationship.objects.filter(entity=entity)
        .select_related("decision", "decision__organization")
        .annotate(total_amount=Sum("linked_amounts__amount"))[
            offset : offset + page_size
        ]
    )

    return list(relationships)


"""
5. CACHING STRATEGIES
====================
"""

from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key


def get_entity_financial_summary_cached(entity_afm):
    cache_key = f"entity_financial_summary:{entity_afm}"

    # Try cache first
    summary = cache.get(cache_key)
    if summary is not None:
        return summary

    # Calculate and cache for 1 hour
    summary = financial_service.get_entity_financial_summary(entity)
    cache.set(cache_key, summary, 3600)
    return summary


"""
6. DATABASE-SPECIFIC OPTIMIZATIONS
==================================
"""

# PostgreSQL: Use EXPLAIN ANALYZE to check query plans
"""
EXPLAIN ANALYZE 
SELECT SUM(daf.amount) 
FROM core_decisionentityrelationship der
JOIN core_decisionamountfield daf ON daf.associated_relationship_id = der.id
WHERE der.entity_id = 123 AND der.role IN ('grantee', 'donationReceiver');
"""

# Consider materialized views for expensive aggregations
"""
CREATE MATERIALIZED VIEW entity_financial_summary AS
SELECT 
    der.entity_id,
    der.role,
    DATE_TRUNC('month', d.issue_date) as month,
    SUM(daf.amount) as total_amount,
    COUNT(DISTINCT der.decision_id) as decision_count
FROM core_decisionentityrelationship der
JOIN core_decisionamountfield daf ON daf.associated_relationship_id = der.id  
JOIN core_decision d ON d.id = der.decision_id
WHERE der.role IN ('grantee', 'donationReceiver', 'sponsorAFMName')
GROUP BY der.entity_id, der.role, DATE_TRUNC('month', d.issue_date);

CREATE UNIQUE INDEX ON entity_financial_summary (entity_id, role, month);
"""

"""
7. MONITORING & ALERTING
========================
"""

import logging
from django.db import connection

logger = logging.getLogger(__name__)


def log_slow_queries():
    """Monitor query performance"""
    queries = connection.queries
    for query in queries:
        time = float(query["time"])
        if time > 1.0:  # Log queries taking more than 1 second
            logger.warning(f"Slow query ({time}s): {query['sql']}")


"""
8. BULK OPERATIONS
==================
"""


# For bulk updates, use bulk_update instead of individual saves
def update_entity_amounts_bulk(relationships_data):
    relationships_to_update = []

    for rel_data in relationships_data:
        rel = DecisionEntityRelationship.objects.get(id=rel_data["id"])
        rel.some_field = rel_data["new_value"]
        relationships_to_update.append(rel)

    # Bulk update instead of individual saves
    DecisionEntityRelationship.objects.bulk_update(
        relationships_to_update, ["some_field"], batch_size=1000
    )


"""
9. CONNECTION POOLING
=====================
"""

# In settings.py for production
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "OPTIONS": {
            "MAX_CONNS": 20,
            "CONN_MAX_AGE": 0,
        },
        # Add connection pooling with pgbouncer or django-db-pool
    }
}

"""
10. GOTCHAS TO AVOID
===================
"""

# GOTCHA 1: Forgetting to filter by roles
# This will include ALL relationships, even non-financial ones
relationships = DecisionEntityRelationship.objects.filter(entity=entity)  # BAD

# GOTCHA 2: Using Python sum() instead of database Sum()
total = sum(rel.linked_amounts.values_list("amount", flat=True))  # BAD - Python sum
total = DecisionEntityRelationship.objects.aggregate(
    Sum("linked_amounts__amount")
)  # GOOD

# GOTCHA 3: Not handling NULL amounts
# This can cause incorrect aggregations
total = Sum("linked_amounts__amount")  # BAD - NULLs might be treated as 0
total = Sum(
    "linked_amounts__amount", filter=Q(linked_amounts__amount__isnull=False)
)  # GOOD

# GOTCHA 4: Forgetting timezone-aware datetime filtering
from django.utils import timezone

start_date = timezone.make_aware(datetime(2023, 1, 1))  # GOOD

# GOTCHA 5: Not using select_related for foreign key access
relationships = DecisionEntityRelationship.objects.filter(entity=entity)
for rel in relationships:
    print(rel.decision.ada)  # BAD - N+1 queries

relationships = DecisionEntityRelationship.objects.filter(entity=entity).select_related(
    "decision"
)  # GOOD
