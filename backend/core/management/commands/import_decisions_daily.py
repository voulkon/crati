from django.core.management.base import BaseCommand
from core.services.decision_ingestion_service import DecisionIngestionService
from core.fetchers.diavgeia_fetcher import DiavgeiaFetcher
from core.importers.decisions import DecisionImporter
from datetime import date, datetime, timedelta
from django.utils import timezone
import requests
from loguru import logger
from core.services.decision_analysis_service import DecisionAnalysisService


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
            help="Use Celery for distributed processing",
        )

    def handle(self, *args, **options):
        # Create service components
        fetcher = DiavgeiaFetcher()
        decision_importer = DecisionImporter()
        service = DecisionIngestionService(
            diavgeia_fetcher=fetcher,
            decision_importer=decision_importer,
        )

        target_date = options.get("date") or (date.today() - timedelta(days=1))

        self.stdout.write(f"Starting sync for {target_date}")

        try:
            if options["incremental"]:
                # Use incremental sync
                result = service.fetch_decisions_since_timestamp(save_to_db=True)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Incremental sync completed. Processed {result['processed_count']} decisions."
                    )
                )
            else:
                # Fetch specific day
                result = service.fetch_daily_decisions(
                    target_date=target_date,
                    save_to_db=True,
                    want_it_distributed=options["distributed"],
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Daily sync completed for {target_date}. Processed {result['processed_count']} decisions."
                    )
                )

            # Reconciliation
            if options["reconcile"]:
                self._reconcile_counts(target_date, result["processed_count"])

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Sync failed: {str(e)}"))
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
