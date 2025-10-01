from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.db import models
from datetime import datetime, timedelta

from core.models.decisions import Decision
from core.models.decision_health import DecisionHealthCheck, DecisionHealthSummary, HealthStatus
from core.services.decision_health_service import DecisionHealthService


@staff_member_required
def health_dashboard_view(request):
    """Dashboard view showing health statistics"""
    # Get recent health checks (convert to list to avoid slice/filter issue)
    recent_checks_queryset = DecisionHealthCheck.objects.select_related('decision').order_by('-last_checked_at')[:100]
    recent_checks = list(recent_checks_queryset)
    
    # Calculate statistics
    stats = {
        'total': len(recent_checks),
        'healthy': sum(1 for hc in recent_checks if hc.overall_status == HealthStatus.HEALTHY),
        'warnings': sum(1 for hc in recent_checks if hc.overall_status == HealthStatus.WARNING), 
        'errors': sum(1 for hc in recent_checks if hc.overall_status == HealthStatus.ERROR),
        'unknown': sum(1 for hc in recent_checks if hc.overall_status == HealthStatus.UNKNOWN),
    }
    
    # Component statistics
    component_stats = {}
    components = ['ingestion', 'relations', 'entities', 'document_extraction', 'opensearch', 'coverage']
    for component in components:
        component_stats[component] = {
            'healthy': sum(1 for hc in recent_checks if getattr(hc, f"{component}_status") == HealthStatus.HEALTHY),
            'warnings': sum(1 for hc in recent_checks if getattr(hc, f"{component}_status") == HealthStatus.WARNING),
            'errors': sum(1 for hc in recent_checks if getattr(hc, f"{component}_status") == HealthStatus.ERROR),
        }
    
    # Recent problematic decisions (get fresh data for problems)
    recent_problems = DecisionHealthCheck.objects.filter(
        models.Q(has_errors=True) | models.Q(has_warnings=True)
    ).select_related('decision').order_by('-last_checked_at')[:20]
    
    context = {
        'title': 'Decision Health Dashboard',
        'stats': stats,
        'component_stats': component_stats,
        'recent_problems': recent_problems,
    }
    
    return render(request, 'admin/decision_health_dashboard.html', context)


@staff_member_required
def refresh_single_check(request, pk):
    """Refresh health check for a single decision"""
    health_check = get_object_or_404(DecisionHealthCheck, pk=pk)
    health_service = DecisionHealthService()
    
    try:
        health_service.check_decision_health(health_check.decision, force_refresh=True)
        messages.success(request, f"Health check refreshed for decision {health_check.decision.ada}")
    except Exception as e:
        messages.error(request, f"Failed to refresh health check: {str(e)}")
    
    return redirect('admin:core_decisionhealthcheck_changelist')


@staff_member_required
def bulk_check_view(request):
    """View for running bulk health checks"""
    if request.method == 'POST':
        # Parse parameters
        days_back = int(request.POST.get('days_back', 7))
        organization_id = request.POST.get('organization_id')
        limit = int(request.POST.get('limit', 100))
        
        # Build query for decisions to check
        start_date = datetime.now() - timedelta(days=days_back)
        
        queryset = Decision.objects.filter(issue_date__gte=start_date)
        if organization_id:
            queryset = queryset.filter(organization_id=organization_id)
        
        decisions = list(queryset.order_by('-issue_date')[:limit])
        
        # Run health checks
        health_service = DecisionHealthService()
        results = health_service.bulk_check_decisions(decisions)
        
        context = {
            'title': 'Bulk Health Check Results',
            'results': results,
            'checked_count': len(decisions),
        }
        
        return render(request, 'admin/bulk_health_check_results.html', context)
    
    # GET request - show form
    context = {
        'title': 'Bulk Health Check',
    }
    
    return render(request, 'admin/bulk_health_check.html', context)


@staff_member_required
def quick_health_check_view(request):
    """Quick health check for recent decisions"""
    
    if request.method == 'POST':
        # Run health check
        days = int(request.POST.get('days', 1))
        limit = int(request.POST.get('limit', 20))
        
        # Get recent decisions
        since_date = timezone.now() - timedelta(days=days)
        recent_decisions = Decision.objects.filter(
            issue_date__gte=since_date
        ).order_by('-issue_date')[:limit]
        
        if recent_decisions:
            health_service = DecisionHealthService()
            results = health_service.bulk_check_decisions(list(recent_decisions))
            
            context = {
                'title': 'Quick Health Check Results',
                'results': results,
                'checked_decisions': len(recent_decisions),
                'days': days,
            }
            return render(request, 'admin/quick_health_results.html', context)
        else:
            context = {
                'title': 'Quick Health Check',
                'no_decisions': True,
                'days': days,
            }
            return render(request, 'admin/quick_health_check.html', context)
    
    # GET request - show form  
    context = {
        'title': 'Quick Health Check',
    }
    return render(request, 'admin/quick_health_check.html', context)
