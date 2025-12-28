import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../contexts/TranslationContext';
import apiClient from '../api/client';
import './DecisionCard.css';
import EntityDisplay from './EntityDisplay';

const OrganizationIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="metadata-icon">
    <path d="M3 21h18M5 21V7l8-4 8 4v14M9 10a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v11H9V10z" />
  </svg>
);

const PenIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="metadata-icon">
    <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path>
  </svg>
);

const CalendarIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="metadata-icon">
    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
    <line x1="16" y1="2" x2="16" y2="6"></line>
    <line x1="8" y1="2" x2="8" y2="6"></line>
    <line x1="3" y1="10" x2="21" y2="10"></line>
  </svg>
);

const DecisionCard = ({ decision, formatAmount, index, isLastItem, onViewDocumentContent }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [isLoadingContent, setIsLoadingContent] = useState(false);
  const [documentContent, setDocumentContent] = useState(null);
  const [showContent, setShowContent] = useState(false);
  const [entityRelationships, setEntityRelationships] = useState(null);
  const [showEntities, setShowEntities] = useState(false);
  const [loadingEntities, setLoadingEntities] = useState(false);

  const kaeTotal = decision.kae_total;
  const primaryAmount = decision.amount;
  const hasAmountDiscrepancy = decision.has_amount_discrepancy;
  
  // Check if entity data is already included in decision (from optimized endpoint)
  const hasPreloadedEntityData = decision.entity_amount !== undefined || decision.main_recipient !== undefined;
  
  const handleViewContent = async () => {
    if (documentContent) {
      setShowContent(!showContent);
      return;
    }

    if (!onViewDocumentContent) {
      console.error('onViewDocumentContent function not provided');
      return;
    }

    setIsLoadingContent(true);
    try {
      const content = await onViewDocumentContent(decision.id);
      setDocumentContent(content);
      setShowContent(true);
    } catch (error) {
      console.error('Failed to fetch document content:', error);
    } finally {
      setIsLoadingContent(false);
    }
  };

  const handleViewEntities = async () => {
    if (entityRelationships) {
      setShowEntities(!showEntities);
      return;
    }

    setLoadingEntities(true);
    try {
      const response = await apiClient.get(`/decisions/${decision.id}/entities/`);
      
      // Group relationships by role and entity AFM
      const groupedRelationships = {};
      
      response.data.relationships.forEach(rel => {
        const key = `${rel.role}-${rel.entity.afm}`;
        
        if (!groupedRelationships[key]) {
          groupedRelationships[key] = {
            ...rel,
            occurrences: 1,
            parent_key_paths: [rel.parent_key_path]
          };
        } else {
          groupedRelationships[key].occurrences += 1;
          groupedRelationships[key].parent_key_paths.push(rel.parent_key_path);
        }
      });
      
      const processedData = {
        ...response.data,
        relationships: Object.values(groupedRelationships)
      };
      
      setEntityRelationships(processedData);
      setShowEntities(true);
    } catch (error) {
      console.error('Failed to fetch entity relationships:', error);
    } finally {
      setLoadingEntities(false);
    }
  };

  const handleOrganizationClick = (organizationUid) => {
    navigate(`/entity/organization/${organizationUid}`);
  };

  const handleSignerClick = (signerUid) => {
    navigate(`/entity/signer/${signerUid}`);
  };

  const handleEntityClick = (afm) => {
    navigate(`/entity/afm/${afm}`);
  };

  const handleCompanyClick = (company) => {
    // Navigate to the AFM entity page for this company
    navigate(`/entity/afm/${company.afm}`);
  };

  // NEW: Handle ADA click to navigate to decision detail page
  const handleAdaClick = () => {
    navigate(`/decision/${decision.id}`);
  };

  // Auto-load entities on mount (only if not preloaded)
  useEffect(() => {
    if (!hasPreloadedEntityData && !entityRelationships && !loadingEntities) {
      handleViewEntities();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Get the main recipient/sponsor with amount
  const getMainRecipient = () => {
    // If we have preloaded data from optimized API, use it
    if (hasPreloadedEntityData && decision.main_recipient) {
      return {
        entity: {
          afm: decision.main_recipient.afm,
          name: decision.main_recipient.name,
        },
        total_amount: decision.main_recipient.amount,
      };
    }
    
    // Otherwise use loaded entity relationships
    if (!entityRelationships?.relationships) return null;
    
    // First try to find sponsor or creditor with amount
    let recipient = entityRelationships.relationships.find(rel => 
      (rel.role?.toLowerCase().includes('sponsor') || rel.role?.toLowerCase().includes('creditor')) 
      && rel.total_amount
    );
    
    // If no sponsor/creditor found, try to find ANY entity with an amount (excluding org which is usually 0)
    if (!recipient) {
      recipient = entityRelationships.relationships.find(rel => 
        rel.total_amount && rel.role?.toLowerCase() !== 'org'
      );
    }
    
    return recipient;
  };

  const mainRecipient = getMainRecipient();
  
  // Calculate total amount from all entities if no main recipient
  const getTotalAmount = () => {
    // If we have preloaded entity amount, use it
    if (hasPreloadedEntityData && decision.entity_amount) {
      return decision.entity_amount;
    }
    
    if (mainRecipient?.total_amount) return mainRecipient.total_amount;
    
    if (entityRelationships?.relationships) {
      const total = entityRelationships.relationships
        .filter(rel => rel.role?.toLowerCase() !== 'org') // Exclude org amounts
        .reduce((sum, rel) => {
          return sum + (rel.total_amount || 0);
        }, 0);
      if (total > 0) return total;
    }
    
    return decision.amount || null;
  };

  const displayAmount = getTotalAmount();

  return (
    <div className={`decision-card ${isLastItem ? 'last-item' : ''}`}>
      {/* Clickable Title */}
      <button 
        className="decision-subject clickable-title"
        onClick={handleAdaClick}
        title={t('decisionCard.viewDecisionDetails')}
      >
        {decision.subject}
      </button>

      {/* Simple recipient and amount display */}
      <div className="decision-main-info">
        {loadingEntities ? (
          <div className="loading-state">⏳ {t('common.loading')}</div>
        ) : (
          <>
            <div className="info-content">
              {mainRecipient && (
                <div className="recipient-display">
                  <span className="recipient-arrow">→</span>
                  <button
                    className="recipient-name"
                    onClick={() => handleEntityClick(mainRecipient.entity.afm)}
                    title={t('decisionCard.viewEntityDetails')}
                  >
                    {mainRecipient.entity.name}
                  </button>
                </div>
              )}
              <div className="amount-display">
                {formatAmount(displayAmount)}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Organization and Signers Metadata */}
      <div className="decision-metadata">
        {decision.organization && (
          <div className="metadata-row metadata-org" title={t('decisionCard.organization')}>
            <OrganizationIcon />
            <button 
              className="metadata-value clickable"
              onClick={(e) => {
                e.stopPropagation();
                handleOrganizationClick(decision.organization.uid);
              }}
            >
              {decision.organization.label}
            </button>
          </div>
        )}
        
        {decision.signers && decision.signers.length > 0 && (
          <div className="metadata-row metadata-signer" title={decision.signers.length > 1 ? t('decisionCard.signers') : t('decisionCard.signer')}>
            <PenIcon />
            {decision.signers.map((signer, idx) => (
              <React.Fragment key={signer.uid}>
                {idx > 0 && <span className="separator">, </span>}
                <button 
                  className="metadata-value clickable"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleSignerClick(signer.uid);
                  }}
                >
                  {signer.first_name} {signer.last_name}
                </button>
              </React.Fragment>
            ))}
          </div>
        )}

        <div className="metadata-row metadata-date" title={t('decisionCard.issueDate')}>
          <CalendarIcon />
          <span className="metadata-value">
            {new Date(decision.issue_date).toLocaleDateString('en-GB', {
              day: '2-digit',
              month: '2-digit',
              year: 'numeric'
            })}
          </span>
        </div>
      </div>

      {/* Document Actions Section - Compact */}
      <div className="document-actions">
        {decision.document_url && (
          <a 
            href={decision.document_url}
            target="_blank"
            rel="noopener noreferrer"
            className="document-link original"
            title={t('decisionCard.viewOriginalDocument')}
          >
            📄 {t('decisionCard.viewOriginalDocument')}
          </a>
        )}

        {decision.has_document_content && (
          <button 
            onClick={handleViewContent}
            disabled={isLoadingContent}
            className="document-link content-button"
            title={showContent ? t('decisionCard.hideDocumentContent') : t('decisionCard.viewDocumentContent')}
          >
            {isLoadingContent ? '⏳' : showContent ? '⬆️' : '⬇️'} {showContent ? t('decisionCard.hideText') : t('decisionCard.showText')}
          </button>
        )}
      </div>

      {/* Document Content Display */}
      {showContent && documentContent && (
        <div className="document-content-section">
          <div className="document-content">
            <div className="raw-text-container">
              <pre className="raw-text">{documentContent.raw_text}</pre>
            </div>
          </div>
        </div>
      )}

      {decision.kae_amounts && decision.kae_amounts.length > 1 && (
        <details className="kae-breakdown">
          <summary className="kae-summary">
            {t('decisionCard.viewKaeBreakdown', { count: decision.kae_amounts.length })}
          </summary>
          <div className="kae-content">
            {decision.kae_amounts.map((kae, kaeIndex) => (
              <div 
                key={kaeIndex}
                className={`kae-item ${kaeIndex < decision.kae_amounts.length - 1 ? 'has-border' : ''}`}
              >
                <span className="kae-code">KAE: {kae.kae}</span>
                <span className="kae-amount">{formatAmount(kae.amount)}</span>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
};

export default DecisionCard;