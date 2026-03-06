from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class NotificationSubscription(models.Model):
    """
    User subscription for notifications about decisions.
    
    Supports multiple subscription types:
    - organization: Watch all decisions from a specific organization
    - entity: Watch decisions involving a specific AFM entity
    - relationship: Watch decisions involving a specific org-entity relationship
    - person: Watch decisions involving companies where a person is associated
    - signer: Watch decisions signed by a specific person
    - filter: Watch decisions matching filter criteria only (no specific target)
    """
    
    user = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='notification_subscriptions',
        verbose_name=_("User")
    )
    
    # Target fields (what to watch)
    organization = models.ForeignKey(
        'core.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subscriptions',
        verbose_name=_("Organization")
    )
    
    entity = models.ForeignKey(
        'core.AFMEntity',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subscriptions',
        verbose_name=_("AFM Entity")
    )
    
    relationship_org = models.ForeignKey(
        'core.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='relationship_subscriptions',
        verbose_name=_("Relationship Organization")
    )
    
    relationship_entity = models.ForeignKey(
        'core.AFMEntity',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='relationship_subscriptions',
        verbose_name=_("Relationship Entity")
    )
    
    person_name = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text=_("Watch companies where this person is associated (director, representative, etc.)")
    )
    
    signer_name = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text=_("Watch decisions signed by this person")
    )
    
    # User-defined alias for the subscription
    alias = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        verbose_name=_("Alias"),
        help_text=_("Optional custom name for this subscription")
    )
    
    # Filter fields (optional criteria)
    keywords = models.JSONField(
        null=True,
        blank=True,
        help_text=_("List of keywords to match in decision subject/content")
    )
    
    amount_min = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Minimum amount filter")
    )
    
    amount_max = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Maximum amount filter")
    )
    
    decision_types = models.JSONField(
        null=True,
        blank=True,
        help_text=_("List of decision type codes to filter by")
    )
    
    # Status and metadata
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    
    CHECK_FREQUENCY_CHOICES = [
        ('daily', _('Daily')),
        ('weekly', _('Weekly')),
        ('manual', _('Manual only')),
    ]
    
    check_frequency = models.CharField(
        max_length=20,
        choices=CHECK_FREQUENCY_CHOICES,
        default='daily',
        verbose_name=_("Check frequency"),
        help_text=_("How often to automatically check for new matching decisions")
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))
    last_checked = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last checked"),
        help_text=_("When this subscription was last checked for new decisions")
    )
    
    @property
    def subscription_type(self):
        """
        Returns the type of subscription based on which target field is set.
        Returns 'filter' if no target is set (filter-only subscription).
        """
        if self.organization_id is not None:
            return "organization"
        elif self.entity_id is not None:
            return "entity"
        elif self.relationship_org_id is not None and self.relationship_entity_id is not None:
            return "relationship"
        elif self.person_name:
            return "person"
        elif self.signer_name:
            return "signer"
        else:
            return "filter"
    
    def clean(self):
        """
        Validate that at least one target OR at least one filter is set.
        """
        has_target = any([
            self.organization_id is not None,
            self.entity_id is not None,
            self.relationship_org_id is not None and self.relationship_entity_id is not None,
            self.person_name,
            self.signer_name
        ])
        
        has_filter = any([
            self.keywords,
            self.amount_min is not None,
            self.amount_max is not None,
            self.decision_types
        ])
        
        if not has_target and not has_filter:
            raise ValidationError(
                _("At least one target (organization, entity, relationship, person, or signer) "
                  "OR at least one filter (keywords, amounts, decision types) must be set.")
            )
        
        # Validate relationship subscription has both org and entity
        if self.relationship_org_id is not None and self.relationship_entity_id is None:
            raise ValidationError(
                _("Relationship subscription requires both organization and entity.")
            )
        if self.relationship_entity_id is not None and self.relationship_org_id is None:
            raise ValidationError(
                _("Relationship subscription requires both organization and entity.")
            )
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = _("Notification Subscription")
        verbose_name_plural = _("Notification Subscriptions")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['last_checked']),
            models.Index(fields=['person_name']),
            models.Index(fields=['signer_name']),
        ]
        constraints = [
            # Prevent duplicate organization subscriptions
            models.UniqueConstraint(
                fields=['user', 'organization'],
                condition=models.Q(organization__isnull=False),
                name='unique_user_organization'
            ),
            # Prevent duplicate entity subscriptions
            models.UniqueConstraint(
                fields=['user', 'entity'],
                condition=models.Q(entity__isnull=False),
                name='unique_user_entity'
            ),
            # Prevent duplicate relationship subscriptions
            models.UniqueConstraint(
                fields=['user', 'relationship_org', 'relationship_entity'],
                condition=models.Q(relationship_org__isnull=False, relationship_entity__isnull=False),
                name='unique_user_relationship'
            ),
            # Prevent duplicate person subscriptions
            models.UniqueConstraint(
                fields=['user', 'person_name'],
                condition=models.Q(person_name__isnull=False),
                name='unique_user_person'
            ),
            # Prevent duplicate signer subscriptions
            models.UniqueConstraint(
                fields=['user', 'signer_name'],
                condition=models.Q(signer_name__isnull=False),
                name='unique_user_signer'
            ),
        ]
    
    def __str__(self):
        # Use alias if provided
        if self.alias:
            return f"{self.user.username} → {self.alias}"
        
        # Otherwise, use descriptive label based on subscription type
        type_label = self.subscription_type
        if type_label == "organization":
            return f"{self.user.username} → Org: {self.organization.label if self.organization else 'N/A'}"
        elif type_label == "entity":
            return f"{self.user.username} → Entity: {self.entity.afm if self.entity else 'N/A'}"
        elif type_label == "relationship":
            return f"{self.user.username} → Relationship: {self.relationship_org.label if self.relationship_org else 'N/A'} ↔ {self.relationship_entity.afm if self.relationship_entity else 'N/A'}"
        elif type_label == "person":
            return f"{self.user.username} → Person: {self.person_name}"
        elif type_label == "signer":
            return f"{self.user.username} → Signer: {self.signer_name}"
        else:
            return f"{self.user.username} → Filter subscription"