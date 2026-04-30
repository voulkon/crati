
class SearchMethod:
    """Constants for entity search methods"""
    POSTGRES_SIMPLE = 'postgres_simple'  # Basic ILIKE search (always available)
    POSTGRES_FTS = 'postgres_fts'        # PostgreSQL Full-Text Search (requires search_vector)
    OPENSEARCH = 'opensearch'            # OpenSearch (requires OpenSearch indexing)
    
    # All valid methods
    ALL = [POSTGRES_SIMPLE, POSTGRES_FTS, OPENSEARCH]
    
    # Default fallback method (always available, no prerequisites)
    DEFAULT = POSTGRES_SIMPLE
