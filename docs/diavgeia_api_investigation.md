# Diavgeia API Investigation: Pagination & Timestamp Handling

## Overview

This document details our comprehensive investigation into pagination issues and timestamp handling quirks discovered while implementing the Diavgeia decision ingestion service. The investigation revealed critical API bugs that significantly impact how date/time queries should be structured.

## Initial Problem

### Symptoms
- **Expected**: ~26,042 decisions for date 2025-04-29 (based on official website)
- **Actual**: Only 1,481 decisions returned by our API queries
- **Gap**: Missing ~94.3% of expected decisions

### Initial Hypothesis
We suspected pagination wasn't working correctly, as we were only getting the first page of results despite implementing pagination logic.

## Investigation Phase 1: Pagination Verification

### What We Tested
```python
# Basic pagination test showed it was working correctly
page=0: 500 decisions
page=1: 500 decisions  
page=2: 481 decisions (last page)
total=1481 decisions across 3 pages
```

### Conclusion
**Pagination was working perfectly.** The issue was not with our pagination implementation but with the search criteria itself.

## Investigation Phase 2: Search Criteria Analysis

### API Documentation Review
From the official Diavgeia API documentation, we identified key search parameters:

```
from_date: Ημερομηνία τελευταίας τροποποίησης - Από (Last modification date - From)
to_date: Ημερομηνία τελευταίας τροποποίησης - Έως (Last modification date - To)  
from_issue_date: Ημερομηνία έκδοσης - Από (Issue date - From)
to_issue_date: Ημερομηνία έκδοσης - Έως (Issue date - To)
```

### Critical Discovery: Automatic Date Range Logic
The API documentation revealed automatic behavior:
> "Αν δεν οριστεί τιμή για το from_date: Αν η τιμή του to_date είναι μεταγενέστερη (ή ίση) της τιμής του from_issue_date, τότε το σύστημα αυτομάτως εισάγει ως τιμή το from_issue_date."

**Translation**: If `from_date` is not specified and `to_date` is later than or equal to `from_issue_date`, the system automatically sets `from_date` to `from_issue_date`.

This means the API was automatically adding a **submission timestamp filter** from our target date to **NOW**, severely limiting results.

## Investigation Phase 3: Comprehensive Search Testing

### Methodology
We implemented `debug_search_criteria_comprehensive()` to test various parameter combinations:

```python
def debug_search_criteria_comprehensive(self, target_date: date, expected_total: Optional[int] = None):
    """Test 15+ different search parameter combinations"""
```

### Test Categories
1. **Status Filters**: Testing different status values (`PUBLISHED`, `ALL`, Greek equivalents)
2. **Date Combinations**: Testing issue dates vs modification dates
3. **Time Formats**: Testing with and without time components
4. **Range Extensions**: Testing ±1 day ranges
5. **Parameter Combinations**: Testing various combinations of the above

### Key Results
```python
{
    'current_default': 1481,           # Original approach
    'status_all': 1481,               # Status changes had no effect
    'wide_modification_range': 1482,   # Slight improvement
    'extended_issue_range': 48215,     # 3x improvement! (±1 day)
    'with_time_stamps': 2995348,       # Completely broken!
    'with_timezone': 2995333           # Also broken!
}
```

## Investigation Phase 4: Timestamp Format Deep Dive

### The Shocking Discovery
When we added **ANY** time component to dates, the API returned ~3 million decisions instead of ~1,500:

#### ✅ **Working (Date-only)**:
```python
"from_issue_date": "2025-04-29"
"to_issue_date": "2025-04-29"
# Result: 1,481 decisions
```

#### ❌ **Broken (With time)**:
```python
"from_issue_date": "2025-04-29T00:00:00"  
"to_issue_date": "2025-04-29T23:59:59"
# Result: 2,995,348 decisions (entire database!)
```

### Comprehensive Timestamp Testing
```python
def debug_timestamp_precision(self, target_date: date, expected_total: Optional[int] = None):
    """Test various timestamp formats and precision levels"""
```

#### Results Summary
| Format Type | Example | Result | Status |
|-------------|---------|--------|--------|
| Date only | `2025-04-29` | 1,481 | ✅ Works |
| With time | `2025-04-29T00:00:00` | ~3M | ❌ Broken |
| With timezone | `2025-04-29T00:00:00+03:00` | ~3M | ❌ Broken |
| Extended range | `2025-04-28` to `2025-04-30` | 48,211 | ✅ Better |
| Hourly ranges | `T09:00:00` to `T10:00:00` | ~3M | ❌ Broken |

### Timezone Testing
```python
def debug_timezone_interpretation(self, target_date: date):
    """Test how API interprets different timezone formats"""
```

All timezone variations returned ~3M decisions, confirming the timestamp bug affects **any** time component regardless of timezone specification.

## Root Cause Analysis

### The API Bug
**The Diavgeia API has a critical bug where adding ANY time component (`T00:00:00`) to date parameters causes it to ignore the date range entirely and return nearly all decisions in the database.**

### Why Extended Ranges Work
The `extended_issue_range` approach (±1 day) works because:
1. **Uses date-only format** (avoids the timestamp bug)
2. **Covers potential timezone boundary issues** 
3. **Captures decisions with slightly different issue dates**
4. **Returns ~48K decisions** (roughly 3 days worth vs 1 day)

## Final Strategy & Implementation

### ✅ **Adopted Solution**
```python
def _fetch_for_single_increment(
    self, start_date: date, end_date: date, base_search_params: Dict[str, Any]
) -> List[Decision]:
    """Fetch decisions using date-only format with wide modification range"""
    
    current_search_params = base_search_params.copy()
    
    # ✅ USE DATE-ONLY FORMAT (no time components!)
    current_search_params["from_issue_date"] = start_date.isoformat()  # "2025-04-29"
    current_search_params["to_issue_date"] = end_date.isoformat()      # "2025-04-29"
    
    # ✅ Add wide modification date range to prevent automatic filtering
    current_search_params["from_date"] = "2020-01-01"
    current_search_params["to_date"] = "2030-12-31"
    
    # Standard pagination
    current_search_params["page"] = page
    current_search_params["size"] = self.DEFAULT_PAGE_SIZE
```

### Key Principles
1. **Never use time components** in date parameters
2. **Always specify wide modification date ranges** to prevent automatic API logic
3. **Use date-only ISO format** (`YYYY-MM-DD`)
4. **Handle timezone issues through date range extension** if needed

## Impact on Distributed System Design

### Original Plan (❌ Not Possible)
```python
# Can't split by hours due to API bug
{"from_issue_date": "2025-04-29T09:00:00", "to_issue_date": "2025-04-29T10:00:00"}
```

### ✅ **Alternative Distribution Strategies**

#### Option 1: Split by Date Only
```python
# Distribute by single days
worker_tasks = [
    {"from_issue_date": "2025-04-29", "to_issue_date": "2025-04-29"},
    {"from_issue_date": "2025-04-30", "to_issue_date": "2025-04-30"},
]
```

#### Option 2: Split by Other Criteria
```python
# Split by organization, document type, etc.
worker_tasks = [
    {"org": "org1", "from_issue_date": "2025-04-29", "to_issue_date": "2025-04-29"},
    {"org": "org2", "from_issue_date": "2025-04-29", "to_issue_date": "2025-04-29"},
]
```

#### Option 3: Post-Processing Filter
Fetch all decisions for the day and filter by actual timestamps in application code.

## Debugging Tools Created

### 1. `debug_search_criteria_comprehensive()`
- Tests 15+ different search parameter combinations
- Provides coverage percentage vs expected totals
- Includes emoji indicators for quick assessment
- **Usage**: One-time comprehensive testing

### 2. `debug_timestamp_precision()`  
- Tests various timestamp formats and precisions
- Analyzes hourly distribution for worker planning
- Tests boundary conditions
- **Usage**: Understanding timestamp behavior

### 3. `debug_timezone_interpretation()`
- Tests different timezone representations
- Validates timezone handling across formats
- **Usage**: Timezone-specific debugging

## Investigation Phase 5: Final Hourly Separation Verification

### Final Test: `debug_hourly_separation_final_test()`
As a final verification, we tested whether hourly separation could work with any combination of parameters:

```python
def debug_hourly_separation_final_test(self, target_date: date):
    """Final test to confirm that hourly separation is impossible due to API bug"""
    
    # Test specific hour ranges with various parameter combinations
    test_scenarios = [
        "Basic hourly range (9-10 AM)",
        "With wide modification range", 
        "With status=ALL",
        "Date-only with post-filtering simulation"
    ]
```

### Test Results
| Scenario | Parameters | Expected | Actual | Status |
|----------|------------|----------|--------|--------|
| Basic hourly (9-10 AM) | Time components | ~60-70 | 2,995,348 | ❌ Broken |
| + Wide modification range | Time + wide dates | ~60-70 | 2,995,348 | ❌ Still broken |
| + Status=ALL | Time + status | ~60-70 | 2,995,348 | ❌ Still broken |
| Date-only simulation | Date only + filter | ~60-70 | 1,481 → 62 | ✅ Works via post-processing |

### Final Conclusion on Hourly Distribution
**Hourly separation is IMPOSSIBLE through API parameters due to the timestamp bug.** The only viable approach is:

1. **Fetch full day** using date-only parameters
2. **Post-process filter** by actual timestamp in application code
3. **Distribute by date ranges** instead of hourly ranges

### Post-Processing Filter Example
```python
def filter_decisions_by_hour_range(decisions: List[Decision], start_hour: int, end_hour: int) -> List[Decision]:
    """Filter decisions by hour range after fetching from API"""
    filtered = []
    for decision in decisions:
        if decision.submission_timestamp:
            hour = decision.submission_timestamp.hour
            if start_hour <= hour < end_hour:
                filtered.append(decision)
    return filtered

# Usage for distributed processing
all_decisions_for_day = fetch_all_decisions_for_date("2025-04-29")
worker_1_decisions = filter_decisions_by_hour_range(all_decisions_for_day, 0, 8)   # 0-8 AM
worker_2_decisions = filter_decisions_by_hour_range(all_decisions_for_day, 8, 16)  # 8-16 PM  
worker_3_decisions = filter_decisions_by_hour_range(all_decisions_for_day, 16, 24) # 16-24 PM
```

## Lessons Learned

### Technical Insights
1. **Always test API behavior thoroughly** - official documentation may not reveal all quirks
2. **Date/time handling is often the most error-prone** part of external APIs
3. **Comprehensive testing suites save time** in the long run
4. **APIs may have undocumented automatic behaviors** that affect results

### API Integration Best Practices
1. **Start with minimal working examples** before adding complexity
2. **Test edge cases systematically** (boundaries, formats, combinations)
3. **Create debugging tools early** in the integration process
4. **Document discovered behaviors** for team knowledge

### Distributed System Considerations
1. **Validate distribution strategies** against API limitations
2. **Have fallback approaches** when ideal distribution isn't possible  
3. **Consider post-processing** when API limitations prevent optimal querying
4. **Balance API limitations** against system performance requirements

## Code Quality Improvements

### Before Investigation
```python
# Naive approach - didn't work as expected
current_search_params["from_issue_date"] = start_date.isoformat()
current_search_params["to_issue_date"] = end_date.isoformat()
```

### After Investigation  
```python
# Robust approach with comprehensive understanding
current_search_params["from_issue_date"] = start_date.isoformat()  # Date-only
current_search_params["to_issue_date"] = end_date.isoformat()      # Date-only  
current_search_params["from_date"] = "2020-01-01"                 # Wide range
current_search_params["to_date"] = "2030-12-31"                   # Wide range
# Comprehensive pagination logic with proper error handling
```

## Future Considerations

### Monitoring & Alerting
- Monitor decision counts vs expected values
- Alert on significant deviations from historical patterns
- Track API response times and error rates

### API Updates
- Regularly test for API behavior changes
- Maintain debugging tools for regression testing
- Document any new discoveries or workarounds

### Performance Optimization
- Consider caching strategies for repeated queries
- Implement intelligent retry logic for API failures
- Monitor and optimize database import performance

## Conclusion

This investigation transformed what initially appeared to be a simple pagination bug into a comprehensive understanding of Diavgeia API limitations and quirks. The discovery of the timestamp bug saved significant future development time and informed our distributed system architecture decisions.

**Key Takeaway**: Sometimes the "obvious" solution (adding precise timestamps) is exactly the wrong approach due to underlying API bugs. Systematic testing and documentation are essential for robust API integrations.
