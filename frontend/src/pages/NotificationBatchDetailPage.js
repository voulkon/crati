import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from '../contexts/TranslationContext';
import { getNotificationBatch, getBatchDecisions, markBatchRead } from '../api/notifications';
import DecisionCard from '../components/DecisionCard';
import SortControl from '../components/SortControl';
import apiClient from '../api/client';
import { formatAmount } from '../utils/dateUtils';
import './NotificationBatchDetailPage.css';

/**
 * Page showing a notification batch with all its matching decisions
 * Similar structure to RelationshipDetailPage
 */
const NotificationBatchDetailPage = () => {
  const { batchId } = useParams();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [batch, setBatch] = useState(null);
  const [decisions, setDecisions] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(null);

  // Filters
  const [sortBy, setSortBy] = useState('recent');
  const [isViewedFilter, setIsViewedFilter] = useState(null); // null, true, or false

  // Fetch batch data
  useEffect(() => {
    const fetchBatchData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Get batch details
        const batchData = await getNotificationBatch(batchId);
        setBatch(batchData);

        // Auto-mark as read if not already
        if (!batchData.is_read) {
          await markBatchRead(batchId);
          batchData.is_read = true;
        }

        // Get batch decisions (paginated) with sorting
        const decisionsData = await getBatchDecisions(batchId, 1, 20, isViewedFilter, sortBy);
        setDecisions(decisionsData.results || []);
        setPagination({
          current_page: 1,
          total_count: decisionsData.count,
          has_next: !!decisionsData.next,
          has_previous: !!decisionsData.previous
        });

      } catch (err) {
        console.error('Error fetching batch data:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    if (batchId) {
      fetchBatchData();
    }
  }, [batchId, isViewedFilter, sortBy]);

  const handleLoadMore = async () => {
    if (!pagination?.has_next || loadingMore) return;

    try {
      setLoadingMore(true);
      const nextPage = pagination.current_page + 1;
      const decisionsData = await getBatchDecisions(batchId, nextPage, 20, isViewedFilter, sortBy);
      
      setDecisions(prev => [...prev, ...(decisionsData.results || [])]);
      setPagination({
        current_page: nextPage,
        total_count: decisionsData.count,
        has_next: !!decisionsData.next,
        has_previous: !!decisionsData.previous
      });
    } catch (err) {
      console.error('Error loading more decisions:', err);
    } finally {
      setLoadingMore(false);
    }
  };

  const handleViewDocumentContent = async (decisionAda) => {
    try {
      const response = await apiClient.get(`/decision/${decisionAda}/content/`);
      return response.data;
    } catch (error) {
      console.error('Error fetching document content:', error);
      throw error;
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading && !batch) {
    return (
      <div className="notification-batch-page loading-container">
        <h2>{t('notifications.loadingBatch')}</h2>
        <div className="spinner"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="notification-batch-page error-container">
        <h2>{t('notifications.errorLoadingBatch')}</h2>
        <p>{error}</p>
        <button onClick={() => navigate(-1)} className="back-button">
          {t('common.goBack')}
        </button>
      </div>
    );
  }

  if (!batch) {
    return (
      <div className="notification-batch-page not-found-container">
        <h2>{t('notifications.batchNotFound')}</h2>
        <button onClick={() => navigate(-1)} className="back-button">
          {t('common.goBack')}
        </button>
      </div>
    );
  }

  return (
    <div className="notification-batch-detail-page">
      {/* Breadcrumb */}
      <div className="breadcrumb">
        <button onClick={() => navigate(-1)} className="breadcrumb-link">
          {t('navigation.back')}
        </button>
        <span className="breadcrumb-separator">•</span>
        <span>{t('notifications.batchDetail')}</span>
      </div>

      {/* Header Section */}
      <div className="batch-header">
        <h1 className="batch-title">{t('notifications.notificationBatch')}</h1>
        
        {batch.subscription && (
          <div className="subscription-info">
            <span className="subscription-label">{t('notifications.subscription')}:</span>
            <span className="subscription-alias">{batch.subscription.alias || t('notifications.unnamed')}</span>
            {batch.subscription.organization_label && (
              <span className="subscription-detail">→ {batch.subscription.organization_label}</span>
            )}
            {batch.subscription.entity_name && (
              <span className="subscription-detail">→ {batch.subscription.entity_name}</span>
            )}
          </div>
        )}

        <div className="batch-metadata">
          <div className="metadata-item">
            <span className="metadata-label">{t('notifications.checkWindow')}:</span>
            <span className="metadata-value">
              {formatDate(batch.check_window_start)} — {formatDate(batch.check_window_end)}
            </span>
          </div>
          <div className="metadata-item">
            <span className="metadata-label">{t('notifications.created')}:</span>
            <span className="metadata-value">{formatDate(batch.created_at)}</span>
          </div>
        </div>
      </div>

      {/* Statistics Section */}
      {batch.aggregate_stats && Object.keys(batch.aggregate_stats).length > 0 && (
        <div className="statistics-grid">
          {batch.aggregate_stats.total_amount && (
            <div className="stat-card">
              <h3>{t('notifications.totalAmount')}</h3>
              <div className="stat-value">{formatAmount(batch.aggregate_stats.total_amount)}</div>
            </div>
          )}
          
          {batch.aggregate_stats.avg_amount && (
            <div className="stat-card">
              <h3>{t('notifications.avgAmount')}</h3>
              <div className="stat-value">{formatAmount(batch.aggregate_stats.avg_amount)}</div>
            </div>
          )}

          {batch.aggregate_stats.decision_types && (
            <div className="stat-card">
              <h3>{t('notifications.decisionTypes')}</h3>
              <div className="stat-value">{Object.keys(batch.aggregate_stats.decision_types).length}</div>
            </div>
          )}
        </div>
      )}

      {/* Decisions Section */}
      <div className="decisions-section">
        <div className="decisions-header">
          <h3 className="decisions-title">
            {t('notifications.matchingDecisions')} ({batch.match_count || 0})
          </h3>
          
          <div className="controls-container">
            <SortControl sortBy={sortBy} onSortChange={setSortBy} options="simple" />
            
            {/* Viewed filter */}
            <div className="viewed-filter">
              <label>{t('notifications.showViewed')}:</label>
              <select 
                value={isViewedFilter === null ? 'all' : isViewedFilter.toString()} 
                onChange={(e) => {
                  const value = e.target.value;
                  setIsViewedFilter(value === 'all' ? null : value === 'true');
                }}
              >
                <option value="all">{t('common.all')}</option>
                <option value="false">{t('notifications.notViewed')}</option>
                <option value="true">{t('notifications.viewed')}</option>
              </select>
            </div>
          </div>
        </div>

        {/* Decisions List */}
        {loading ? (
          <div className="loading-text">{t('common.loading')}</div>
        ) : decisions.length === 0 ? (
          <div className="no-decisions-message">
            {t('notifications.noDecisionsInBatch')}
          </div>
        ) : (
          <>
            <div className="decisions-list">
              {decisions.map((batchDecision, index) => (
                <DecisionCard
                  key={batchDecision.id}
                  decision={batchDecision.decision}
                  formatAmount={formatAmount}
                  index={index}
                  isLastItem={index === decisions.length - 1}
                  onViewDocumentContent={handleViewDocumentContent}
                />
              ))}
            </div>

            {pagination?.has_next && (
              <div className="load-more-container">
                <button 
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                  className={`load-more-button ${loadingMore ? 'loading' : ''}`}
                >
                  {loadingMore ? t('common.loading') : t('common.loadMore')}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default NotificationBatchDetailPage;
