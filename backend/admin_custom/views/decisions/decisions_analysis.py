from core.services.decision_analysis_service import DecisionAnalysisService
from datetime import date, datetime, timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render
from loguru import logger


@staff_member_required
def daily_decision_analysis(request):
    """Admin view for analyzing daily decision composition"""
    # Get target date from request
    date_param = request.GET.get("date", "")

    try:
        if date_param:
            target_date = datetime.strptime(date_param, "%Y-%m-%d").date()
        else:
            target_date = date.today() - timedelta(days=1)  # Default to yesterday
    except ValueError:
        target_date = date.today() - timedelta(days=1)

    # Initialize analysis service
    analysis_service = DecisionAnalysisService()

    # Get comprehensive analysis
    analysis_data = analysis_service.get_daily_decision_analysis(target_date)

    # Calculate navigation dates
    prev_date = target_date - timedelta(days=1)
    next_date = target_date + timedelta(days=1)

    # Don't allow future dates
    if next_date > date.today():
        next_date = None

    context = {
        "target_date": target_date,
        "prev_date": prev_date,
        "next_date": next_date,
        "analysis": analysis_data,
    }

    return render(request, "admin/daily_decision_analysis.html", context)

@staff_member_required
def decision_analysis_api(request):
    """JSON API endpoint for decision analysis data"""
    target_date_str = request.GET.get("date")
    comparison_dates = request.GET.getlist("compare_dates")

    analysis_service = DecisionAnalysisService()

    try:
        if target_date_str:
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
            analysis_data = analysis_service.get_daily_decision_analysis(target_date)
        elif comparison_dates:
            # Compare multiple dates
            dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in comparison_dates]
            analysis_data = analysis_service.compare_daily_patterns(dates)
        else:
            # Default to yesterday
            target_date = date.today() - timedelta(days=1)
            analysis_data = analysis_service.get_daily_decision_analysis(target_date)

        return JsonResponse(analysis_data, safe=False)

    except ValueError as e:
        return JsonResponse({"error": f"Invalid date format: {str(e)}"}, status=400)
    except Exception as e:
        logger.error(f"Decision analysis API error: {str(e)}")
        return JsonResponse({"error": "Internal server error"}, status=500)

