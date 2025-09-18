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

  return superSearch(query, { 
    includeDocuments: false, // For autocomplete, don't include documents for speed
    limit 
  });
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
