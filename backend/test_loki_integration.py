#!/usr/bin/env python3
"""
Test script to generate sample log entries for verifying the Loki integration
"""

import logging
import time
import sys
import os

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('loki_test')

def test_logging_integration():
    """Generate various types of log entries to test Loki integration"""
    
    logger.info("🚀 Starting Loki integration test...")
    
    # Test different log levels
    logger.debug("DEBUG: This is a debug message for troubleshooting")
    logger.info("INFO: Application successfully connected to database")
    logger.warning("WARNING: High memory usage detected - 85% utilization")
    logger.error("ERROR: Failed to process document with ID 12345")
    
    # Test structured logging
    logger.info("User authentication successful", extra={
        'user_id': 'user_123',
        'session_id': 'sess_abc456',
        'ip_address': '192.168.1.100'
    })
    
    # Simulate some application-specific logs
    logger.info("📄 Processing new document: Contract_2024_001.pdf")
    logger.info("🔍 OpenSearch indexing completed for 50 documents")
    logger.info("⚡ Celery task 'index_recent_documents' executed successfully")
    logger.info("📊 Daily backup task completed - 2.3GB backed up")
    
    # Test error scenarios
    logger.error("💥 Database connection timeout after 30 seconds")
    logger.error("🔴 OpenSearch cluster health check failed")
    logger.warning("⚠️  Redis memory usage is at 90% capacity")
    
    # Test performance logs
    logger.info("🏁 API request completed in 245ms - GET /api/documents/")
    logger.info("🔄 Background sync task took 1.2s to process 100 records")
    
    logger.info("✅ Loki integration test completed successfully!")

if __name__ == "__main__":
    test_logging_integration()