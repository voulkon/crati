import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../contexts/TranslationContext';
import apiClient from '../api/client';
import SuperSearch from '../components/SuperSearch';
import TopRelationshipPairs from '../components/TopRelationshipPairs';
import './HomePage.css';

const HomePage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [topOrganizations, setTopOrganizations] = useState([]);
  const [recentDecisions, setRecentDecisions] = useState([]);
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
          organizationsResponse,
          decisionsResponse
        ] = await Promise.all([
          // Top organizations this week
          apiClient.get(`/explore/organizations/?start_date=${weekAgo}&end_date=${today}&limit=6`),
          
          // Get recent high-value decisions using optimized endpoint
          apiClient.get(
            `/explore/decisions-optimized/?start_date=${weekAgo}&end_date=${today}&sort_by=entity_amount_desc&page_size=5`
          )
        ]);

        setTopOrganizations(organizationsResponse.data.organizations || []);
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
            
            {/* Super Search Component - Enhanced as main feature */}
            <div className="hero-search-enhanced">
              <SuperSearch
                placeholder="Search organizations, documents, companies, signers..."
                autoFocus={false}
                showFullResults={true}
                className="homepage-super-search"
              />
            </div>
          </div>
        </section>

        {/* Top Org×Entity Relationships - Full Width */}
        <TopRelationshipPairs 
          dateRange={{
            start_date: weekAgo,
            end_date: today
          }}
          limit={6}
        />

        {/* Two Column Grid: Organizations & Decisions */}
        <div className="data-grid">
          {/* Top Organizations */}
          <section className="data-section">
            <div className="section-header">
              <h2 className="section-title">{t('homepage.mostActiveOrganizations')}</h2>
              <button 
                className="see-all-button"
                onClick={() => navigate(`/explore/temporal/${weekAgo}/${today}`)}
              >
                {t('homepage.seeAll')} →
              </button>
            </div>
            <div className="organizations-list">
              {topOrganizations.slice(0, 5).map((org, index) => (
                <div 
                  key={org.uid}
                  className="organization-card compact"
                  onClick={() => navigate(`/entity/organization/${org.uid}`)}
                >
                  <div className="card-rank">#{index + 1}</div>
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
          <section className="data-section">
            <div className="section-header">
              <h2 className="section-title">{t('homepage.notableRecentDecisions')}</h2>
              <button 
                className="see-all-button"
                onClick={() => navigate(`/explore/temporal/${weekAgo}/${today}?sort_by=amount_desc`)}
              >
                {t('homepage.seeAll')} →
              </button>
            </div>
            <div className="decisions-list compact">
              {recentDecisions.slice(0, 5).map((decision, index) => (
                <div 
                  key={decision.ada} 
                  className="decision-item compact clickable"
                  onClick={() => navigate(`/decision/${decision.ada}`)}
                >
                  <div className="card-rank">#{index + 1}</div>
                  <div className="decision-content">
                    <div className="decision-subject">
                      {decision.subject.length > 80 
                        ? `${decision.subject.substring(0, 80)}...` 
                        : decision.subject
                      }
                    </div>
                    <div className="decision-meta">
                      <span className="decision-org">
                        {decision.organization?.label && decision.organization.label.length > 40
                          ? `${decision.organization.label.substring(0, 40)}...`
                          : decision.organization?.label
                        }
                      </span>
                    </div>
                    <div className="decision-amount-compact">
                      {formatAmount(decision.amount)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>

      </div>
    </div>
  );
};

export default HomePage;