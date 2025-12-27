from celery import shared_task
from core.models import Backup
from core.services.backup_service import BackupService
from loguru import logger

@shared_task
def create_backup_task(backup_id):
    service = BackupService()
    backup = Backup.objects.get(id=backup_id)
    
    if backup.backup_type == Backup.BackupType.POSTGRES:
        service.create_postgres_backup(backup_id)
    elif backup.backup_type == Backup.BackupType.OPENSEARCH:
        service.create_opensearch_snapshot(backup_id)

@shared_task
def restore_backup_task(backup_id):
    service = BackupService()
    backup = Backup.objects.get(id=backup_id)
    
    # Update status to indicate restore is starting
    backup.logs += "Starting restore process...\n"
    backup.save()
    
    success = False
    message = ""
    
    if backup.backup_type == Backup.BackupType.POSTGRES:
        success, message = service.restore_postgres_backup(backup_id)
    elif backup.backup_type == Backup.BackupType.OPENSEARCH:
        success, message = service.restore_opensearch_snapshot(backup_id)
        
    backup.logs += f"Restore finished. Success: {success}. Message: {message}\n"
    backup.save()
