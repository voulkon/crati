"""
Admin classes for Notification models.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from notifications.models import NotificationSubscription, Notification


class NotificationSubscriptionAdmin(admin.ModelAdmin):
    """Admin interface for NotificationSubscription model."""
    
    list_display = [
        'id',
        'user',
        'subscription_type_display',
        'target_display',
        'is_active',
        'created_at',
        'last_checked'
    ]
    
    list_filter = [
        'is_active',
        'created_at',
        'last_checked'
    ]
    
    search_fields = [
        'user__username',
        'user__email',
        'organization__label',
        'organization__uid',
        'entity__afm',
        'entity__name',
        'person_name',
        'signer_name'
    ]
    
    readonly_fields = [
        'created_at',
        'subscription_type'
    ]
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Target (What to Watch)', {
            'description': 'Select one target type (organization, entity, relationship, person, or signer)',
            'fields': (
                'organization',
                'entity',
                'relationship_org',
                'relationship_entity',
                'person_name',
                'signer_name'
            )
        }),
        ('Filters (Optional)', {
            'description': 'Additional filters to narrow down matches',
            'fields': (
                'keywords',
                'amount_min',
                'amount_max',
                'decision_types'
            )
        }),
        ('Status', {
            'fields': (
                'is_active',
                'created_at',
                'last_checked'
            )
        }),
    )
    
    def subscription_type_display(self, obj):
        """Display subscription type with color coding."""
        colors = {
            'organization': 'blue',
            'entity': 'green',
            'relationship': 'purple',
            'person': 'orange',
            'signer': 'red',
            'filter': 'gray'
        }
        color = colors.get(obj.subscription_type, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_subscription_type_display() if hasattr(obj, 'get_subscription_type_display') else obj.subscription_type.title()
        )
    subscription_type_display.short_description = 'Type'
    
    def target_display(self, obj):
        """Display the target of the subscription."""
        if obj.subscription_type == 'organization':
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:core_organization_change', args=[obj.organization.uid]),
                obj.organization.label[:50] if obj.organization else 'N/A'
            )
        elif obj.subscription_type == 'entity':
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:core_afmentity_change', args=[obj.entity.id]),
                f"{obj.entity.afm} - {obj.entity.name}"[:50] if obj.entity else 'N/A'
            )
        elif obj.subscription_type == 'relationship':
            return format_html(
                '{} ↔ {}',
                obj.relationship_org.label[:25] if obj.relationship_org else 'N/A',
                obj.relationship_entity.afm if obj.relationship_entity else 'N/A'
            )
        elif obj.subscription_type == 'person':
            return obj.person_name
        elif obj.subscription_type == 'signer':
            return obj.signer_name
        else:
            return 'Filter only'
    target_display.short_description = 'Target'


class NotificationAdmin(admin.ModelAdmin):
    """Admin interface for Notification model."""
    
    list_display = [
        'id',
        'user',
        'subscription_type',
        'decision_link',
        'match_reason',
        'is_read',
        'is_dismissed',
        'created_at'
    ]
    
    list_filter = [
        'match_reason',
        'is_read',
        'is_dismissed',
        'created_at'
    ]
    
    search_fields = [
        'user__username',
        'user__email',
        'decision__ada',
        'decision__subject'
    ]
    
    readonly_fields = [
        'user',
        'subscription',
        'decision',
        'match_reason',
        'match_details',
        'created_at',
        'read_at'
    ]
    
    fieldsets = (
        ('User & Subscription', {
            'fields': ('user', 'subscription')
        }),
        ('Decision', {
            'fields': ('decision', 'match_reason', 'match_details')
        }),
        ('Status', {
            'fields': ('is_read', 'is_dismissed', 'created_at', 'read_at')
        }),
    )
    
    def subscription_type(self, obj):
        """Display subscription type."""
        return obj.subscription.subscription_type.title()
    subscription_type.short_description = 'Subscription Type'
    
    def decision_link(self, obj):
        """Display decision with link."""
        return format_html(
            '<a href="{}">{}</a><br/><small>{}</small>',
            reverse('admin:core_decision_change', args=[obj.decision.id]),
            obj.decision.ada,
            obj.decision.subject[:50] if obj.decision.subject else ''
        )
    decision_link.short_description = 'Decision'
    
    def has_add_permission(self, request):
        """Prevent manual creation of notifications in admin."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent editing notifications in admin (read-only)."""
        return False
