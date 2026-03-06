import { useMemo } from 'react';
import { useLocation, useParams, matchPath } from 'react-router-dom';

/**
 * @typedef {Object} OrganizationContext
 * @property {'organization'} type
 * @property {string} organizationUid
 * @property {string} [organizationName]
 */

/**
 * @typedef {Object} EntityContext
 * @property {'entity'} type
 * @property {string} afm
 * @property {string} [entityName]
 */

/**
 * @typedef {Object} SignerContext
 * @property {'signer'} type
 * @property {string} signerName
 */

/**
 * @typedef {Object} RelationshipContext
 * @property {'relationship'} type
 * @property {string} organizationUid
 * @property {string} afm
 * @property {string} [organizationName]
 * @property {string} [entityName]
 */

/**
 * @typedef {Object} PersonContext
 * @property {'person'} type
 * @property {string} personName
 */

/**
 * @typedef {Object} PassiveContext
 * @property {'passive'} type - Pages where users can create free-form subscriptions (home, search, library)
 * @property {any} [metadata] - Optional metadata about the page
 */

/**
 * @typedef {Object} DisabledContext
 * @property {'disabled'} type - Pages where subscriptions are disabled (decision details, unit pages)
 * @property {string} [reason] - Reason why subscriptions are disabled (for hover text)
 */

/**
 * @typedef {OrganizationContext | EntityContext | SignerContext | RelationshipContext | PersonContext | PassiveContext | DisabledContext} NotificationContext
 */

/**
 * @typedef {Object} ContextCapabilities
 * @property {boolean} canSubscribe
 * @property {string|null} subscriptionType
 * @property {string} [suggestedName]
 */

/**
 * @typedef {Object} TargetData
 * @property {string} id
 * @property {string} name
 * @property {string} type
 */

/**
 * @typedef {Object} NotificationContextResult
 * @property {NotificationContext} context
 * @property {ContextCapabilities} capabilities
 * @property {boolean} isLoading
 * @property {TargetData} [targetData]
 */

/**
 * Detects the current page context and returns appropriate notification subscription information
 * 
 * @param {Object} [options] - Optional configuration
 * @param {any} [options.entityData] - Entity data from page state (for entity pages)
 * @returns {NotificationContextResult}
 */
export function useNotificationContext(options = {}) {
    const location = useLocation();
    const params = useParams();
    const { entityData } = options;

    // Detect context from current route
    const context = useMemo(() => {
        return detectContextFromRoute(location.pathname, params, entityData);
    }, [location.pathname, params, entityData]);

    // Calculate capabilities based on context
    const capabilities = useMemo(() => {
        return getContextCapabilities(context);
    }, [context]);

    // Determine if we're waiting for entity data to load
    const isLoading = useMemo(() => {
        // If we're on a page that should have entity data but don't have it yet, we're loading
        const needsEntityData = ['organization', 'entity', 'signer', 'person', 'relationship'].includes(context.type);
        return needsEntityData && !entityData && !context.organizationName && !context.entityName && !context.signerName && !context.personName;
    }, [context, entityData]);

    // Build target data if available
    const targetData = useMemo(() => {
        if (!entityData) return undefined;

        switch (context.type) {
            case 'organization':
                return {
                    id: context.organizationUid,
                    name: entityData.label || entityData.name || context.organizationName || '',
                    type: 'organization',
                    ...entityData
                };

            case 'entity':
                return {
                    id: context.afm,
                    name: entityData.label || entityData.name || context.entityName || '',
                    type: 'entity',
                    ...entityData
                };

            case 'signer':
                return {
                    id: context.signerName,
                    name: entityData.label || entityData.name || context.signerName,
                    type: 'signer',
                    ...entityData
                };

            case 'person':
                return {
                    id: context.personName,
                    name: entityData.label || entityData.name || context.personName,
                    type: 'person',
                    ...entityData
                };

            case 'relationship':
                return {
                    id: `${context.organizationUid}_${context.afm}`,
                    name: `${context.organizationName || ''} × ${context.entityName || ''}`,
                    type: 'relationship',
                    organizationUid: context.organizationUid,
                    afm: context.afm,
                    ...entityData
                };

            default:
                return undefined;
        }
    }, [context, entityData]);

    return {
        context,
        capabilities,
        isLoading,
        targetData
    };
}

/**
 * Detects notification context from the current route
 * 
 * @param {string} pathname - Current pathname
 * @param {Record<string, string>} params - Route parameters
 * @param {any} [entityData] - Entity data from page state
 * @returns {NotificationContext}
 */
function detectContextFromRoute(pathname, params, entityData) {
    // Match patterns in order of specificity

    // Relationship page: /relationship/entity/:afm/org/:orgUid
    if (matchPath('/relationship/entity/:afm/org/:orgUid', pathname)) {
        return {
            type: 'relationship',
            organizationUid: params.orgUid,
            afm: params.afm,
            organizationName: entityData?.organization?.label || entityData?.organization?.name,
            entityName: entityData?.entity?.label || entityData?.entity?.name
        };
    }

    // AFM Entity page: /entity/afm/:afm
    if (matchPath('/entity/afm/:afm', pathname)) {
        return {
            type: 'entity',
            afm: params.afm,
            entityName: entityData?.label || entityData?.name
        };
    }

    // Generic Entity page: /entity/:entityType/:entityId
    if (matchPath('/entity/:entityType/:entityId', pathname)) {
        const { entityType, entityId } = params;

        // Organization
        if (entityType === 'organization') {
            return {
                type: 'organization',
                organizationUid: entityId,
                organizationName: entityData?.label || entityData?.name
            };
        }

        // Signer
        if (entityType === 'signer') {
            return {
                type: 'signer',
                signerName: decodeURIComponent(entityId),
            };
        }

        // Person
        if (entityType === 'person') {
            return {
                type: 'person',
                personName: decodeURIComponent(entityId),
            };
        }

        // Unit pages - disabled
        if (entityType === 'unit') {
            return { 
                type: 'disabled',
                reason: 'Cannot subscribe to organizational units.'
            };
        }

        // Unknown entity type - treat as disabled for safety
        return { 
            type: 'disabled',
            reason: 'This page type does not support subscriptions.'
        };
    }

    // Decision detail page: /decision/:ada
    // Disabled - user is already viewing a specific decision
    if (matchPath('/decision/:ada', pathname)) {
        return { 
            type: 'disabled',
            reason: 'Cannot subscribe to individual decisions. Subscribe to organizations or entities instead.'
        };
    }

    // Passive pages (home, search, library, etc.)
    if (matchPath('/', pathname) && pathname === '/') {
        return { type: 'passive' };
    }

    if (matchPath('/search', pathname)) {
        return { type: 'passive' };
    }

    if (matchPath('/library', pathname)) {
        return { type: 'passive' };
    }

    if (matchPath('/organizations', pathname)) {
        return { type: 'passive' };
    }

    // Fallback: Default to passive for any unmapped routes
    // This allows the bell button to show and open a subscription modal
    // even on pages we haven't explicitly mapped yet
    console.warn('Unmapped route detected for notifications:', pathname);
    return { 
        type: 'passive',
        metadata: {
            source: 'unmapped',
            pathname
        }
    };
}

/**
 * Calculates context capabilities (whether user can subscribe, etc.)
 * 
 * @param {NotificationContext} context
 * @returns {ContextCapabilities}
 */
function getContextCapabilities(context) {
    switch (context.type) {
        case 'organization':
            return {
                canSubscribe: true,
                subscriptionType: 'organization',
                suggestedName: context.organizationName || `Organization ${context.organizationUid}`
            };

        case 'entity':
            return {
                canSubscribe: true,
                subscriptionType: 'entity',
                suggestedName: context.entityName || `Entity ${context.afm}`
            };

        case 'signer':
            return {
                canSubscribe: true,
                subscriptionType: 'signer',
                suggestedName: context.signerName
            };

        case 'person':
            return {
                canSubscribe: true,
                subscriptionType: 'person',
                suggestedName: context.personName
            };

        case 'relationship':
            return {
                canSubscribe: true,
                subscriptionType: 'relationship',
                suggestedName: `${context.organizationName || 'Organization'} × ${context.entityName || 'Entity'}`
            };

        case 'passive':
            return {
                canSubscribe: false,
                subscriptionType: null
            };

        case 'disabled':
            return {
                canSubscribe: false,
                subscriptionType: null
            };

        default:
            return {
                canSubscribe: false,
                subscriptionType: null
            };
    }
}

export default useNotificationContext;
