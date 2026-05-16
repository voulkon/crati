"""
AFM Entity Scoring Service

Calculates importance scores for AFM entities based on:
- Appearance frequency across decisions
- Total transaction amounts
- Number of unique organizations worked with
- Direct assignment count and percentage
- Recency of appearances (optional)

The scoring algorithm is configurable via AFMScoringConfig model with:
- Configurable weights for each feature
- Configurable impact direction (positive/negative)
- Multiple normalization strategies (min-max, z-score, robust, log)
"""

from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from django.db import transaction
from django.db.models import Sum, Count, Q, Max, F, Min, Avg, StdDev
from django.utils import timezone
from loguru import logger
import math
import numpy as np

from core.models.entities import AFMEntity, DecisionEntityRelationship
from core.models.afm_scoring import (
    AFMScoringConfig, 
    AFMEntityScore, 
    NormalizationStrategy,
    FeatureImpact
)
from core.models.entities import DecisionAmountField
from core.models.decision_classification import DecisionClassification


class FeatureNormalizer:
    """
    Utility class for normalizing features using different strategies.
    """
    
    @staticmethod
    def normalize(
        value: float,
        strategy: str,
        stats: Dict[str, float],
        impact: str = FeatureImpact.POSITIVE
    ) -> float:
        """
        Normalize a value to 0-1 range using the specified strategy.
        
        Args:
            value: Raw value to normalize
            strategy: Normalization strategy (from NormalizationStrategy)
            stats: Statistics needed for normalization (min, max, mean, std, median, iqr)
            impact: Whether higher is better (POSITIVE) or worse (NEGATIVE)
            
        Returns:
            Normalized value in 0-1 range
        """
        if strategy == NormalizationStrategy.MIN_MAX:
            normalized = FeatureNormalizer._min_max(value, stats)
        elif strategy == NormalizationStrategy.Z_SCORE:
            normalized = FeatureNormalizer._z_score(value, stats)
        elif strategy == NormalizationStrategy.ROBUST:
            normalized = FeatureNormalizer._robust(value, stats)
        elif strategy == NormalizationStrategy.LOG:
            normalized = FeatureNormalizer._log_transform(value, stats)
        else:
            normalized = FeatureNormalizer._min_max(value, stats)
        
        # Apply impact direction
        if impact == FeatureImpact.NEGATIVE:
            normalized = 1.0 - normalized
        
        # Clip to 0-1 range
        return max(0.0, min(1.0, normalized))
    
    @staticmethod
    def _min_max(value: float, stats: Dict[str, float]) -> float:
        """Min-max normalization: (value - min) / (max - min)"""
        min_val = stats.get('min', 0.0)
        max_val = stats.get('max', 1.0)
        
        if max_val == min_val:
            return 0.0 if value == min_val else 1.0
        
        return (value - min_val) / (max_val - min_val)
    
    @staticmethod
    def _z_score(value: float, stats: Dict[str, float]) -> float:
        """
        Z-score normalization: (value - mean) / std
        Then map to 0-1 using sigmoid-like transformation
        """
        mean = stats.get('mean', 0.0)
        std = stats.get('std', 1.0)
        
        if std == 0:
            return 0.5
        
        z = (value - mean) / std
        # Map z-score to 0-1 using sigmoid: 1 / (1 + exp(-z))
        # This gives ~0 for z < -3, ~0.5 for z = 0, ~1 for z > 3
        try:
            return 1.0 / (1.0 + math.exp(-z))
        except OverflowError:
            return 0.0 if z < 0 else 1.0
    
    @staticmethod
    def _robust(value: float, stats: Dict[str, float]) -> float:
        """
        Robust scaling: (value - median) / IQR
        Uses median and IQR (interquartile range) instead of mean/std
        More resistant to outliers
        """
        median = stats.get('median', 0.0)
        iqr = stats.get('iqr', 1.0)
        
        if iqr == 0:
            return 0.5
        
        # Scale by IQR
        scaled = (value - median) / iqr
        
        # Map to 0-1 using sigmoid
        try:
            return 1.0 / (1.0 + math.exp(-scaled))
        except OverflowError:
            return 0.0 if scaled < 0 else 1.0
    
    @staticmethod
    def _log_transform(value: float, stats: Dict[str, float]) -> float:
        """
        Log transform + min-max normalization.
        Good for highly skewed data (like amounts).
        """
        # Add 1 to handle zero values
        log_value = math.log1p(max(0, value))
        
        min_log = stats.get('min_log', 0.0)
        max_log = stats.get('max_log', 1.0)
        
        if max_log == min_log:
            return 0.0 if log_value == min_log else 1.0
        
        return (log_value - min_log) / (max_log - min_log)


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
                'frequency_weight': 0.20,
                'amount_weight': 0.25,
                'organization_weight': 0.15,
                'direct_assignment_count_weight': 0.20,
                'direct_assignment_percentage_weight': 0.20,
                'normalization_strategy': NormalizationStrategy.ROBUST,
                'min_appearances': 3,
                'min_total_amount': Decimal('5000.00'),
                'min_unique_organizations': 2,
                'min_direct_assignments': 0,
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
        Calculate score for a single AFM entity using configured normalization and weights.
        
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
        
        # Get normalization strategy and feature config
        strategy = self.config.normalization_strategy
        feature_config = self.config.get_feature_config()
        
        # Compute normalized scores (0-1 range) for each feature
        frequency_score = FeatureNormalizer.normalize(
            value=float(metrics['appearances']),
            strategy=strategy,
            stats=global_stats['features']['frequency'],
            impact=feature_config['frequency']['impact']
        )
        
        amount_score = FeatureNormalizer.normalize(
            value=float(metrics['total_amount']),
            strategy=strategy,
            stats=global_stats['features']['amount'],
            impact=feature_config['amount']['impact']
        )
        
        org_score = FeatureNormalizer.normalize(
            value=float(metrics['unique_orgs']),
            strategy=strategy,
            stats=global_stats['features']['organization'],
            impact=feature_config['organization']['impact']
        )
        
        direct_count_score = FeatureNormalizer.normalize(
            value=float(metrics['direct_assignment_count']),
            strategy=strategy,
            stats=global_stats['features']['direct_assignment_count'],
            impact=feature_config['direct_assignment_count']['impact']
        )
        
        direct_pct_score = FeatureNormalizer.normalize(
            value=metrics['direct_assignment_percentage'],
            strategy=strategy,
            stats=global_stats['features']['direct_assignment_percentage'],
            impact=feature_config['direct_assignment_percentage']['impact']
        )
        
        # Compute weighted total score (0-100 scale)
        total_score = (
            frequency_score * self.config.frequency_weight +
            amount_score * self.config.amount_weight +
            org_score * self.config.organization_weight +
            direct_count_score * self.config.direct_assignment_count_weight +
            direct_pct_score * self.config.direct_assignment_percentage_weight
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
                'direct_assignment_count_score': direct_count_score,
                'direct_assignment_percentage_score': direct_pct_score,
                'total_appearances': metrics['appearances'],
                'total_amount': metrics['total_amount'],
                'unique_organizations': metrics['unique_orgs'],
                'direct_assignment_count': metrics['direct_assignment_count'],
                'direct_assignment_percentage': metrics['direct_assignment_percentage'],
                'is_eligible': is_eligible,
                'config_used': self.config,
                'normalization_stats': {
                    'strategy': strategy,
                    'feature_impacts': {
                        k: v['impact'] for k, v in feature_config.items()
                    }
                },
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
        
        # Direct assignment count and percentage
        # Count decisions where entity appears that are classified as direct assignments
        direct_assignment_count = DecisionEntityRelationship.objects.filter(
            entity=entity,
            decision__classification__is_direct_assignment=True
        ).values('decision').distinct().count()
        
        # Calculate percentage
        direct_assignment_percentage = 0.0
        if appearances > 0:
            direct_assignment_percentage = (direct_assignment_count / appearances) * 100.0
        
        return {
            'appearances': appearances,
            'unique_orgs': unique_orgs,
            'total_amount': total_amount,
            'direct_assignment_count': direct_assignment_count,
            'direct_assignment_percentage': direct_assignment_percentage,
        }
    
    def _compute_global_statistics(self) -> Dict[str, Any]:
        """
        Compute global statistics for normalization based on the configured strategy.
        
        Returns statistics needed for the configured normalization method:
        - MIN_MAX: min, max
        - Z_SCORE: mean, std
        - ROBUST: median, iqr (interquartile range)
        - LOG: min_log, max_log (log-transformed values)
        """
        logger.info(f"Computing global statistics for {self.config.normalization_strategy} normalization")
        
        from django.db.models import OuterRef, Subquery
        
        strategy = self.config.normalization_strategy
        
        # We need to gather metrics for all entities to compute statistics
        # This is expensive but necessary for proper normalization
        
        # For efficiency, we'll use aggregation queries where possible
        # and fall back to list comprehension for complex metrics
        
        stats = {
            'strategy': strategy,
            'features': {}
        }
        
        # === Frequency (appearances) ===
        freq_agg = AFMEntity.objects.aggregate(
            min_val=Min('total_appearances'),
            max_val=Max('total_appearances'),
            avg_val=Avg('total_appearances'),
            std_val=StdDev('total_appearances')
        )
        stats['features']['frequency'] = self._build_feature_stats(
            'frequency',
            freq_agg,
            strategy
        )
        
        # === Amount ===
        # Need to aggregate amounts per entity, then compute stats
        amount_sums = DecisionAmountField.objects.filter(
            associated_relationship__entity=OuterRef('pk'),
            amount__isnull=False
        ).values('associated_relationship__entity').annotate(
            total=Sum('amount')
        ).values('total')
        
        entities_with_amount = AFMEntity.objects.annotate(
            total_amount_subq=Subquery(amount_sums)
        )
        
        amount_agg = entities_with_amount.aggregate(
            min_val=Min('total_amount_subq'),
            max_val=Max('total_amount_subq'),
            avg_val=Avg('total_amount_subq'),
            std_val=StdDev('total_amount_subq')
        )
        stats['features']['amount'] = self._build_feature_stats(
            'amount',
            amount_agg,
            strategy
        )
        
        # === Organizations ===
        # Need subquery for org counts
        org_counts = DecisionEntityRelationship.objects.filter(
            entity=OuterRef('pk')
        ).values('entity').annotate(
            org_count=Count('decision__organization', distinct=True)
        ).values('org_count')
        
        entities_with_org_count = AFMEntity.objects.annotate(
            unique_org_count=Subquery(org_counts)
        )
        
        org_agg = entities_with_org_count.aggregate(
            min_val=Min('unique_org_count'),
            max_val=Max('unique_org_count'),
            avg_val=Avg('unique_org_count'),
            std_val=StdDev('unique_org_count')
        )
        stats['features']['organization'] = self._build_feature_stats(
            'organization',
            org_agg,
            strategy
        )
        
        # === Direct Assignment Count ===
        # This is more complex - need to count per entity
        # For performance, we'll use a simplified approach with conservative estimates
        direct_count_agg = DecisionClassification.objects.filter(
            is_direct_assignment=True
        ).aggregate(
            total=Count('decision')
        )
        
        # Conservative estimate: max possible is total direct assignments
        max_direct = direct_count_agg['total'] or 1
        
        stats['features']['direct_assignment_count'] = {
            'min': 0,
            'max': max(max_direct, 1),  # Ensure at least 1 to avoid division by zero
            'mean': max_direct / 2,  # Rough estimate
            'std': max_direct / 4,  # Rough estimate
            'median': max_direct / 2,
            'iqr': max_direct / 2,
            'min_log': 0,
            'max_log': math.log1p(max_direct),
        }
        
        # === Direct Assignment Percentage ===
        # Percentage ranges from 0 to 100
        stats['features']['direct_assignment_percentage'] = {
            'min': 0,
            'max': 100,
            'mean': 50,
            'std': 25,
            'median': 50,
            'iqr': 50,
            'min_log': 0,
            'max_log': math.log1p(100),
        }
        
        logger.info(f"Global stats computed for {strategy} normalization")
        return stats
    
    def _build_feature_stats(
        self,
        feature_name: str,
        aggregation: Dict[str, Any],
        strategy: str
    ) -> Dict[str, float]:
        """
        Build feature statistics dictionary from aggregation results.
        
        Args:
            feature_name: Name of the feature
            aggregation: Dict with min_val, max_val, avg_val, std_val
            strategy: Normalization strategy
            
        Returns:
            Dict with statistics needed for the strategy
        """
        min_val = float(aggregation.get('min_val') or 0)
        max_val = float(aggregation.get('max_val') or 1)
        mean_val = float(aggregation.get('avg_val') or 0)
        std_val = float(aggregation.get('std_val') or 1)
        
        # Ensure max > min
        if max_val == min_val:
            max_val = min_val + 1
        
        # Ensure std > 0
        if std_val == 0:
            std_val = 1.0
        
        stats = {
            'min': min_val,
            'max': max_val,
            'mean': mean_val,
            'std': std_val,
        }
        
        # Add median and IQR if using robust normalization
        # (These would require more complex queries, so we'll estimate)
        if strategy == NormalizationStrategy.ROBUST:
            # Estimate median as mean (not perfect but avoids expensive query)
            # Estimate IQR as ~1.35 * std (relationship for normal distribution)
            stats['median'] = mean_val
            stats['iqr'] = 1.35 * std_val if std_val > 0 else 1.0
        else:
            stats['median'] = mean_val
            stats['iqr'] = max_val - min_val
        
        # Add log-transformed stats if using log normalization
        if strategy == NormalizationStrategy.LOG:
            stats['min_log'] = math.log1p(max(0, min_val))
            stats['max_log'] = math.log1p(max(0, max_val))
        else:
            stats['min_log'] = 0
            stats['max_log'] = 1
        
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
        
        if metrics['direct_assignment_count'] < self.config.min_direct_assignments:
            return False
        
        return True
    
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
