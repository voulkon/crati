import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import { useTranslation } from '../contexts/TranslationContext';
import { OrganizationIcon, EntityIcon } from './Icons';
import './TopCounterparts.css'; // Reuse the same styles

// Import DateRangeContext if available
let useDateRange;
try {
  const DateRangeContext = require('../contexts/DateRangeContext');
  useDateRange = DateRangeContext.useDateRange;
} catch (e) {
  // DateRangeContext not available, will use props only
}

/**
 * Component to display top Org×Entity relationship pairs
 * Supports both general relationships and direct assignments
 * Can work standalone or with DateRangeContext
 */
const TopRelationshipPairs = ({ 
  dateRange: propDateRange, // Optional: override context date range
  limit = 10,
  showDirectAssignmentsToggle = true,
  defaultDirectAssignmentsOnly = true
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const contextDateRange = useDateRange?.()?.dateRange; // Optional: use context if available
  
  // Use prop dateRange if provided, otherwise fall back to context
  const dateRange = propDateRange || contextDateRange;
  
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(false);
  const [directAssignmentsOnly, setDirectAssignmentsOnly] = useState(defaultDirectAssignmentsOnly);

  useEffect(() => {
    const fetchTopPairs = async () => {
      if (!dateRange || !dateRange.start_date || !dateRange.end_date) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        let response;
        
        if (directAssignmentsOnly) {
          // Use direct assignments endpoint
          const params = new URLSearchParams({
            start_date: dateRange.start_date,
            end_date: dateRange.end_date,
            limit: limit,
            offset: 0
          });
          
          response = await apiClient.get(`/direct-assignments/top-pairs/?${params}`);
          
          // Transform response to match expected format
          setData({
            date_range: {
              start_date: response.data.date_range.start,
              end_date: response.data.date_range.end
            },
            results: response.data.results.map(item => ({
              'decision__organization__uid': item.organization.uid,
              'decision__organization__label': item.organization.label,
              'entity__afm': item.entity.afm,
              'entity__name': item.entity.name,
              'entity__entity_type': item.entity.entity_type,
              'total_amount': parseFloat(item.total_amount),
              'decision_count': item.decision_count
            })),
            total_count: response.data.results.length
          });
        } else {
          // Use general relationships endpoint
          const params = new URLSearchParams({
            start_date: dateRange.start_date,
            end_date: dateRange.end_date,
            limit: limit
          });

          response = await apiClient.get(`/explore/temporal/top-relationships/?${params}`);
          
          setData({
            date_range: response.data.date_range,
            results: response.data.results,
            total_count: response.data.pagination.total_count
          });
        }
      } catch (err) {
        console.error('Error fetching top relationship pairs:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchTopPairs();
  }, [dateRange, limit, directAssignmentsOnly]);

  const formatAmount = (amount) => {
    if (!amount || amount === 0) return t('common.noAmount');
    return `€${amount.toLocaleString(undefined, { 
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    })}`;
  };

  const handlePairClick = (pair) => {
    // Navigate to relationship page
    const orgUid = pair['decision__organization__uid'];
    const entityAfm = pair['entity__afm'];
    navigate(
      `/relationship/entity/${entityAfm}/org/${orgUid}?start_date=${dateRange.start_date}&end_date=${dateRange.end_date}`
    );
  };

  if (loading) {
    return (
      <div className="top-counterparts-section">
        <h3 className="section-title">
          {t('relationships.topPairs')}
        </h3>
        <div className="counterparts-loading">{t('common.loading')}...</div>
      </div>
    );
  }

  if (error || !data || !data.results || data.results.length === 0) {
    return null; // Don't show section if no data
  }

  return (
    <div className="top-counterparts-section">
      <div className="section-header">
        <h3 className="section-title">{t('relationships.topPairs')}</h3>
        <div className="section-controls">
          {showDirectAssignmentsToggle && (
            <label className="toggle-switch">
              <input
                type="checkbox"
                checked={directAssignmentsOnly}
                onChange={(e) => setDirectAssignmentsOnly(e.target.checked)}
              />
              <span className="toggle-slider"></span>
              <span className="toggle-label">
                {t('filters.directAssignmentsOnly') || 'Direct Assignments Only'}
              </span>
            </label>
          )}
          <button 
            className="expand-toggle"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? t('common.collapse') : t('common.expand')} {expanded ? '▲' : '▼'}
          </button>
        </div>
      </div>

      <div className="counterparts-info">
        <span className="date-range-info">
          {t('counterparts.dateRange')}: {new Date(data.date_range.start_date).toLocaleDateString()} - {new Date(data.date_range.end_date).toLocaleDateString()}
        </span>
        <span className="total-count-info">
          {t('relationships.showingTopPairs', { count: data.results.length })}
        </span>
      </div>

      <div className={`counterparts-grid ${expanded ? 'expanded' : 'collapsed'}`}>
        {data.results.map((pair, index) => {
          const orgUid = pair['decision__organization__uid'];
          const orgLabel = pair['decision__organization__label'];
          const entityAfm = pair['entity__afm'];
          const entityName = pair['entity__name'];
          
          return (
            <button
              key={`${orgUid}-${entityAfm}`}
              className="counterpart-card relationship-pair-card"
              onClick={() => handlePairClick(pair)}
            >
              <div className="counterpart-header">
                <span className="counterpart-rank">#{index + 1}</span>
                <div className="pair-names">
                  <div className="pair-org">
                    <span className="pair-label">
                      <OrganizationIcon size={16} className="pair-icon" /> {orgLabel}
                    </span>
                    <span className="pair-id">{t('relationships.uidLabel')}: {orgUid}</span>
                  </div>
                  <div className="pair-connector">⇄</div>
                  <div className="pair-entity">
                    <span className="pair-label">
                      <EntityIcon size={16} className="pair-icon" /> {entityName}
                    </span>
                    <span className="pair-id">{t('relationships.afmLabel')}: {entityAfm}</span>
                  </div>
                </div>
              </div>
              <div className="counterpart-stats">
                <div className="stat-item">
                  <span className="stat-label">{t('counterparts.totalAmount')}</span>
                  <span className="stat-value amount">{formatAmount(pair.total_amount)}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">{t('counterparts.decisions')}</span>
                  <span className="stat-value count">{pair.decision_count}</span>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {!expanded && data.results.length > 3 && (
        <button 
          className="see-all-button"
          onClick={() => setExpanded(true)}
        >
          {t('counterparts.seeAll')} ({data.results.length})
        </button>
      )}
    </div>
  );
};

export default TopRelationshipPairs;
