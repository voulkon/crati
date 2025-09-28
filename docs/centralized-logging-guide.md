# Centralized Logging with Grafana + Loki

This setup provides comprehensive centralized logging for the Diavgeia application stack using Grafana and Loki.

## Architecture Overview

```
┌─────────────────┐    ┌──────────────┐    ┌──────────────┐
│   Services      │───▶│     Loki     │───▶│   Grafana    │
│ (Django, Celery)│    │ (Log Storage)│    │(Visualization)│
└─────────────────┘    └──────────────┘    └──────────────┘
                              │
                              ▼
                       ┌──────────────┐
                       │    Jaeger    │
                       │ (Traces)     │
                       └──────────────┘
```

## Components

### 1. Loki (Log Aggregation)
- **Port**: 3100
- **Purpose**: Lightweight log aggregation system optimized for storing and querying logs
- **Configuration**: `/docker/loki-config/local-config.yaml`

### 2. Grafana (Visualization)
- **Port**: 3000 
- **Purpose**: Dashboards and log visualization
- **Default Login**: admin / admin (change via `GRAFANA_ADMIN_PASSWORD`)
- **Dashboards**: Pre-configured dashboard for application monitoring

### 3. Enhanced Logging Framework
- **JSON Structured Logs**: All logs are formatted as JSON for easy parsing
- **OpenTelemetry Integration**: Automatic trace correlation
- **Service Context**: Every log includes service identification
- **Task/Endpoint Context**: Celery tasks and API calls include specific context

## Quick Start

1. **Start the logging stack**:
   ```bash
   cd docker
   docker-compose -f docker-compose-lite.yml up -d loki grafana
   ```

2. **Start your services** (they'll now automatically send logs to Loki):
   ```bash
   docker-compose -f docker-compose-lite.yml up -d
   ```

3. **Access Grafana**:
   - URL: http://localhost:3000
   - Login: admin / admin
   - Navigate to "Diavgeia Application Logs" dashboard

## Log Structure

All logs follow this JSON structure:

```json
{
  "timestamp": "2025-09-29T10:30:00.123Z",
  "levelname": "INFO",
  "service_name": "diavgeia-backend",
  "message": "User login successful",
  "trace_id": "abc123...",
  "span_id": "def456...",
  "endpoint": "/api/v1/login",
  "method": "POST",
  "user_id": "123",
  "duration_ms": 45,
  "status_code": 200
}
```

## Service Labels

Each service is automatically labeled for easy filtering:

- **diavgeia-backend**: Django API server
- **diavgeia-worker**: Celery worker processes  
- **diavgeia-beat**: Celery beat scheduler
- **diavgeia-flower**: Celery monitoring UI

## Using the Logging Utilities

### 1. API Logging (Django)

```python
from diavgeia_project.logging_utils import api_logger, log_api_calls

# Method 1: Decorator (automatic)
@log_api_calls()
def my_view(request):
    return JsonResponse({"status": "success"})

# Method 2: Manual logging
def my_view(request):
    api_logger.info("Processing user request", extra={
        "user_id": request.user.id,
        "action": "data_export"
    })
    return JsonResponse({"status": "success"})
```

### 2. Task Logging (Celery)

```python
from diavgeia_project.logging_utils import task_logger, log_task_execution

# Method 1: Decorator (automatic)
@log_task_execution()
@app.task
def my_task(param1, param2):
    return "Task completed"

# Method 2: Manual logging  
@app.task
def my_task(param1, param2):
    task_logger.info("Task processing started", extra={
        "param1": param1,
        "data_size": len(param2)
    })
    # ... task logic ...
    task_logger.info("Task completed successfully")
```

### 3. Custom Context Logging

```python
from diavgeia_project.logging_utils import get_logger

logger = get_logger(__name__)

# Add temporary context
with logger.context(user_id=123, operation="data_import"):
    logger.info("Starting data import")
    # All logs in this block will include user_id and operation

# Set persistent context
logger.set_context(session_id="abc123")
logger.info("This will include session_id")
```

## Dashboard Features

The pre-configured Grafana dashboard includes:

1. **Log Rate by Service**: Real-time view of logging activity
2. **Error Rate by Service**: Monitor error frequencies  
3. **API Endpoint Performance**: Track endpoint response times and error rates
4. **Celery Task Performance**: Monitor task execution times and success rates
5. **Recent Errors**: Quick view of latest errors across all services
6. **Application Logs**: Searchable, filterable log viewer

## Querying Logs

### Loki Query Examples

```logql
# All logs from Django backend
{service_name="diavgeia-backend"}

# API errors only
{component="django"} |~ "ERROR|CRITICAL"

# Celery task failures
{component="celery"} | json | error_type != ""

# Specific endpoint logs
{component="django"} | json | endpoint="/api/v1/decisions"

# Logs with specific trace ID (correlation with Jaeger)
{} | json | trace_id="your-trace-id-here"

# High latency API calls
{component="django"} | json | duration_ms > 1000
```

### Using LogQL Filters

```logql
# Parse JSON and filter
{service_name="diavgeia-backend"} | json | status_code >= 400

# Rate calculations
rate({component="django"}[5m])

# Aggregations
sum by (endpoint) (rate({component="django"} | json | status_code >= 400[5m]))
```

## Trace-Log Correlation

Logs automatically include OpenTelemetry trace IDs. In Grafana:

1. **From Logs to Traces**: Click on trace_id in logs to jump to Jaeger
2. **From Traces to Logs**: In Jaeger, traces link back to related logs
3. **Combined View**: Use Grafana's explore feature to see logs and traces side-by-side

## Environment Configuration

### Environment Variables

```env
# Grafana
GRAFANA_ADMIN_PASSWORD=your-secure-password
GRAFANA_ROOT_URL=http://localhost:3000

# Service identification 
SERVICE_NAME=diavgeia-backend  # Optional, auto-detected
```

### Log Levels

Configure in Django settings or via environment:

```python
# Production: INFO and above
# Development: DEBUG and above  
# Critical systems: WARNING and above
```

## Troubleshooting

### 1. No Logs in Grafana
- Check Loki is running: `curl http://localhost:3100/ready`
- Verify services are sending logs to Loki driver
- Check docker logs: `docker logs diavgeia_loki`

### 2. High Log Volume
- Adjust log levels in Django settings
- Use log sampling for high-frequency operations
- Configure Loki retention policies

### 3. Missing Context
- Ensure logging utilities are imported and used
- Check OpenTelemetry instrumentation is active
- Verify JSON formatter is enabled

## Best Practices

### 1. Log Levels
- **DEBUG**: Detailed information for development
- **INFO**: General information (user actions, task completions)
- **WARNING**: Something unexpected but handled
- **ERROR**: Error occurred but application continues  
- **CRITICAL**: Serious error, application may stop

### 2. Context Information
- Always include relevant identifiers (user_id, task_id, etc.)
- Add timing information for performance monitoring
- Include error context (what was being attempted)

### 3. Sensitive Data
- Never log passwords, tokens, or personal data
- Truncate large payloads
- Use structured fields rather than message interpolation

### 4. Performance
- Use appropriate log levels for production
- Consider async logging for high-volume applications
- Monitor Loki storage usage

## Maintenance

### Log Retention
Loki automatically manages log retention. For production, consider:
- Configuring retention policies in `loki-config.yaml`
- Setting up log compaction
- Monitoring storage usage

### Dashboard Updates
Dashboards are in `/docker/grafana-provisioning/dashboards/`
- Edit JSON files directly
- Changes are auto-reloaded by Grafana
- Export dashboards from UI for backup

### Scaling
For high-volume production:
- Use Loki clustering
- Configure log shipping via Promtail
- Set up alerting rules
- Consider log sampling strategies