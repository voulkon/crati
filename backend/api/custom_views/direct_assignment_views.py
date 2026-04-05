"""
API views for Direct Assignment Detection

These views provide endpoints for querying decisions classified as direct assignments.

Classification is done by DirectAssignmentDetectionService and stored in DecisionClassification model.
Results are cached for fast querying.

Available endpoints:
- DirectAssignmentDecisionListView: List all classified direct assignment decisions
- DirectAssignmentStatsView: Get statistics about direct assignments

Note: Entity-level aggregation views (top entities, etc.) are deprecated and will be 
reimplemented using FinancialCalculationService in a future iteration.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from core.models.decisions import Decision
from core.models.decision_classification import DecisionClassification


class DirectAssignmentDecisionListView(APIView):
    """
    List all decisions classified as direct assignments.
    
    Uses DecisionClassification model for FAST filtering (indexed).
    No heavy computation needed - results are pre-classified by the pipeline.
    """
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Get paginated list of direct assignment decisions",
        manual_parameters=[
            openapi.Parameter(
                'page',
                openapi.IN_QUERY,
                description="Page number",
                type=openapi.TYPE_INTEGER,
                default=1
            ),
            openapi.Parameter(
                'page_size',
                openapi.IN_QUERY,
                description="Number of results per page",
                type=openapi.TYPE_INTEGER,
                default=20
            ),
            openapi.Parameter(
                'start_date',
                openapi.IN_QUERY,
                description="Filter by issue date (YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATE
            ),
            openapi.Parameter(
                'end_date',
                openapi.IN_QUERY,
                description="Filter by issue date (YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATE
            ),
            openapi.Parameter(
                'organization',
                openapi.IN_QUERY,
                description="Filter by organization UID",
                type=openapi.TYPE_STRING
            ),
        ],
        responses={
            200: openapi.Response(
                description="Paginated list of direct assignment decisions",
                examples={
                    "application/json": {
                        "count": 1250,
                        "next": "http://api/direct-assignments/?page=2",
                        "previous": null,
                        "results": [
                            {
                                "ada": "ΩΔΦΓ46ΨΘ3Δ-ΤΛΩ",
                                "subject": "ΑΝΑΘΕΣΗ ΥΠΗΡΕΣΙΩΝ ΚΑΘΑΡΙΟΤΗΤΑΣ",
                                "amount": "15000.00",
                                "issue_date": "2026-01-15T10:30:00Z",
                                "organization": {
                                    "uid": "99221811",
                                    "label": "ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ"
                                },
                                "classified_at": "2026-01-15T10:35:00Z"
                            }
                        ]
                    }
                }
            )
        }
    )
    def get(self, request):
        """Get paginated list of direct assignment decisions"""
        
        # Start with classified decisions (uses covering index!)
        queryset = Decision.objects.filter(
            classification__is_direct_assignment=True
        ).select_related('classification', 'organization', 'decision_type')
        
        # Date filters
        start_date = request.query_params.get('start_date')
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            queryset = queryset.filter(issue_date__gte=start_date)
        
        end_date = request.query_params.get('end_date')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
            queryset = queryset.filter(issue_date__lte=end_date)
        
        # Organization filter
        organization = request.query_params.get('organization')
        if organization:
            queryset = queryset.filter(organization__uid=organization)
        
        # Order by most recent first
        queryset = queryset.order_by('-issue_date')
        
        # Paginate
        paginator = PageNumberPagination()
        paginator.page_size = int(request.query_params.get('page_size', 20))
        page = paginator.paginate_queryset(queryset, request)
        
        # Serialize
        results = [
            {
                'ada': d.ada,
                'subject': d.subject,
                'amount': str(d.amount) if d.amount else None,
                'issue_date': d.issue_date.isoformat() if d.issue_date else None,
                'organization': {
                    'uid': d.organization.uid if d.organization else None,
                    'label': d.organization.label if d.organization else None
                },
                'decision_type': {
                    'uid': d.decision_type.uid if d.decision_type else None,
                    'label': d.decision_type.label if d.decision_type else None
                },
                'classified_at': d.classification.classified_at.isoformat() if hasattr(d, 'classification') else None,
                'classifier_version': d.classification.classifier_version if hasattr(d, 'classification') else None
            }
            for d in page
        ]
        
        return paginator.get_paginated_response(results)


class DirectAssignmentStatsView(APIView):
    """
    Get overall statistics about direct assignment classifications.
    
    Provides counts and aggregates for monitoring and dashboards.
    """
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Get direct assignment statistics",
        responses={
            200: openapi.Response(
                description="Classification statistics",
                examples={
                    "application/json": {
                        "total_decisions": 125000,
                        "classified_decisions": 120000,
                        "direct_assignments": 12500,
                        "non_direct_assignments": 107500,
                        "unclassified": 5000,
                        "classification_rate": 96.0
                    }
                }
            )
        }
    )
    def get(self, request):
        """Get classification statistics"""
        
        from django.db.models import Count, Q
        
        # Get counts
        total_decisions = Decision.objects.count()
        
        classification_stats = DecisionClassification.objects.aggregate(
            direct_assignments=Count('decision', filter=Q(is_direct_assignment=True)),
            non_direct_assignments=Count('decision', filter=Q(is_direct_assignment=False)),
            total_classified=Count('decision')
        )
        
        direct_assignments = classification_stats['direct_assignments'] or 0
        non_direct_assignments = classification_stats['non_direct_assignments'] or 0
        classified_decisions = classification_stats['total_classified'] or 0
        unclassified = total_decisions - classified_decisions
        
        classification_rate = (classified_decisions / total_decisions * 100) if total_decisions > 0 else 0
        
        return Response({
            'total_decisions': total_decisions,
            'classified_decisions': classified_decisions,
            'direct_assignments': direct_assignments,
            'non_direct_assignments': non_direct_assignments,
            'unclassified': unclassified,
            'classification_rate': round(classification_rate, 2),
            'threshold_eur': '37200.00',
            'decision_type': 'Δ.1'
        })


# =============================================================================
# DEPRECATED VIEWS (to be reimplemented with FinancialCalculationService)
# =============================================================================

class DirectAssignmentTopEntitiesView(APIView):
    """
    DEPRECATED: This view used DirectAssignmentEntitySummary which has been removed.
    
    Will be reimplemented using FinancialCalculationService for entity aggregations.
    For now, returns 501 Not Implemented.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        return Response(
            {
                'error': 'This endpoint is being reimplemented',
                'message': 'Entity aggregation views will use FinancialCalculationService',
                'status': 'deprecated'
            },
            status=status.HTTP_501_NOT_IMPLEMENTED
        )


class DirectAssignmentRecentEntitiesView(APIView):
    """
    DEPRECATED: This view used DirectAssignmentEntitySummary which has been removed.
    
    Will be reimplemented using FinancialCalculationService for entity aggregations.
    """
class DirectAssignmentRecentEntitiesView(APIView):
    """
    DEPRECATED: This view used DirectAssignmentEntitySummary which has been removed.
    
    Will be reimplemented using FinancialCalculationService for entity aggregations.
    For now, returns 501 Not Implemented.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        return Response(
            {
                'error': 'This endpoint is being reimplemented',
                'message': 'Entity aggregation views will use FinancialCalculationService',
                'status': 'deprecated'
            },
            status=status.HTTP_501_NOT_IMPLEMENTED
        )


class DirectAssignmentEntityDetailView(APIView):
    """
    DEPRECATED: This view used DirectAssignmentEntitySummary which has been removed.
    
    Will be reimplemented using FinancialCalculationService for entity aggregations.
    For now, returns 501 Not Implemented.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, afm):
        return Response(
            {
                'error': 'This endpoint is being reimplemented',
                'message': 'Entity aggregation views will use FinancialCalculationService',
                'status': 'deprecated'
            },
            status=status.HTTP_501_NOT_IMPLEMENTED
        )


class DirectAssignmentSummaryView(APIView):
    """
    DEPRECATED: This view used DirectAssignmentEntitySummary which has been removed.
    
    Will be reimplemented using FinancialCalculationService for entity aggregations.
    For now, returns 501 Not Implemented.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        return Response(
            {
                'error': 'This endpoint is being reimplemented',
                'message': 'Use DirectAssignmentStatsView for classification statistics',
                'status': 'deprecated'
            },
            status=status.HTTP_501_NOT_IMPLEMENTED
        )
        
        # Date filters
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
        
        summary = direct_assignment_service.get_overall_summary(
            start_date=start_date,
            end_date=end_date
        )
        
        # Convert Decimal to float
        summary['decisions']['total_amount'] = float(summary['decisions']['total_amount'])
        summary['decisions']['avg_amount'] = float(summary['decisions']['avg_amount'])
        summary['decisions']['max_amount'] = float(summary['decisions']['max_amount'])
        
        for entity in summary['entities']['top_5']:
            entity['total_amount'] = float(entity['total_amount'])
            entity['avg_amount'] = float(entity['avg_amount'])
            entity['max_amount'] = float(entity['max_amount'])
            entity['min_amount'] = float(entity['min_amount'])
        
        return Response(summary)


class DirectAssignmentValidateDecisionView(APIView):
    """
    Validate if a specific decision qualifies as a direct assignment below threshold.
    """
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Validate if a decision qualifies as direct assignment below threshold"
    )
    def get(self, request, ada):
        """Validate decision by ADA"""
        
        from core.models.decisions import Decision
        
        try:
            decision = Decision.objects.select_related('decision_type').get(ada=ada)
        except Decision.DoesNotExist:
            return Response(
                {'error': f'Decision with ADA {ada} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        validation = direct_assignment_service.validate_decision_eligibility(decision)
        
        return Response(validation)
