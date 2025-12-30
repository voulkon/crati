# Grafana Log Queries for Decision Pipeline

## Query by Ingestion ID

The orchestrator now adds a unique `ingestion_id` to all logs for a single decision's pipeline run.

### Example Logs Output

```
2025-12-30 19:08:19 | INFO | ================================================================================
2025-12-30 19:08:19 | INFO | 🚀 Starting pipeline for decision ΡΗΣΥ46ΜΑΠΣ-600
2025-12-30 19:08:19 | INFO |    Ingestion ID: a1b2c3d4 (use this to filter logs)
2025-12-30 19:08:19 | INFO |    Force reprocess: True
2025-12-30 19:08:19 | INFO | ================================================================================

2025-12-30 19:08:19 | INFO | 
================================================================================
📝 STAGE 1/5: ENTITY EXTRACTION
================================================================================

2025-12-30 19:08:19 | INFO | 
================================================================================
🏢 STAGE 2/5: COMPANY ENRICHMENT
================================================================================

2025-12-30 19:08:19 | INFO | 
================================================================================
📄 STAGE 3/5: DOCUMENT PROCESSING
================================================================================

2025-12-30 19:08:19 | INFO | 
================================================================================
🔎 STAGE 4/5: OPENSEARCH INDEXING
================================================================================

2025-12-30 19:08:19 | INFO | 
================================================================================
📊 STAGE 5/5: COVERAGE METRICS
================================================================================

2025-12-30 19:08:19 | INFO | 
================================================================================
2025-12-30 19:08:19 | INFO | ✅ Pipeline completed for ΡΗΣΥ46ΜΑΠΣ-600
2025-12-30 19:08:19 | INFO |    Overall Status: HEALTHY
2025-12-30 19:08:19 | INFO |    Ingestion ID: a1b2c3d4
2025-12-30 19:08:19 | INFO | ================================================================================
```

## Grafana Loki Queries

### 1. Filter by Specific Decision (ADA)

```logql
{container="worker"} |= "ΡΗΣΥ46ΜΑΠΣ-600"
```

### 2. Filter by Ingestion ID (All Logs for One Pipeline Run)

```logql
{container="worker"} | json | ingestion_id="a1b2c3d4"
```

**Note:** The `ingestion_id` is added to log context via `logger.contextualize()`, so Loki can extract it as a JSON field.

### 3. Find Failed Pipelines

```logql
{container="worker"} |= "Pipeline completed" |= "Status: ERROR"
```

### 4. Track Single Decision Through Full Pipeline

```logql
{container="worker"} 
| json 
| ada="ΡΗΣΥ46ΜΑΠΣ-600"
| line_format "{{.ts}} | {{.level}} | {{.message}}"
```

### 5. Show Only Pipeline Stage Headers

```logql
{container="worker"} |~ "STAGE [1-5]/5"
```

### 6. Failed OpenSearch Indexing

```logql
{container="worker"} |= "STAGE 4/5: OPENSEARCH" |= "ERROR"
```

### 7. All Decisions Processed in Last Hour

```logql
{container="worker"} |= "Starting pipeline for decision" [1h]
```

### 8. Group by Status (Health Metrics)

```logql
sum by (overall_status) (
  count_over_time({container="worker"} |= "Pipeline completed" | json [1h])
)
```

## Loguru Configuration for JSON Output

If you want structured logs for better Grafana parsing, update your loguru config:

```python
# In settings.py or logging config
from loguru import logger
import sys

logger.configure(
    handlers=[
        {
            "sink": sys.stderr,
            "format": "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[ingestion_id]:-} | {extra[ada]:-} | {message}",
            "serialize": False,  # Set to True for JSON output
        }
    ]
)
```

### JSON Output Example

```json
{
  "text": "🚀 Starting pipeline for decision ΡΗΣΥ46ΜΑΠΣ-600",
  "record": {
    "elapsed": {"repr": "0:00:00.123456", "seconds": 0.123456},
    "extra": {
      "ingestion_id": "a1b2c3d4",
      "ada": "ΡΗΣΥ46ΜΑΠΣ-600"
    },
    "level": {
      "name": "INFO",
      "no": 20
    },
    "message": "🚀 Starting pipeline for decision ΡΗΣΥ46ΜΑΠΣ-600",
    "time": {"repr": "2025-12-30 19:08:19.123456+00:00", "timestamp": 1735579699.123456}
  }
}
```

Then in Grafana:
```logql
{container="worker"} | json | ingestion_id="a1b2c3d4" | level="ERROR"
```

## Visual Separators in Logs

The pipeline now uses visual separators to make stages easy to identify:

```
================================================================================
📝 STAGE 1/5: ENTITY EXTRACTION
================================================================================
```

**Benefits:**
- Easy to scan logs visually
- Stage boundaries are obvious
- Can grep/search for specific stages
- Clear start/end markers

## Quick Debugging Workflow

1. **Find the ingestion_id:**
   ```logql
   {container="worker"} |= "Starting pipeline for decision" |= "ΡΗΣΥ46ΜΑΠΣ-600"
   ```
   Look for: `Ingestion ID: a1b2c3d4`

2. **Get all logs for that run:**
   ```logql
   {container="worker"} | json | ingestion_id="a1b2c3d4"
   ```

3. **Find errors:**
   ```logql
   {container="worker"} | json | ingestion_id="a1b2c3d4" | level="ERROR"
   ```

4. **Check specific stage:**
   ```logql
   {container="worker"} | json | ingestion_id="a1b2c3d4" |= "STAGE 3/5"
   ```

## Example Grafana Dashboard Queries

### Panel 1: Pipeline Success Rate (Last 24h)

```logql
sum(
  count_over_time({container="worker"} |= "Pipeline completed" |= "Status: HEALTHY" [24h])
) 
/ 
sum(
  count_over_time({container="worker"} |= "Pipeline completed" [24h])
) * 100
```

### Panel 2: Failed Stage Distribution

```logql
sum by (stage) (
  count_over_time({container="worker"} |~ "STAGE [1-5]/5.*ERROR" [24h])
)
```

### Panel 3: Processing Time per Decision

```logql
{container="worker"} 
|= "Pipeline completed" 
| json 
| line_format "{{.elapsed_seconds}}"
```

### Panel 4: Active Pipeline Runs (Real-time)

```logql
count(
  {container="worker"} |= "Starting pipeline" [1m]
) 
-
count(
  {container="worker"} |= "Pipeline completed" [1m]
)
```

## Tips

1. **Always use `ingestion_id`** - It's the unique key to trace a single decision through the pipeline
2. **Visual separators** - Make it easy to see stage boundaries in raw logs
3. **Stage markers** - `STAGE X/5` format is grep-friendly
4. **Status in completion log** - Final status is always logged at the end
5. **Celery task ID** - Also logged for cross-referencing with Celery Flower

## Command Line Grep Examples

```bash
# Find all logs for specific ingestion ID
docker logs worker 2>&1 | grep "a1b2c3d4"

# See only stage headers
docker logs worker 2>&1 | grep "STAGE"

# Find failed pipelines
docker logs worker 2>&1 | grep "Pipeline completed" | grep "ERROR"

# Count decisions processed today
docker logs worker 2>&1 | grep "Starting pipeline" | grep "2025-12-30" | wc -l
```

---

**Summary:**
- ✅ Every pipeline run gets unique `ingestion_id`
- ✅ Visual separators (`====`) between stages
- ✅ Structured logging with context (ada, ingestion_id)
- ✅ Easy Grafana filtering: `| json | ingestion_id="..."`
- ✅ Clear stage markers for grep/search
