import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import apiClient from '../api/client';
import DualRangeSlider from '../components/DualRangeSlider';
import DecisionCard from '../components/DecisionCard';
import { createDynamicDateRangeUtils, formatAmount } from '../utils/dateUtils';
import { useTranslation } from '../contexts/TranslationContext';
import './EntityDetailPage.css';

const EntityDetailPage = () => {
  const { entityType, entityId, date, startDate, endDate, year, month, week } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  
  // Determine exploration mode
  const explorationMode = location.pathname.startsWith('/explore') ? 'temporal' : 'entity';
  
  // Enhanced state to handle both modes - restore from URL params
  const [entityData, setEntityData] = useState(null);
  const [statistics, setStatistics] = useState(null);
  const [decisions, setDecisions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sortBy, setSortBy] = useState(searchParams.get('sort') || 'recent');
  const [pagination, setPagination] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [searchQuery, setSearchQuery] = useState(searchParams.get('search') || '');
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState(searchParams.get('search') || '');
  
  // Enhanced date range state
  const [entityDateRange, setEntityDateRange] = useState(null);
  const [dateRangeLoading, setDateRangeLoading] = useState(true);
  const [dynamicDateUtils, setDynamicDateUtils] = useState(null);
  const [timeRange, setTimeRange] = useState(null);
  const [monthRange, setMonthRange] = useState(null);
  
  // Decision type filtering state - restore from URL
  const [availableDecisionTypes, setAvailableDecisionTypes] = useState([]);
  const [selectedDecisionTypes, setSelectedDecisionTypes] = useState(
    searchParams.get('types') ? searchParams.get('types').split(',') : []
  );
  const [showDecisionTypeFilter, setShowDecisionTypeFilter] = useState(false);
  const [decisionTypesLoading, setDecisionTypesLoading] = useState(false);
  const [isOrganizationsExpanded, setIsOrganizationsExpanded] = useState(true);
  const [isTimeRangeExpanded, setIsTimeRangeExpanded] = useState(true);
  
  // Amount filtering state - restore from URL
  const [amountFilters, setAmountFilters] = useState({
    minAmount: searchParams.get('minAmount') || '',
    maxAmount: searchParams.get('maxAmount') || ''
  });
  
  // Temporal exploration specific state - restore from URL
  const [organizationFilters, setOrganizationFilters] = useState(
    searchParams.get('orgs') ? searchParams.get('orgs').split(',') : []
  );
  const [availableOrganizations, setAvailableOrganizations] = useState([]);
  const [temporalSummary, setTemporalSummary] = useState(null);

  // Parse temporal parameters into date range
  const parseTemporalDateRange = useCallback(() => {
    if (explorationMode !== 'temporal') return null;

    let startDateStr, endDateStr, label;

    if (date) {
      // Single day exploration: /explore/temporal/2025-05-31
      startDateStr = date;
      endDateStr = date;
      label = t('exploration.decisionsOn', { date: new Date(date).toLocaleDateString() });
    } else if (startDate && endDate) {
      // Date range exploration: /explore/temporal/2025-05-01/2025-05-31
      startDateStr = startDate;
      endDateStr = endDate;
      label = t('exploration.decisionsFrom', { 
        startDate: new Date(startDate).toLocaleDateString(), 
        endDate: new Date(endDate).toLocaleDateString() 
      });
    } else if (year && month) {
      // Monthly exploration: /explore/month/2025/05
      const yearNum = parseInt(year);
      const monthNum = parseInt(month);
      const startOfMonth = new Date(yearNum, monthNum - 1, 1);
      const endOfMonth = new Date(yearNum, monthNum, 0);
      startDateStr = startOfMonth.toISOString().split('T')[0];
      endDateStr = endOfMonth.toISOString().split('T')[0];
      label = t('exploration.decisionsIn', { 
        period: startOfMonth.toLocaleDateString('en-US', { year: 'numeric', month: 'long' }) 
      });
    } else if (year && week) {
      // Weekly exploration: /explore/week/2025/22
      const yearNum = parseInt(year);
      const weekNum = parseInt(week);
      // Calculate week start/end dates
      const jan1 = new Date(yearNum, 0, 1);
      const weekStart = new Date(jan1);
      weekStart.setDate(jan1.getDate() + (weekNum - 1) * 7 - jan1.getDay());
      const weekEnd = new Date(weekStart);
      weekEnd.setDate(weekStart.getDate() + 6);
      startDateStr = weekStart.toISOString().split('T')[0];
      endDateStr = weekEnd.toISOString().split('T')[0];
      label = t('exploration.week', { week: weekNum, year: yearNum });
    }

    return { startDateStr, endDateStr, label };
  }, [explorationMode, date, startDate, endDate, year, month, week, t]);

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchQuery(searchQuery);
    }, 500);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Sync state with URL parameters when they change
  useEffect(() => {
    const urlSort = searchParams.get('sort') || 'recent';
    const urlTypes = searchParams.get('types') ? searchParams.get('types').split(',') : [];
    const urlOrgs = searchParams.get('orgs') ? searchParams.get('orgs').split(',') : [];
    const urlMinAmount = searchParams.get('minAmount') || '';
    const urlMaxAmount = searchParams.get('maxAmount') || '';
    const urlSearch = searchParams.get('search') || '';
    
    // Update state if URL values differ
    if (urlSort !== sortBy) setSortBy(urlSort);
    if (JSON.stringify(urlTypes) !== JSON.stringify(selectedDecisionTypes)) setSelectedDecisionTypes(urlTypes);
    if (JSON.stringify(urlOrgs) !== JSON.stringify(organizationFilters)) setOrganizationFilters(urlOrgs);
    if (urlMinAmount !== amountFilters.minAmount || urlMaxAmount !== amountFilters.maxAmount) {
      setAmountFilters({ minAmount: urlMinAmount, maxAmount: urlMaxAmount });
    }
    if (urlSearch !== searchQuery) setSearchQuery(urlSearch);
  }, [searchParams]);

  const handleViewDocumentContent = async (decisionId) => {
    try {
      // Use integer ID - no encoding needed!
      const response = await apiClient.get(`/decision/${decisionId}/content/`);
      return response.data;
    } catch (error) {
      console.error('Error fetching document content:', error);
      
      // Handle axios-specific error structure
      if (error.response) {
        const errorMessage = error.response.data?.error || 
                            error.response.data?.message || 
                            `HTTP ${error.response.status}: ${error.response.statusText}`;
        throw new Error(errorMessage);
      } else if (error.request) {
        // The request was made but no response was received
        throw new Error('No response from server');
      } else {
        // Something happened in setting up the request that triggered an Error
        throw new Error(error.message || 'Request failed');
      }
    }
  };
  // Enhanced fetch functions for both modes
  const fetchEntityDateRange = useCallback(async () => {
    try {
      setDateRangeLoading(true);
      
      if (explorationMode === 'temporal') {
        // For temporal mode, get global date range
        const response = await apiClient.get('/explore/date-range/');
        setEntityDateRange(response.data);
        
        if (response.data.has_data) {
          const dateUtils = createDynamicDateRangeUtils(response.data);
          setDynamicDateUtils(dateUtils);
          
          // Set time range from URL parameters
          const temporalRange = parseTemporalDateRange();
          if (temporalRange) {
            setTimeRange({
              startDate: temporalRange.startDateStr,
              endDate: temporalRange.endDateStr
            });
            
            // Convert to month range for slider
            const startIndex = dateUtils.dateToIndex(new Date(temporalRange.startDateStr));
            const endIndex = dateUtils.dateToIndex(new Date(temporalRange.endDateStr));
            setMonthRange({ startIndex, endIndex });
          }
        }
      } else {
        // Existing entity mode logic
        const response = await apiClient.get(
          `/entity/${entityType}/${entityId}/date-range/`
        );
        
        setEntityDateRange(response.data);
        
        if (response.data.has_data) {
          const dateUtils = createDynamicDateRangeUtils(response.data);
          setDynamicDateUtils(dateUtils);
          
          const defaultRange = dateUtils.getDefaultRange();
          setMonthRange(defaultRange);
          setTimeRange({
            startDate: dateUtils.indexToDateString(defaultRange.startIndex),
            endDate: dateUtils.indexToDateString(defaultRange.endIndex, true)
          });
        }
      }
      
    } catch (err) {
      console.error('Failed to fetch date range:', err);
      setError(t('errors.failedToLoad'));
    } finally {
      setDateRangeLoading(false);
    }
  }, [explorationMode, entityType, entityId, parseTemporalDateRange, t]);

  const fetchDecisionTypes = useCallback(async () => {
    if (!timeRange) return;
    
    try {
      setDecisionTypesLoading(true);
      const params = new URLSearchParams({
        start_date: timeRange.startDate,
        end_date: timeRange.endDate
      });

      let endpoint;
      if (explorationMode === 'temporal') {
        endpoint = `/explore/decision-types/?${params.toString()}`;
      } else {
        endpoint = `/entity/${entityType}/${entityId}/decision-types/?${params.toString()}`;
      }

      const response = await apiClient.get(endpoint);
      setAvailableDecisionTypes(response.data.decision_types);
    } catch (err) {
      console.error('Failed to fetch decision types:', err);
    } finally {
      setDecisionTypesLoading(false);
    }
  }, [explorationMode, entityType, entityId, timeRange]);

  const fetchStatistics = useCallback(async () => {
    if (!timeRange) return;
    
    try {
      const params = new URLSearchParams({
        start_date: timeRange.startDate,
        end_date: timeRange.endDate
      });

      let endpoint;
      if (explorationMode === 'temporal') {
        endpoint = `/explore/statistics/?${params.toString()}`;
      } else {
        endpoint = `/entity/${entityType}/${entityId}/statistics/?${params.toString()}`;
      }

      const response = await apiClient.get(endpoint);
      setStatistics(response.data);
      
      if (explorationMode === 'temporal') {
        setTemporalSummary(response.data);
      } else {
        setEntityData(response.data.entity);
      }
    } catch (err) {
      console.error('Failed to fetch statistics:', err);
      setError(t('errors.failedToLoad'));
    }
  }, [explorationMode, entityType, entityId, timeRange, t]);

  const fetchDecisions = useCallback(async (page = 1, append = false) => {
    if (!timeRange) return;
    
    try {
      if (!append) {
        setLoading(true);
      } else {
        setLoadingMore(true);
      }
      
      const params = new URLSearchParams({
        start_date: timeRange.startDate,
        end_date: timeRange.endDate,
        page_size: '20',
        sort_by: sortBy,
        page: page.toString()
      });
      
      if (debouncedSearchQuery.trim()) {
        params.append('q', debouncedSearchQuery.trim());
      }

      // Add decision type filtering
      if (selectedDecisionTypes.length > 0) {
        params.append('decision_types', selectedDecisionTypes.join(','));
      }

      // Add amount filtering
      if (amountFilters.minAmount) {
        params.append('min_amount', amountFilters.minAmount);
      }
      if (amountFilters.maxAmount) {
        params.append('max_amount', amountFilters.maxAmount);
      }

      // Add organization filtering for temporal mode
      if (explorationMode === 'temporal' && organizationFilters.length > 0) {
        params.append('organization_ids', organizationFilters.join(','));
      }

      let endpoint;
      if (explorationMode === 'temporal') {
        endpoint = `/explore/decisions-optimized/?${params.toString()}`;
      } else {
        endpoint = `/entity/${entityType}/${entityId}/decisions/?${params.toString()}`;
      }

      const response = await apiClient.get(endpoint);
      
      if (append) {
        setDecisions(prevDecisions => [...prevDecisions, ...response.data.results]);
      } else {
        setDecisions(response.data.results);
      }
      
      setPagination(response.data.pagination);
      
    } catch (err) {
      console.error('Failed to fetch decisions:', err);
      setError(t('errors.failedToLoad'));
    } finally {
      if (!append) {
        setLoading(false);
      } else {
        setLoadingMore(false);
      }
    }
  }, [explorationMode, entityType, entityId, timeRange, sortBy, debouncedSearchQuery, selectedDecisionTypes, amountFilters, organizationFilters, t]);

  const loadMoreDecisions = useCallback(() => {
    if (pagination && pagination.has_next && !loadingMore) {
      fetchDecisions(pagination.current_page + 1, true);
    }
  }, [pagination, loadingMore, fetchDecisions]);
  
  // Enhanced page title and breadcrumbs
  const getPageInfo = () => {
    if (explorationMode === 'temporal') {
      const temporalRange = parseTemporalDateRange();
      return {
        title: t('entityDetail.temporalExploration'),
        subtitle: temporalRange?.label || t('exploration.exploreByTimePeriod'),
        breadcrumb: t('entityDetail.exploreArrow') + ' ' + t('entityDetail.timeArrow')
      };
    } else {
      return {
        title: entityData?.name || t('common.unknown') + ' Entity',
        subtitle: `${entityType.charAt(0).toUpperCase() + entityType.slice(1)} • ID: ${entityId}`,
        breadcrumb: t('entityDetail.exploreArrow') + ' ' + t('entityDetail.entityArrow')
      };
    }
  };

  // Add handler for organization chart navigation
  const handleViewOrganizationChart = () => {
    console.log('Organization chart button clicked!');
    if (entityType === 'organization') {
      navigate(`/organizations?uid=${entityId}`);
    }
  };

  // Update URL params when filters change
  const updateUrlParams = (updates = {}) => {
    const params = new URLSearchParams();
    
    // Get current or updated values
    const currentSort = updates.sort !== undefined ? updates.sort : sortBy;
    const currentTypes = updates.types !== undefined ? updates.types : selectedDecisionTypes;
    const currentOrgs = updates.orgs !== undefined ? updates.orgs : organizationFilters;
    const currentMinAmount = updates.minAmount !== undefined ? updates.minAmount : amountFilters.minAmount;
    const currentMaxAmount = updates.maxAmount !== undefined ? updates.maxAmount : amountFilters.maxAmount;
    const currentSearch = updates.search !== undefined ? updates.search : searchQuery;
    
    // Only add non-default values to URL
    if (currentSort !== 'recent') {
      params.set('sort', currentSort);
    }
    
    if (currentTypes.length > 0) {
      params.set('types', currentTypes.join(','));
    }
    
    if (currentOrgs.length > 0) {
      params.set('orgs', currentOrgs.join(','));
    }
    
    if (currentMinAmount) {
      params.set('minAmount', currentMinAmount);
    }
    
    if (currentMaxAmount) {
      params.set('maxAmount', currentMaxAmount);
    }
    
    if (currentSearch) {
      params.set('search', currentSearch);
    }
    
    setSearchParams(params);
  };

  // Initial load effect
  useEffect(() => {
    const loadInitialData = async () => {
      setLoading(true);
      setError(null);
      
      try {
        await fetchEntityDateRange();
      } catch (err) {
        setError(t('errors.failedToLoad'));
      } finally {
        setLoading(false);
      }
    };

    loadInitialData();
  }, [fetchEntityDateRange, t]);

  // Load data when time range is set
  useEffect(() => {
    if (timeRange) {
      const loadData = async () => {
        try {
          await Promise.all([
            fetchStatistics(),
            fetchDecisions(1, false),
            fetchDecisionTypes()
          ]);
        } catch (err) {
          setError(t('errors.failedToLoad'));
        }
      };

      loadData();
    }
  }, [timeRange, fetchStatistics, fetchDecisions, fetchDecisionTypes, t]);

  useEffect(() => {
    const handleScroll = () => {
      if (
        window.innerHeight + document.documentElement.scrollTop >= 
        document.documentElement.offsetHeight - 1000 && 
        pagination && 
        pagination.has_next && 
        !loadingMore &&
        !loading
      ) {
        loadMoreDecisions();
      }
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, [pagination, loadingMore, loading, loadMoreDecisions]);

  // Handlers
  const handleMonthRangeChange = (startIndex, endIndex) => {
    if (!dynamicDateUtils) return;
    
    setMonthRange({ startIndex, endIndex });
    setTimeRange({
      startDate: dynamicDateUtils.indexToDateString(startIndex),
      endDate: dynamicDateUtils.indexToDateString(endIndex, true)
    });
  };

  const handleDecisionTypeToggle = (typeUid, isChecked) => {
    const newTypes = isChecked 
      ? [...selectedDecisionTypes, typeUid]
      : selectedDecisionTypes.filter(uid => uid !== typeUid);
    
    setSelectedDecisionTypes(newTypes);
    updateUrlParams({ types: newTypes });
  };

  const handleAmountFilterChange = (field, value) => {
    const newAmountFilters = {
      ...amountFilters,
      [field]: value
    };
    setAmountFilters(newAmountFilters);
    updateUrlParams({ [field]: value });
  };

  const handleSortChange = (newSort) => {
    setSortBy(newSort);
    updateUrlParams({ sort: newSort });
  };

  const handleSearchChange = (newSearch) => {
    setSearchQuery(newSearch);
    updateUrlParams({ search: newSearch });
  };

  const handleOrganizationFilterChange = (orgUid, isChecked) => {
    const newOrgs = isChecked
      ? [...organizationFilters, orgUid]
      : organizationFilters.filter(uid => uid !== orgUid);
    
    setOrganizationFilters(newOrgs);
    updateUrlParams({ orgs: newOrgs });
  };

  const clearAllFilters = () => {
    setSelectedDecisionTypes([]);
    setAmountFilters({ minAmount: '', maxAmount: '' });
    setSearchQuery('');
    setOrganizationFilters([]);
    updateUrlParams({ 
      types: [], 
      orgs: [], 
      minAmount: '', 
      maxAmount: '', 
      search: '' 
    });
  };

  const formatSliderValue = useCallback((value) => {
    if (!dynamicDateUtils) return '';
    return dynamicDateUtils.formatMonth(value);
  }, [dynamicDateUtils]);

  // Calculate active filters count
  const activeFiltersCount = selectedDecisionTypes.length + 
    (amountFilters.minAmount ? 1 : 0) + 
    (amountFilters.maxAmount ? 1 : 0) +
    (searchQuery ? 1 : 0);

  // Loading states
  if (dateRangeLoading || loading) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <h2>{t('entityDetail.loadingEntity', { entityType })}</h2>
        <div>{t('entityDetail.loadingData', { entityId })}</div>
      </div>
    );
  }

  // No data state
  if (entityDateRange && !entityDateRange.has_data) {
    return (
      <div style={{ padding: '20px' }}>
        <button onClick={() => navigate('/dev')} className="back-button">
          {t('entityDetail.backToOrgChart')}
        </button>
        
        <div style={{ 
          backgroundColor: '#fff3cd', 
          border: '1px solid #ffeaa7',
          borderRadius: '6px',
          padding: '20px',
          marginTop: '20px',
          textAlign: 'center'
        }}>
          <h2>{t('entityDetail.noDataAvailable')}</h2>
          <p>{entityDateRange.message}</p>
          <p>{t('entityDetail.entityLabel', { entityType, entityId })}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '20px' }}>
        <div style={{ 
          backgroundColor: '#ffe6e6', 
          border: '1px solid #ff9999',
          borderRadius: '4px',
          padding: '15px',
          marginBottom: '20px'
        }}>
          <strong>{t('common.error')}:</strong> {error}
        </div>
        <button onClick={() => navigate('/dev')}>
          {t('entityDetail.backToOrgChart')}
        </button>
      </div>
    );
  }

  const pageInfo = getPageInfo();

  return (
    <div className="entity-detail-page">
      <div className="entity-header">
        <div className="header-actions">
          {/* Organization Chart Button for organization entities */}
          {entityType === 'organization' && explorationMode !== 'temporal' && (
            <button 
              onClick={handleViewOrganizationChart}
              className="org-chart-button"
              title={t('entityDetail.viewOrganizationChart')}
            >
              🏢 {t('entityDetail.viewOrganizationChart')}
            </button>
          )}
        </div>
        
        <div className="page-breadcrumb">{pageInfo.breadcrumb}</div>
        
        <h1 className="entity-title">{pageInfo.title}</h1>
        <div className="entity-subtitle">{pageInfo.subtitle}</div>
        
        {/* Signer Organizations and Positions - Collapsible */}
        {entityType === 'signer' && entityData?.metadata?.organizations && (
          <details 
            className="signer-organizations-section collapsible-section"
            open={isOrganizationsExpanded}
            onToggle={(e) => setIsOrganizationsExpanded(e.target.open)}
          >
            <summary className="section-summary">
              <span className="summary-title">
                {t('entityDetail.organizationsAndPositions')}
              </span>
              <span className="summary-count">
                ({entityData.metadata.total_organizations} {t('entityDetail.organizationsCountLabel')}, {entityData.metadata.total_positions} {t('entityDetail.positionsCountLabel')})
              </span>
              <span className="toggle-icon">
                {isOrganizationsExpanded ? '▼' : '▶'}
              </span>
            </summary>
            
            <div className="section-content">
              <div className="organizations-grid">
                {entityData.metadata.organizations.map((orgData, index) => (
                  <div key={orgData.organization.uid} className="organization-card">
                    <div className="org-header">
                      <button 
                        className="org-name clickable-entity"
                        onClick={() => navigate(`/entity/organization/${orgData.organization.uid}`)}
                        title={t('entityDetail.viewOrganizationDetails')}
                      >
                        🏢 {orgData.organization.label}
                      </button>
                      {orgData.decision_count && (
                        <span className="decision-count">
                          — {t('entityDetail.decisionsCount', { count: orgData.decision_count })}
                        </span>
                      )}
                    </div>
                    
                    {orgData.positions && orgData.positions.length > 0 && (
                      <div className="positions-list">
                        <span className="positions-label">{t('entityDetail.positions')}:</span>
                        <div className="positions-tags">
                          {orgData.positions.map((position, posIndex) => (
                            <div 
                              key={position.uid} 
                              className={`position-tag ${position.status.toLowerCase()}`}
                            >
                              <span className="position-title">{position.label}</span>
                              {position.unit && (
                                <span className="position-unit">• {position.unit}</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    {orgData.latest_decision && (
                      <div className="org-activity">
                        <span className="activity-label">{t('entityDetail.lastActivity')}:</span>
                        <span className="activity-date">
                          {new Date(orgData.latest_decision).toLocaleDateString('en-GB', {
                            day: '2-digit',
                            month: '2-digit',
                            year: 'numeric'
                          })}
                        </span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </details>
        )}
        
        {/* Enhanced time range - Collapsible */}
        {dynamicDateUtils && monthRange && (
          <details 
            className="time-range-container collapsible-section"
            open={isTimeRangeExpanded}
            onToggle={(e) => setIsTimeRangeExpanded(e.target.open)}
          >
            <summary className="section-summary">
              <span className="summary-title">
                {t('entityDetail.timeRange')}
              </span>
              <span className="summary-count">
                {explorationMode === 'temporal' ? t('exploration.globalData') : t('exploration.entityData')} — {t('exploration.availableDataShort', {
                  days: entityDateRange.date_range.span_days
                })}
              </span>
              <span className="toggle-icon">
                {isTimeRangeExpanded ? '▼' : '▶'}
              </span>
            </summary>
            
            <div className="section-content">
              <div className="time-range-header">
                <span className="date-span-info">
                  {t('exploration.availableData', {
                    start: entityDateRange.date_range.earliest,
                    end: entityDateRange.date_range.latest,
                    days: entityDateRange.date_range.span_days
                  })}
                </span>
              </div>
              
              <DualRangeSlider
                min={0}
                max={dynamicDateUtils.totalMonths - 1}
                startValue={monthRange.startIndex}
                endValue={monthRange.endIndex}
                onChange={handleMonthRangeChange}
                label={t('entityDetail.selectTimePeriod')}
                formatValue={formatSliderValue}
                activityData={entityDateRange.activity_chart}
              />
            </div>
          </details>
        )}
      </div>

      {/* Enhanced Statistics Cards for both modes */}
      {statistics && (
        <div className="statistics-grid">
          <div className="stat-card">
            <h3 className="stat-title">{t('statistics.totalDecisions')}</h3>
            <div className="stat-value">
              {statistics.summary.decisions.total_count.toLocaleString()}
            </div>
            {explorationMode === 'temporal' && (
              <div className="stat-context">
                {t('entityDetail.acrossOrganizations', { count: temporalSummary?.organizations_count || 0 })}
              </div>
            )}
          </div>

          <div className="stat-card">
            <h3 className="stat-title">{t('statistics.totalAmount')}</h3>
            <div className="stat-value">
              €{statistics.summary.financial.primary_amount.toLocaleString(undefined, { 
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
              })}
            </div>
            {statistics.summary.financial.has_discrepancy && (
              <div className="discrepancy-warning">
                {t('statistics.amountDiscrepancy', { percentage: statistics.summary.financial.discrepancy_percentage })}
              </div>
            )}
          </div>

          <div className="stat-card">
            <h3 className="stat-title">{t('statistics.averageAmount')}</h3>
            <div className="stat-value">
              €{statistics.summary.decisions.avg_amount.toLocaleString(undefined, { 
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
              })}
            </div>
          </div>

          <div className="stat-card">
            <h3 className="stat-title">{t('statistics.period')}</h3>
            <div className="stat-period">
              {t('statistics.days', { count: statistics.period.days_count })}
            </div>
            <div className="stat-date-range">
              {new Date(statistics.period.start_date).toLocaleDateString()} - {new Date(statistics.period.end_date).toLocaleDateString()}
            </div>
          </div>
        </div>
      )}

      {/* Enhanced Filters Section for both modes */}
      <div className="decisions-section">
        <div className="decisions-header">
          <h3 className="decisions-title">
            {explorationMode === 'temporal' ? t('entityDetail.allDecisions') : t('entityDetail.entityDecisions')}
          </h3>
          
          <div className="controls-container">
            <div className="search-container">
              <label className="search-label">{t('entityDetail.search')}:</label>
              <div className="search-input-wrapper">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => handleSearchChange(e.target.value)}
                  placeholder={t('entityDetail.searchInDecisions')}
                  className="search-input"
                />
                {searchQuery && (
                  <button onClick={() => handleSearchChange('')} className="clear-button">
                    ×
                  </button>
                )}
              </div>
            </div>
            
            <div className="sort-container">
              <label className="sort-label">{t('entityDetail.sortBy')}:</label>
              <select 
                value={sortBy}
                onChange={(e) => handleSortChange(e.target.value)}
                className="sort-select"
              >
                <option value="recent">{t('exploration.recent')}</option>
                <option value="amount_desc">{t('exploration.amountDesc')}</option>
              </select>
            </div>
          </div>
        </div>

        <div className="filters-section">
          <div className="filters-header">
            <button 
              onClick={() => setShowDecisionTypeFilter(!showDecisionTypeFilter)}
              className="filter-toggle-button"
            >
              🔍 {t('entityDetail.filters')} {activeFiltersCount > 0 && `(${activeFiltersCount})`}
            </button>
            
            {activeFiltersCount > 0 && (
              <button onClick={clearAllFilters} className="clear-filters-button">
                {t('entityDetail.clearAllFilters')}
              </button>
            )}
          </div>

          {showDecisionTypeFilter && (
            <div className="filters-panel">
              {/* Amount Filters */}
              <div className="filter-group">
                <h4>{t('entityDetail.amountRange')}</h4>
                <div className="amount-filters">
                  <input
                    type="number"
                    placeholder={t('entityDetail.minAmountPlaceholder')}
                    value={amountFilters.minAmount}
                    onChange={(e) => handleAmountFilterChange('minAmount', e.target.value)}
                    className="amount-input"
                  />
                  <span className="amount-separator">{t('entityDetail.amountTo')}</span>
                  <input
                    type="number"
                    placeholder={t('entityDetail.maxAmountPlaceholder')}
                    value={amountFilters.maxAmount}
                    onChange={(e) => handleAmountFilterChange('maxAmount', e.target.value)}
                    className="amount-input"
                  />
                </div>
              </div>

              {/* Decision Type Filters */}
              <div className="filter-group">
                <h4>{t('entityDetail.decisionTypes')}</h4>
                {decisionTypesLoading ? (
                  <div className="loading-text">{t('entityDetail.loadingDecisionTypes')}</div>
                ) : (
                  <div className="decision-types-grid">
                    {availableDecisionTypes.map(type => (
                      <label key={type.uid} className="decision-type-checkbox">
                        <input
                          type="checkbox"
                          checked={selectedDecisionTypes.includes(type.uid)}
                          onChange={(e) => handleDecisionTypeToggle(type.uid, e.target.checked)}
                        />
                        <span className="checkbox-content">
                          <span className="type-label">{type.label}</span>
                          <span className="type-stats">
                            {t('entityDetail.decisionTypesCount', { 
                              count: type.count, 
                              amount: type.total_amount.toLocaleString() 
                            })}
                          </span>
                        </span>
                      </label>
                    ))}
                  </div>
                )}
              </div>

              {/* Organization Filters - only for temporal mode */}
              {explorationMode === 'temporal' && (
                <div className="filter-group">
                  <h4>{t('entityDetail.organizations')}</h4>
                  {/* Add organization filter UI */}
                </div>
              )}
            </div>
          )}
        </div>
        
        {/* Search Results Info */}
        {searchQuery && (
          <div className="search-results-info">
            <span className="search-results-bold">
              {t('entityDetail.searchResultsFor')} "{searchQuery}"
            </span>
            {pagination && (
              <span className="search-results-count">
                {t('entityDetail.resultsFound', { count: pagination.total_count })}
              </span>
            )}
          </div>
        )}

        {/* Active Filters Display */}
        {activeFiltersCount > 0 && (
          <div className="active-filters">
            <span className="filters-label">{t('entityDetail.activeFilters')}</span>
            {selectedDecisionTypes.map(typeUid => {
              const type = availableDecisionTypes.find(t => t.uid === typeUid);
              return (
                <span key={typeUid} className="filter-tag">
                  {type?.label || typeUid}
                  <button onClick={() => handleDecisionTypeToggle(typeUid, false)}>×</button>
                </span>
              );
            })}
            {amountFilters.minAmount && (
              <span className="filter-tag">
                {t('entityDetail.minAmountFilter', { amount: amountFilters.minAmount })}
                <button onClick={() => handleAmountFilterChange('minAmount', '')}>×</button>
              </span>
            )}
            {amountFilters.maxAmount && (
              <span className="filter-tag">
                {t('entityDetail.maxAmountFilter', { amount: amountFilters.maxAmount })}
                <button onClick={() => handleAmountFilterChange('maxAmount', '')}>×</button>
              </span>
            )}
          </div>
        )}

    

        {decisions.length > 0 ? (
          <div>
            {decisions.map((decision, index) => (
              <DecisionCard
                key={decision.ada}
                decision={decision}
                formatAmount={formatAmount}
                index={index}
                isLastItem={index === decisions.length - 1}
                onViewDocumentContent={handleViewDocumentContent}
              />
            ))}
            
            {loadingMore && (
              <div className="loading-more-container">
                <div className="loading-more-text">
                  {t('entityDetail.loadingMoreDecisions')}
                </div>
              </div>
            )}
            
            {pagination && (
              <div className="pagination-info">
                {t('entityDetail.showingDecisions', { 
                  current: decisions.length, 
                  total: pagination.total_count 
                })}
              </div>
            )}
          </div>
        ) : (
          <div className="no-decisions-message">
            {t('entityDetail.noDecisionsFound')}
          </div>
        )}

        {pagination && pagination.has_next && (
          <div className="load-more-container">
            <button 
              onClick={loadMoreDecisions}
              disabled={loadingMore}
              className={`load-more-button ${loadingMore ? 'loading' : ''}`}
            >
              {loadingMore ? 
                t('entityDetail.loadingMoreButton') : 
                t('entityDetail.loadMoreButton', { remaining: pagination.total_count - decisions.length })
              }
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default EntityDetailPage;