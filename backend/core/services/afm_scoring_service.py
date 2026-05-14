"""
AFM Entity Scoring Service

Calculates importance scores for AFM entities based on:
- Appearance frequency across decisions
- Total transaction amounts
- Number of unique organizations worked with
- Recency of appearances (optional)

The scoring algorithm is configurable via AFMScoringConfig model.
"""

from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from django.db import transaction
from django.db.models import Sum, Count, Q, Max, F
from django.utils import timezone
from loguru import logger

from core.models.entities import AFMEntity, DecisionEntityRelationship
from core.models.afm_scoring import AFMScoringConfig, AFMEntityScore
from core.models.entities import DecisionAmountField


class AFMEntityScoringService:
    """
    Service for scoring and ranking AFM entities.
    
    Usage:
        service = AFMEntityScoringService()
        stats = service.score_all_entities()
        
        # Or score specific entities
        service.score_entities([entity1, entity2, ...])
    """
    
    def __init__(self, config: Optional[AFMScoringConfig] = None):
        """
        Initialize scoring service.
        
        Args:
            config: Optional scoring config (uses active config if not provided)
        """
        self.config = config or AFMScoringConfig.get_active()
        if not self.config:
            logger.warning("No active AFMScoringConfig found, creating default")
            self.config = self._create_default_config()
    
    def _create_default_config(self) -> AFMScoringConfig:
        """Create a default scoring configuration."""
        config, created = AFMScoringConfig.objects.get_or_create(
            name="Default",
            defaults={
                'is_active': True,
                'frequency_weight': 0.30,
                'amount_weight': 0.50,
                'organization_weight': 0.20,
                'min_appearances': 3,
                'min_total_amount': Decimal('5000.00'),
                'min_unique_organizations': 2,
                'retry_failed_after_days': 90,
                'never_retry_after_failures': 5,
            }
        )
        if created:
            logger.info("Created default AFMScoringConfig")
        return config
    
    def score_all_entities(
        self, 
        batch_size: int = 1000,
        exclude_already_fetched: bool = False
    ) -> Dict[str, Any]:
        """
        Score all AFM entities in the database.
        
        Args:
            batch_size: Number of entities to process per batch
            exclude_already_fetched: Skip entities that already have successful GEMI data
            
        Returns:
            Statistics about the scoring operation
        """
        logger.info(f"Starting AFM entity scoring with config: {self.config.name}")
        
        # Validate config
        try:
            self.config.validate_weights()
        except ValueError as e:
            logger.error(f"Invalid scoring config: {e}")
            raise
        
        # Build queryset
        queryset = AFMEntity.objects.all()
        
        if exclude_already_fetched:
            queryset = queryset.filter(
                Q(gemi_lookup_success=False) | Q(gemi_lookup_attempted__isnull=True)
            )
        
        total_entities = queryset.count()
        logger.info(f"Scoring {total_entities} entities")
        
        # Compute global statistics for normalization
        global_stats = self._compute_global_statistics()
        
        scored_count = 0
        eligible_count = 0
        
        # Process in batches
        for offset in range(0, total_entities, batch_size):
            batch = queryset[offset:offset + batch_size]
            
            with transaction.atomic():
                for entity in batch:
                    score_data = self.score_entity(entity, global_stats)
                    if score_data['is_eligible']:
                        eligible_count += 1
                    scored_count += 1
            
            if scored_count % 1000 == 0:
                logger.info(f"Scored {scored_count}/{total_entities} entities")
        
        # Assign priority ranks (1 = highest priority)
        self._assign_priority_ranks()
        
        stats = {
            'total_scored': scored_count,
            'eligible_for_fetch': eligible_count,
            'ineligible': scored_count - eligible_count,
            'config_used': self.config.name,
            'global_stats': global_stats,
        }
        
        logger.info(f"Scoring completed", extra=stats)
        return stats
    
    def score_entity(
        self, 
        entity: AFMEntity,
        global_stats: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate score for a single AFM entity.
        
        Args:
            entity: AFMEntity to score
            global_stats: Pre-computed global statistics (for normalization)
            
        Returns:
            Dictionary with score components and metadata
        """
        if global_stats is None:
            global_stats = self._compute_global_statistics()
        
        # Gather raw metrics for this entity
        metrics = self._gather_entity_metrics(entity)
        
        # Check eligibility (minimum thresholds)
        is_eligible = self._check_eligibility(entity, metrics)
        
        # Compute normalized scores (0-1 range)
        frequency_score = self._normalize_frequency(
            metrics['appearances'], 
            global_stats['max_appearances']
        )
        amount_score = self._normalize_amount(
            metrics['total_amount'],
            global_stats['max_amount']
        )
        org_score = self._normalize_organizations(
            metrics['unique_orgs'],
            global_stats['max_orgs']
        )
        
        # Compute weighted total score (0-100 scale)
        total_score = (
            frequency_score * self.config.frequency_weight +
            amount_score * self.config.amount_weight +
            org_score * self.config.organization_weight
        ) * 100
        
        # Apply recency boost if enabled
        if self.config.enable_recency_boost:
            if self._is_recent(entity):
                total_score *= self.config.recency_boost_multiplier
                logger.debug(f"Applied recency boost to {entity.afm}")
        
        # Save to database
        score_obj, created = AFMEntityScore.objects.update_or_create(
            entity=entity,
            defaults={
                'total_score': total_score,
                'frequency_score': frequency_score,
                'amount_score': amount_score,
                'organization_score': org_score,
                'total_appearances': metrics['appearances'],
                'total_amount': metrics['total_amount'],
                'unique_organizations': metrics['unique_orgs'],
                'is_eligible': is_eligible,
                'config_used': self.config,
            }
        )
        
        return {
            'entity_afm': entity.afm,
            'total_score': total_score,
            'is_eligible': is_eligible,
            'metrics': metrics,
            'created': created,
        }
    
    def _gather_entity_metrics(self, entity: AFMEntity) -> Dict[str, Any]:
        """Gather raw metrics for an entity."""
        
        # Total appearances (use cached value from AFMEntity if available)
        appearances = entity.total_appearances or 0
        
        # Unique organizations (count via relationships)
        unique_orgs = DecisionEntityRelationship.objects.filter(
            entity=entity
        ).values('decision__organization').distinct().count()
        
        # Total amounts (sum via linked amounts)
        total_amount = DecisionAmountField.objects.filter(
            associated_relationship__entity=entity,
            amount__isnull=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        return {
            'appearances': appearances,
            'unique_orgs': unique_orgs,
            'total_amount': total_amount,
        }
    
    def _compute_global_statistics(self) -> Dict[str, Any]:
        """
        Compute global statistics for normalization.
        
        Returns max values across all entities to normalize scores to 0-1 range.
        """
        logger.info("Computing global statistics for normalization")
        
        # Max appearances
        max_appearances = AFMEntity.objects.aggregate(
            max_app=Max('total_appearances')
        )['max_app'] or 1
        
        # Max unique organizations per entity
        # This requires a subquery - count unique orgs per entity, then get max
        from django.db.models import OuterRef, Subquery
        
        org_counts = DecisionEntityRelationship.objects.filter(
            entity=OuterRef('pk')
        ).values('entity').annotate(
            org_count=Count('decision__organization', distinct=True)
        ).values('org_count')
        
        entities_with_org_count = AFMEntity.objects.annotate(
            unique_org_count=Subquery(org_counts)
        )
        
        max_orgs = entities_with_org_count.aggregate(
            max_orgs=Max('unique_org_count')
        )['max_orgs'] or 1
        
        # Max total amount per entity
        # Similar approach - sum amounts per entity, then get max
        amount_sums = DecisionAmountField.objects.filter(
            associated_relationship__entity=OuterRef('pk'),
            amount__isnull=False
        ).values('associated_relationship__entity').annotate(
            total=Sum('amount')
        ).values('total')
        
        entities_with_amount = AFMEntity.objects.annotate(
            total_amount_subq=Subquery(amount_sums)
        )
        
        max_amount = entities_with_amount.aggregate(
            max_amt=Max('total_amount_subq')
        )['max_amt'] or Decimal('1.00')
        
        stats = {
            'max_appearances': max_appearances,
            'max_orgs': max_orgs,
            'max_amount': float(max_amount),
        }
        
        logger.info(f"Global stats computed", extra=stats)
        return stats
    
    def _check_eligibility(self, entity: AFMEntity, metrics: Dict[str, Any]) -> bool:
        """
        Check if entity meets minimum thresholds.
        
        Also filters out entities that should never be retried.
        """
        # Check if already successfully fetched
        if entity.gemi_lookup_success and entity.gemi_companies_count > 0:
            return False  # Already have data, no need to fetch
        
        # Check if too many failures
        if entity.error_count >= self.config.never_retry_after_failures:
            return False
        
        # Check if recent failure (respect retry delay)
        if entity.gemi_lookup_attempted and not entity.gemi_lookup_success:
            days_since_attempt = (timezone.now() - entity.gemi_lookup_attempted).days
            if days_since_attempt < self.config.retry_failed_after_days:
                return False  # Too soon to retry
        
        # Check minimum thresholds
        if metrics['appearances'] < self.config.min_appearances:
            return False
        
        if metrics['total_amount'] < self.config.min_total_amount:
            return False
        
        if metrics['unique_orgs'] < self.config.min_unique_organizations:
            return False
        
        return True
    
    def _normalize_frequency(self, appearances: int, max_appearances: int) -> float:
        """Normalize appearance frequency to 0-1 range."""
        if max_appearances == 0:
            return 0.0
        return min(appearances / max_appearances, 1.0)
    
    def _normalize_amount(self, amount: Decimal, max_amount: float) -> float:
        """Normalize total amount to 0-1 range."""
        if max_amount == 0:
            return 0.0
        return min(float(amount) / max_amount, 1.0)
    
    def _normalize_organizations(self, org_count: int, max_orgs: int) -> float:
        """Normalize unique organization count to 0-1 range."""
        if max_orgs == 0:
            return 0.0
        return min(org_count / max_orgs, 1.0)
    
    def _is_recent(self, entity: AFMEntity) -> bool:
        """Check if entity has been seen recently."""
        if not entity.last_seen:
            return False
        
        threshold_date = timezone.now() - timedelta(days=self.config.recency_days_threshold)
        return entity.last_seen >= threshold_date
    
    def _assign_priority_ranks(self):
        """
        Assign priority ranks to eligible entities.
        
        Rank 1 = highest priority (highest score), 2 = second highest, etc.
        """
        eligible_scores = AFMEntityScore.objects.filter(
            is_eligible=True
        ).order_by('-total_score')
        
        rank = 1
        for score in eligible_scores:
            score.fetch_priority = rank
            score.save(update_fields=['fetch_priority'])
            rank += 1
        
        logger.info(f"Assigned priority ranks to {rank - 1} eligible entities")
    
    def get_top_entities(
        self, 
        limit: int = 100,
        only_eligible: bool = True,
        exclude_fetched: bool = True
    ) -> List[Tuple[AFMEntity, AFMEntityScore]]:
        """
        Get top-scored entities.
        
        Args:
            limit: Maximum number of entities to return
            only_eligible: Only return eligible entities
            exclude_fetched: Exclude entities with successful GEMI data
            
        Returns:
            List of (entity, score) tuples ordered by score descending
        """
        queryset = AFMEntityScore.objects.select_related('entity')
        
        if only_eligible:
            queryset = queryset.filter(is_eligible=True)
        
        if exclude_fetched:
            queryset = queryset.filter(
                Q(entity__gemi_lookup_success=False) | 
                Q(entity__gemi_lookup_attempted__isnull=True)
            )
        
        queryset = queryset.order_by('-total_score')[:limit]
        
        return [(score.entity, score) for score in queryset]
