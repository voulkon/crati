"""
Management command to monitor and control the Import Job Queue

Usage:
    # View queue status
    python manage.py import_queue status
    
    # Clear stale jobs (stuck for >24 hours)
    python manage.py import_queue clear-stale
    
    # Manually dispatch next pending job
    python manage.py import_queue dispatch-next
    
    # Set max concurrent jobs (runtime override)
    python manage.py import_queue set-limit 2
"""
from django.core.management.base import BaseCommand
from core.services.import_job_queue import ImportJobQueue
from core.models.import_jobs import ImportJob, ImportJobStatus
from django.utils import timezone
from datetime import timedelta
import json


class Command(BaseCommand):
    help = "Monitor and control the Import Job Queue"

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            type=str,
            choices=['status', 'clear-stale', 'dispatch-next', 'set-limit'],
            help='Action to perform'
        )
        parser.add_argument(
            '--max-age-hours',
            type=int,
            default=24,
            help='Max age in hours for stale jobs (default: 24)'
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='New max concurrent jobs limit (for set-limit action)'
        )

    def handle(self, *args, **options):
        action = options['action']
        queue = ImportJobQueue()
        
        if action == 'status':
            self.show_status(queue)
        
        elif action == 'clear-stale':
            self.clear_stale(queue, options['max_age_hours'])
        
        elif action == 'dispatch-next':
            self.dispatch_next(queue)
        
        elif action == 'set-limit':
            if not options['limit']:
                self.stdout.write(
                    self.style.ERROR("Error: --limit is required for set-limit action")
                )
                return
            self.set_limit(options['limit'])

    def show_status(self, queue: ImportJobQueue):
        """Display current queue status"""
        status = queue.get_queue_status()
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write("Import Job Queue Status")
        self.stdout.write("="*60)
        
        self.stdout.write(f"\nMax Concurrent Jobs: {status['max_concurrent']}")
        self.stdout.write(f"Active Jobs: {status['active_count']}")
        self.stdout.write(f"Pending Jobs: {status['pending_count']}")
        self.stdout.write(f"Can Start New: {status['can_start_new']}")
        
        if status['active_jobs']:
            self.stdout.write("\n" + "-"*60)
            self.stdout.write("Active Jobs:")
            self.stdout.write("-"*60)
            for job in status['active_jobs']:
                self.stdout.write(
                    f"  #{job['id']} | {job['start_date']} | {job['status']} | "
                    f"Created: {job['created_at']}"
                )
        
        if status['pending_jobs']:
            self.stdout.write("\n" + "-"*60)
            self.stdout.write("Pending Jobs (Queue):")
            self.stdout.write("-"*60)
            for job in status['pending_jobs']:
                self.stdout.write(
                    f"  #{job['id']} | {job['start_date']} | "
                    f"Created: {job['created_at']}"
                )
        
        # Show recent completed jobs
        recent_completed = ImportJob.objects.filter(
            status__in=[ImportJobStatus.COMPLETED, ImportJobStatus.PARTIALLY_COMPLETED, ImportJobStatus.FAILED]
        ).order_by('-completed_at')[:5]
        
        if recent_completed:
            self.stdout.write("\n" + "-"*60)
            self.stdout.write("Recent Completed Jobs:")
            self.stdout.write("-"*60)
            for job in recent_completed:
                self.stdout.write(
                    f"  #{job.id} | {job.start_date} | {job.status} | "
                    f"Decisions: {job.total_decisions} | "
                    f"Completed: {job.completed_at}"
                )
        
        self.stdout.write("\n" + "="*60 + "\n")

    def clear_stale(self, queue: ImportJobQueue, max_age_hours: int):
        """Clear stale jobs that are stuck"""
        self.stdout.write(f"\nClearing jobs stuck for >{max_age_hours} hours...")
        
        count = queue.clear_stale_jobs(max_age_hours)
        
        if count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"\n✓ Marked {count} stale jobs as failed")
            )
        else:
            self.stdout.write("\n✓ No stale jobs found")
        
        # Try to dispatch next job after clearing
        dispatched = queue.dispatch_next_job()
        if dispatched:
            self.stdout.write(
                self.style.SUCCESS(f"\n✓ Auto-dispatched next job #{dispatched.id}")
            )

    def dispatch_next(self, queue: ImportJobQueue):
        """Manually dispatch next pending job"""
        self.stdout.write("\nDispatching next pending job...")
        
        job = queue.dispatch_next_job()
        
        if job:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Dispatched Job #{job.id} for {job.start_date}\n"
                    f"  Task ID: {job.celery_task_id}"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING("\n⚠ No job dispatched (at capacity or no pending jobs)")
            )

    def set_limit(self, limit: int):
        """Set max concurrent jobs (runtime override)"""
        from django.conf import settings
        
        old_limit = settings.IMPORT_MAX_CONCURRENT_JOBS
        settings.IMPORT_MAX_CONCURRENT_JOBS = limit
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Updated max concurrent jobs: {old_limit} → {limit}\n"
                f"  Note: This is a runtime override. Set IMPORT_MAX_CONCURRENT_JOBS "
                f"environment variable for persistent change."
            )
        )
