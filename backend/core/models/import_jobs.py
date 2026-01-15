from django.db import models
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone
from core.models.organizations import Organization, Signer, Unit
from django.utils.translation import gettext_lazy as _

class ImportJobStatus(models.TextChoices):
    PENDING = 'pending', _('Pending')
    RUNNING = 'running', _('Running')
    FETCHING = 'fetching', _('Fetching from API')
    SPLITTING = 'splitting', _('Splitting into chunks')
    PROCESSING = 'processing', _('Processing chunks')
    COMPLETED = 'completed', _('Completed')
    PARTIALLY_COMPLETED = 'partially_completed', _('Partially Completed')
    FAILED = 'failed', _('Failed')

class ImportJob(models.Model):
    """Tracks a decision import operation"""
    
    # Date range for the import
    start_date = models.DateField(_("Start Date"))
    end_date = models.DateField(_("End Date"))
    
    # Filters
    organization = models.ForeignKey(Organization, 
                                    on_delete=models.SET_NULL, 
                                    null=True, blank=True,
                                    verbose_name=_("Organization"))
    unit = models.ForeignKey(Unit, 
                            on_delete=models.SET_NULL, 
                            null=True, blank=True,
                            verbose_name=_("Unit"))
    signer = models.ForeignKey(Signer, 
                              on_delete=models.SET_NULL, 
                              null=True, blank=True,
                              verbose_name=_("Signer"))
    
    # Job info
    status = models.CharField(max_length=20, 
                             choices=ImportJobStatus.choices,
                             default=ImportJobStatus.PENDING)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, 
                                  on_delete=models.SET_NULL, 
                                  null=True,
                                  verbose_name=_("Created By"))
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Results
    total_decisions = models.IntegerField(default=0, 
                                         verbose_name=_("Total Decisions"))
    new_decisions = models.IntegerField(default=0,
                                      verbose_name=_("New Decisions"))
    updated_decisions = models.IntegerField(default=0,
                                          verbose_name=_("Updated Decisions"))
    error_count = models.IntegerField(default=0,
                                     verbose_name=_("Errors"))
    error_details = models.TextField(blank=True, null=True,
                                    verbose_name=_("Error Details"))
    
    # Task metadata
    celery_task_id = models.CharField(max_length=50, blank=True, null=True)
    
    # 🆕 Chunked import tracking (for Redis-based distributed imports)
    total_chunks = models.IntegerField(default=0, 
                                      verbose_name=_("Total Chunks"),
                                      help_text=_("Number of Redis chunks created"))
    chunks_completed = models.IntegerField(default=0,
                                          verbose_name=_("Chunks Completed"))
    chunks_failed = models.IntegerField(default=0,
                                       verbose_name=_("Chunks Failed"))
    chunk_task_ids = ArrayField(
        models.CharField(max_length=255),
        default=list,
        blank=True,
        verbose_name=_("Chunk Task IDs"),
        help_text=_("Celery task IDs for chunk processing")
    )
    search_params = models.JSONField(
        null=True, blank=True,
        verbose_name=_("Search Parameters"),
        help_text=_("API search parameters used")
    )
    
    class Meta:
        verbose_name = _("Import Job")
        verbose_name_plural = _("Import Jobs")
        ordering = ['-created_at']
    
    def __str__(self):
        if self.organization:
            entity = f"Organization: {self.organization.label}"
        elif self.unit:
            entity = f"Unit: {self.unit.label}"
        elif self.signer:
            entity = f"Signer: {self.signer.label}"
        else:
            entity = "All"
        
        return f"Import {self.start_date} - {self.end_date} ({entity})"
    
    @property
    def progress_percentage(self) -> float:
        """Calculate completion percentage based on chunks"""
        if self.total_chunks == 0:
            return 0.0
        completed = self.chunks_completed + self.chunks_failed
        return (completed / self.total_chunks) * 100
    
    @property
    def is_complete(self) -> bool:
        """Check if all chunks have been processed"""
        if self.total_chunks == 0:
            return False
        return (self.chunks_completed + self.chunks_failed) >= self.total_chunks
    
    def mark_chunk_completed(self, decisions_count: int = 0):
        """Atomically increment completed chunk counter"""
        from django.db.models import F
        ImportJob.objects.filter(pk=self.pk).update(
            chunks_completed=F('chunks_completed') + 1,
            new_decisions=F('new_decisions') + decisions_count,
        )
        self.refresh_from_db()
        
        # Auto-complete if all chunks done
        if self.is_complete and self.status == ImportJobStatus.PROCESSING:
            if self.chunks_failed == 0:
                self.status = ImportJobStatus.COMPLETED
            else:
                self.status = ImportJobStatus.PARTIALLY_COMPLETED
            self.completed_at = timezone.now()
            self.save(update_fields=['status', 'completed_at'])
    
    def mark_chunk_failed(self, error_msg: str = None, decisions_count: int = 0):
        """Atomically increment failed chunk counter"""
        from django.db.models import F
        ImportJob.objects.filter(pk=self.pk).update(
            chunks_failed=F('chunks_failed') + 1,
            error_count=F('error_count') + decisions_count,
        )
        self.refresh_from_db()
        
        # Store error details
        if error_msg:
            if not self.error_details:
                self.error_details = ""
            self.error_details += f"\n[{timezone.now().isoformat()}] {error_msg}"
            self.save(update_fields=['error_details'])
        
        # Auto-complete/fail if all chunks done
        if self.is_complete and self.status == ImportJobStatus.PROCESSING:
            if self.chunks_completed == 0:
                self.status = ImportJobStatus.FAILED
            else:
                self.status = ImportJobStatus.PARTIALLY_COMPLETED
            self.completed_at = timezone.now()
            self.save(update_fields=['status', 'completed_at'])

class DateCoverage(models.Model):
    """Tracks which dates have decisions in the database"""
    date = models.DateField(db_index=True)
    organization = models.ForeignKey(Organization, 
                                    on_delete=models.CASCADE, 
                                    null=True, blank=True)
    unit = models.ForeignKey(Unit, 
                            on_delete=models.CASCADE, 
                            null=True, blank=True)
    signer = models.ForeignKey(Signer, 
                              on_delete=models.CASCADE,
                              null=True, blank=True)
    decision_count = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [
            ['date', 'organization', 'unit', 'signer']
        ]
        verbose_name = _("Date Coverage")
        verbose_name_plural = _("Date Coverage")