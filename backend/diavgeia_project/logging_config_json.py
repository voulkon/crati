"""
JSON Logging Configuration for Django + Loki

This module provides a production-ready logging configuration that:
1. Outputs structured JSON logs to stdout
2. Works with Promtail -> Loki -> Grafana pipeline
3. Supports contextual metadata (ingestion_id, ada, stage, etc.)
4. Compatible with both Django and Celery

Usage:
    In settings.py, replace the LOGGING dict with:
    
    from diavgeia_project.logging_config_json import get_json_logging_config
    LOGGING = get_json_logging_config(DEBUG)
"""

import sys


def get_json_logging_config(debug_mode=False):
    """
    Get logging configuration with JSON formatting.
    
    Args:
        debug_mode: If True, adds verbose console output for debugging
        
    Returns:
        dict: Django LOGGING configuration
    """
    
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        
        'formatters': {
            'json': {
                '()': 'pythonjsonlogger.json.JsonFormatter',
                'format': '%(asctime)s %(name)s %(levelname)s %(message)s %(funcName)s %(pathname)s %(lineno)d',
                'rename_fields': {
                    'asctime': 'timestamp',
                    'levelname': 'level',
                    'name': 'logger',
                    'funcName': 'function',
                    'pathname': 'file',
                    'lineno': 'line',
                },
                'datefmt': '%Y-%m-%d %H:%M:%S.%f',
            },
            'verbose': {
                'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
                'style': '{',
            },
        },
        
        'filters': {
            'require_debug_false': {
                '()': 'django.utils.log.RequireDebugFalse',
            },
            'require_debug_true': {
                '()': 'django.utils.log.RequireDebugTrue',
            },
        },
        
        'handlers': {
            'console_json': {
                'level': 'INFO',
                'class': 'logging.StreamHandler',
                'formatter': 'json',
                'stream': 'ext://sys.stdout',
            },
            'console_debug': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
                'formatter': 'verbose',
                'filters': ['require_debug_true'],
                'stream': 'ext://sys.stderr',
            },
        },
        
        'root': {
            'level': 'INFO',
            'handlers': ['console_json'],
        },
        
        'loggers': {
            'django': {
                'handlers': ['console_json'],
                'level': 'INFO',
                'propagate': False,
            },
            'django.request': {
                'handlers': ['console_json'],
                'level': 'ERROR',
                'propagate': False,
            },
            'django.security': {
                'handlers': ['console_json'],
                'level': 'INFO',
                'propagate': False,
            },
            'api': {
                'handlers': ['console_json'],
                'level': 'INFO',
                'propagate': False,
            },
            'core': {
                'handlers': ['console_json'],
                'level': 'INFO',
                'propagate': False,
            },
            'users': {
                'handlers': ['console_json'],
                'level': 'INFO',
                'propagate': False,
            },
            'celery': {
                'handlers': ['console_json'],
                'level': 'INFO',
                'propagate': False,
            },
            'celery.task': {
                'handlers': ['console_json'],
                'level': 'INFO',
                'propagate': False,
            },
            # Suppress noisy libraries
            'requests': {
                'handlers': ['console_json'],
                'level': 'WARNING',
                'propagate': False,
            },
            'urllib3': {
                'handlers': ['console_json'],
                'level': 'WARNING',
                'propagate': False,
            },
        }
    }
    
    # In debug mode, add verbose console output
    if debug_mode:
        config['handlers']['console_debug']['level'] = 'DEBUG'
        for logger_name in ['django', 'api', 'core', 'celery']:
            if logger_name in config['loggers']:
                config['loggers'][logger_name]['handlers'].append('console_debug')
    
    return config


# Context-aware logger helpers
class StructuredLogger:
    """
    Helper class for adding structured metadata to logs.
    
    Usage:
        logger = StructuredLogger('core.pipeline')
        logger.info("Processing started", ingestion_id="abc123", ada="TEST-ADA")
    """
    
    def __init__(self, name):
        import logging
        self.logger = logging.getLogger(name)
    
    def _log(self, level, message, **context):
        """Log with structured context as extra fields"""
        # Filter out None values to keep JSON clean
        extra = {k: v for k, v in context.items() if v is not None}
        getattr(self.logger, level)(message, extra=extra)
    
    def debug(self, message, **context):
        self._log('debug', message, **context)
    
    def info(self, message, **context):
        self._log('info', message, **context)
    
    def warning(self, message, **context):
        self._log('warning', message, **context)
    
    def error(self, message, **context):
        self._log('error', message, **context)
    
    def exception(self, message, **context):
        """Log exception with traceback"""
        extra = {k: v for k, v in context.items() if v is not None}
        self.logger.exception(message, extra=extra)


# Example usage in pipeline
"""
from diavgeia_project.logging_config_json import StructuredLogger

class DecisionPipelineOrchestrator:
    def __init__(self):
        self.logger = StructuredLogger('core.pipeline')
    
    def run_pipeline(self, decision_ada: str, force_reprocess: bool = False):
        import uuid
        ingestion_id = str(uuid.uuid4())[:8]
        
        self.logger.info(
            "Pipeline started",
            ingestion_id=ingestion_id,
            ada=decision_ada,
            force_reprocess=force_reprocess
        )
        
        # All subsequent logs can include the same context
        self.logger.info(
            "Entity extraction started",
            ingestion_id=ingestion_id,
            ada=decision_ada,
            stage="entity_extraction"
        )
        
        try:
            # ... processing ...
            self.logger.info(
                "Pipeline completed",
                ingestion_id=ingestion_id,
                ada=decision_ada,
                duration_ms=1234
            )
        except Exception as e:
            self.logger.exception(
                "Pipeline failed",
                ingestion_id=ingestion_id,
                ada=decision_ada,
                error_type=type(e).__name__
            )

# Then in Grafana:
# {component="celery"} | json | ingestion_id="abc12345"
# {component="celery"} | json | ada="ΨΨ4746ΛΕΑΩ-ΩΞΨ"
# {component="celery"} | json | stage="entity_extraction"
"""
