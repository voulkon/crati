"""
Database Storage Dashboard

Comprehensive view of PostgreSQL database storage usage:
- Overall database size and stats
- Table sizes (with indexes, TOAST)
- Column storage analysis
- Index sizes
- Row counts
- Bloat estimates
"""

from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.db import connection
from loguru import logger


@staff_member_required
def db_storage_dashboard(request):
    """Main dashboard for database storage analysis"""
    
    # Get overall database stats
    db_stats = _get_database_stats()
    
    # Get table sizes
    table_stats = _get_table_stats()
    
    # Get index stats
    index_stats = _get_index_stats()
    
    # Get column stats for key tables
    column_stats = _get_column_stats()
    
    # Get bloat estimates
    bloat_stats = _get_bloat_estimates()
    
    context = {
        'title': 'Database Storage Dashboard',
        'db_stats': db_stats,
        'table_stats': table_stats,
        'index_stats': index_stats,
        'column_stats': column_stats,
        'bloat_stats': bloat_stats,
    }
    
    return render(request, 'admin/db_storage_dashboard.html', context)


def _get_database_stats():
    """Get overall database statistics"""
    with connection.cursor() as cursor:
        # Get database size
        cursor.execute("""
            SELECT 
                pg_database.datname,
                pg_size_pretty(pg_database_size(pg_database.datname)) as size_pretty,
                pg_database_size(pg_database.datname) as size_bytes
            FROM pg_database
            WHERE datname = current_database()
        """)
        db_row = cursor.fetchone()
        
        # Get table count
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
        """)
        table_count = cursor.fetchone()[0]
        
        # Get index count
        cursor.execute("""
            SELECT COUNT(*) 
            FROM pg_indexes 
            WHERE schemaname = 'public'
        """)
        index_count = cursor.fetchone()[0]
        
        # Get total rows across all tables
        cursor.execute("""
            SELECT 
                SUM(n_live_tup) as total_rows,
                SUM(n_dead_tup) as dead_rows
            FROM pg_stat_user_tables
        """)
        row_stats = cursor.fetchone()
        
        # Get total index size
        cursor.execute("""
            SELECT pg_size_pretty(SUM(pg_relation_size(indexrelid))) as total_index_size
            FROM pg_index
            JOIN pg_class ON pg_class.oid = pg_index.indexrelid
            WHERE pg_class.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
        """)
        total_index_size = cursor.fetchone()[0]
        
        return {
            'database_name': db_row[0],
            'total_size': db_row[1],
            'total_size_bytes': db_row[2],
            'table_count': table_count,
            'index_count': index_count,
            'total_rows': row_stats[0] or 0,
            'dead_rows': row_stats[1] or 0,
            'total_index_size': total_index_size,
        }


def _get_table_stats():
    """Get detailed statistics for each table"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                schemaname,
                relname as tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||relname)) as total_size,
                pg_size_pretty(pg_relation_size(schemaname||'.'||relname)) as table_size,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||relname) - pg_relation_size(schemaname||'.'||relname)) as external_size,
                pg_total_relation_size(schemaname||'.'||relname) as total_bytes,
                pg_relation_size(schemaname||'.'||relname) as table_bytes,
                n_live_tup as row_count,
                n_dead_tup as dead_rows,
                CASE 
                    WHEN n_live_tup > 0 
                    THEN round(100.0 * n_dead_tup / n_live_tup, 2)
                    ELSE 0 
                END as dead_ratio
            FROM pg_stat_user_tables
            ORDER BY pg_total_relation_size(schemaname||'.'||relname) DESC
            LIMIT 50
        """)
        
        tables = []
        for row in cursor.fetchall():
            tables.append({
                'schema': row[0],
                'name': row[1],
                'total_size': row[2],
                'table_size': row[3],
                'external_size': row[4],  # TOAST + indexes
                'total_bytes': row[5],
                'table_bytes': row[6],
                'row_count': row[7] or 0,
                'dead_rows': row[8] or 0,
                'dead_ratio': row[9] or 0,
            })
        
        return tables


def _get_index_stats():
    """Get index statistics"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                schemaname,
                relname as tablename,
                indexrelname as indexname,
                pg_size_pretty(pg_relation_size(pg_stat_user_indexes.indexrelid)) as index_size,
                pg_relation_size(pg_stat_user_indexes.indexrelid) as size_bytes,
                idx_scan as scans,
                idx_tup_read as tuples_read,
                idx_tup_fetch as tuples_fetched
            FROM pg_stat_user_indexes
            JOIN pg_index ON pg_stat_user_indexes.indexrelid = pg_index.indexrelid
            ORDER BY pg_relation_size(pg_stat_user_indexes.indexrelid) DESC
            LIMIT 50
        """)
        
        indexes = []
        for row in cursor.fetchall():
            indexes.append({
                'schema': row[0],
                'table': row[1],
                'name': row[2],
                'size': row[3],
                'size_bytes': row[4],
                'scans': row[5] or 0,
                'tuples_read': row[6] or 0,
                'tuples_fetched': row[7] or 0,
            })
        
        return indexes


def _get_column_stats():
    """Get column storage statistics for key tables"""
    
    # Focus on tables that are likely to have large columns
    key_tables = [
        'core_documentextraction',
        'core_documentpage',
        'core_document',
    ]
    
    column_data = {}
    
    with connection.cursor() as cursor:
        for table in key_tables:
            # Get column stats
            cursor.execute(f"""
                SELECT 
                    attname as column_name,
                    format_type(atttypid, atttypmod) as data_type,
                    CASE 
                        WHEN atttypid = ANY (ARRAY[25, 1043, 1042]::oid[]) THEN 'text'  -- text, varchar, char
                        WHEN atttypid = 3614 THEN 'tsvector'  -- tsvector
                        WHEN atttypid = 17 THEN 'bytea'  -- bytea
                        ELSE 'other'
                    END as type_category,
                    attnotnull as not_null,
                    attnum as position
                FROM pg_attribute
                JOIN pg_class ON pg_attribute.attrelid = pg_class.oid
                JOIN pg_namespace ON pg_class.relnamespace = pg_namespace.oid
                WHERE pg_namespace.nspname = 'public'
                AND pg_class.relname = %s
                AND attnum > 0
                AND NOT attisdropped
                ORDER BY attnum
            """, [table])
            
            columns = []
            for row in cursor.fetchall():
                col_name = row[0]
                col_type = row[1]
                col_category = row[2]
                
                # Estimate size for TOAST-able columns
                size_estimate = None
                if col_category in ('text', 'tsvector', 'bytea'):
                    cursor.execute(f"""
                        SELECT 
                            COUNT(*) FILTER (WHERE {col_name} IS NOT NULL) as non_null_count,
                            AVG(LENGTH({col_name}::text)) as avg_length,
                            MAX(LENGTH({col_name}::text)) as max_length,
                            MIN(LENGTH({col_name}::text)) FILTER (WHERE {col_name} IS NOT NULL) as min_length
                        FROM {table}
                    """)
                    stats = cursor.fetchone()
                    if stats:
                        non_null = stats[0] or 0
                        avg_len = stats[1] or 0
                        max_len = stats[2] or 0
                        min_len = stats[3] or 0
                        
                        # Estimate total size in MB
                        estimated_mb = (non_null * avg_len) / (1024 * 1024) if avg_len else 0
                        
                        size_estimate = {
                            'non_null_count': non_null,
                            'avg_length': round(avg_len, 2) if avg_len else 0,
                            'max_length': max_len,
                            'min_length': min_len,
                            'estimated_mb': round(estimated_mb, 2),
                        }
                
                columns.append({
                    'name': col_name,
                    'type': col_type,
                    'category': col_category,
                    'not_null': row[3],
                    'position': row[4],
                    'size_estimate': size_estimate,
                })
            
            column_data[table] = columns
    
    return column_data


def _get_bloat_estimates():
    """Estimate table and index bloat"""
    with connection.cursor() as cursor:
        # Table bloat estimation
        cursor.execute("""
            SELECT 
                schemaname,
                relname as tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||relname)) as total_size,
                round(100.0 * n_dead_tup / GREATEST(n_live_tup, 1), 2) as bloat_pct,
                pg_size_pretty(CAST(
                    pg_total_relation_size(schemaname||'.'||relname) * 
                    (n_dead_tup::numeric / GREATEST(n_live_tup + n_dead_tup, 1))
                    AS bigint
                )) as estimated_bloat_size,
                last_vacuum,
                last_autovacuum
            FROM pg_stat_user_tables
            WHERE n_live_tup > 0
            ORDER BY n_dead_tup DESC
            LIMIT 20
        """)
        
        bloat_tables = []
        for row in cursor.fetchall():
            bloat_tables.append({
                'schema': row[0],
                'table': row[1],
                'total_size': row[2],
                'bloat_pct': row[3] or 0,
                'estimated_bloat': row[4],
                'last_vacuum': row[5],
                'last_autovacuum': row[6],
            })
        
        return {
            'tables': bloat_tables,
        }
