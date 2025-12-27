from django.contrib import admin
from django.contrib import messages
from django.urls import path
from django.template.response import TemplateResponse
from core.models import Backup
from core.tasks import create_backup_task, restore_backup_task
from core.services.database_stats_service import DatabaseStatsService

class BackupAdmin(admin.ModelAdmin):
    list_display = ('id', 'backup_type', 'created_at', 'status', 'size_bytes', 's3_key')
    list_filter = ('backup_type', 'status', 'created_at')
    readonly_fields = ('status', 's3_key', 'size_bytes', 'logs', 'snapshot_name', 'created_at', 'updated_at')
    actions = ['restore_backup']
    change_list_template = "admin/backup_change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('stats/', self.admin_site.admin_view(self.stats_view), name='backup_stats'),
        ]
        return my_urls + urls

    def stats_view(self, request):
        service = DatabaseStatsService()
        context = dict(
           self.admin_site.each_context(request),
           postgres_stats=service.get_postgres_stats(),
           opensearch_stats=service.get_opensearch_stats(),
           title="Database Statistics"
        )
        return TemplateResponse(request, "admin/backup_stats.html", context)

    def save_model(self, request, obj, form, change):
        if not change:  # Creating new object
            super().save_model(request, obj, form, change)
            # Trigger the backup task
            create_backup_task.delay(obj.id)
            messages.info(request, f"Backup process started for {obj.get_backup_type_display()}.")
        else:
            super().save_model(request, obj, form, change)

    @admin.action(description='Restore selected backup')
    def restore_backup(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Please select exactly one backup to restore.", messages.WARNING)
            return
        
        backup = queryset.first()
        if backup.status != Backup.Status.SUCCESS:
            self.message_user(request, "Can only restore successful backups.", messages.ERROR)
            return

        restore_backup_task.delay(backup.id)
        self.message_user(request, f"Restore process started for {backup}.", messages.SUCCESS)
