from django.db import connection
from core.services.opensearch_service import OpenSearchService

class DatabaseStatsService:
    def get_postgres_stats(self):
        with connection.cursor() as cursor:
            # Get DB Size
            cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()));")
            db_size = cursor.fetchone()[0]
            
            # Get Table Row Counts
            cursor.execute("""
                SELECT relname, n_live_tup
                FROM pg_stat_user_tables
                ORDER BY n_live_tup DESC;
            """)
            tables = [{'name': row[0], 'rows': row[1]} for row in cursor.fetchall()]
            
        return {
            'size': db_size,
            'tables': tables
        }

    def get_opensearch_stats(self):
        service = OpenSearchService()
        return service.analyze_index_health()
