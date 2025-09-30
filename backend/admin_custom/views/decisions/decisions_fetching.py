from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from datetime import date, datetime, timedelta
from loguru import logger

@staff_member_required
def fetch_daily_decisions(request):
    """Admin view to trigger fetching decisions for a specific day"""
    if request.method == "POST":
        target_date_str = request.POST.get("date")
        force = request.POST.get("force", False)

        try:
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return JsonResponse(
                {"success": False, "error": "Invalid date format"}, status=400
            )

        try:
            # Import here to avoid circular imports
            from core.fetchers.diavgeia_fetcher import DiavgeiaFetcher
            from core.importers.decisions import DecisionImporter
            from core.services.decision_ingestion_service import (
                DecisionIngestionService,
            )

            # Create service components
            fetcher = DiavgeiaFetcher()
            decision_importer = DecisionImporter()
            service = DecisionIngestionService(
                diavgeia_fetcher=fetcher,
                decision_importer=decision_importer,
            )

            # Fetch decisions for the day
            result = service.fetch_daily_decisions(
                target_date=target_date, save_to_db=True
            )

            return JsonResponse(
                {
                    "success": True,
                    "message": f'Successfully fetched {result["processed_count"]} decisions for {target_date}',
                    "processed_count": result["processed_count"],
                    "date": target_date.isoformat(),
                }
            )

        except Exception as e:
            logger.error(f"Error fetching decisions for {target_date}: {str(e)}")
            return JsonResponse(
                {"success": False, "error": f"Failed to fetch decisions: {str(e)}"},
                status=500,
            )

    return JsonResponse({"success": False, "error": "Method not allowed"}, status=405)

