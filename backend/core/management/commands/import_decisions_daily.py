from django.core.management.base import BaseCommand
from core.services.decision_ingestion_service import DecisionIngestionService
from core.fetchers.diavgeia_fetcher import DiavgeiaFetcher
from core.importers.decisions import DecisionImporter
from datetime import date, datetime, timedelta
from django.utils import timezone
import requests
from loguru import logger
from core.services.decision_analysis_service import DecisionAnalysisService
import os


class Command(BaseCommand):
    help = "Sync decisions for a specific day with reconciliation"

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
            help="Date to sync (YYYY-MM-DD). Defaults to yesterday.",
        )
        parser.add_argument(
            "--incremental",
            action="store_true",
            help="Use incremental sync based on last timestamp",
        )
        parser.add_argument(
            "--reconcile",
            action="store_true",
            help="Compare results with official API counts",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force sync even if already completed for this date",
        )
        parser.add_argument(
            "--distributed",
            action="store_true",
            help="Use Celery for distributed processing (fetches full day, distributes storage)",
        )

    def handle(self, *args, **options):
        # Setup file logging for this import run
        target_date = options.get("date") or (date.today() - timedelta(days=1))
        log_dir = "/code/logs"
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = f"{log_dir}/import_decisions_{target_date.strftime('%Y%m%d')}_{datetime.now().strftime('%H%M%S')}.log"
        
        # Configure loguru to write to file
        logger.add(
            log_file,
            rotation="100 MB",
            retention="30 days",
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} - {message}",
            compression="gz"
        )
        
        logger.info(f"Starting import for {target_date} - Logs will be saved to: {log_file}")
        self.stdout.write(f"Starting sync for {target_date}")
        self.stdout.write(f"Logs are being saved to: {log_file}")

        # Create service components
        fetcher = DiavgeiaFetcher()
        decision_importer = DecisionImporter()
        service = DecisionIngestionService(
            diavgeia_fetcher=fetcher,
            decision_importer=decision_importer,
        )

        try:
            if options["incremental"]:
                # Use incremental sync
                logger.info("Starting incremental sync")
                result = service.fetch_decisions_since_timestamp(save_to_db=True)
                logger.info(f"Incremental sync completed. Processed {result['processed_count']} decisions.")
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Incremental sync completed. Processed {result['processed_count']} decisions."
                    )
                )
            else:
                # Check if we should use the new distributed approach
                if options["distributed"]:
                    # Use the new pickle-based distributed approach
                    from core.tasks.tasks_decisions_import import fetch_daily_decisions_distributed
                    
                    logger.info(f"Starting distributed sync for {target_date}")
                    
                    task = fetch_daily_decisions_distributed.delay(
                        target_date_str=target_date.isoformat()
                    )
                    
                    logger.info(f"Dispatched orchestrator task: {task.id}")
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Distributed sync dispatched for {target_date}. "
                            f"Orchestrator task ID: {task.id}"
                        )
                    )
                    self.stdout.write(
                        f"The system will:"
                    )
                    self.stdout.write(
                        f"  1. Fetch all ~1500 decisions for {target_date} (single task)"
                    )
                    self.stdout.write(
                        f"  2. Split storage work into ~30 parallel tasks (50 decisions each)"
                    )
                    self.stdout.write(
                        f"Monitor: python manage.py monitor_distributed_import --status --pickles"
                    )
                    
                    result = {
                        'status': 'dispatched',
                        'processed_count': 'pending',
                        'task_id': task.id
                    }
                else:
                    # Use traditional single-process approach with batching
                    logger.info(f"Starting single-process sync for {target_date}")
                    result = service.fetch_daily_decisions(
                        target_date=target_date,
                        save_to_db=True,
                        want_it_distributed=False,  # Force local processing
                    )
                    logger.info(f"Single-process sync completed for {target_date}. Processed {result['processed_count']} decisions.")
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Single-process sync completed for {target_date}. Processed {result['processed_count']} decisions."
                        )
                    )

            # Reconciliation
            if options["reconcile"]:
                logger.info("Starting reconciliation")
                self._reconcile_counts(target_date, result["processed_count"])

            logger.info(f"Import process completed successfully. Check logs at: {log_file}")
            self.stdout.write(f"Import completed. Full logs available at: {log_file}")

        except Exception as e:
            logger.error(f"Import process failed: {str(e)}", exc_info=True)
            self.stdout.write(self.style.ERROR(f"Sync failed: {str(e)}"))
            self.stdout.write(f"Check detailed error logs at: {log_file}")
            raise

    def _reconcile_counts(self, target_date: date, our_count: int):
        """Compare our counts with official API and show detailed analysis"""
        try:
            # Get official counts
            response = requests.get(
                "https://diavgeia.gov.gr/static/api/search/countPerDayLastMonth",
                timeout=30,
            )
            response.raise_for_status()

            official_data = response.json()

            # Find count for our target date
            target_timestamp = target_date.strftime("%Y-%m-%dT00:00:00Z")
            official_count = None

            for item in official_data.get("facetsResults", []):
                if item["label"] == target_timestamp:
                    official_count = item["counter"]
                    break

            if official_count is not None:
                difference = our_count - official_count
                percentage_diff = (
                    (difference / official_count * 100) if official_count > 0 else 0
                )

                self.stdout.write(f"Reconciliation for {target_date}:")
                self.stdout.write(f"  Official count: {official_count}")
                self.stdout.write(f"  Our count: {our_count}")
                self.stdout.write(
                    f"  Difference: {difference} ({percentage_diff:.2f}%)"
                )

                if abs(percentage_diff) > 5:  # More than 5% difference
                    self.stdout.write(
                        self.style.WARNING(
                            f"Large discrepancy detected! Consider investigating."
                        )
                    )

                    # Show detailed analysis for large discrepancies
                    self._show_detailed_analysis(target_date)
                else:
                    self.stdout.write(
                        self.style.SUCCESS("Counts are reasonably aligned.")
                    )
            else:
                self.stdout.write(
                    self.style.WARNING(f"No official count found for {target_date}")
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Reconciliation failed: {str(e)}"))

    def _show_detailed_analysis(self, target_date: date):
        """Show detailed analysis when discrepancies are found"""
        try:
            analysis_service = DecisionAnalysisService()
            analysis = analysis_service.get_daily_decision_analysis(target_date)

            if not analysis["has_data"]:
                self.stdout.write("  No decisions found in local database")
                return

            self.stdout.write("\n  Detailed Analysis:")
            self.stdout.write(f"    Total decisions: {analysis['total_count']}")

            # Show top 3 organizations
            if analysis["top_organizations"]:
                self.stdout.write("    Top organizations:")
                for i, org in enumerate(analysis["top_organizations"][:3], 1):
                    self.stdout.write(
                        f"      {i}. {org['organization__label']}: {org['count']} decisions"
                    )

            # Show top 3 types
            if analysis["top_types"]:
                self.stdout.write("    Top decision types:")
                for i, act_type in enumerate(analysis["top_types"][:3], 1):
                    self.stdout.write(
                        f"      {i}. {act_type['type__label']}: {act_type['count']} decisions"
                    )

            # Show quality indicators
            quality = analysis["quality_indicators"]
            self.stdout.write(
                f"    Data completeness: {quality['completeness_score']}%"
            )

            if quality["missing_subject_count"] > 0:
                self.stdout.write(
                    f"    Missing subjects: {quality['missing_subject_count']}"
                )
            if quality["missing_organization_count"] > 0:
                self.stdout.write(
                    f"    Missing organizations: {quality['missing_organization_count']}"
                )

        except Exception as e:
            self.stdout.write(f"    Failed to get detailed analysis: {str(e)}")
