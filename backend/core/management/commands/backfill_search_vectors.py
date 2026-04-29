"""
Regenerate search_vector data from existing raw_text.

This command backfills search_vector data for DocumentExtraction and DocumentPage tables,
allowing PostgreSQL full-text search to work on existing records.

Usage:
    # Backfill all DocumentExtraction records
    python manage.py backfill_search_vectors --model=extraction
    
    # Backfill only records without search_vector (NULL)
    python manage.py backfill_search_vectors --model=extraction --only-null
    
    # Backfill with custom batch size
    python manage.py backfill_search_vectors --batch-size=1000
    
    # Backfill both models
    python manage.py backfill_search_vectors --model=both
    
    # Dry run
    python manage.py backfill_search_vectors --dry-run

Performance:
    - Processes ~1000-2000 records/second (depends on text length)
    - For 500k documents: ~5-10 minutes
    - Batched updates minimize lock time
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.contrib.postgres.search import SearchVector
from core.models.document_analysis import DocumentExtraction, DocumentPage
from loguru import logger
import time


class Command(BaseCommand):
    help = 'Regenerate search_vector data from existing raw_text'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            choices=['extraction', 'page', 'both'],
            default='extraction',
            help='Which model to backfill (default: extraction)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Batch size for updates (default: 1000)'
        )
        parser.add_argument(
            '--only-null',
            action='store_true',
            help='Only update records where search_vector IS NULL'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be affected without making changes'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip trigger status check and confirmation'
        )
    
    def handle(self, *args, **options):
        """Main command handler"""
        # Determine which models to operate on
        if options['model'] == 'both':
            models = ['extraction', 'page']
        else:
            models = [options['model']]
        
        # Check trigger status
        if not options['force']:
            self._check_trigger_status()
        
        # Show what will be affected
        stats = self._get_stats(models, options['only_null'])
        self._show_stats(stats, options['dry_run'])
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] No changes made'))
            return
        
        # Confirmation
        if not options['force']:
            total_records = sum(s['to_backfill'] for s in stats.values())
            estimated_time = total_records / 1500  # Rough estimate: 1500 records/second
            
            self.stdout.write(self.style.WARNING(
                f'\nThis will regenerate search_vector for {total_records:,} records.\n'
                f'Estimated time: {estimated_time/60:.1f} minutes'
            ))
            
            confirm = input('Continue? [y/N]: ')
            if confirm.lower() != 'y':
                self.stdout.write('Aborted')
                return
        
        # Perform backfill
        start_time = time.time()
        
        for model in models:
            if stats[model]['to_backfill'] > 0:
                self.stdout.write(self.style.WARNING(f'\n=== Backfilling {model.upper()} ==='))
                self._backfill_model(model, options)
        
        elapsed = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Backfill completed in {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)'
        ))
        
        # Show final stats
        self.stdout.write('\n=== Final Status ===')
        final_stats = self._get_stats(models, only_null=False)
        self._show_stats(final_stats, dry_run=False)
    
    def _check_trigger_status(self):
        """Check if triggers are enabled and inform user"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    tgname,
                    CASE tgenabled 
                        WHEN 'O' THEN 'enabled'
                        WHEN 'D' THEN 'disabled'
                        ELSE 'unknown'
                    END as status
                FROM pg_trigger 
                WHERE tgname LIKE '%search_vector%'
            """)
            
            disabled_triggers = []
            for row in cursor.fetchall():
                if row[1] == 'disabled':
                    disabled_triggers.append(row[0])
            
            if disabled_triggers:
                self.stdout.write(self.style.WARNING(
                    f'\n⚠️  WARNING: Triggers are disabled: {", ".join(disabled_triggers)}\n'
                    f'New/updated documents will NOT be auto-indexed.\n'
                    f'Consider enabling triggers after backfill with:\n'
                    f'  python manage.py manage_postgres_search --enable-trigger\n'
                ))
    
    def _get_stats(self, models, only_null=False):
        """Get statistics for each model"""
        stats = {}
        
        with connection.cursor() as cursor:
            for model in models:
                if model == 'extraction':
                    table = 'core_documentextraction'
                    text_field = 'raw_text'
                else:
                    table = 'core_documentpage'
                    text_field = 'raw_text'
                
                # Count records to backfill
                if only_null:
                    cursor.execute(f"""
                        SELECT COUNT(*) 
                        FROM {table}
                        WHERE search_vector IS NULL 
                        AND {text_field} IS NOT NULL
                    """)
                else:
                    cursor.execute(f"""
                        SELECT COUNT(*) 
                        FROM {table}
                        WHERE {text_field} IS NOT NULL
                    """)
                
                to_backfill = cursor.fetchone()[0]
                
                # Get total counts
                cursor.execute(f"""
                    SELECT 
                        COUNT(*) FILTER (WHERE search_vector IS NULL) as null_count,
                        COUNT(*) FILTER (WHERE search_vector IS NOT NULL) as indexed_count,
                        COUNT(*) as total_count
                    FROM {table}
                """)
                
                counts = cursor.fetchone()
                
                stats[model] = {
                    'table': table,
                    'to_backfill': to_backfill,
                    'null_count': counts[0],
                    'indexed_count': counts[1],
                    'total_count': counts[2]
                }
        
        return stats
    
    def _show_stats(self, stats, dry_run=False):
        """Display statistics"""
        for model, data in stats.items():
            self.stdout.write(f'\n{model.upper()}:')
            self.stdout.write(f"  Total records: {data['total_count']:,}")
            self.stdout.write(f"  With search_vector: {data['indexed_count']:,}")
            self.stdout.write(f"  Without search_vector: {data['null_count']:,}")
            
            if data['to_backfill'] > 0:
                if dry_run:
                    self.stdout.write(self.style.WARNING(
                        f"  → Would backfill {data['to_backfill']:,} records"
                    ))
                else:
                    self.stdout.write(f"  → To backfill: {data['to_backfill']:,}")
            else:
                self.stdout.write(self.style.SUCCESS(
                    '  ✓ Nothing to backfill'
                ))
    
    def _backfill_model(self, model, options):
        """Backfill search_vector for a specific model"""
        if model == 'extraction':
            model_class = DocumentExtraction
            text_field = 'raw_text'
        else:
            model_class = DocumentPage
            text_field = 'raw_text'
        
        batch_size = options['batch_size']
        only_null = options['only_null']
        
        # Build queryset
        if only_null:
            qs = model_class.objects.filter(
                search_vector__isnull=True,
                **{f'{text_field}__isnull': False}
            )
        else:
            qs = model_class.objects.filter(
                **{f'{text_field}__isnull': False}
            )
        
        total = qs.count()
        
        if total == 0:
            self.stdout.write(self.style.SUCCESS('✓ No records to backfill'))
            return
        
        self.stdout.write(f'Backfilling search_vector for {total:,} records (batch size: {batch_size:,})...')
        
        # Process in batches
        processed = 0
        batch_num = 0
        start_time = time.time()
        
        while processed < total:
            batch_num += 1
            batch_start = time.time()
            
            # Get IDs for this batch
            batch_ids = list(qs.values_list('id', flat=True)[processed:processed + batch_size])
            
            if not batch_ids:
                break
            
            # Update search_vector for this batch using Django's SearchVector
            # Use Greek configuration for proper text analysis
            with transaction.atomic():
                model_class.objects.filter(id__in=batch_ids).update(
                    search_vector=SearchVector(text_field, config='greek')
                )
            
            processed += len(batch_ids)
            batch_elapsed = time.time() - batch_start
            total_elapsed = time.time() - start_time
            records_per_second = processed / total_elapsed if total_elapsed > 0 else 0
            estimated_remaining = (total - processed) / records_per_second if records_per_second > 0 else 0
            
            progress = (processed / total) * 100
            self.stdout.write(
                f'  Batch {batch_num}: Processed {len(batch_ids):,} records in {batch_elapsed:.1f}s '
                f'({processed:,}/{total:,} = {progress:.1f}%) '
                f'[{records_per_second:.0f} rec/s, ETA: {estimated_remaining:.0f}s]'
            )
        
        total_elapsed = time.time() - start_time
        avg_speed = processed / total_elapsed if total_elapsed > 0 else 0
        
        self.stdout.write(self.style.SUCCESS(
            f'✓ Backfilled search_vector for {processed:,} records in {total_elapsed:.1f}s '
            f'(avg: {avg_speed:.0f} records/second)'
        ))
        logger.info(f"Backfilled search_vector for {processed:,} {model} records in {total_elapsed:.1f}s")
