import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../contexts/TranslationContext';
import apiClient from '../api/client';
import './DecisionCard.css';
import EntityDisplay from './EntityDisplay';

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

  return (
    <div className={`decision-card ${isLastItem ? 'last-item' : ''}`}>
      <div className="decision-header">
        <div className="decision-content">
          {/* Make ADA clickable */}
          <div className="decision-ada">
            <span className="ada-label">ADA: </span>
            <button 
              className="ada-link clickable-entity"
              onClick={handleAdaClick}
              title={t('decisionCard.viewDecisionDetails')}
            >
              {decision.ada}
            </button>
          </div>
          <div className="decision-subject">
            {decision.subject}
          </div>
          
          {/* Organization Information - Clickable */}
          {decision.organization && (
            <div className="decision-organization">
              <span className="organization-label">{t('decisionCard.organization')}:</span>
              <button 
                className="organization-name clickable-entity"
                onClick={() => handleOrganizationClick(decision.organization.uid)}
                title={t('decisionCard.viewOrganizationDetails')}
              >
                {decision.organization.label}
              </button>
            </div>
          )}

          {/* Signers Information - Clickable */}
          {decision.signers && decision.signers.length > 0 && (
            <div className="decision-signers">
              <span className="signers-label">
                {decision.signers.length === 1 ? t('decisionCard.signer') : t('decisionCard.signers')}:
              </span>
              <div className="signers-list">
                {decision.signers.map((signer, signerIndex) => (
                  <span key={signer.uid || signerIndex}>
                    <button 
                      className="signer-name clickable-entity"
                      onClick={() => handleSignerClick(signer.uid)}
                      title={t('decisionCard.viewSignerDetails')}
                    >
                      {signer.first_name} {signer.last_name}
                    </button>
                    {signerIndex < decision.signers.length - 1 && <span className="signer-separator">, </span>}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
        
        <span className={`status-badge ${decision.status.toLowerCase()}`}>
          {decision.status}
        </span>
      </div>

      <div className="decision-amounts">
        <div className="amount-item">
          <div className="amount-label">{t('decisionCard.primaryAmount')}</div>
          <div className={`amount-value ${hasAmountDiscrepancy ? 'discrepancy' : ''}`}>
            {formatAmount(primaryAmount)}
          </div>
        </div>

        {kaeTotal !== null && (
          <div className="amount-item">
            <div className="amount-label">
              {t('decisionCard.kaeTotal', { count: decision.kae_amounts?.length || 0 })}
            </div>
            <div className={`amount-value ${hasAmountDiscrepancy ? 'discrepancy' : ''}`}>
              {formatAmount(kaeTotal)}
            </div>
          </div>
        )}

        <div className="amount-item">
          <div className="amount-label">{t('decisionCard.issueDate')}</div>
          <div className="date-value">
            {new Date(decision.issue_date).toLocaleDateString('en-GB', {
              day: '2-digit',
              month: '2-digit',
              year: 'numeric'
            })}
          </div>
        </div>
      </div>

      {hasAmountDiscrepancy && (
        <div className="discrepancy-warning">
          <div className="warning-title">
            ⚠️ {t('decisionCard.amountDiscrepancyDetected')}
          </div>
          <div className="warning-text">
            {t('decisionCard.amountDiscrepancyText', { percentage: decision.discrepancy_percentage })}
          </div>
        </div>
      )}

      {/* Document Actions Section */}
      <div className="document-actions">
        {decision.document_url && (
          <a 
            href={decision.document_url}
            target="_blank"
            rel="noopener noreferrer"
            className="document-link original"
          >
            📄 {t('decisionCard.viewOriginalDocument')}
            <span className="external-icon">↗</span>
          </a>
        )}

        {decision.has_document_content && (
          <button 
            onClick={handleViewContent}
            disabled={isLoadingContent}
            className="document-link content-button"
          >
            {isLoadingContent ? (
              <>
                ⏳ {t('common.loading')}
              </>
            ) : (
              <>
                📋 {showContent ? t('decisionCard.hideDocumentContent') : t('decisionCard.viewDocumentContent')}
              </>
            )}
          </button>
        )}

        <button 
          onClick={handleViewEntities}
          disabled={loadingEntities}
          className="document-link entities-button"
          title={t('decisionCard.viewRelatedEntities')}
        >
          {loadingEntities ? (
            <>
              ⏳ {t('common.loading')}
            </>
          ) : (
            <>
              🏢 {showEntities ? t('decisionCard.hideRelatedEntities') : t('decisionCard.viewRelatedEntities')}
            </>
          )}
        </button>

        {/* NEW: Quick link to full decision details */}
        <button 
          onClick={handleAdaClick}
          className="document-link decision-detail-button"
          title={t('decisionCard.viewDecisionDetails')}
        >
          🔍 {t('decisionCard.viewFullDetails')}
        </button>
      </div>

      {/* Document Content Display */}
      {showContent && documentContent && (
        <details className="document-content-section" open>
          <summary className="content-summary">
            {t('decisionCard.documentContentSummary', { provider: documentContent.provider || t('common.unknown') })}
          </summary>
          <div className="document-content">
            <div className="content-metadata">
              <span className="content-info">
                {t('decisionCard.extracted')}: {documentContent.extraction_date ? 
                  new Date(documentContent.extraction_date).toLocaleDateString('en-GB', {
                    day: '2-digit',
                    month: '2-digit',
                    year: 'numeric'
                  }) : t('common.unknown')}
              </span>
              {documentContent.character_count && (
                <span className="content-info">
                  {t('decisionCard.characters')}: {documentContent.character_count.toLocaleString()}
                </span>
              )}
              {documentContent.page_count && (
                <span className="content-info">
                  {t('decisionCard.pages')}: {documentContent.page_count}
                </span>
              )}
            </div>
            <div className="raw-text-container">
              <pre className="raw-text">{documentContent.raw_text}</pre>
            </div>
          </div>
        </details>
      )}

      {/* Entity Relationships Display */}
      {showEntities && entityRelationships && (
                <details className="entities-content-section" open>
          <summary className="entities-summary">
            {t('decisionCard.relatedEntitiesSummary', { 
              count: entityRelationships.total_entities || entityRelationships.relationships?.length || 0 
            })}
          </summary>
          <div className="entities-content">
            <EntityDisplay 
              entityRelationships={entityRelationships.relationships}
              showRoleBadge={true}
              compact={true}
              className="decision-card-entities"
            />
          </div>
        </details>
      )
      }

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

      {/* NEW: Entity Relationships Section */}
      <div className="entity-relationships">
        <div className="section-header" onClick={handleViewEntities} role="button" tabIndex={0}>
          <h3 className="section-title">
            {t('decisionCard.entityRelationships')}
          </h3>
          <span className="toggle-icon">
            {showEntities ? '▲' : '▼'}
          </span>
        </div>

        {showEntities && (
          <div className="section-content">
            {loadingEntities ? (
              <div className="loading-spinner">
                ⏳ {t('common.loading')}
              </div>
            ) : (
              <div className="entities-list">
                {entityRelationships && entityRelationships.length > 0 ? (
                  entityRelationships.map((entity, index) => (
                    <div key={entity.afm} className={`entity-item ${index < entityRelationships.length - 1 ? 'has-border' : ''}`}>
                      <div className="entity-info">
                        <span className="entity-label">{t('decisionCard.entity')}:</span>
                        <span className="entity-value">{entity.entity_name}</span>
                      </div>
                      <div className="entity-actions">
                        <button 
                          onClick={() => handleEntityClick(entity.afm)}
                          className="entity-link"
                          title={t('decisionCard.viewEntityDetails')}
                        >
                          {t('decisionCard.viewDetails')}
                        </button>
                        {entity.company_id && (
                          <button 
                            onClick={() => handleCompanyClick(entity.company_id)}
                            className="company-link"
                            title={t('decisionCard.viewCompanyDetails')}
                          >
                            {t('decisionCard.viewCompany')}
                          </button>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="no-entities">
                    {t('decisionCard.noEntityRelationships')}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default DecisionCard;