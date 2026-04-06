"""
Service for classifying decisions as direct assignments (ΑΠΕΥΘΕΙΑΣ ΑΝΑΘΕΣΕΙΣ).

This service encapsulates the classification algorithm that determines whether
a decision qualifies as a direct assignment based on:
1. Decision type (Δ.1)
2. Amount below threshold (€37,200)
3. Other future criteria

Results are stored in DecisionClassification model for fast querying.
The pipeline orchestrator calls this service during Stage 8.
"""

from decimal import Decimal
from typing import Dict, Optional
from loguru import logger
from django.db.models import QuerySet, Q

from core.models.decisions import Decision
from core.models.decision_classification import DecisionClassification
from core.services.financial_calculation_service import financial_service


class DirectAssignmentDetectionService:
    """
    Classifies decisions as direct assignments and stores results.
    
    Business Rules:
    1. Must be decision type Δ.1 (direct assignment type)
    2. Total amount must be below €37,200 threshold
    3. Must have a valid amount
    
    Uses FinancialCalculationService for accurate amount calculations.
    Some examples:
    9ΔΩΗΩ16-Β2Α
    Ρ5ΟΓΩΕ6-Ι41
    6ΜΚ4ΟΚ91-32Χ
    ΨΠ9446ΨΧΥΙ-ΕΛ3
    Ρ9Ψ4Ω6Ι-ΤΘ8
    62ΡΑΟΡΝ0-0Ξ9
    """
    
    # Constants
    DIRECT_ASSIGNMENT_TYPE_UID = "Δ.1"
    STANDARD_THRESHOLD = Decimal("37200.00")  # €30,000 + 24% VAT
    CLASSIFIER_VERSION = "v1.0"
    
    def __init__(self):
        """Initialize service with financial calculation dependency."""
        self.financial_service = financial_service
    
    # =============================================================================
    # CORE CLASSIFICATION LOGIC
    # =============================================================================
    
    def classify_decision(self, decision: Decision) -> Dict[str, any]:
        """
        Apply classification algorithm to determine if decision is a direct assignment.
        
        This method performs the classification WITHOUT saving to database.
        Use classify_and_save() to persist results.
        
        Args:
            decision: Decision object to classify
        
        Returns:
            Dictionary with classification results:
            - is_direct_assignment: bool
            - confidence: float (0.0 to 1.0)
            - reason: str (explanation)
            - amount: Decimal (amount used for classification)
        """
        # Rule 1: Must be type Δ.1
        if not decision.decision_type:
            return {
                'is_direct_assignment': False,
                'confidence': 1.0,
                'reason': 'No decision type',
                'amount': None
            }
        
        if decision.decision_type.uid != self.DIRECT_ASSIGNMENT_TYPE_UID:
            return {
                'is_direct_assignment': False,
                'confidence': 1.0,
                'reason': f'Not Δ.1 type (found: {decision.decision_type.uid})',
                'amount': decision.amount
            }
        
        # Rule 2: Must have amount
        # Use FinancialCalculationService for accurate amount calculation
        breakdown = self.financial_service.get_decision_amount_breakdown(decision)
        total_amount = breakdown['total_amount']
        
        if total_amount is None or total_amount <= 0:
            return {
                'is_direct_assignment': False,
                'confidence': 0.5,  # Low confidence - it's Δ.1 but no amount
                'reason': 'No valid amount found',
                'amount': None
            }
        
        # Rule 3: Amount must be below threshold
        if total_amount >= self.STANDARD_THRESHOLD:
            return {
                'is_direct_assignment': False,
                'confidence': 1.0,
                'reason': f'Amount €{total_amount} >= threshold €{self.STANDARD_THRESHOLD}',
                'amount': total_amount
            }
        
        # All rules passed - this IS a direct assignment
        return {
            'is_direct_assignment': True,
            'confidence': 1.0,
            'reason': f'Δ.1 type with amount €{total_amount} < €{self.STANDARD_THRESHOLD}',
            'amount': total_amount
        }
    
    def classify_and_save(self, decision: Decision) -> DecisionClassification:
        """
        Classify decision and save results to DecisionClassification table.
        
        This method is called by the pipeline orchestrator (Stage 8).
        Uses update_or_create for idempotency.
        
        Args:
            decision: Decision to classify
        
        Returns:
            DecisionClassification object (created or updated)
        """
        result = self.classify_decision(decision)
        
        classification, created = DecisionClassification.objects.update_or_create(
            decision=decision,
            defaults={
                'is_direct_assignment': result['is_direct_assignment'],
                'classifier_version': self.CLASSIFIER_VERSION
            }
        )
        
        action = "Created" if created else "Updated"
        logger.debug(
            f"{action} classification for {decision.ada}: "
            f"is_direct_assignment={result['is_direct_assignment']} "
            f"({result['reason']})"
        )
        
        return classification
    
    # =============================================================================
    # BULK CLASSIFICATION
    # =============================================================================
    
    def bulk_classify(
        self,
        decisions: QuerySet,
        batch_size: int = 1000
    ) -> Dict[str, int]:
        """
        Efficiently classify multiple decisions in bulk.
        
        Used by:
        - Management command for backfilling existing decisions
        - Scheduled task for catching unclassified decisions
        
        Args:
            decisions: QuerySet of Decision objects to classify
            batch_size: Number of decisions to process per batch
        
        Returns:
            Statistics dictionary with counts
        """
        stats = {
            'total_processed': 0,
            'direct_assignments': 0,
            'non_direct_assignments': 0,
            'created': 0,
            'updated': 0,
            'errors': 0
        }
        
        classifications_to_create = []
        classifications_to_update = []
        
        # Get existing classifications to determine create vs update
        existing_classifications = {
            c.decision_id: c
            for c in DecisionClassification.objects.filter(
                decision__in=decisions
            ).select_related('decision')
        }
        
        logger.info(f"Starting bulk classification of {decisions.count()} decisions")
        
        for decision in decisions.select_related('decision_type').iterator(chunk_size=batch_size):
            try:
                result = self.classify_decision(decision)
                stats['total_processed'] += 1
                
                if result['is_direct_assignment']:
                    stats['direct_assignments'] += 1
                else:
                    stats['non_direct_assignments'] += 1
                
                # Check if classification exists
                if decision.id in existing_classifications:
                    # Update existing
                    existing = existing_classifications[decision.id]
                    existing.is_direct_assignment = result['is_direct_assignment']
                    existing.classifier_version = self.CLASSIFIER_VERSION
                    classifications_to_update.append(existing)
                    stats['updated'] += 1
                else:
                    # Create new
                    classifications_to_create.append(
                        DecisionClassification(
                            decision=decision,
                            is_direct_assignment=result['is_direct_assignment'],
                            classifier_version=self.CLASSIFIER_VERSION
                        )
                    )
                    stats['created'] += 1
                
                # Batch save when reaching batch_size
                if len(classifications_to_create) >= batch_size:
                    DecisionClassification.objects.bulk_create(
                        classifications_to_create,
                        batch_size=batch_size,
                        ignore_conflicts=True
                    )
                    classifications_to_create = []
                
                if len(classifications_to_update) >= batch_size:
                    DecisionClassification.objects.bulk_update(
                        classifications_to_update,
                        ['is_direct_assignment', 'classifier_version', 'classified_at'],
                        batch_size=batch_size
                    )
                    classifications_to_update = []
                    
            except Exception as e:
                logger.error(f"Error classifying decision {decision.ada}: {e}")
                stats['errors'] += 1
                continue
        
        # Save remaining
        if classifications_to_create:
            DecisionClassification.objects.bulk_create(
                classifications_to_create,
                batch_size=batch_size,
                ignore_conflicts=True
            )
        
        if classifications_to_update:
            DecisionClassification.objects.bulk_update(
                classifications_to_update,
                ['is_direct_assignment', 'classifier_version', 'classified_at'],
                batch_size=batch_size
            )
        
        logger.success(
            f"Bulk classification complete: {stats['total_processed']} processed, "
            f"{stats['direct_assignments']} direct assignments found, "
            f"{stats['created']} created, {stats['updated']} updated, "
            f"{stats['errors']} errors"
        )
        
        return stats
    
    # =============================================================================
    # QUERY HELPERS (for finding unclassified decisions)
    # =============================================================================
    
    def get_unclassified_decisions(
        self,
        limit: Optional[int] = None
    ) -> QuerySet:
        """
        Get decisions that haven't been classified yet.
        
        Uses partial index for efficient querying.
        Orders by most recent first.
        
        Args:
            limit: Optional limit on number of results
        
        Returns:
            QuerySet of unclassified Decision objects
        """
        qs = Decision.objects.filter(
            classification__isnull=True
        ).select_related('decision_type').order_by('-issue_date')
        
        if limit:
            qs = qs[:limit]
        
        return qs
    
    def get_outdated_classifications(
        self,
        limit: Optional[int] = None
    ) -> QuerySet:
        """
        Get decisions with outdated classifier version.
        
        Use this for re-classification when algorithm changes.
        
        Args:
            limit: Optional limit on number of results
        
        Returns:
            QuerySet of Decision objects needing reclassification
        """
        qs = Decision.objects.filter(
            Q(classification__classifier_version__lt=self.CLASSIFIER_VERSION) |
            Q(classification__classifier_version__isnull=True)
        ).select_related('decision_type', 'classification').order_by('-issue_date')
        
        if limit:
            qs = qs[:limit]
        
        return qs


# Singleton instance for easy importing
classification_service = DirectAssignmentDetectionService()
