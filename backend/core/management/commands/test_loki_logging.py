"""
Django management command to test Loki logging integration
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import logging
import time

logger = logging.getLogger('diavgeia_project')

class Command(BaseCommand):
    help = 'Test Loki logging integration with various log levels and messages'

    def handle(self, *args, **options):
        self.stdout.write("🧪 Testing Loki integration via Django logging...")
        
        # Test different log levels
        logger.debug("🔧 DEBUG: This is a debug message for troubleshooting")
        logger.info("📋 INFO: Application successfully connected to database")
        logger.warning("⚠️  WARNING: High memory usage detected - 85% utilization")
        logger.error("❌ ERROR: Failed to process document with ID 12345")
        
        # Test structured logging with context
        logger.info("👤 User authentication successful", extra={
            'user_id': 'user_123',
            'session_id': 'sess_abc456',
            'ip_address': '192.168.1.100'
        })
        
        # Application-specific test logs
        logger.info("📄 Processing new document: Contract_2024_001.pdf")
        logger.info("🔍 OpenSearch indexing completed for 50 documents")  
        logger.info("⚡ Celery task 'index_recent_documents' executed successfully")
        logger.info("📊 Daily backup task completed - 2.3GB backed up")
        
        # Test error scenarios
        logger.error("💥 Database connection timeout after 30 seconds")
        logger.error("🔴 OpenSearch cluster health check failed")
        logger.warning("⚠️  Redis memory usage is at 90% capacity")
        
        # Performance logs
        logger.info("🏁 API request completed in 245ms - GET /api/documents/")
        logger.info("🔄 Background sync task took 1.2s to process 100 records")
        
        logger.info("✅ Django-based Loki integration test completed!")
        self.stdout.write(self.style.SUCCESS("✅ Loki integration test completed successfully!"))