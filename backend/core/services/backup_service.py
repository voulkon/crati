import os
import subprocess
import boto3
from django.conf import settings
from django.utils import timezone
from core.models import Backup
from core.services.opensearch_service import OpenSearchService
from loguru import logger

class BackupService:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'eu-north-1')
        )
        self.bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'diavgeia-backups')
        self.opensearch_service = OpenSearchService()

    def create_postgres_backup(self, backup_id):
        backup = Backup.objects.get(id=backup_id)
        backup.status = Backup.Status.IN_PROGRESS
        backup.save()

        local_path = None
        try:
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            filename = f"postgres_backup_{timestamp}.dump"
            local_path = f"/tmp/{filename}"
            s3_key = f"backups/postgres/{filename}"

            # PG Dump
            # Using custom format (-Fc) which is compressed and allows selective restore
            db_settings = settings.DATABASES['default']
            env = os.environ.copy()
            env['PGPASSWORD'] = db_settings['PASSWORD']
            
            cmd = [
                'pg_dump',
                '-h', db_settings['HOST'],
                '-p', str(db_settings['PORT']),
                '-U', db_settings['USER'],
                '-d', db_settings['NAME'],
                '-F', 'c', # Custom format
                '-f', local_path
            ]
            
            logger.info(f"Starting pg_dump to {local_path}")
            backup.logs += f"Starting pg_dump to {local_path}\n"
            backup.save()
            
            subprocess.run(cmd, env=env, check=True)

            # Upload to S3
            logger.info(f"Uploading to S3: {s3_key}")
            backup.logs += f"Uploading to S3: {s3_key}\n"
            backup.save()
            
            self.s3_client.upload_file(local_path, self.bucket_name, s3_key)
            
            # Update backup record
            backup.s3_key = s3_key
            backup.size_bytes = os.path.getsize(local_path)
            backup.status = Backup.Status.SUCCESS
            backup.logs += f"Backup successful. Size: {backup.size_bytes} bytes.\n"
            backup.save()

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            backup.status = Backup.Status.FAILED
            backup.logs += f"Error: {str(e)}\n"
            backup.save()
        finally:
            if local_path and os.path.exists(local_path):
                os.remove(local_path)

    def restore_postgres_backup(self, backup_id):
        backup = Backup.objects.get(id=backup_id)
        # We don't change status to IN_PROGRESS here immediately because this might be called from a task
        # But let's assume the caller handles the initial status update or we do it here.
        
        local_path = None
        try:
            filename = os.path.basename(backup.s3_key)
            local_path = f"/tmp/{filename}"
            
            logger.info(f"Downloading from S3: {backup.s3_key}")
            self.s3_client.download_file(self.bucket_name, backup.s3_key, local_path)
            
            db_settings = settings.DATABASES['default']
            env = os.environ.copy()
            env['PGPASSWORD'] = db_settings['PASSWORD']
            
            # PG Restore
            # --clean: clean (drop) database objects before recreating them
            # --if-exists: used with --clean
            # --no-owner: do not output commands to set ownership of objects to match the original database
            # --no-privileges: do not output commands to grant access privileges
            cmd = [
                'pg_restore',
                '-h', db_settings['HOST'],
                '-p', str(db_settings['PORT']),
                '-U', db_settings['USER'],
                '-d', db_settings['NAME'],
                '--clean',
                '--if-exists',
                '--no-owner',
                '--no-privileges',
                local_path
            ]
            
            logger.info(f"Starting pg_restore from {local_path}")
            subprocess.run(cmd, env=env, check=True)
            
            logger.info("Restore successful")
            return True, "Restore successful"

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False, str(e)
        finally:
            if local_path and os.path.exists(local_path):
                os.remove(local_path)

    def create_opensearch_snapshot(self, backup_id):
        backup = Backup.objects.get(id=backup_id)
        backup.status = Backup.Status.IN_PROGRESS
        backup.save()
        
        try:
            timestamp = timezone.now().strftime('%Y%m%d-%H%M%S')
            snapshot_name = f"snapshot-{timestamp}"
            
            # Ensure repository is registered
            # We assume 's3-backup-repo' is the name we want to use
            repo_name = "s3-backup-repo"
            self.opensearch_service.register_s3_repository(
                repository_name=repo_name,
                bucket_name=self.bucket_name,
                base_path="backups/opensearch"
            )
            
            self.opensearch_service.create_snapshot(
                repository_name=repo_name,
                snapshot_name=snapshot_name
            )
            
            backup.snapshot_name = snapshot_name
            backup.status = Backup.Status.SUCCESS
            backup.logs += f"Snapshot {snapshot_name} created successfully.\n"
            backup.save()
            
        except Exception as e:
            logger.error(f"OpenSearch snapshot failed: {e}")
            backup.status = Backup.Status.FAILED
            backup.logs += f"Error: {str(e)}\n"
            backup.save()

    def restore_opensearch_snapshot(self, backup_id):
        backup = Backup.objects.get(id=backup_id)
        
        try:
            repo_name = "s3-backup-repo"
            # Ensure repo is registered (idempotent usually)
            self.opensearch_service.register_s3_repository(
                repository_name=repo_name,
                bucket_name=self.bucket_name,
                base_path="backups/opensearch"
            )
            
            self.opensearch_service.restore_snapshot(
                repository_name=repo_name,
                snapshot_name=backup.snapshot_name
            )
            return True, "Restore started successfully"
        except Exception as e:
            return False, str(e)
