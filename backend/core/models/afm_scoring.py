"""
AFM Entity Scoring and Queue Configuration Models

These models control how AFM entities are scored, filtered, and prioritized
for company data fetching from GEMI.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class AFMScoringConfig(models.Model):
    """
    Configuration for AFM entity scoring algorithm.
    Only one active configuration should exist at a time.
    """
    
    name = models.CharField(
        max_length=100,
        help_text="Name for this scoring configuration (e.g., 'Default', 'Aggressive', 'Conservative')"
    )
    is_active = models.BooleanField(
        default=False,
        help_text="Only one config can be active at a time"
    )
    
    # Scoring weights (must sum to 1.0)
    frequency_weight = models.FloatField(
        default=0.30,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Weight for appearance frequency (0-1)"
    )
    amount_weight = models.FloatField(
        default=0.50,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Weight for total transaction amounts (0-1)"
    )
    organization_weight = models.FloatField(
        default=0.20,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Weight for unique organization count (0-1)"
    )
    
    # Filtering criteria (minimum thresholds)
    min_appearances = models.PositiveIntegerField(
        default=3,
        help_text="Minimum number of decision appearances to be eligible for fetching"
    )
    min_total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=5000.00,
        help_text="Minimum total transaction amount (€) to be eligible"
    )
    min_unique_organizations = models.PositiveIntegerField(
        default=2,
        help_text="Minimum number of unique organizations worked with"
    )
    
    # Retry configuration
    retry_failed_after_days = models.PositiveIntegerField(
        default=90,
        help_text="Days to wait before retrying a failed GEMI lookup"
    )
    never_retry_after_failures = models.PositiveIntegerField(
        default=5,
        help_text="Stop retrying after this many consecutive failures"
    )
    
    # Recency boost (optional)
    enable_recency_boost = models.BooleanField(
        default=False,
        help_text="Boost score for entities seen recently"
    )
    recency_days_threshold = models.PositiveIntegerField(
        default=30,
        help_text="Days threshold for recency boost"
    )
    recency_boost_multiplier = models.FloatField(
        default=1.2,
        validators=[MinValueValidator(1.0), MaxValueValidator(3.0)],
        help_text="Multiplier for recent entities (e.g., 1.2 = 20% boost)"
    )
    
    # Metadata
    notes = models.TextField(
        blank=True,
        help_text="Notes about this configuration"
    )
    
    class Meta:
        verbose_name = "AFM Scoring Configuration"
        verbose_name_plural = "AFM Scoring Configurations"
        ordering = ['-is_active', 'name']
    
    def __str__(self):
        status = "ACTIVE" if self.is_active else "Inactive"
        return f"{self.name} ({status})"
    
    def save(self, *args, **kwargs):
        """Ensure only one active config exists."""
        if self.is_active:
            # Deactivate all other configs
            AFMScoringConfig.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)
    
    def validate_weights(self):
        """Check that weights sum to approximately 1.0."""
        total = self.frequency_weight + self.amount_weight + self.organization_weight
        if not (0.99 <= total <= 1.01):  # Allow small floating point errors
            raise ValueError(f"Weights must sum to 1.0, got {total}")
    
    @classmethod
    def get_active(cls):
        """Get the active scoring configuration."""
        return cls.objects.filter(is_active=True).first()


class AFMEntityScore(models.Model):
    """
    Stores computed importance scores for AFM entities.
    Updated periodically by scoring service.
    """
    
    entity = models.OneToOneField(
        'core.AFMEntity',
        on_delete=models.CASCADE,
        related_name='score_data',
        primary_key=True
    )
    
    # Computed score components
    total_score = models.FloatField(
        default=0.0,
        db_index=True,
        help_text="Final weighted score (0-100)"
    )
    frequency_score = models.FloatField(
        default=0.0,
        help_text="Normalized appearance frequency score"
    )
    amount_score = models.FloatField(
        default=0.0,
        help_text="Normalized total amount score"
    )
    organization_score = models.FloatField(
        default=0.0,
        help_text="Normalized unique organization score"
    )
    
    # Raw metrics used for scoring
    total_appearances = models.PositiveIntegerField(
        default=0,
        help_text="Total decision appearances"
    )
    total_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Sum of all associated transaction amounts"
    )
    unique_organizations = models.PositiveIntegerField(
        default=0,
        help_text="Count of unique organizations"
    )
    
    # Queue status
    is_eligible = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Meets minimum thresholds for fetching"
    )
    fetch_priority = models.IntegerField(
        default=0,
        db_index=True,
        help_text="Priority rank (1 = highest priority)"
    )
    
    # Metadata
    config_used = models.ForeignKey(
        AFMScoringConfig,
        on_delete=models.SET_NULL,
        null=True,
        help_text="Configuration used to compute this score"
    )
    scored_at = models.DateTimeField(
        auto_now=True,
        help_text="When this score was last computed"
    )
    
    class Meta:
        verbose_name = "AFM Entity Score"
        verbose_name_plural = "AFM Entity Scores"
        ordering = ['-total_score']
        indexes = [
            models.Index(fields=['-total_score']),
            models.Index(fields=['is_eligible', '-total_score']),
            models.Index(fields=['fetch_priority']),
        ]
    
    def __str__(self):
        return f"{self.entity.afm}: {self.total_score:.2f} (Rank #{self.fetch_priority})"
