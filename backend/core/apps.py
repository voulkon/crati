from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    
    def ready(self):
        import core.signals  # noqa
        # ("Core app is ready and signals are imported.")
        
        # Auto-initialize feature flags on startup
        self._initialize_feature_flags()
    
    def _initialize_feature_flags(self):
        """Initialize feature flags in the database if they don't exist."""
        import sys
        from django.db import connection
        from django.db.utils import OperationalError, ProgrammingError
        
        # Skip during migrations and certain management commands
        if 'migrate' in sys.argv or 'makemigrations' in sys.argv:
            return
        
        try:
            # Check if the database tables exist
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_name = 'core_feature_flags')"
                )
                table_exists = cursor.fetchone()[0]
                
            if not table_exists:
                return
            
            # Import here to avoid circular imports
            from core.services.feature_flag_service import feature_flags
            from loguru import logger
            
            # Initialize flags (this is idempotent - safe to call multiple times)
            count = feature_flags.initialize_flags_in_db()
            if count > 0:
                logger.info(f"Auto-initialized {count} feature flags in database")
                
        except (OperationalError, ProgrammingError):
            # Database not ready yet, skip initialization
            pass
        except Exception as e:
            # Log but don't crash the app
            from loguru import logger
            logger.warning(f"Could not auto-initialize feature flags: {e}")