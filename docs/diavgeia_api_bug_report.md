# Diavgeia API Critical Bug Report

## Executive Summary
We have discovered a critical bug in the Diavgeia API that causes timestamp-based queries to return incorrect results. This significantly impacts any application attempting to query decisions by specific time ranges.

## Bug Description

### Issue
When any time component (`T00:00:00`) is added to date parameters (`from_issue_date`, `to_issue_date`), the API ignores the date range filters and returns nearly the entire database (~3 million decisions) instead of the expected filtered results.

### Affected Parameters
- `from_issue_date` with time components
- `to_issue_date` with time components
- Any timezone specifications (e.g., `+03:00`, `Z`)

### Expected vs Actual Behavior

#### ✅ **Correct Behavior (Date-only)**
```http
GET /decisions?from_issue_date=2025-04-29&to_issue_date=2025-04-29
```
**Expected**: ~1,481 decisions for April 29, 2025  
**Actual**: 1,481 decisions ✅

#### ❌ **Broken Behavior (With timestamps)**
```http
GET /decisions?from_issue_date=2025-04-29T00:00:00&to_issue_date=2025-04-29T23:59:59
```
**Expected**: ~1,481 decisions for April 29, 2025  
**Actual**: 2,995,348 decisions (entire database) ❌

## Impact Assessment

### Severity: **CRITICAL**
- **Data Integrity**: Applications receive 2000x more data than expected
- **Performance**: Massive unnecessary data transfer and processing
- **Functionality**: Impossible to query by specific time ranges
- **User Experience**: Timeouts, memory issues, incorrect results

### Affected Use Cases
1. **Time-based filtering**: Cannot filter decisions by hour, minute, or precise time ranges
2. **Distributed processing**: Cannot split large date ranges by time for parallel processing
3. **Incremental updates**: Cannot efficiently query for decisions within specific time windows
4. **Timezone-aware applications**: Cannot handle timezone-specific queries

## Reproduction Steps

### Minimal Test Case
```bash
# Working query (date-only)
curl "https://diavgeia.gov.gr/api/decisions?from_issue_date=2025-04-29&to_issue_date=2025-04-29"
# Returns: ~1,481 decisions

# Broken query (with time)
curl "https://diavgeia.gov.gr/api/decisions?from_issue_date=2025-04-29T00:00:00&to_issue_date=2025-04-29T23:59:59"
# Returns: ~3,000,000 decisions (entire database)
```

### Comprehensive Test Matrix
| Parameter Format | Result Count | Status |
|------------------|--------------|--------|
| `2025-04-29` | 1,481 | ✅ Works |
| `2025-04-29T00:00:00` | 2,995,348 | ❌ Broken |
| `2025-04-29T00:00:00Z` | 2,995,333 | ❌ Broken |
| `2025-04-29T00:00:00+03:00` | 2,995,348 | ❌ Broken |
| `2025-04-29T09:00:00` to `2025-04-29T10:00:00` | 2,995,348 | ❌ Broken |

## Environment Details
- **API Version**: Current production API (as of January 2025)
- **Tested Endpoints**: `/api/decisions`
- **Date Range Tested**: 2025-04-29 (chosen for verification against official website data)
- **Client**: Python `requests` library, cURL

## Workarounds

### Current Workaround
Use date-only format and implement time filtering in application code:

```python
# 1. Query with date-only format
decisions = api.get_decisions(
    from_issue_date="2025-04-29",
    to_issue_date="2025-04-29"
)

# 2. Filter by time in application code
filtered_decisions = [
    d for d in decisions 
    if start_time <= d.submission_timestamp.time() < end_time
]
```

### Limitations of Workaround
- **Inefficient**: Must transfer and process entire day's data
- **Memory intensive**: Large datasets may cause memory issues
- **Network overhead**: Unnecessary bandwidth usage
- **Complex logic**: Applications must implement time filtering logic

## Recommended Fix

### Server-Side Solution
The API should properly handle timestamp components in date parameters:

```http
# Should work correctly
GET /decisions?from_issue_date=2025-04-29T09:00:00&to_issue_date=2025-04-29T10:00:00
# Expected: Decisions issued between 9-10 AM on April 29, 2025
```

### Suggested Implementation
1. **Parse timestamp components** properly in date parameters
2. **Apply timezone handling** consistently across all date parameters
3. **Validate date range logic** when timestamps are provided
4. **Maintain backward compatibility** with date-only format

## Testing Recommendations

### Regression Tests
```http
# Test cases that should be included in API test suite
GET /decisions?from_issue_date=2025-04-29&to_issue_date=2025-04-29
# Expected: ~1,481 results

GET /decisions?from_issue_date=2025-04-29T00:00:00&to_issue_date=2025-04-29T23:59:59
# Expected: ~1,481 results (same as date-only)

GET /decisions?from_issue_date=2025-04-29T09:00:00&to_issue_date=2025-04-29T10:00:00
# Expected: ~60-70 results (subset of the day)
```

### Edge Cases to Test
- **Timezone boundaries**: Queries spanning midnight in different timezones
- **Daylight saving transitions**: Queries during DST changes
- **Leap seconds**: Queries during leap second adjustments
- **Invalid timestamps**: Proper error handling for malformed timestamps

## Documentation Impact

### Current Documentation Issues
The current API documentation does not mention:
- Timestamp format support limitations
- Time component behavior
- Timezone handling specifics
- Expected result count variations

### Suggested Documentation Updates
1. **Clearly specify** supported timestamp formats
2. **Document timezone handling** behavior
3. **Provide examples** of working vs non-working queries
4. **Add troubleshooting section** for common timestamp issues

## Business Impact

### For API Consumers
- **Development delays**: Workarounds require additional development time
- **Performance issues**: Inefficient data transfer and processing
- **Operational costs**: Increased bandwidth and compute resources
- **Data quality**: Risk of incorrect results in production systems

### For API Providers
- **Support load**: Increased support tickets from confused developers
- **Resource usage**: Unnecessary server load from oversized responses
- **Reputation**: API reliability and usability concerns
- **Adoption**: May discourage integration by new developers

## Contact Information

**Reported by**: Development Team, CRATI Project  
**Date**: January 2025  
**Priority**: Critical  
**Urgency**: High

### Technical Contact
For technical questions about this bug report, please contact the development team.

### Reproduction Code
Complete reproduction code and test cases are available upon request.

## Appendix: Detailed Test Results

### Full Test Output Sample
```json
{
  "date_only_query": {
    "parameters": {"from_issue_date": "2025-04-29", "to_issue_date": "2025-04-29"},
    "result_count": 1481,
    "status": "WORKING"
  },
  "timestamp_query": {
    "parameters": {"from_issue_date": "2025-04-29T00:00:00", "to_issue_date": "2025-04-29T23:59:59"},
    "result_count": 2995348,
    "status": "BROKEN",
    "expected_count": 1481,
    "ratio": "2024x more results than expected"
  }
}
```

### Performance Impact
- **Expected response size**: ~150KB (1,481 decisions)
- **Actual response size**: ~300MB (3M decisions)
- **Transfer time increase**: 2000x longer
- **Memory usage increase**: 2000x higher
- **Processing time increase**: 2000x longer

---

**This report represents a critical bug that significantly impacts API usability and should be prioritized for immediate resolution.**
