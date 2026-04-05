"""
Search Suggestions Model

Provides configurable default search suggestions for the homepage search.
Allows admins to configure trending/popular entities through the admin interface.
"""

from django.db import models
from django.core.cache import cache
from django.utils import timezone


class SearchSuggestion(models.Model):
    """
    Model for storing default search suggestions.
    
    Admins can configure popular organizations, signers, or other entities
    to show as suggestions when users click on the search without typing.
    """
    
    SUGGESTION_TYPES = [
        ('organization', 'Organization'),
        ('signer', 'Signer'),
        ('unit', 'Unit'),
        ('company', 'Company'),
        ('company_person', 'Company Person'),
    ]
    
    # Type and reference
    suggestion_type = models.CharField(
        max_length=50,
        choices=SUGGESTION_TYPES,
        help_text="Type of entity to suggest"
    )
    
    entity_id = models.CharField(
        max_length=255,
        help_text="UID of the entity (organization.uid, signer.uid, etc.)"
    )
    
    display_text = models.CharField(
        max_length=500,
        help_text="Text to display in the suggestion (automatically populated from entity)"
    )
    
    # Ordering and visibility
    order = models.IntegerField(
        default=0,
        help_text="Display order (lower numbers appear first)"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this suggestion is currently active"
    )
    
    # Metadata
    description = models.TextField(
        blank=True,
        help_text="Optional description or reason for featuring this entity"
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Analytics
    click_count = models.IntegerField(
        default=0,
        help_text="Number of times this suggestion was clicked"
    )
    
    last_clicked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this suggestion was clicked"
    )
    
    class Meta:
        db_table = 'core_search_suggestion'
        verbose_name = 'Search Suggestion'
        verbose_name_plural = 'Search Suggestions'
        ordering = ['order', '-click_count']
        indexes = [
            models.Index(fields=['suggestion_type', 'is_active', 'order']),
            models.Index(fields=['is_active', 'order']),
        ]
    
    def __str__(self):
        return f"{self.get_suggestion_type_display()}: {self.display_text}"
    
    @classmethod
    def get_active_suggestions(cls, limit=10):
        """Get active suggestions in display order."""
        cache_key = f'search_suggestions_active_{limit}'
        suggestions = cache.get(cache_key)
        
        if suggestions is None:
            suggestions = list(
                cls.objects
                .filter(is_active=True)
                .order_by('order', '-click_count')[:limit]
            )
            # Cache for 5 minutes
            cache.set(cache_key, suggestions, 300)
        
        return suggestions
    
    @classmethod
    def clear_cache(cls):
        """Clear all cached suggestions."""
        # You might want to clear multiple cache keys if you have different limits
        for limit in [5, 10, 15, 20]:
            cache.delete(f'search_suggestions_active_{limit}')
    
    def save(self, *args, **kwargs):
        """Override save to clear cache when suggestions are updated."""
        super().save(*args, **kwargs)
        self.__class__.clear_cache()
    
    def delete(self, *args, **kwargs):
        """Override delete to clear cache when suggestions are removed."""
        super().delete(*args, **kwargs)
        self.__class__.clear_cache()
    
    def record_click(self):
        """Record a click on this suggestion."""
        self.click_count += 1
        self.last_clicked_at = timezone.now()
        self.save(update_fields=['click_count', 'last_clicked_at'])
