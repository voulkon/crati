# Logging Configuration Guide

## Environment Variables

Control log levels and formats using these environment variables:

### Log Format
- **`USE_JSON_LOGGING`**: Enable JSON logging for Loki/Grafana
  - `true` = JSON format (production)
  - `false` = Text format (default, development)

### Log Levels

- **`DJANGO_LOG_LEVEL`**: Overall Django application log level (default: `INFO`)
  - Values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
  
- **`CELERY_LOG_LEVEL`**: Celery tasks and worker logs (default: `INFO`)
  - Values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
  
- **`DB_LOG_LEVEL`**: Django database query logs (default: `WARNING`)
  - Set to `DEBUG` to see all SQL queries (very verbose!)
  - Set to `WARNING` to hide routine SQL logs

### Examples

#### Production (Minimal Logs)
```bash
USE_JSON_LOGGING=true
DJANGO_LOG_LEVEL=INFO
CELERY_LOG_LEVEL=INFO
DB_LOG_LEVEL=WARNING
```

#### Development (More Verbose)
```bash
USE_JSON_LOGGING=false
DJANGO_LOG_LEVEL=DEBUG
CELERY_LOG_LEVEL=DEBUG
DB_LOG_LEVEL=WARNING  # Still suppress SQL unless needed
```

#### Debug SQL Queries
```bash
DJANGO_LOG_LEVEL=DEBUG
DB_LOG_LEVEL=DEBUG  # Now you'll see all SQL queries
```

#### Troubleshooting Celery
```bash
CELERY_LOG_LEVEL=DEBUG  # See detailed Celery task execution
DJANGO_LOG_LEVEL=INFO   # Keep Django logs at INFO
```

## What Gets Suppressed

The following loggers are automatically set to `WARNING` level to reduce noise:

- `celery.worker.strategy` - Task receive messages
- `celery.app.trace` - "TaskPool: Apply" messages
- `opentelemetry.instrumentation.celery` - OpenTelemetry "prerun signal" messages
- `django.db.backends` - SQL queries (unless `DB_LOG_LEVEL=DEBUG`)
- `requests` - HTTP request library
- `urllib3` - HTTP connection pooling

## Setting in Docker Compose

Add to your service's environment section:

```yaml
services:
  backend:
    environment:
      - USE_JSON_LOGGING=true
      - DJANGO_LOG_LEVEL=INFO
      - CELERY_LOG_LEVEL=INFO
      - DB_LOG_LEVEL=WARNING
  
  celery:
    environment:
      - USE_JSON_LOGGING=true
      - DJANGO_LOG_LEVEL=INFO
      - CELERY_LOG_LEVEL=INFO
      - DB_LOG_LEVEL=WARNING
```

## Grafana Log Queries

With these settings, you can query logs efficiently:

```logql
# Only INFO and above from all services
{component="celery"} |= "INFO"

# Only ERROR logs
{component="celery"} |= "ERROR"

# Specific task logs
{component="celery"} |= "store_decisions_from_pickle"

# Without noisy DB queries
{component="celery"} != "django.db.backends"
```
