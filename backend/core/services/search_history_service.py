"""
Search History Service

Redis-based service for tracking and retrieving personal search history.
Provides fast access to recent searches for both authenticated users and anonymous IPs.

Benefits over DB-only approach:
- Ultra-fast retrieval for autocomplete/suggestions
- Automatic expiration (90 days)
- Sorted list with timestamps
- Deduplication of searches
- Privacy-friendly (can be cleared on demand)

Architecture:
- Redis Sorted Set per user/IP: stores query + metadata as JSON
- Score = timestamp (for chronological ordering)
- Automatically expires after 90 days
- Complements SearchAnalytics model (which persists all searches)
"""

import json
import time
from typing import List, Dict, Any, Optional
from django.conf import settings
from django_redis import get_redis_connection
from loguru import logger

from api.redis_keys import (
    get_user_search_history_key,
    get_ip_search_history_key,
    SEARCH_HISTORY_EXPIRE
)


class SearchHistoryService:
    """
    Manages personal search history using Redis Sorted Sets.
    
    Data structure:
    - Key: search_history:user:<user_id> or search_history:ip:<ip>
    - Type: Sorted Set (ZADD, ZRANGE, ZREVRANGE)
    - Member: JSON string with query and metadata
    - Score: Unix timestamp
    
    Example usage:
        service = SearchHistoryService()
        
        # Track a search
        service.track_search(
            query="Δημοτικό Συμβούλιο",
            user_id=123,
            results_count=45,
            search_types=['organization', 'signer']
        )
        
        # Get recent searches
        history = service.get_user_history(user_id=123, limit=10)
        
        # Get unique queries for autocomplete
        recent_queries = service.get_recent_queries(user_id=123, limit=5)
    """
    
    def __init__(self):
        """Initialize Redis connection using Django's connection pool"""
        # Use default cache connection (DB 1)
        self.redis_client = get_redis_connection("default")
        logger.debug("SearchHistoryService initialized with Redis connection pool")
    
    def track_search(
        self,
        query: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        results_count: Optional[int] = None,
        search_types: Optional[List[str]] = None,
        entity_type: Optional[str] = None,
        filters_applied: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Track a search in Redis history.
        
        Args:
            query: The search query string
            user_id: User ID (for authenticated users)
            ip_address: IP address (for anonymous users or as fallback)
            results_count: Number of results returned
            search_types: Types of entities searched (e.g., ['organization', 'signer'])
            entity_type: Primary entity type searched
            filters_applied: Any filters applied to the search
            
        Returns:
            True if successfully tracked, False otherwise
        """
        if not query or not query.strip():
            return False
        
        normalized_query = query.strip().lower()
        timestamp = time.time()
        
        # Build metadata
        metadata = {
            'query': query.strip(),  # Keep original casing
            'normalized_query': normalized_query,
            'timestamp': timestamp,
        }
        
        if results_count is not None:
            metadata['results_count'] = results_count
        if search_types:
            metadata['search_types'] = search_types
        if entity_type:
            metadata['entity_type'] = entity_type
        if filters_applied:
            metadata['filters_applied'] = filters_applied
        
        success = False
        
        # Track for authenticated user
        if user_id:
            success = self._add_to_history(
                key=get_user_search_history_key(user_id),
                query=normalized_query,
                metadata=metadata,
                timestamp=timestamp
            ) or success
        
        # Track for IP (always track, useful for anonymous users)
        if ip_address:
            success = self._add_to_history(
                key=get_ip_search_history_key(ip_address),
                query=normalized_query,
                metadata=metadata,
                timestamp=timestamp
            ) or success
        
        return success
    
    def _add_to_history(
        self,
        key: str,
        query: str,
        metadata: Dict[str, Any],
        timestamp: float
    ) -> bool:
        """
        Add a search to a Redis sorted set.
        
        Uses normalized query as the member to prevent duplicates.
        If the same query is searched again, it updates the timestamp.
        """
        try:
            # Serialize metadata
            member = json.dumps(metadata)
            
            # Add to sorted set (score = timestamp)
            # ZADD automatically updates if member exists
            self.redis_client.zadd(key, {member: timestamp})
            
            # Set expiration on the key
            self.redis_client.expire(key, SEARCH_HISTORY_EXPIRE)
            
            # Trim to keep only last 100 searches per user/IP
            # (sorted sets keep everything by default)
            self.redis_client.zremrangebyrank(key, 0, -101)
            
            logger.debug(f"Tracked search '{query}' in {key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to track search in {key}: {e}")
            return False
    
    def get_user_history(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get a user's search history (most recent first).
        
        Args:
            user_id: User ID
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            List of search metadata dicts, sorted by timestamp (newest first)
        """
        key = get_user_search_history_key(user_id)
        return self._get_history(key, limit, offset)
    
    def get_ip_history(
        self,
        ip_address: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get an IP's search history (most recent first).
        
        Args:
            ip_address: IP address
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            List of search metadata dicts, sorted by timestamp (newest first)
        """
        key = get_ip_search_history_key(ip_address)
        return self._get_history(key, limit, offset)
    
    def _get_history(
        self,
        key: str,
        limit: int,
        offset: int
    ) -> List[Dict[str, Any]]:
        """
        Retrieve history from a Redis sorted set.
        
        Returns most recent searches first (reverse chronological order).
        """
        try:
            # ZREVRANGE: get members in reverse order (highest score first)
            # withscores=True returns (member, score) tuples
            start = offset
            end = offset + limit - 1
            
            members = self.redis_client.zrevrange(key, start, end, withscores=True)
            
            history = []
            for member_bytes, score in members:
                try:
                    metadata = json.loads(member_bytes.decode('utf-8'))
                    # Score is the timestamp
                    if 'timestamp' not in metadata:
                        metadata['timestamp'] = score
                    history.append(metadata)
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.warning(f"Failed to decode history entry: {e}")
                    continue
            
            return history
            
        except Exception as e:
            logger.error(f"Failed to retrieve history from {key}: {e}")
            return []
    
    def get_recent_queries(
        self,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        limit: int = 10,
        unique: bool = True
    ) -> List[str]:
        """
        Get recent query strings (for autocomplete suggestions).
        
        Args:
            user_id: User ID (optional)
            ip_address: IP address (optional)
            limit: Maximum number of queries
            unique: If True, deduplicate queries (default: True)
            
        Returns:
            List of query strings (most recent first)
        """
        history = []
        
        if user_id:
            history.extend(self.get_user_history(user_id, limit=limit * 2))
        
        if ip_address:
            history.extend(self.get_ip_history(ip_address, limit=limit * 2))
        
        # Extract queries
        queries = [item.get('query', '') for item in history if item.get('query')]
        
        # Deduplicate while preserving order
        if unique:
            seen = set()
            unique_queries = []
            for q in queries:
                normalized = q.lower()
                if normalized not in seen:
                    seen.add(normalized)
                    unique_queries.append(q)
            queries = unique_queries
        
        return queries[:limit]
    
    def clear_user_history(self, user_id: int) -> bool:
        """Clear all search history for a user (privacy feature)."""
        key = get_user_search_history_key(user_id)
        try:
            self.redis_client.delete(key)
            logger.info(f"Cleared search history for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear history for user {user_id}: {e}")
            return False
    
    def clear_ip_history(self, ip_address: str) -> bool:
        """Clear all search history for an IP."""
        key = get_ip_search_history_key(ip_address)
        try:
            self.redis_client.delete(key)
            logger.info(f"Cleared search history for IP {ip_address}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear history for IP {ip_address}: {e}")
            return False
    
    def get_history_stats(
        self,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get statistics about search history.
        
        Returns:
            Dict with total searches, date range, top search types, etc.
        """
        history = []
        
        if user_id:
            history.extend(self.get_user_history(user_id, limit=100))
        
        if ip_address:
            history.extend(self.get_ip_history(ip_address, limit=100))
        
        if not history:
            return {
                'total_searches': 0,
                'unique_queries': 0,
                'date_range': None,
                'top_search_types': []
            }
        
        # Calculate stats
        from collections import Counter
        
        unique_queries = set(item.get('normalized_query', '') for item in history)
        timestamps = [item.get('timestamp', 0) for item in history if item.get('timestamp')]
        
        search_types_counter = Counter()
        for item in history:
            types = item.get('search_types', [])
            if isinstance(types, list):
                search_types_counter.update(types)
        
        return {
            'total_searches': len(history),
            'unique_queries': len(unique_queries),
            'date_range': {
                'earliest': min(timestamps) if timestamps else None,
                'latest': max(timestamps) if timestamps else None,
            },
            'top_search_types': search_types_counter.most_common(5)
        }
