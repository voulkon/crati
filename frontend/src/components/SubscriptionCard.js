import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    updateSubscription,
    deleteSubscription,
    triggerCheckNow
} from '../api/notifications';
import {
    Building2,
    User,
    Users,
    UserCheck,
    Filter,
    FileText,
    Zap,
    Pause,
    Play,
    Bell,
    Clock,
    Trash2,
    RefreshCw,
    Edit2,
    Check,
    X
} from 'lucide-react';
import './SubscriptionCard.css';

/**
 * SubscriptionCard - Individual subscription display card
 * Shows subscription details with actions
 */
export default function SubscriptionCard({ subscription, onRefresh }) {
    const navigate = useNavigate();
    const [isActionLoading, setIsActionLoading] = useState(false);
    const [isEditingAlias, setIsEditingAlias] = useState(false);
    const [aliasValue, setAliasValue] = useState(subscription.alias || '');

    // Get icon for subscription type
    const getTypeIcon = (type) => {
        const icons = {
            organization: <Building2 size={16} />,
            entity: <Building2 size={16} />,
            relationship: <Users size={16} />,
            person: <User size={16} />,
            signer: <UserCheck size={16} />,
            filter: <Filter size={16} />
        };
        return icons[type] || <FileText size={16} />;
    };

    // Get display label for subscription type
    const getTypeLabel = (type) => {
        const labels = {
            organization: 'Organization',
            entity: 'Entity',
            relationship: 'Relationship',
            person: 'Person',
            signer: 'Signer',
            filter: 'Filter Only'
        };
        return labels[type] || type;
    };

    // Get target display info
    const getTargetDisplay = () => {
        if (subscription.organization_uid && !subscription.relationship_entity_afm) {
            return {
                primary: subscription.organization_label || subscription.organization_uid,
                secondary: `UID: ${subscription.organization_uid}`,
                link: `/entity/organization/${subscription.organization_uid}`
            };
        }

        if (subscription.entity_afm && !subscription.relationship_org_uid) {
            return {
                primary: subscription.entity_name || subscription.entity_afm,
                secondary: `AFM: ${subscription.entity_afm}`,
                link: `/entity/afm/${subscription.entity_afm}`
            };
        }

        if (subscription.relationship_org_uid && subscription.relationship_entity_afm) {
            const orgLabel = subscription.relationship_org_label || subscription.relationship_org_uid;
            const entityName = subscription.relationship_entity_name || subscription.relationship_entity_afm;
            return {
                primary: `${orgLabel} ↔ ${entityName}`,
                secondary: `${subscription.relationship_org_uid} × ${subscription.relationship_entity_afm}`,
                link: `/relationship/entity/${subscription.relationship_entity_afm}/org/${subscription.relationship_org_uid}`
            };
        }

        if (subscription.signer_name) {
            return {
                primary: subscription.signer_name,
                secondary: 'Signer',
                link: null
            };
        }

        if (subscription.person_name) {
            return {
                primary: subscription.person_name,
                secondary: 'Person',
                link: null
            };
        }

        return {
            primary: 'Filter-based subscription',
            secondary: 'Custom filters',
            link: null
        };
    };

    // Save alias
    const handleSaveAlias = async () => {
        if (aliasValue === subscription.alias) {
            setIsEditingAlias(false);
            return;
        }

        setIsActionLoading(true);
        try {
            await updateSubscription(subscription.id, {
                alias: aliasValue || null
            });
            await onRefresh();
            setIsEditingAlias(false);
        } catch (error) {
            console.error('Failed to update alias:', error);
            alert('Failed to update alias');
        } finally {
            setIsActionLoading(false);
        }
    };

    // Cancel alias edit
    const handleCancelAlias = () => {
        setAliasValue(subscription.alias || '');
        setIsEditingAlias(false);
    };

    // Toggle pause/resume
    const handleTogglePause = async () => {
        setIsActionLoading(true);
        try {
            await updateSubscription(subscription.id, {
                is_active: !subscription.is_active
            });
            await onRefresh();
        } catch (error) {
            console.error('Failed to toggle subscription:', error);
            alert('Failed to update subscription');
        } finally {
            setIsActionLoading(false);
        }
    };

    // Delete subscription
    const handleDelete = async () => {
        if (!window.confirm('Are you sure you want to delete this subscription?')) {
            return;
        }

        setIsActionLoading(true);
        try {
            await deleteSubscription(subscription.id);
            await onRefresh();
        } catch (error) {
            console.error('Failed to delete subscription:', error);
            alert('Failed to delete subscription');
        } finally {
            setIsActionLoading(false);
        }
    };

    // Check now
    const handleCheckNow = async () => {
        setIsActionLoading(true);
        try {
            await triggerCheckNow(subscription.id);
            alert('Check complete! Refreshing...');
            await onRefresh();
        } catch (error) {
            console.error('Failed to check subscription:', error);
            alert('Failed to check subscription');
        } finally {
            setIsActionLoading(false);
        }
    };

    // Navigate to target
    const handleNavigateToTarget = () => {
        const target = getTargetDisplay();
        if (target.link) {
            navigate(target.link);
        }
    };

    // Format last checked time
    const formatLastChecked = (timestamp) => {
        if (!timestamp) return 'Never checked';

        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
        const diffDays = Math.floor(diffHours / 24);

        if (diffHours < 1) return 'Just now';
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;

        return date.toLocaleDateString();
    };

    const target = getTargetDisplay();
    const hasFilters = subscription.keywords?.length > 0 ||
        subscription.amount_min != null ||
        subscription.amount_max != null ||
        subscription.decision_types?.length > 0;

    // Determine display title - use alias if available, otherwise use descriptive placeholder
    const displayTitle = subscription.alias || 'Click to add custom name';
    const hasCustomAlias = !!subscription.alias;

    return (
        <div className={`subscription-card ${!subscription.is_active ? 'paused' : ''}`}>
            {/* Header */}
            <div className="subscription-card-header">
                <div className="subscription-type">
                    {getTypeIcon(subscription.subscription_type)}
                    <span className="subscription-type-label">
                        {getTypeLabel(subscription.subscription_type)}
                    </span>
                </div>
                <div className={`subscription-status ${subscription.is_active ? 'active' : 'paused'}`}>
                    {subscription.is_active ? (
                        <><Zap size={12} /> Active</>
                    ) : (
                        <><Pause size={12} /> Paused</>
                    )}
                </div>
            </div>

            {/* Alias/Name - Editable */}
            <div className="subscription-alias">
                {isEditingAlias ? (
                    <div className="subscription-alias-edit">
                        <input
                            type="text"
                            value={aliasValue}
                            onChange={(e) => setAliasValue(e.target.value)}
                            placeholder="Enter custom name..."
                            className="subscription-alias-input"
                            autoFocus
                            onKeyDown={(e) => {
                                if (e.key === 'Enter') handleSaveAlias();
                                if (e.key === 'Escape') handleCancelAlias();
                            }}
                        />
                        <div className="subscription-alias-actions">
                            <button
                                className="alias-btn alias-btn-save"
                                onClick={handleSaveAlias}
                                disabled={isActionLoading}
                                title="Save"
                            >
                                <Check size={14} />
                            </button>
                            <button
                                className="alias-btn alias-btn-cancel"
                                onClick={handleCancelAlias}
                                disabled={isActionLoading}
                                title="Cancel"
                            >
                                <X size={14} />
                            </button>
                        </div>
                    </div>
                ) : (
                    <div
                        className={`subscription-alias-display ${!hasCustomAlias ? 'no-alias' : ''}`}
                        onClick={() => setIsEditingAlias(true)}
                        title="Click to edit name"
                    >
                        <span className="subscription-alias-text">{displayTitle}</span>
                        <Edit2 size={14} className="subscription-alias-edit-icon" />
                    </div>
                )}
            </div>

            {/* Target - Always show what this subscription is tracking */}
            <div className="subscription-target">
                <div
                    className={`subscription-target-name ${target.link ? 'clickable' : ''}`}
                    onClick={target.link ? handleNavigateToTarget : undefined}
                    title={target.link ? 'Click to view details' : ''}
                >
                    {target.primary}
                </div>
                {target.secondary && (
                    <div className="subscription-target-secondary">
                        {target.secondary}
                    </div>
                )}
            </div>

            {/* Filters Summary */}
            {hasFilters && (
                <div className="subscription-filters">
                    {subscription.keywords?.length > 0 && (
                        <div className="filter-item">
                            <span className="filter-label">Keywords:</span>
                            <span className="filter-value">
                                {subscription.keywords.slice(0, 3).join(', ')}
                                {subscription.keywords.length > 3 && ` +${subscription.keywords.length - 3} more`}
                            </span>
                        </div>
                    )}

                    {(subscription.amount_min != null || subscription.amount_max != null) && (
                        <div className="filter-item">
                            <span className="filter-label">Amount:</span>
                            <span className="filter-value">
                                {subscription.amount_min != null && `≥ €${subscription.amount_min}`}
                                {subscription.amount_min != null && subscription.amount_max != null && ' - '}
                                {subscription.amount_max != null && `≤ €${subscription.amount_max}`}
                            </span>
                        </div>
                    )}

                    {subscription.decision_types?.length > 0 && (
                        <div className="filter-item">
                            <span className="filter-label">Types:</span>
                            <span className="filter-value">
                                {subscription.decision_types.length} selected
                            </span>
                        </div>
                    )}
                </div>
            )}

            {/* Metadata */}
            <div className="subscription-metadata">
                <div className="metadata-item">
                    <Bell size={14} className="metadata-icon" />
                    <span className="metadata-text">
                        {subscription.notification_count || 0} notification{subscription.notification_count !== 1 ? 's' : ''}
                    </span>
                </div>
                <div className="metadata-item">
                    <Clock size={14} className="metadata-icon" />
                    <span className="metadata-text">
                        {formatLastChecked(subscription.last_checked_at)}
                    </span>
                </div>
            </div>

            {/* Actions */}
            <div className="subscription-actions">
                <button
                    className="subscription-btn subscription-btn-primary"
                    onClick={handleCheckNow}
                    disabled={isActionLoading}
                    title="Check for new decisions now"
                >
                    {isActionLoading ? '...' : (
                        <><RefreshCw size={14} /> Check Now</>
                    )}
                </button>

                <button
                    className="subscription-btn subscription-btn-secondary"
                    onClick={handleTogglePause}
                    disabled={isActionLoading}
                    title={subscription.is_active ? 'Pause subscription' : 'Resume subscription'}
                >
                    {subscription.is_active ? (
                        <><Pause size={14} /> Pause</>
                    ) : (
                        <><Play size={14} /> Resume</>
                    )}
                </button>

                <button
                    className="subscription-btn subscription-btn-danger"
                    onClick={handleDelete}
                    disabled={isActionLoading}
                    title="Delete subscription"
                >
                    <Trash2 size={14} />
                </button>
            </div>
        </div>
    );
}
