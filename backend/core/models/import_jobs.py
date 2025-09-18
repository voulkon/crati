from django.db import models
from django.conf import settings
from core.models.organizations import Organization, Signer, Unit
from django.utils.translation import gettext_lazy as _

class ImportJobStatus(models.TextChoices):
    PENDING = 'pending', _('Pending')
    RUNNING = 'running', _('Running')
    COMPLETED = 'completed', _('Completed')
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