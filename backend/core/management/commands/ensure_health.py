"""
Management command for running health guarantee checks.

Usage:
    # Dry run to see what would be fixed
    python manage.py ensure_health --dry-run
    
    # Actually fix everything
    python manage.py ensure_health
    
    # Fix only specific steps
    python manage.py ensure_health --step organizations
    python manage.py ensure_health --step entities
    python manage.py ensure_health --step companies
    python manage.py ensure_health --step opensearch
    
    # Target specific decisions
    python manage.py ensure_health --adas ADA1 ADA2 ADA3
"""

from django.core.management.base import BaseCommand
from loguru import logger

from core.services.decision_health_guarantee_service import DecisionHealthGuaranteeService


class Command(BaseCommand):
    help = 'Ensure data consistency across all decisions by running health guarantee checks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only show what would be done without making changes',
        )
        parser.add_argument(
            '--step',
            type=str,
            choices=['organizations', 'entities', 'companies', 'opensearch', 'all'],
            default='all',
            help='Run only a specific health check step',
        )
        parser.add_argument(
            '--max-workers',
            type=int,
            default=5,
            help='Number of parallel workers (default: 5)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Batch size for processing (default: 100)',
        )
        parser.add_argument(
            '--adas',
            nargs='+',
            help='Specific decision ADAs to check (optional)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        step = options['step']
        max_workers = options['max_workers']
        batch_size = options['batch_size']
        decision_adas = options.get('adas')

        service = DecisionHealthGuaranteeService()

        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 Running in DRY RUN mode - no changes will be made'))

        if decision_adas:
            self.stdout.write(
                self.style.WARNING(f'🎯 Targeting {len(decision_adas)} specific decisions')
            )

        try:
            if step == 'all':
                results = service.ensure_all_decisions_health(
                    max_workers=max_workers,
                    dry_run=dry_run,
                    decision_adas=decision_adas
                )
            elif step == 'organizations':
                results = service.ensure_organization_resolution(
                    batch_size=batch_size,
                    max_workers=max_workers,
                    dry_run=dry_run,
                    decision_adas=decision_adas
                )
            elif step == 'entities':
                results = service.ensure_entity_extraction(
                    batch_size=batch_size,
                    max_workers=max_workers,
                    dry_run=dry_run,
                    decision_adas=decision_adas
                )
            elif step == 'companies':
                # Extract AFMs from targeted decisions if specified
                afm_list = None
                if decision_adas:
                    from core.models.entities import DecisionEntityRelationship
                    afm_list = list(
                        DecisionEntityRelationship.objects.filter(
                            decision__ada__in=decision_adas
                        ).values_list('entity__afm', flat=True).distinct()
                    )
                
                results = service.ensure_company_enrichment(
                    batch_size=batch_size,
                    dry_run=dry_run,
                    afm_list=afm_list
                )
            elif step == 'opensearch':
                results = service.ensure_opensearch_indexing(
                    batch_size=batch_size,
                    max_workers=max_workers,
                    dry_run=dry_run,
                    decision_adas=decision_adas
                )

            # Print results summary
            self.stdout.write('\n' + '=' * 80)
            self.stdout.write(self.style.SUCCESS('✅ Health guarantee check completed'))
            self.stdout.write('=' * 80 + '\n')

            if step == 'all':
                self._print_full_summary(results)
            else:
                self._print_step_summary(results, step)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Health guarantee check failed: {e}'))
            logger.exception("Health guarantee check failed")
            raise

    def _print_full_summary(self, results):
        """Print summary for full health check."""
        steps = results.get('steps', {})

        for step_name, step_results in steps.items():
            self.stdout.write(f'\n{step_name.replace("_", " ").title()}:')

            if step_results.get('status') == 'skipped':
                # Show what would be processed if feature was enabled
                total_missing = step_results.get('total_missing', 0)
                total_extractions = step_results.get('total_extractions', 0)
                would_process = step_results.get('would_process_if_enabled', 0)
                would_check = step_results.get('would_check_if_enabled', 0)
                
                if total_missing > 0 or would_process > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  Skipped (feature flag disabled) - '
                            f'{total_missing or would_process} items would be processed if enabled'
                        )
                    )
                elif total_extractions > 0 or would_check > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  Skipped (feature flag disabled) - '
                            f'{total_extractions or would_check} items would be checked if enabled'
                        )
                    )
                else:
                    self.stdout.write(self.style.WARNING('  Skipped (feature flag disabled)'))
                continue

            if 'total_missing' in step_results:
                total = step_results['total_missing']
                processed = step_results.get('resolved') or step_results.get('processed') or step_results.get('indexed') or step_results.get('queued', 0)
                self.stdout.write(f'  {processed}/{total} items processed')

            if step_results.get('errors'):
                error_count = len(step_results['errors'])
                self.stdout.write(self.style.ERROR(f'  {error_count} errors'))

    def _print_step_summary(self, results, step_name):
        """Print summary for individual step."""
        if results.get('status') == 'skipped':
            total_missing = results.get('total_missing', 0)
            total_extractions = results.get('total_extractions', 0)
            would_process = results.get('would_process_if_enabled', 0)
            would_check = results.get('would_check_if_enabled', 0)
            
            if total_missing > 0 or would_process > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f'{step_name.title()} skipped (feature flag disabled)\n'
                        f'Would process: {total_missing or would_process} items if enabled'
                    )
                )
            elif total_extractions > 0 or would_check > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f'{step_name.title()} skipped (feature flag disabled)\n'
                        f'Would check: {total_extractions or would_check} items if enabled'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'{step_name.title()} skipped (feature flag disabled)')
                )
            
            # Show sample if available
            if results.get('sample_entities'):
                self.stdout.write('\n  Sample entities that would be enriched:')
                for entity in results['sample_entities'][:5]:
                    self.stdout.write(f'    - AFM: {entity.get("afm")}, Name: {entity.get("name")}')
            
            if results.get('sample_documents'):
                self.stdout.write('\n  Sample documents that would be checked:')
                for doc in results['sample_documents'][:5]:
                    self.stdout.write(
                        f'    - {doc.get("ada")} ({doc.get("text_length")} chars)'
                    )
            
            return

        if results.get('status') == 'dry_run':
            self.stdout.write(self.style.WARNING('DRY RUN RESULTS:'))
            self.stdout.write(f'  Would process: {results.get("total_missing", 0)} items')
            if 'sample_decisions' in results:
                self.stdout.write('  Sample decisions:')
                for item in results['sample_decisions'][:5]:
                    self.stdout.write(f'    - {item}')
            return

        total = results.get('total_missing', 0)
        processed = results.get('resolved') or results.get('processed') or results.get('indexed') or results.get('queued', 0)

        self.stdout.write(f'Processed: {processed}/{total}')

        if results.get('errors'):
            self.stdout.write(self.style.ERROR(f'Errors: {len(results["errors"])}'))
            self.stdout.write('First few errors:')
            for error in results['errors'][:5]:
                self.stdout.write(f'  - {error.get("ada")}: {error.get("error")}')