import apiClient from './client';

/**
 * Search API service for the super search functionality
 */

/**
 * Perform a super search across all entity types
 * @param {string} query - Search query
 * @param {Object} options - Search options
 * @param {boolean} options.includeDocuments - Whether to include document results
 * @param {number} options.limit - Maximum number of results per category
 * @returns {Promise<Object>} Search results
 */
export const superSearch = async (query, options = {}) => {
  const {
    includeDocuments = true,
    limit = 10
  } = options;

  const params = new URLSearchParams({
    q: query,
    include_documents: includeDocuments,
    limit: limit
  });

  try {
    const response = await apiClient.get(`/search/super/?${params}`);
    return response.data;
  } catch (error) {
    console.error('Super search failed:', error);
    throw error;
  }
};

/**
 * Get autocomplete suggestions as user types
 * @param {string} query - Partial search query
 * @param {number} limit - Maximum number of results
 * @returns {Promise<Object>} Autocomplete suggestions
 */
export const getSearchSuggestions = async (query, limit = 5) => {
  if (!query || query.length < 2) {
    return {
      query: '',
      results: {
        organizations: [],
        signers: [],
        units: [],
        companies: [],
        company_persons: [],
        documents: []
      },
      total_count: 0
    };
  }

  return searchEntitiesFast(query, limit);
};

/**
 * Fast entity-only search (no documents)
 * @param {string} query - Search query
 * @param {number} limit - Maximum number of results per category
 * @returns {Promise<Object>} Entity search results
 */
export const searchEntitiesFast = async (query, limit = 5) => {
  const params = new URLSearchParams({
    q: query,
    limit: limit
  });

  try {
    const response = await apiClient.get(`/search/entities-fast/?${params}`);
    return response.data;
  } catch (error) {
    console.error('Fast entity search failed:', error);
    throw error;
  }
};

/**
 * Search documents only
 * @param {string} query - Search query
 * @param {number} limit - Maximum number of results
 * @returns {Promise<Object>} Document search results
 */
export const searchDocuments = async (query, limit = 5) => {
  const params = new URLSearchParams({
    q: query,
    limit: limit
  });

  try {
    const response = await apiClient.get(`/search/documents/?${params}`);
    return response.data;
  } catch (error) {
    console.error('Document search failed:', error);
    throw error;
  }
};

/**
 * Get full search results including documents
 * @param {string} query - Search query
 * @param {number} limit - Maximum number of results per category
 * @returns {Promise<Object>} Full search results
 */
export const getFullSearchResults = async (query, limit = 10) => {
  return superSearch(query, { 
    includeDocuments: true, 
    limit 
  });
};
/**
 * Search with two separate API calls - entities first (fast), then documents (slow)
 * @param {string} query - Search query
 * @param {Object} options - Search options
 * @param {boolean} options.includeDocuments - Whether to include document results
 * @param {number} options.limit - Maximum number of results per category
 * @param {Function} options.onEntities - Callback when entities are received
 * @param {Function} options.onDocuments - Callback when documents are received
 * @param {Function} options.onDone - Callback when search is complete
 * @param {Function} options.onError - Callback on error
 * @returns {Object} Object with cancel function
 */
export const streamSearch = (query, options = {}) => {
  const {
    includeDocuments = true,
    limit = 5,
    onEntities = () => {},
    onDocuments = () => {},
    onDone = () => {},
    onError = () => {}
  } = options;

  let isCancelled = false;

  // Immediately start the fast entity search
  (async () => {
    try {
      // Phase 1: Fast entity search
      const entityResults = await searchEntitiesFast(query, limit);
      
      if (isCancelled) return;
      
      onEntities(entityResults);
      
      // Phase 2: Slow document search (if requested)
      if (includeDocuments) {
        const documentResults = await searchDocuments(query, limit);
        
        if (isCancelled) return;
        
        onDocuments(documentResults);
      }
      
      // All done
      if (!isCancelled) {
        onDone({ query });
      }
    } catch (error) {
      if (!isCancelled) {
        console.error('Search failed:', error);
        onError(error);
      }
    }
  })();

  // Return cleanup function
  return () => {
    isCancelled = true;
  };
};

/**
 * Get autocomplete suggestions for common Greek administrative terms
 * @param {string} query - Search query prefix
 * @param {string} category - Filter by category (optional)
 * @returns {Promise<Object>} Autocomplete suggestions
 */
export const getAutocompleteSuggestions = async (query, category = null) => {
  const params = new URLSearchParams();
  if (query) params.append('q', query);
  if (category) params.append('category', category);

  try {
    const response = await apiClient.get(`/search/autocomplete/?${params}`);
    return response.data;
  } catch (error) {
    console.error('Autocomplete suggestions failed:', error);
    throw error;
  }
};

/**
 * Get default search suggestions (shown when user focuses on search box)
 * Returns pre-configured popular entities from admin
 * @param {number} limit - Maximum number of suggestions
 * @returns {Promise<Object>} Default suggestions
 */
export const getDefaultSuggestions = async (limit = 10) => {
  const params = new URLSearchParams({ limit });

  try {
    const response = await apiClient.get(`/search/suggestions/?${params}`);
    return response.data;
  } catch (error) {
    console.error('Failed to fetch default suggestions:', error);
    throw error;
  }
};

/**
 * Search specific entity categories with custom limits per category
 * @param {string} query - Search query
 * @param {Object} categoryLimits - Limits per category { organizations: 5, signers: 10, ... }
 * @returns {Promise<Object>} Category-specific search results
 */
export const searchCategories = async (query, categoryLimits = {}) => {
  const {
    organizations = 5,
    signers = 5,
    units = 5,
    companies = 5,
    company_persons = 5,
    documents = 5
  } = categoryLimits;

  // Build entity type list and determine max limit for entities
  const entityTypes = [];
  let maxEntityLimit = 0;
  
  if (organizations > 0) {
    entityTypes.push('organization');
    maxEntityLimit = Math.max(maxEntityLimit, organizations);
  }
  if (signers > 0) {
    entityTypes.push('signer');
    maxEntityLimit = Math.max(maxEntityLimit, signers);
  }
  if (units > 0) {
    entityTypes.push('unit');
    maxEntityLimit = Math.max(maxEntityLimit, units);
  }
  if (companies > 0) {
    entityTypes.push('company');
    maxEntityLimit = Math.max(maxEntityLimit, companies);
  }
  if (company_persons > 0) {
    entityTypes.push('company_person');
    maxEntityLimit = Math.max(maxEntityLimit, company_persons);
  }

  try {
    // Fetch entities with the max limit to avoid multiple calls
    const entityParams = new URLSearchParams({
      q: query,
      types: entityTypes.join(','),
      limit: maxEntityLimit
    });

    const entityResponse = await apiClient.get(`/search/entities-fast/?${entityParams}`);
    const results = {
      query: query,
      results: {},
      total_count: 0
    };

    // Trim results to match requested limits
    if (entityResponse.data.results) {
      Object.entries(entityResponse.data.results).forEach(([category, items]) => {
        const categoryKey = category; // e.g., 'organizations'
        
        // Find the corresponding limit
        let limit = 5;
        if (categoryKey === 'organizations') limit = organizations;
        else if (categoryKey === 'signers') limit = signers;
        else if (categoryKey === 'units') limit = units;
        else if (categoryKey === 'companies') limit = companies;
        else if (categoryKey === 'company_persons') limit = company_persons;

        if (limit > 0 && items && items.length > 0) {
          results.results[categoryKey] = items.slice(0, limit);
          results.total_count += results.results[categoryKey].length;
        }
      });
    }

    // Fetch documents if requested
    if (documents > 0) {
      const docResponse = await searchDocuments(query, documents);
      if (docResponse.results?.documents) {
        results.results.documents = docResponse.results.documents;
        results.total_count += results.results.documents.length;
      }
    }

    return results;
  } catch (error) {
    console.error('Category search failed:', error);
    throw error;
  }
};