from rest_framework import serializers
from notifications.models import NotificationBatch, NotificationBatchDecision, NotificationSubscription
from core.models.decisions import Decision


class SubscriptionNestedForBatchSerializer(serializers.ModelSerializer):
    """Lightweight serializer for nested subscription details in batches."""
    
    subscription_type = serializers.CharField(read_only=True)
    organization_label = serializers.CharField(source='organization.label', read_only=True)
    entity_name = serializers.CharField(source='entity.name', read_only=True)
    entity_afm = serializers.CharField(source='entity.afm', read_only=True)
    
    class Meta:
        model = NotificationSubscription
        fields = [
            'id',
            'alias',
            'subscription_type',
            'organization_label',
            'entity_name',
            'entity_afm',
            'keywords',
            'keyword_match_operator',
        ]
        read_only_fields = fields


class DecisionNestedForBatchSerializer(serializers.ModelSerializer):
    """Lightweight serializer for nested decision details in batch decisions."""
    
    organization_label = serializers.CharField(source='organization.label', read_only=True)
    organization_uid = serializers.CharField(source='organization.uid', read_only=True)
    decision_type_label = serializers.CharField(source='decision_type.label', read_only=True)
    
    class Meta:
        model = Decision
        fields = [
            'id',
            'ada',
            'subject',
            'protocol_number',
            'issue_date',
            'publish_timestamp',
            'organization_label',
            'organization_uid',
            'decision_type_label',
            'amount',
        ]
        read_only_fields = fields


class NotificationBatchDecisionSerializer(serializers.ModelSerializer):
    """
    Serializer for individual decisions within a batch.
    Used for the decisions list endpoint.
    """
    
    decision = DecisionNestedForBatchSerializer(read_only=True)
    
    class Meta:
        model = NotificationBatchDecision
        fields = [
            'id',
            'decision',
            'match_reason',
            'match_details',
            'is_viewed',
            'viewed_at',
            'added_at',
        ]
        read_only_fields = fields


class NotificationBatchListSerializer(serializers.ModelSerializer):
    """
    Optimized serializer for batch list view with lighter payload.
    Minimal nested data for performance.
    """
    
    subscription_alias = serializers.CharField(source='subscription.alias', read_only=True)
    subscription_type = serializers.CharField(source='subscription.subscription_type', read_only=True)
    
    class Meta:
        model = NotificationBatch
        fields = [
            'id',
            'subscription',
            'subscription_alias',
            'subscription_type',
            'match_count',
            'check_window_start',
            'check_window_end',
            'is_read',
            'is_dismissed',
            'created_at',
        ]
        read_only_fields = fields


class NotificationBatchDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for NotificationBatch with nested details.
    Used for retrieve operation.
    """
    
    subscription = SubscriptionNestedForBatchSerializer(read_only=True)
    
    class Meta:
        model = NotificationBatch
        fields = [
            'id',
            'user',
            'subscription',
            'check_window_start',
            'check_window_end',
            'match_count',
            'aggregate_stats',
            'is_read',
            'is_dismissed',
            'created_at',
            'read_at',
            'dismissed_at',
        ]
        read_only_fields = fields
