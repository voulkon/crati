from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid


class Subscription(models.Model):
    name = models.CharField(max_length=50)
    max_requests_per_day = models.PositiveIntegerField(default=1000)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    can_access_premium_data = models.BooleanField(default=False)
    can_queue_bulk_tasks = models.BooleanField(default=False)
    max_saved_items = models.PositiveIntegerField(default=100)  # New: limit saved items
    max_search_history = models.PositiveIntegerField(default=50)  # New: limit search history

    def __str__(self):
        return self.name


class CustomUser(AbstractUser):
    clerk_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    subscription = models.ForeignKey(
        Subscription, null=True, blank=True, on_delete=models.SET_NULL
    )
    subscription_expires = models.DateTimeField(null=True, blank=True)
    api_key = models.CharField(max_length=64, unique=True, null=True, blank=True)
    usage_this_month = models.IntegerField(default=0)
    
    # New: User preferences
    preferred_theme = models.CharField(max_length=20, default='light')  # light/dark
    preferred_palette = models.CharField(max_length=20, default='blue')  # blue/purple/green/etc
    preferred_layout = models.CharField(max_length=30, default='horizontal-right')
    
    @property
    def has_active_subscription(self):
        return (
            self.subscription is not None
            and self.subscription_expires is not None
            and self.subscription_expires > timezone.now()
        )

    @property
    def daily_request_limit(self):
        if self.has_active_subscription:
            return self.subscription.max_requests_per_day
        return 100  # Default limit for authenticated users without subscription

    @property
    def max_saved_items(self):
        if self.has_active_subscription:
            return self.subscription.max_saved_items
        return 20  # Free tier limit

    @property
    def max_search_history(self):
        if self.has_active_subscription:
            return self.subscription.max_search_history
        return 10  # Free tier limit

    def __str__(self):
        return self.username

# New: User activity tracking models
class SavedEntity(models.Model):
    ENTITY_TYPES = [
        ('ministry', 'Ministry'),
        ('organization', 'Organization'),
        ('unit', 'Unit'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='saved_entities')
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPES)
    entity_id = models.CharField(max_length=50)
    entity_name = models.CharField(max_length=255)
    entity_data = models.JSONField(null=True, blank=True)  # Store additional entity info
    notes = models.TextField(blank=True)  # User can add personal notes
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'entity_type', 'entity_id']
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.entity_name}"

class SavedDecision(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='saved_decisions')
    decision = models.ForeignKey(
        'core.Decision',
        on_delete=models.CASCADE,
        related_name='saved_by_users',
        to_field='ada'
    )
    tags = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'decision']  # New constraint
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.decision.ada}"
    
    # Convenience properties for backward compatibility
    @property
    def decision_ada(self):
        return self.decision.ada
    
    @property
    def decision_subject(self):
        return self.decision.subject

class SearchHistory(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='search_history')
    query = models.TextField()
    filters = models.JSONField(null=True, blank=True)  # Store search filters
    results_count = models.IntegerField(null=True, blank=True)
    search_type = models.CharField(max_length=50, default='general')  # 'general', 'entity', 'decision'
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.query[:50]}"

class VisitedEntity(models.Model):
    """Track entities user has visited for quick access"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='visited_entities')
    entity_type = models.CharField(max_length=20)
    entity_id = models.CharField(max_length=50)
    entity_name = models.CharField(max_length=255)
    visit_count = models.PositiveIntegerField(default=1)
    last_visited = models.DateTimeField(auto_now=True)
    first_visited = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'entity_type', 'entity_id']
        ordering = ['-last_visited']
    
    def __str__(self):
        return f"{self.user.username} visited {self.entity_name} ({self.visit_count}x)"
