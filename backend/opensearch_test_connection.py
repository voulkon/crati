#!/usr/bin/env python3
"""
Quick test script to debug OpenSearch connection issues
Run this with: python manage.py shell < test_opensearch_connection.py
"""

import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'diavgeia_project.settings')
django.setup()

from core.services.opensearch_service import OpenSearchService
from core.services.search_service import SearchService
from loguru import logger

print("=" * 50)
print("TESTING OPENSEARCH CONNECTION")
print("=" * 50)

# Test 1: Direct OpenSearch service
print("\n1. Testing OpenSearchService directly...")
opensearch = OpenSearchService()

print("\n2. Testing simple search...")
result = opensearch.test_simple_search("κομιτσα")

print("\n3. Testing SearchService...")
search_service = SearchService()

print("\n4. Testing document search through SearchService...")
search_result = search_service.search_documents("πληρωμη", limit=5)  # Changed to "πληρωμη" which should match some documents
print(f"Search result keys: {list(search_result.keys())}")
print(f"Result count: {search_result.get('count', 0)}")
print(f"Source: {search_result.get('source', 'unknown')}")

if search_result.get('results'):
    print(f"First result type: {type(search_result['results'][0])}")
    print(f"First result keys: {list(search_result['results'][0].keys()) if isinstance(search_result['results'][0], dict) else 'Not a dict'}")
    
    # Show some result details
    first_result = search_result['results'][0]
    if 'opensearch_source' in first_result:
        opensearch_data = first_result['opensearch_source']
        print(f"First result ADA: {opensearch_data.get('ada', 'N/A')}")
        print(f"First result title: {opensearch_data.get('title', 'N/A')[:100]}...")
    
    if 'text_excerpt' in first_result:
        excerpt = first_result['text_excerpt']
        print(f"Text excerpt: {excerpt[:200]}...")

print(f"\n5. Testing simple Greek search in OpenSearch...")
simple_result = opensearch.search_documents("πληρωμη", size=3)
print(f"Direct OpenSearch hits: {len(simple_result.get('hits', {}).get('hits', []))}")
if simple_result.get('hits', {}).get('hits'):
    first_hit = simple_result['hits']['hits'][0]
    print(f"First hit score: {first_hit.get('_score')}")
    print(f"First hit highlights: {first_hit.get('highlight', {})}")

print("\n" + "=" * 50)
print("TEST COMPLETE")
print("=" * 50)
