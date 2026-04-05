"""
Feature Flag Models

Provides database-backed feature flags with environment variable fallback.
Allows runtime configuration of system features through the admin interface.
"""

from django.db import models
from django.core.cache import cache
from django.utils import timezone


class FeatureFlag(models.Model):
    """
    Feature flag model for controlling system functionality.
    
    Flags can be enabled/disabled through the admin interface with database priority.
    If a flag is not in the database, the system falls back to environment variables.
    
    Features support runtime updates with automatic cache invalidation.
    """
    
    FLAG_CATEGORIES = [
        ('authentication', 'Authentication & Access'),
        ('data_indexing', 'Data Indexing'),
        ('data_extraction', 'Data Extraction'),
        ('data_enrichment', 'Data Enrichment'),
        ('api', 'API Features'),
        ('frontend', 'Frontend Features'),
        ('system', 'System Features'),
    ]
    
    # Core fields
    key = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique identifier for the feature flag (e.g., 'STEALTH_MODE')"
    )
    
    enabled = models.BooleanField(
        default=True,
        help_text="Enable or disable this feature"
    )
    
    # Metadata
    category = models.CharField(
        max_length=50,
        choices=FLAG_CATEGORIES,
        default='system',
        help_text="Category for organizing flags"
    )
    
    name = models.CharField(
        max_length=200,
        help_text="Human-readable name for this flag"
    )
    
    description = models.TextField(
        help_text="Detailed description of what this flag controls"
    )
    
    # Additional information
    default_value = models.BooleanField(
        default=False,
        help_text="Default value if not set in database or environment"
    )
    
    env_var_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Associated environment variable name (if applicable)"
    )
    
    requires_restart = models.BooleanField(
        default=False,
        help_text="Whether changing this flag requires a service restart"
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_checked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this flag was checked"
    )
    
    # Safety features
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this flag is currently active in the system"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Additional notes or warnings about this flag"
    )
    
    class Meta:
        db_table = 'core_feature_flags'
        verbose_name = 'Feature Flag'
        verbose_name_plural = 'Feature Flags'
        ordering = ['category', 'key']
        indexes = [
            models.Index(fields=['key', 'is_active']),
            models.Index(fields=['category']),
        ]
    
    def __str__(self):
        status = "✓" if self.enabled else "✗"
        return f"{status} {self.name} ({self.key})"
    
    def save(self, *args, **kwargs):
        """Override save to invalidate cache when flag changes."""
        super().save(*args, **kwargs)
        # Invalidate cache for this flag
        cache_key = f"feature_flag:{self.key}"
        cache.delete(cache_key)
        # Also invalidate the all flags cache
        cache.delete("feature_flags:all")
    
    def delete(self, *args, **kwargs):
        """Override delete to invalidate cache."""
        cache_key = f"feature_flag:{self.key}"
        cache.delete(cache_key)
        cache.delete("feature_flags:all")
        super().delete(*args, **kwargs)
    
    @staticmethod
    def get_cache_key(key: str) -> str:
        """Get the cache key for a feature flag."""
        return f"feature_flag:{key}"


class FeatureFlagAuditLog(models.Model):
    """
    Audit log for tracking feature flag changes.
    
    Maintains a history of all flag modifications for compliance and debugging.
    """
    
    feature_flag = models.ForeignKey(
        FeatureFlag,
        on_delete=models.CASCADE,
        related_name='audit_logs'
    )
    
    changed_by = models.CharField(
        max_length=200,
        help_text="User or system that made the change"
    )
    
    change_type = models.CharField(
        max_length=20,
        choices=[
            ('created', 'Created'),
            ('enabled', 'Enabled'),
            ('disabled', 'Disabled'),
            ('updated', 'Updated'),
        ]
    )
    
    old_value = models.BooleanField(null=True, blank=True)
    new_value = models.BooleanField(null=True, blank=True)
    
    changed_at = models.DateTimeField(default=timezone.now)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'core_feature_flag_audit_logs'
        verbose_name = 'Feature Flag Audit Log'
        verbose_name_plural = 'Feature Flag Audit Logs'
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['feature_flag', '-changed_at']),
        ]
    
    def __str__(self):
        return f"{self.feature_flag.key} - {self.change_type} at {self.changed_at}"
