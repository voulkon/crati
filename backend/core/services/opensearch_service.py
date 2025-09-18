import requests
import json
import time
from django.conf import settings
from typing import Dict, Any, List
from loguru import logger

class OpenSearchService:
    def __init__(self):
        self.opensearch_url = getattr(settings, 'OPENSEARCH_URL', 'http://opensearch:9200')
        self.index_name = 'diavgeia-documents'
        self.max_content_length = 10000
        self.preview_length = 500
        
        # Test connection on initialization
        self._test_connection()
    
    def _test_connection(self):
        """Test OpenSearch connection and log results"""
        try:
            response = requests.get(f"{self.opensearch_url}/_cluster/health", timeout=5)
            if response.status_code == 200:
                health = response.json()
                logger.info(f"✅ OpenSearch connection OK - Status: {health.get('status')}")
                
                # Test if our index exists
                index_response = requests.get(f"{self.opensearch_url}/{self.index_name}", timeout=5)
                if index_response.status_code == 200:
                    logger.info(f"✅ Index '{self.index_name}' exists")
                    
                    # Get document count
                    count_response = requests.get(f"{self.opensearch_url}/{self.index_name}/_count", timeout=5)
                    if count_response.status_code == 200:
                        count_data = count_response.json()
                        doc_count = count_data.get('count', 0)
                        logger.info(f"📊 Index contains {doc_count} documents")
                    else:
                        logger.warning(f"❌ Could not get document count: {count_response.status_code}")
                else:
                    logger.warning(f"⚠️ Index '{self.index_name}' does not exist: {index_response.status_code}")
            else:
                logger.error(f"❌ OpenSearch health check failed: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ OpenSearch connection test failed: {e}")
    
    def _prepare_content(self, raw_text: str) -> Dict[str, str]:
        """Prepare content with smart truncation"""
        if not raw_text:
            return {'content': '', 'content_preview': ''}
        
        # Clean the text
        cleaned = raw_text.strip()
        
        # Create preview (first meaningful paragraph)
        lines = cleaned.split('\n')
        preview_lines = []
        preview_chars = 0
        
        for line in lines:
            line = line.strip()
            if line and len(line) > 20:  # Skip very short lines
                if preview_chars + len(line) <= self.preview_length:
                    preview_lines.append(line)
                    preview_chars += len(line)
                else:
                    break
        
        preview = ' '.join(preview_lines)
        
        # Create search content (smart truncation at sentence boundaries)
        if len(cleaned) <= self.max_content_length:
            content = cleaned
        else:
            # Truncate at sentence boundary near the limit
            truncated = cleaned[:self.max_content_length]
            last_sentence = max(
                truncated.rfind('.'),
                truncated.rfind('!'),
                truncated.rfind('?'),
                truncated.rfind('.')  # Greek period
            )
            
            if last_sentence > self.max_content_length * 0.8:  # If we found a good break point
                content = truncated[:last_sentence + 1]
            else:
                content = truncated  # Just truncate
        
        return {
            'content': content,
            'content_preview': preview
        }
    
    def index_document(self, document_data: Dict[str, Any]) -> bool:
        """Index a single document with smart content handling"""
        try:
            # Prepare content
            raw_text = document_data.get('content', '')
            content_data = self._prepare_content(raw_text)
            
            # Update document data
            document_data.update(content_data)
            
            # Add metadata
            document_data['indexed_at'] = time.time()
            document_data['content_length'] = len(content_data['content'])
            document_data['is_truncated'] = len(raw_text) > self.max_content_length
            
            response = requests.post(
                f"{self.opensearch_url}/{self.index_name}/_doc/{document_data['decision_id']}",
                json=document_data,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"Indexed document {document_data['decision_id']} ({len(content_data['content'])} chars)")
                
                # Force index refresh to make document immediately searchable
                refresh_response = requests.post(f"{self.opensearch_url}/{self.index_name}/_refresh")
                
                return True
            else:
                logger.error(f"Failed to index document {document_data['decision_id']}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error indexing document {document_data['decision_id']}: {e}")
            return False
    
    def search_documents(self, query: str, filters: Dict = None, size: int = 10) -> Dict[str, Any]:
        """Enhanced search with filtering"""
        
        logger.info(f"🔍 OpenSearch search_documents called with query: '{query}', filters: {filters}, size: {size}")
        
        # Build the search query
        search_body = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["title^3", "content^2", "content_preview"],
                                "analyzer": "greek_text_analyzer"
                            }
                        }
                    ]
                }
            },
            "highlight": {
                "fields": {
                    "title": {"number_of_fragments": 1},
                    "content": {"fragment_size": 150, "number_of_fragments": 3},
                    "content_preview": {"number_of_fragments": 1}
                }
            },
            "_source": [
                "decision_id", "ada", "title", "content_preview", 
                "organization", "decision_type", "issue_date", 
                "page_count", "character_count", "is_truncated"
            ],
            "size": size
        }
        
        # Add filters if provided
        if filters:
            filter_clauses = []
            
            if filters.get('organization'):
                filter_clauses.append({"term": {"organization.raw": filters['organization']}})
            
            if filters.get('decision_type'):
                filter_clauses.append({"term": {"decision_type": filters['decision_type']}})
                
            if filters.get('date_from') or filters.get('date_to'):
                date_range = {}
                if filters.get('date_from'):
                    date_range['gte'] = filters['date_from']
                if filters.get('date_to'):
                    date_range['lte'] = filters['date_to']
                filter_clauses.append({"range": {"issue_date": date_range}})
            
            if filter_clauses:
                search_body["query"]["bool"]["filter"] = filter_clauses
        
        logger.debug(f"🔍 Search body: {json.dumps(search_body, indent=2, ensure_ascii=False)}")
        
        try:
            url = f"{self.opensearch_url}/{self.index_name}/_search"
            logger.debug(f"🌐 Making request to: {url}")
            
            response = requests.post(url, json=search_body, timeout=10)
            
            logger.debug(f"📡 Response status: {response.status_code}")
            logger.debug(f"📡 Response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                result = response.json()
                hits = result.get('hits', {}).get('hits', [])
                total = result.get('hits', {}).get('total', {})
                
                logger.info(f"✅ Search successful - Total: {total}, Hits returned: {len(hits)}")
                
                if hits:
                    logger.debug(f"🎯 First hit preview: {hits[0].get('_source', {}).get('title', 'No title')}")
                    logger.debug(f"🎯 First hit highlights: {hits[0].get('highlight', {})}")
                else:
                    logger.warning("⚠️ No hits returned from OpenSearch")
                
                return result
            else:
                error_text = response.text
                logger.error(f"❌ Search failed: {response.status_code} - {error_text}")
                return {"hits": {"hits": []}}
                
        except Exception as e:
            logger.error(f"❌ Search error: {e}")
            import traceback
            logger.error(f"❌ Search error traceback: {traceback.format_exc()}")
            return {"hits": {"hits": []}}
    
    def _analyze_text(self, text: str) -> List[str]:
        """Analyze text with the Greek analyzer to see what tokens are produced"""
        analyze_request = {
            "analyzer": "greek_text_analyzer",
            "text": text
        }
        
        try:
            response = requests.post(
                f"{self.opensearch_url}/{self.index_name}/_analyze",
                json=analyze_request
            )
            
            if response.status_code == 200:
                result = response.json()
                return [token['token'] for token in result.get('tokens', [])]
            else:
                logger.error(f"Analysis failed: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return []
    
    def test_simple_search(self, query: str = "test") -> Dict[str, Any]:
        """Simple test search to debug connection"""
        logger.info(f"🧪 Testing simple search with query: '{query}'")
        
        # Simple match_all query first
        simple_body = {
            "query": {"match_all": {}},
            "size": 3
        }
        
        try:
            url = f"{self.opensearch_url}/{self.index_name}/_search"
            logger.info(f"🌐 Testing with match_all at: {url}")
            
            response = requests.post(url, json=simple_body, timeout=10)
            logger.info(f"📡 Match_all response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                total = result.get('hits', {}).get('total', {})
                hits = result.get('hits', {}).get('hits', [])
                logger.info(f"✅ Match_all successful - Total docs: {total}, Sample: {len(hits)}")
                
                # Now try the actual search
                search_body = {
                    "query": {
                        "multi_match": {
                            "query": query,
                            "fields": ["title", "content", "content_preview"]
                        }
                    },
                    "size": 3
                }
                
                search_response = requests.post(url, json=search_body, timeout=10)
                logger.info(f"📡 Search response status: {search_response.status_code}")
                
                if search_response.status_code == 200:
                    search_result = search_response.json()
                    search_hits = search_result.get('hits', {}).get('hits', [])
                    logger.info(f"✅ Search successful - Hits: {len(search_hits)}")
                    return search_result
                else:
                    logger.error(f"❌ Search failed: {search_response.status_code} - {search_response.text}")
                    return result  # Return match_all results
                    
            else:
                logger.error(f"❌ Match_all failed: {response.status_code} - {response.text}")
                return {"hits": {"hits": []}}
                
        except Exception as e:
            logger.error(f"❌ Test search error: {e}")
            import traceback
            logger.error(f"❌ Test search traceback: {traceback.format_exc()}")
            return {"hits": {"hits": []}}
    
    def _force_refresh(self):
        """Force refresh the index to make documents immediately searchable"""
        try:
            response = requests.post(f"{self.opensearch_url}/{self.index_name}/_refresh", timeout=10)
            if response.status_code == 200:
                logger.info("✅ OpenSearch index refreshed successfully")
                return True
            else:
                logger.error(f"❌ Failed to refresh index: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Error refreshing index: {e}")
            return False
    
    def register_s3_repository(self, repository_name="s3-backup-repo", bucket_name=None, base_path="opensearch/backups"):
        """Register S3 repository for snapshots"""
        from django.conf import settings
        
        if not bucket_name:
            bucket_name = getattr(settings, 'AWS_BACKUP_BUCKET', 'my-backups')
        
        body = {
            "type": "s3",
            "settings": {
                "bucket": bucket_name,
                "base_path": base_path,
                "compress": True,
                "server_side_encryption": True
            }
        }
        
        try:
            response = self.client.snapshot.create_repository(
                repository=repository_name,
                body=body
            )
            logger.info(f"✅ S3 repository '{repository_name}' registered successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to register S3 repository: {e}")
            return False

    def create_snapshot(self, repository_name="s3-backup-repo", snapshot_name=None):
        """Create a snapshot backup"""
        from datetime import datetime
        
        if not snapshot_name:
            snapshot_name = f"snapshot-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        body = {
            "indices": "*",
            "ignore_unavailable": True,
            "include_global_state": False
        }
        
        try:
            response = self.client.snapshot.create(
                repository=repository_name,
                snapshot=snapshot_name,
                body=body
            )
            logger.info(f"✅ Snapshot '{snapshot_name}' created successfully")
            return {"success": True, "snapshot": snapshot_name}
        except Exception as e:
            logger.error(f"❌ Failed to create snapshot: {e}")
            return {"success": False, "error": str(e)}

    def list_snapshots(self, repository_name="s3-backup-repo"):
        """List all snapshots in repository"""
        try:
            response = self.client.snapshot.get(
                repository=repository_name,
                snapshot="_all"
            )
            return response["snapshots"]
        except Exception as e:
            logger.error(f"❌ Failed to list snapshots: {e}")
            return []

    def restore_snapshot(self, repository_name="s3-backup-repo", snapshot_name=None):
        """Restore from snapshot"""
        if not snapshot_name:
            logger.error("Snapshot name is required for restore")
            return False
        
        try:
            response = self.client.snapshot.restore(
                repository=repository_name,
                snapshot=snapshot_name
            )
            logger.info(f"✅ Restore from '{snapshot_name}' initiated")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to restore snapshot: {e}")
            return False