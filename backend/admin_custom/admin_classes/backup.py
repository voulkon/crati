from django.contrib import admin
from django.contrib import messages
from django.urls import path
from django.template.response import TemplateResponse
from django.shortcuts import redirect
from django.utils.html import format_html
from core.models import Backup
from core.tasks import create_backup_task, restore_backup_task
from core.services.database_stats_service import DatabaseStatsService

class BackupAdmin(admin.ModelAdmin):
    list_display = ('id', 'backup_type', 'created_at', 'status_badge', 'size_display', 's3_location')
    list_filter = ('backup_type', 'status', 'created_at')
    readonly_fields = ('status', 's3_key', 'size_bytes', 'logs_display', 'snapshot_name', 'created_at', 'updated_at', 's3_full_path')
    actions = ['restore_backup']
    change_list_template = "admin/backup_change_list.html"
    
    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'in_progress': '#2196F3',
            'success': '#4CAF50',
            'failed': '#f44336'
        }
        color = colors.get(obj.status, '#999')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def size_display(self, obj):
        if not obj.size_bytes:
            return '-'
        # Convert to human readable
        size = obj.size_bytes
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
    size_display.short_description = 'Size'
    
    def s3_location(self, obj):
        if obj.backup_type == Backup.BackupType.POSTGRES and obj.s3_key:
            return format_html('<code style="font-size: 11px;">{}</code>', obj.s3_key.split('/')[-1])
        elif obj.backup_type == Backup.BackupType.OPENSEARCH and obj.snapshot_name:
            return format_html('<code style="font-size: 11px;">{}</code>', obj.snapshot_name)
        return '-'
    s3_location.short_description = 'S3/Snapshot Name'
    
    def s3_full_path(self, obj):
        from django.conf import settings
        bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'diavgeia-backups')
        if obj.backup_type == Backup.BackupType.POSTGRES and obj.s3_key:
            return format_html(
                's3://{}/{}<br><small style="color: #666;">Full S3 URI</small>',
                bucket, obj.s3_key
            )
        elif obj.backup_type == Backup.BackupType.OPENSEARCH and obj.snapshot_name:
            return format_html(
                's3://{}/backups/opensearch/{}<br><small style="color: #666;">Snapshot stored in S3-backed repository</small>',
                bucket, obj.snapshot_name
            )
        return 'Not yet uploaded'
    s3_full_path.short_description = 'Full S3 Path'
    
    def logs_display(self, obj):
        if not obj.logs:
            return format_html('<em style="color: #999;">No logs yet</em>')
        return format_html(
            '<pre style="background: #f5f5f5; padding: 10px; border-radius: 4px; max-height: 400px; overflow-y: auto; font-size: 12px;">{}</pre>',
            obj.logs
        )
    logs_display.short_description = 'Logs'

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('stats/', self.admin_site.admin_view(self.stats_view), name='backup_stats'),
            path('trigger-postgres/', self.admin_site.admin_view(self.trigger_postgres_backup), name='trigger_postgres_backup'),
            path('trigger-opensearch/', self.admin_site.admin_view(self.trigger_opensearch_backup), name='trigger_opensearch_backup'),
            path('browse-s3/', self.admin_site.admin_view(self.browse_s3), name='browse_s3'),
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

    def trigger_postgres_backup(self, request):
        backup = Backup.objects.create(
            backup_type=Backup.BackupType.POSTGRES,
            status=Backup.Status.PENDING
        )
        create_backup_task.delay(backup.id)
        self.message_user(request, f"PostgreSQL backup #{backup.id} started. Monitor progress in the backup list.", messages.SUCCESS)
        return redirect('admin:core_backup_changelist')
    
    def trigger_opensearch_backup(self, request):
        backup = Backup.objects.create(
            backup_type=Backup.BackupType.OPENSEARCH,
            status=Backup.Status.PENDING
        )
        create_backup_task.delay(backup.id)
        self.message_user(request, f"OpenSearch backup #{backup.id} started. Monitor progress in the backup list.", messages.SUCCESS)
        return redirect('admin:core_backup_changelist')
    
    def browse_s3(self, request):
        """Browse S3 backups"""
        from django.conf import settings
        import boto3
        from botocore.exceptions import ClientError
        
        # Get bucket name with proper None handling
        bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)
        
        # Check if AWS credentials are configured
        aws_access_key = getattr(settings, 'AWS_ACCESS_KEY_ID', None)
        aws_secret_key = getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
        
        if not aws_access_key or not aws_secret_key:
            context = dict(
                self.admin_site.each_context(request),
                s3_files={'postgres': [], 'opensearch': []},
                bucket_name=bucket_name,
                errors=['AWS credentials not configured. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in settings.'],
                title="Browse S3 Backups"
            )
            return TemplateResponse(request, "admin/browse_s3.html", context)
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=settings.AWS_S3_REGION_NAME
        )
        
        s3_files = {'postgres': [], 'opensearch': []}
        errors = []
        
        try:
            # List PostgreSQL backups
            response = s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix='backups/postgres/'
            )
            if 'Contents' in response:
                for obj in response['Contents']:
                    if obj['Key'].endswith('.dump'):
                        s3_files['postgres'].append({
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'],
                            'filename': obj['Key'].split('/')[-1]
                        })
        except ClientError as e:
            errors.append(f"Error listing PostgreSQL backups: {str(e)}")
        
        try:
            # List OpenSearch snapshots by parsing S3 metadata files
            # Each snapshot has a snap-{uuid}.dat file in backups/opensearch/
            response = s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix='backups/opensearch/'
            )
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    # Look for snap-*.dat files which contain snapshot metadata
                    if obj['Key'].startswith('backups/opensearch/snap-') and obj['Key'].endswith('.dat'):
                        # Extract UUID from filename: snap-{uuid}.dat
                        snapshot_uuid = obj['Key'].split('snap-')[1].replace('.dat', '')
                        
                        # Try to get more details by reading the metadata file
                        try:
                            meta_response = s3_client.get_object(Bucket=bucket_name, Key=obj['Key'])
                            # The file is binary, but we can at least show it exists
                            s3_files['opensearch'].append({
                                'snapshot_uuid': snapshot_uuid,
                                'snapshot_name': f'snapshot-{snapshot_uuid[:8]}',  # Shortened for display
                                'state': 'AVAILABLE',
                                'last_modified': obj['LastModified'],
                                'size': obj['Size'],
                                's3_key': obj['Key']
                            })
                        except Exception as detail_error:
                            # Even if we can't read details, show the snapshot exists
                            s3_files['opensearch'].append({
                                'snapshot_uuid': snapshot_uuid,
                                'snapshot_name': f'snapshot-{snapshot_uuid[:8]}',
                                'state': 'AVAILABLE',
                                'last_modified': obj['LastModified'],
                                'size': obj['Size'],
                                's3_key': obj['Key']
                            })
                
                # Also try to read index.latest to get the current snapshot name
                try:
                    index_response = s3_client.get_object(Bucket=bucket_name, Key='backups/opensearch/index.latest')
                    latest_index = index_response['Body'].read().decode('utf-8').strip()
                    errors.append(f"Latest snapshot index: {latest_index}")
                except Exception:
                    pass
                    
        except ClientError as e:
            errors.append(f"Error listing OpenSearch backups: {str(e)}")
        
        context = dict(
            self.admin_site.each_context(request),
            s3_files=s3_files,
            bucket_name=bucket_name,
            errors=errors,
            title="Browse S3 Backups"
        )
        return TemplateResponse(request, "admin/browse_s3.html", context)

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
