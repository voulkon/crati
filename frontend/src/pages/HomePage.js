import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../contexts/TranslationContext';
import apiClient from '../api/client';
import SuperSearch from '../components/SuperSearch';
import './HomePage.css';

const HomePage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [todayStats, setTodayStats] = useState(null);
  const [weeklyTrends, setWeeklyTrends] = useState(null);
  const [topOrganizations, setTopOrganizations] = useState([]);
  const [recentDecisions, setRecentDecisions] = useState([]);
  const [systemStats, setSystemStats] = useState(null);
  const [loading, setLoading] = useState(true);

  // Get today's date for API calls
  const today = new Date().toISOString().split('T')[0];
  const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        setLoading(true);

        // Parallel API calls for dashboard data
        const [
          todayResponse,
          weekResponse,
          organizationsResponse,
          systemResponse
        ] = await Promise.all([
          // Today's statistics
          apiClient.get(`/explore/statistics/?start_date=${today}&end_date=${today}`),
          
          // Weekly trend
          apiClient.get(`/explore/statistics/?start_date=${weekAgo}&end_date=${today}`),
          
          // Top organizations this week
          apiClient.get(`/explore/organizations/?start_date=${weekAgo}&end_date=${today}&limit=6`),
          
          // System overview
          apiClient.get('/explore/date-range/')
        ]);

        setTodayStats(todayResponse.data);
        setWeeklyTrends(weekResponse.data);
        setTopOrganizations(organizationsResponse.data.organizations || []);
        setSystemStats(systemResponse.data);

        // Get recent high-value decisions
        const decisionsResponse = await apiClient.get(
          `/explore/decisions/?start_date=${weekAgo}&end_date=${today}&sort_by=amount_desc&page_size=5&min_amount=50000`
        );
        setRecentDecisions(decisionsResponse.data.results || []);

      } catch (error) {
        console.error('Failed to load dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };

    loadDashboardData();
  }, [today, weekAgo]);

  const formatAmount = (amount) => {
    if (amount >= 1000000) {
      return `€${(amount / 1000000).toFixed(1)}M`;
    } else if (amount >= 1000) {
      return `€${(amount / 1000).toFixed(0)}K`;
    }
    return `€${amount?.toLocaleString() || 0}`;
  };

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric'
    });
  };

  if (loading) {
    return (
      <div className="homepage-loading">
        <div className="loading-spinner"></div>
        <p>{t('homepage.loading')}</p>
      </div>
    );
  }

  return (
    <div className="homepage">
      <div className="homepage-container">
        {/* Hero Section */}
        <section className="hero-section">
          <div className="hero-content">
            <h1 className="hero-title">
              {t('homepage.title')}
            </h1>
            <p className="hero-subtitle">
              {t('homepage.subtitle')}
            </p>
            
            {/* Super Search Component */}
            <div className="hero-search">
              <SuperSearch
                placeholder="Search organizations, documents, companies, signers..."
                autoFocus={false}
                showFullResults={true}
                className="homepage-super-search"
              />
            </div>
            
            <div className="hero-stats">
              {systemStats && (
                <>
                  <div className="hero-stat">
                    <span className="stat-number">
                      {systemStats.summary?.total_decisions?.toLocaleString() || '0'}
                    </span>
                    <span className="stat-label">{t('homepage.totalDecisions')}</span>
                  </div>
                  <div className="hero-stat">
                    <span className="stat-number">
                      {formatAmount(systemStats.summary?.total_amount || 0)}
                    </span>
                    <span className="stat-label">{t('homepage.totalValue')}</span>
                  </div>
                  <div className="hero-stat">
                    <span className="stat-number">
                      {systemStats.date_range?.span_days || '0'}
                    </span>
                    <span className="stat-label">{t('homepage.daysOfData')}</span>
                  </div>
                </>
              )}
            </div>
          </div>
        </section>

        {/* Today's Highlights */}
        <section className="today-section">
          <h2 className="section-title">{t('homepage.todayActivity')}</h2>
          <div className="highlights-grid">
            <div 
              className="highlight-card clickable"
              onClick={() => navigate(`/explore/temporal/${today}`)}
            >
              <div className="highlight-icon">📊</div>
              <div className="highlight-content">
                <h3 className="highlight-number">
                  {todayStats?.summary?.decisions?.total_count || 0}
                </h3>
                <p className="highlight-label">{t('homepage.newDecisions')}</p>
              </div>
            </div>

            <div 
              className="highlight-card clickable"
              onClick={() => navigate(`/explore/temporal/${today}`)}
            >
              <div className="highlight-icon">💰</div>
              <div className="highlight-content">
                <h3 className="highlight-number">
                  {formatAmount(todayStats?.summary?.financial?.primary_amount || 0)}
                </h3>
                <p className="highlight-label">{t('homepage.totalValue')}</p>
              </div>
            </div>

            <div 
              className="highlight-card clickable"
              onClick={() => navigate(`/explore/temporal/${today}`)}
            >
              <div className="highlight-icon">🏛️</div>
              <div className="highlight-content">
                <h3 className="highlight-number">
                  {todayStats?.summary?.organizations_count || 0}
                </h3>
                <p className="highlight-label">{t('homepage.activeOrganizations')}</p>
              </div>
            </div>

            <div 
              className="highlight-card clickable"
              onClick={() => navigate(`/explore/temporal/${weekAgo}/${today}`)}
            >
              <div className="highlight-icon">📈</div>
              <div className="highlight-content">
                <h3 className="highlight-number">
                  {weeklyTrends?.summary?.decisions?.total_count || 0}
                </h3>
                <p className="highlight-label">{t('homepage.thisWeek')}</p>
              </div>
            </div>
          </div>
        </section>

        {/* Quick Exploration */}
        <section className="exploration-section">
          <h2 className="section-title">{t('homepage.exploreDecisions')}</h2>
          <div className="exploration-grid">
            <div 
              className="exploration-card"
              onClick={() => navigate('/explore/temporal/2025-05-01/2025-05-31')}
            >
              <div className="exploration-icon">📅</div>
              <h3>{t('homepage.thisMonth')}</h3>
              <p>{t('homepage.exploreMay2025')}</p>
            </div>

            <div 
              className="exploration-card"
              onClick={() => navigate('/dev')}
            >
              <div className="exploration-icon">🔍</div>
              <h3>{t('homepage.browseOrganizations')}</h3>
              <p>{t('homepage.searchExploreByOrg')}</p>
            </div>

            <div 
              className="exploration-card"
              onClick={() => navigate('/explore/temporal/2025-01-01/2025-12-31')}
            >
              <div className="exploration-icon">📊</div>
              <h3>{t('homepage.yearOverview')}</h3>
              <p>{t('homepage.analyze2025Trends')}</p>
            </div>

            <div 
              className="exploration-card"
              onClick={() => navigate(`/explore/temporal/${weekAgo}/${today}`)}
            >
              <div className="exploration-icon">⚡</div>
              <h3>{t('homepage.recentActivity')}</h3>
              <p>{t('homepage.last7DaysDecisions')}</p>
            </div>
          </div>
        </section>

        {/* Top Organizations */}
        <section className="organizations-section">
          <div className="section-header">
            <h2 className="section-title">{t('homepage.mostActiveOrganizations')}</h2>
            <button 
              className="see-all-button"
              onClick={() => navigate(`/explore/temporal/${weekAgo}/${today}`)}
            >
              {t('homepage.seeAll')} →
            </button>
          </div>
          <div className="organizations-grid">
            {topOrganizations.slice(0, 6).map((org) => (
              <div 
                key={org.uid}
                className="organization-card"
                onClick={() => navigate(`/entity/organization/${org.uid}`)}
              >
                <div className="org-info">
                  <h4 className="org-name">{org.label}</h4>
                  <div className="org-stats">
                    <span className="org-decisions">{org.count} {t('homepage.decisions')}</span>
                    <span className="org-amount">{formatAmount(org.total_amount)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Recent High-Value Decisions */}
        <section className="decisions-section">
          <div className="section-header">
            <h2 className="section-title">{t('homepage.notableRecentDecisions')}</h2>
            <button 
              className="see-all-button"
              onClick={() => navigate(`/explore/temporal/${weekAgo}/${today}?sort_by=amount_desc`)}
            >
              {t('homepage.seeAll')} →
            </button>
          </div>
          <div className="decisions-list">
            {recentDecisions.slice(0, 5).map((decision) => (
              <div key={decision.ada} className="decision-item">
                <div className="decision-content">
                  <div className="decision-subject">
                    {decision.subject.length > 100 
                      ? `${decision.subject.substring(0, 100)}...` 
                      : decision.subject
                    }
                  </div>
                  <div className="decision-meta">
                    <span className="decision-org">
                      {decision.organization?.label}
                    </span>
                    <span className="decision-date">
                      {formatDate(decision.issue_date)}
                    </span>
                  </div>
                </div>
                <div className="decision-amount">
                  {formatAmount(decision.amount)}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Footer CTA */}
        <section className="cta-section">
          <div className="cta-content">
            <h2>{t('homepage.readyToExplore')}</h2>
            <p>{t('homepage.diveDeepIntoData')}</p>
            <div className="cta-buttons">
              <button 
                className="cta-button primary"
                onClick={() => navigate('/dev')}
              >
                {t('homepage.startExploring')}
              </button>
              <button 
                className="cta-button secondary"
                onClick={() => navigate(`/explore/temporal/${today}`)}
              >
                {t('homepage.todaysDecisions')}
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};

export default HomePage;