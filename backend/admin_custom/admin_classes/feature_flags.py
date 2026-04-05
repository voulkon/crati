"""
Admin interface for Feature Flags.

Provides a user-friendly interface for managing feature flags with:
- Real-time flag toggling
- Category-based organization
- Environment variable comparison
- Audit logging
- Cache management
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Count
from django import forms

from core.models.feature_flags import FeatureFlag, FeatureFlagAuditLog
from core.services.feature_flag_service import feature_flags


class FeatureFlagForm(forms.ModelForm):
    """Custom form for FeatureFlag with additional validation."""
    
    class Meta:
        model = FeatureFlag
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class FeatureFlagAuditLogInline(admin.TabularInline):
    """Inline admin for viewing audit logs."""
    model = FeatureFlagAuditLog
    extra = 0
    can_delete = False
    readonly_fields = ['changed_by', 'change_type', 'old_value', 'new_value', 'changed_at', 'notes']
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    """Admin interface for Feature Flags."""
    
    form = FeatureFlagForm
    
    list_display = [
        'status_icon',
        'key',
        'name',
        'category',
        'enabled_badge',
        'source_info',
        'requires_restart_badge',
        'last_changed_by',
        'last_checked_display',
        'toggle_action',
    ]
    
    list_filter = [
        'category',
        'enabled',
        'is_active',
        'requires_restart',
    ]
    
    search_fields = [
        'key',
        'name',
        'description',
        'notes',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'last_checked_at',
        'current_value_display',
        'environment_value_display',
        'last_change_info',
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('key', 'name', 'category', 'enabled', 'is_active')
        }),
        ('Description', {
            'fields': ('description', 'notes')
        }),
        ('Configuration', {
            'fields': ('default_value', 'env_var_name', 'requires_restart')
        }),
        ('Current Status', {
            'fields': ('current_value_display', 'environment_value_display', 'last_change_info'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_checked_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [FeatureFlagAuditLogInline]
    
    actions = [
        'enable_flags',
        'disable_flags',
        'clear_cache_for_selected',
    ]
    
    def save_model(self, request, obj, form, change):
        """Override to create audit log when flag is changed via admin form."""
        if change:
            # Track what changed
            if 'enabled' in form.changed_data:
                old_value = FeatureFlag.objects.get(pk=obj.pk).enabled
                new_value = obj.enabled
                
                # Save the object first
                super().save_model(request, obj, form, change)
                
                # Create audit log
                FeatureFlagAuditLog.objects.create(
                    feature_flag=obj,
                    changed_by=request.user.username if request.user.is_authenticated else 'unknown',
                    change_type='enabled' if new_value else 'disabled',
                    old_value=old_value,
                    new_value=new_value,
                    notes=f'Changed via admin form. Other changes: {", ".join(form.changed_data)}'
                )
                
                messages.info(
                    request,
                    f'Audit log created for {obj.key} status change'
                )
            else:
                # No status change, just save
                super().save_model(request, obj, form, change)
                
                # Log metadata update if significant fields changed
                if any(field in form.changed_data for field in ['name', 'description', 'category', 'is_active']):
                    FeatureFlagAuditLog.objects.create(
                        feature_flag=obj,
                        changed_by=request.user.username if request.user.is_authenticated else 'unknown',
                        change_type='updated',
                        old_value=None,
                        new_value=None,
                        notes=f'Metadata updated: {", ".join(form.changed_data)}'
                    )
        else:
            # New flag being created
            super().save_model(request, obj, form, change)
            
            FeatureFlagAuditLog.objects.create(
                feature_flag=obj,
                changed_by=request.user.username if request.user.is_authenticated else 'unknown',
                change_type='created',
                old_value=None,
                new_value=obj.enabled,
                notes='Created via admin form'
            )
    
    def get_queryset(self, request):
        """Optimize queryset by prefetching audit logs."""
        queryset = super().get_queryset(request)
        return queryset.prefetch_related('audit_logs')
    
    def changelist_view(self, request, extra_context=None):
        """Override to add initialization prompt when no flags exist."""
        extra_context = extra_context or {}
        
        # Check if flags need initialization
        flag_count = FeatureFlag.objects.count()
        known_flags_count = len(feature_flags.KNOWN_FLAGS)
        
        extra_context['show_initialize_prompt'] = flag_count == 0
        extra_context['flag_count'] = flag_count
        extra_context['known_flags_count'] = known_flags_count
        extra_context['needs_sync'] = flag_count < known_flags_count
        
        return super().changelist_view(request, extra_context)
    
    def get_urls(self):
        """Add custom admin URLs."""
        urls = super().get_urls()
        custom_urls = [
            path(
                'dashboard/',
                self.admin_site.admin_view(self.flag_dashboard),
                name='featureflag_dashboard'
            ),
            path(
                '<int:flag_id>/toggle/',
                self.admin_site.admin_view(self.toggle_flag),
                name='featureflag_toggle'
            ),
            path(
                'clear-cache/',
                self.admin_site.admin_view(self.clear_all_cache),
                name='featureflag_clear_cache'
            ),
            path(
                'initialize/',
                self.admin_site.admin_view(self.initialize_flags),
                name='featureflag_initialize'
            ),
        ]
        return custom_urls + urls
    
    def status_icon(self, obj):
        """Display status icon."""
        if not obj.is_active:
            return format_html('<span style="color: gray;">⊗</span>')
        return format_html(
            '<span style="color: {};">●</span>',
            'green' if obj.enabled else 'red'
        )
    status_icon.short_description = ''
    
    def enabled_badge(self, obj):
        """Display enabled status as badge."""
        if obj.enabled:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-weight: bold;">ON</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">OFF</span>'
        )
    enabled_badge.short_description = 'Status'
    
    def requires_restart_badge(self, obj):
        """Display requires restart badge."""
        if obj.requires_restart:
            return format_html(
                '<span style="background-color: #ffc107; color: black; padding: 2px 8px; '
                'border-radius: 3px; font-size: 11px;">⚠ Restart Required</span>'
            )
        return '-'
    requires_restart_badge.short_description = 'Restart'
    
    def source_info(self, obj):
        """Display where the flag value is coming from."""
        info = feature_flags.get_flag_info(obj.key)
        if info:
            source = info.get('source', 'default')
            colors = {
                'database': '#007bff',
                'environment': '#6c757d',
                'default': '#17a2b8',
            }
            return format_html(
                '<span style="color: {}; font-size: 11px;">● {}</span>',
                colors.get(source, '#6c757d'),
                source.upper()
            )
        return '-'
    source_info.short_description = 'Source'
    
    def last_changed_by(self, obj):
        """Display who last changed this flag."""
        latest_log = obj.audit_logs.filter(
            change_type__in=['enabled', 'disabled']
        ).first()
        
        if latest_log:
            from django.utils.timesince import timesince
            time_ago = timesince(latest_log.changed_at)
            return format_html(
                '<span title="{} - {}">{}<br><small style="color: #666;">{} ago</small></span>',
                latest_log.changed_at.strftime('%Y-%m-%d %H:%M:%S'),
                latest_log.change_type,
                latest_log.changed_by,
                time_ago
            )
        return format_html('<span style="color: #999;">—</span>')
    last_changed_by.short_description = 'Last Changed By'
    
    def last_checked_display(self, obj):
        """Display last checked time in a readable format."""
        if obj.last_checked_at:
            from django.utils.timesince import timesince
            return f"{timesince(obj.last_checked_at)} ago"
        return "Never"
    last_checked_display.short_description = 'Last Checked'
    
    def toggle_action(self, obj):
        """Display toggle button."""
        url = reverse('admin:featureflag_toggle', args=[obj.id])
        action = 'Disable' if obj.enabled else 'Enable'
        color = '#dc3545' if obj.enabled else '#28a745'
        return format_html(
            '<a href="{}" style="background-color: {}; color: white; padding: 5px 10px; '
            'border-radius: 3px; text-decoration: none; font-size: 12px;">{}</a>',
            url, color, action
        )
    toggle_action.short_description = 'Quick Action'
    
    def current_value_display(self, obj):
        """Display the current effective value of the flag."""
        current = feature_flags.is_enabled(obj.key)
        return format_html(
            '<strong style="color: {};">{}</strong>',
            'green' if current else 'red',
            'Enabled' if current else 'Disabled'
        )
    current_value_display.short_description = 'Current Effective Value'
    
    def environment_value_display(self, obj):
        """Display the environment variable value if set."""
        import os
        env_value = os.getenv(obj.env_var_name or obj.key)
        if env_value:
            return format_html(
                '<code>{}</code> = <strong>{}</strong>',
                obj.env_var_name or obj.key,
                env_value
            )
        return 'Not set'
    environment_value_display.short_description = 'Environment Variable'
    
    def last_change_info(self, obj):
        """Display detailed information about the last change."""
        latest_log = obj.audit_logs.order_by('-changed_at').first()
        
        if latest_log:
            return format_html(
                '<div style="padding: 10px; background: #f8f9fa; border-left: 3px solid #007bff; border-radius: 3px;">'
                '<strong>Changed by:</strong> {}<br>'
                '<strong>Action:</strong> {}<br>'
                '<strong>When:</strong> {}<br>'
                '<strong>Old value:</strong> {}<br>'
                '<strong>New value:</strong> {}<br>'
                '{}'
                '</div>',
                latest_log.changed_by,
                latest_log.get_change_type_display(),
                latest_log.changed_at.strftime('%Y-%m-%d %H:%M:%S'),
                '🔵 ON' if latest_log.old_value else '⚪ OFF' if latest_log.old_value is not None else 'N/A',
                '🔵 ON' if latest_log.new_value else '⚪ OFF' if latest_log.new_value is not None else 'N/A',
                f'<strong>Notes:</strong> {latest_log.notes}' if latest_log.notes else ''
            )
        return format_html('<span style="color: #999;">No changes recorded yet</span>')
    last_change_info.short_description = 'Last Change Details'
    
    def toggle_flag(self, request, flag_id):
        """Toggle a feature flag."""
        flag = FeatureFlag.objects.get(pk=flag_id)
        old_value = flag.enabled
        flag.enabled = not flag.enabled
        flag.save()
        
        # Create audit log
        FeatureFlagAuditLog.objects.create(
            feature_flag=flag,
            changed_by=request.user.username if request.user.is_authenticated else 'system',
            change_type='enabled' if flag.enabled else 'disabled',
            old_value=old_value,
            new_value=flag.enabled,
            notes=f'Toggled via admin interface'
        )
        
        messages.success(
            request,
            f'Feature flag "{flag.name}" has been {"enabled" if flag.enabled else "disabled"}.'
        )
        
        if flag.requires_restart:
            messages.warning(
                request,
                f'⚠️ This flag requires a service restart to take full effect!'
            )
        
        return redirect('admin:core_featureflag_changelist')
    
    def enable_flags(self, request, queryset):
        """Enable selected flags."""
        count = 0
        for flag in queryset:
            if not flag.enabled:
                flag.enabled = True
                flag.save()
                FeatureFlagAuditLog.objects.create(
                    feature_flag=flag,
                    changed_by=request.user.username,
                    change_type='enabled',
                    old_value=False,
                    new_value=True,
                    notes='Bulk enabled via admin'
                )
                count += 1
        
        self.message_user(request, f'{count} flag(s) enabled successfully.')
    enable_flags.short_description = 'Enable selected flags'
    
    def disable_flags(self, request, queryset):
        """Disable selected flags."""
        count = 0
        for flag in queryset:
            if flag.enabled:
                flag.enabled = False
                flag.save()
                FeatureFlagAuditLog.objects.create(
                    feature_flag=flag,
                    changed_by=request.user.username,
                    change_type='disabled',
                    old_value=True,
                    new_value=False,
                    notes='Bulk disabled via admin'
                )
                count += 1
        
        self.message_user(request, f'{count} flag(s) disabled successfully.')
    disable_flags.short_description = 'Disable selected flags'
    
    def clear_cache_for_selected(self, request, queryset):
        """Clear cache for selected flags."""
        for flag in queryset:
            feature_flags.clear_cache(flag.key)
        
        self.message_user(
            request,
            f'Cache cleared for {queryset.count()} flag(s).'
        )
    clear_cache_for_selected.short_description = 'Clear cache for selected flags'
    
    def clear_all_cache(self, request):
        """Clear all feature flag caches."""
        feature_flags.clear_cache()
        messages.success(request, 'All feature flag caches have been cleared.')
        return redirect('admin:core_featureflag_changelist')
    
    def initialize_flags(self, request):
        """Initialize all known flags in the database."""
        count = feature_flags.initialize_flags_in_db()
        messages.success(
            request,
            f'Initialized {count} feature flag(s) from configuration.'
        )
        return redirect('admin:core_featureflag_changelist')
    
    def flag_dashboard(self, request):
        """Display feature flag dashboard."""
        flags_by_category = {}
        all_flags = FeatureFlag.objects.filter(is_active=True).select_related()
        
        for flag in all_flags:
            if flag.category not in flags_by_category:
                flags_by_category[flag.category] = []
            
            info = feature_flags.get_flag_info(flag.key)
            flags_by_category[flag.category].append({
                'flag': flag,
                'info': info,
            })
        
        context = {
            'title': 'Feature Flags Dashboard',
            'flags_by_category': flags_by_category,
            'total_flags': all_flags.count(),
            'enabled_flags': all_flags.filter(enabled=True).count(),
        }
        
        return render(request, 'admin/feature_flags/dashboard.html', context)


@admin.register(FeatureFlagAuditLog)
class FeatureFlagAuditLogAdmin(admin.ModelAdmin):
    """Admin interface for Feature Flag Audit Logs."""
    
    list_display = [
        'feature_flag',
        'change_type',
        'old_value',
        'new_value',
        'changed_by',
        'changed_at',
    ]
    
    list_filter = [
        'change_type',
        'changed_at',
        'feature_flag__category',
    ]
    
    search_fields = [
        'feature_flag__key',
        'feature_flag__name',
        'changed_by',
        'notes',
    ]
    
    readonly_fields = [
        'feature_flag',
        'changed_by',
        'change_type',
        'old_value',
        'new_value',
        'changed_at',
        'notes',
    ]
    
    def has_add_permission(self, request):
        """Prevent manual creation of audit logs."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of audit logs."""
        return False
