import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { streamSearch, getAutocompleteSuggestions } from '../api/searchApi';
import './SuperSearch.css';

const SuperSearch = ({ 
  placeholder = "Search organizations, documents, companies...",
  onResultClick,
  showFullResults = true,
  autoFocus = false,
  className = ""
}) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [autocompleteResults, setAutocompleteResults] = useState([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const resultsRef = useRef(null);
  const searchTimeoutRef = useRef(null);
  const sseCleanupRef = useRef(null);
  
  // Auto focus if requested
  useEffect(() => {
    if (autoFocus && inputRef.current) {
      inputRef.current.focus();
    }
  }, [autoFocus]);

  // Cleanup SSE connection on unmount
  useEffect(() => {
    return () => {
      if (sseCleanupRef.current) {
        sseCleanupRef.current();
      }
    };
  }, []);

  // Fetch autocomplete suggestions for Greek administrative terms
  const fetchAutocompleteSuggestions = useCallback(async (searchQuery) => {
    if (!searchQuery.trim() || searchQuery.length < 2) {
      setAutocompleteResults([]);
      return;
    }

    try {
      const suggestions = await getAutocompleteSuggestions(searchQuery);
      setAutocompleteResults(suggestions.suggestions || []);
    } catch (error) {
      console.error('Failed to fetch autocomplete suggestions:', error);
      setAutocompleteResults([]);
    }
  }, []);

  // Debounced search function using SSE
  const performSearch = useCallback(async (searchQuery) => {
    if (!searchQuery.trim()) {
      setResults(null);
      setShowResults(false);
      setAutocompleteResults([]);
      return;
    }

    // Cancel any existing SSE connection
    if (sseCleanupRef.current) {
      sseCleanupRef.current();
      sseCleanupRef.current = null;
    }

    setIsLoading(true);
    setDocumentsLoading(false);
    
    // Fetch autocomplete suggestions in parallel
    fetchAutocompleteSuggestions(searchQuery);

    try {
      // Start SSE streaming search
      const cleanup = streamSearch(searchQuery, {
        includeDocuments: showFullResults,
        limit: 5,
        
        // Handle entity results (fast)
        onEntities: (entityData) => {
          setResults(prevResults => {
            // Merge entity results with existing results
            const newResults = {
              query: entityData.query,
              results: { ...entityData.results },
              total_count: entityData.total_count
            };
            
            // If we already have document results, merge them
            if (prevResults?.results?.documents) {
              newResults.results.documents = prevResults.results.documents;
              newResults.total_count += prevResults.results.documents.length;
            }
            
            return newResults;
          });
          
          setShowResults(true);
          setIsLoading(false);
          setDocumentsLoading(showFullResults); // Start loading documents indicator
        },
        
        // Handle document results (slow)
        onDocuments: (documentData) => {
          setResults(prevResults => {
            if (!prevResults) return documentData;
            
            // Merge document results with entity results
            return {
              query: prevResults.query,
              results: {
                ...prevResults.results,
                documents: documentData.results.documents || []
              },
              total_count: prevResults.total_count + (documentData.results.documents?.length || 0)
            };
          });
          
          setDocumentsLoading(false);
        },
        
        // Handle completion
        onDone: () => {
          setDocumentsLoading(false);
          setIsLoading(false);
          sseCleanupRef.current = null;
        },
        
        // Handle errors
        onError: (error) => {
          console.error('Search stream failed:', error);
          setIsLoading(false);
          setDocumentsLoading(false);
          sseCleanupRef.current = null;
          
          // Show error state but don't hide existing results
          if (!results) {
            setResults({
              query: searchQuery,
              results: {},
              total_count: 0,
              error: error.message
            });
          }
        }
      });
      
      // Store cleanup function
      sseCleanupRef.current = cleanup;
      
    } catch (error) {
      console.error('Search initialization failed:', error);
      setIsLoading(false);
      setDocumentsLoading(false);
      setResults(null);
      setShowResults(false);
    }
  }, [showFullResults, fetchAutocompleteSuggestions]);

  // Handle input changes with debouncing
  const handleInputChange = (e) => {
    const newQuery = e.target.value;
    setQuery(newQuery);

    // Clear previous timeout
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    // Set new timeout for search
    searchTimeoutRef.current = setTimeout(() => {
      performSearch(newQuery);
    }, 300); // 300ms debounce
  };

  // Handle input focus
  const handleInputFocus = () => {
    if (results && query.trim()) {
      setShowResults(true);
    }
  };

  // Handle input blur (with delay to allow clicks)
  const handleInputBlur = () => {
    setTimeout(() => {
      setShowResults(false);
      setSelectedIndex(-1);
    }, 150);
  };

  // Handle keyboard navigation
  const handleKeyDown = (e) => {
    if (!showResults || !results) return;

    const allItems = getAllSelectableItems();
    
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex(prev => 
          prev < allItems.length - 1 ? prev + 1 : 0
        );
        break;
        
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex(prev => 
          prev > 0 ? prev - 1 : allItems.length - 1
        );
        break;
        
      case 'Enter':
        e.preventDefault();
        if (selectedIndex >= 0 && allItems[selectedIndex]) {
          handleItemClick(allItems[selectedIndex]);
        }
        break;
        
      case 'Escape':
        setShowResults(false);
        setSelectedIndex(-1);
        inputRef.current?.blur();
        break;
    }
  };

  // Get all selectable items for keyboard navigation
  const getAllSelectableItems = () => {
    if (!results?.results) return [];
    
    const items = [];
    Object.entries(results.results).forEach(([category, categoryResults]) => {
      if (categoryResults && categoryResults.length > 0) {
        categoryResults.forEach(item => {
          items.push({ ...item, category });
        });
      }
    });
    
    return items;
  };

  // Handle item click
  const handleItemClick = (item) => {
    setShowResults(false);
    setSelectedIndex(-1);
    
    // Call custom handler if provided
    if (onResultClick) {
      onResultClick(item);
      return;
    }

    // Default navigation logic
    switch (item.type) {
      case 'organization':
        navigate(`/entity/organization/${item.id}`);
        break;
      case 'signer':
        navigate(`/entity/signer/${item.id}`);
        break;
      case 'unit':
        navigate(`/entity/unit/${item.id}`);
        break;
      case 'company':
        navigate(`/entity/company/${item.id}`);
        break;
      case 'company_person':
        navigate(`/entity/company-person/${item.id}`);
        break;
      case 'document':
        navigate(`/decision/${item.details.decision_id}`);
        break;
      default:
        console.warn(`Unknown item type: ${item.type}`);
    }
  };

  // Handle clear button
  const handleClear = () => {
    setQuery('');
    setResults(null);
    setShowResults(false);
    setSelectedIndex(-1);
    inputRef.current?.focus();
  };

  // Handle view all results
  const handleViewAll = () => {
    setShowResults(false);
    // Navigate to a full search results page
    navigate(`/search?q=${encodeURIComponent(query)}`);
  };

  // Get icon for item type
  const getItemIcon = (type) => {
    const icons = {
      organization: '🏢',
      signer: '👤',
      unit: '🏛️',
      company: '🏪',
      company_person: '👨‍💼',
      document: '📄'
    };
    return icons[type] || '📋';
  };

  // Get category display name
  const getCategoryName = (category) => {
    const names = {
      organizations: 'Organizations',
      signers: 'Signers',
      units: 'Units',
      companies: 'Companies',
      company_persons: 'Company Persons',
      documents: 'Documents'
    };
    return names[category] || category;
  };

  // Render highlights in text
  const renderHighlightedText = (text) => {
    if (!text) return '';
    
    // Text might already contain HTML tags from the API
    return <span dangerouslySetInnerHTML={{ __html: text }} />;
  };

  // Render document excerpt with highlights
  const renderDocumentExcerpt = (item) => {
    if (item.highlights?.content) {
      return (
        <div className="super-search-document-excerpt">
          {item.highlights.content.slice(0, 2).map((excerpt, index) => (
            <div key={index} dangerouslySetInnerHTML={{ __html: excerpt }} />
          ))}
        </div>
      );
    }
    
    if (item.description) {
      return (
        <div className="super-search-document-excerpt">
          <span dangerouslySetInnerHTML={{ __html: item.description }} />
        </div>
      );
    }
    
    return null;
  };

  // Render document metadata
  const renderDocumentMetadata = (item) => {
    if (!item.details) return null;
    
    const metadata = [];
    
    if (item.details.issue_date) {
      metadata.push({
        icon: '📅',
        text: new Date(item.details.issue_date).toLocaleDateString()
      });
    }
    
    if (item.details.amount && item.details.currency) {
      metadata.push({
        icon: '💰',
        text: `${item.details.amount} ${item.details.currency}`
      });
    }
    
    if (item.details.signers?.length > 0) {
      metadata.push({
        icon: '✍️',
        text: item.details.signers.join(', ')
      });
    }
    
    if (metadata.length === 0) return null;
    
    return (
      <div className="super-search-document-metadata">
        {metadata.map((meta, index) => (
          <div key={index} className="super-search-document-metadata-item">
            <span>{meta.icon}</span>
            <span>{meta.text}</span>
          </div>
        ))}
      </div>
    );
  };

  const allItems = getAllSelectableItems();

  return (
    <div className={`super-search-container ${className}`}>
      <div className="super-search-input-wrapper">
        <span className="super-search-icon">🔍</span>
        <input
          ref={inputRef}
          type="text"
          className="super-search-input"
          placeholder={placeholder}
          value={query}
          onChange={handleInputChange}
          onFocus={handleInputFocus}
          onBlur={handleInputBlur}
          onKeyDown={handleKeyDown}
          autoComplete="off"
        />
        {isLoading && (
          <div className="super-search-loading">
            <div className="super-search-loading-spinner" />
          </div>
        )}
        {!isLoading && documentsLoading && (
          <div className="super-search-loading" title="Loading documents...">
            <div className="super-search-loading-spinner" />
          </div>
        )}
        {query && !isLoading && (
          <button
            className="super-search-clear"
            onClick={handleClear}
            type="button"
            aria-label="Clear search"
          >
            ✕
          </button>
        )}
      </div>

      {showResults && (
        <div ref={resultsRef} className="super-search-results">
          {!results || results.total_count === 0 ? (
            <div className="super-search-no-results">
              No results found for "{query}"
            </div>
          ) : (
            <>
              {Object.entries(results.results).map(([category, categoryResults]) => {
                if (!categoryResults || categoryResults.length === 0) return null;

                return (
                  <div key={category} className="super-search-category">
                    <div className="super-search-category-header">
                      <span className="super-search-category-icon">
                        {getItemIcon(categoryResults[0]?.type)}
                      </span>
                      <span>{getCategoryName(category)}</span>
                      <span className="super-search-category-count">
                        {categoryResults.length}
                      </span>
                    </div>
                    
                    {categoryResults.map((item, index) => {
                      const globalIndex = allItems.findIndex(
                        globalItem => globalItem.id === item.id && globalItem.type === item.type
                      );
                      const isSelected = globalIndex === selectedIndex;
                      const isDocument = item.type === 'document';
                      
                      return (
                        <div
                          key={`${item.type}-${item.id}`}
                          className={`super-search-item ${isDocument ? 'super-search-document-item' : ''} ${isSelected ? 'selected' : ''}`}
                          onClick={() => handleItemClick(item)}
                          onMouseEnter={() => setSelectedIndex(globalIndex)}
                          style={{
                            backgroundColor: isSelected ? 'var(--hover-bg)' : 'transparent'
                          }}
                        >
                          <div className="super-search-item-icon">
                            {getItemIcon(item.type)}
                          </div>
                          
                          <div className="super-search-item-content">
                            <div className="super-search-item-title">
                              {renderHighlightedText(item.title)}
                            </div>
                            
                            {item.subtitle && (
                              <div className="super-search-item-subtitle">
                                {item.subtitle}
                              </div>
                            )}
                            
                            {item.description && !isDocument && (
                              <div className="super-search-item-description">
                                {item.description}
                              </div>
                            )}
                            
                            {isDocument && renderDocumentExcerpt(item)}
                            {isDocument && renderDocumentMetadata(item)}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                );
              })}
              
              {results.total_count > allItems.length && (
                <button 
                  className="super-search-view-all"
                  onClick={handleViewAll}
                >
                  View all {results.total_count} results
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default SuperSearch;
