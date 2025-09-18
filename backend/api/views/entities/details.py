from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.conf import settings
from django.db.models import Count, Sum, Avg
from core.models.entities import AFMEntity, DecisionEntityRelationship
from core.models.decisions import Decision
from core.services.financial_calculation_service import financial_service
from core.utils.performance_monitoring import monitor_query_performance


@api_view(["GET"])
@permission_classes([AllowAny if settings.DEBUG else IsAuthenticated])
@monitor_query_performance(include_context=True)
def afm_entity_detail(request, afm):
    """Get detailed AFM entity information with statistics."""
    try:
        entity = AFMEntity.objects.get(afm=afm)

        # Use the financial service for comprehensive statistics
        financial_summary = financial_service.get_entity_financial_summary(entity)

        # Get basic relationship statistics (non-financial)
        relationships = DecisionEntityRelationship.objects.filter(entity=entity)

        # Activity statistics
        activity_days = (entity.last_seen - entity.first_seen).days
        avg_decisions_per_month = (
            (financial_summary["decision_count"] / max(activity_days / 30, 1))
            if activity_days > 0
            else 0
        )

        entity_data = {
            "afm": entity.afm,
            "name": entity.name,
            "entity_type": entity.entity_type,
            "total_appearances": entity.total_appearances,
            "first_seen": entity.first_seen,
            "last_seen": entity.last_seen,
        }

        # Use financial service data for statistics
        statistics = {
            "total_decisions": financial_summary["decision_count"],
            "total_amount": float(financial_summary["total_received"]),
            "decisions_with_amounts": financial_summary[
                "decision_count"
            ],  # All relationships with linked amounts
            "unique_organizations": financial_summary["unique_organizations"],
            "unique_roles": len(financial_summary["role_breakdown"]),
            "most_frequent_organization": (
                financial_summary["top_organizations"][0]
                if financial_summary["top_organizations"]
                else None
            ),
            "avg_decisions_per_month": avg_decisions_per_month,
            "avg_amount": float(financial_summary["avg_amount"]),
        }

        # Format role breakdown for the response
        available_roles = [
            {
                "role": role_data["role"],
                "count": role_data["decision_count"],
                "total_amount": (
                    float(role_data["total_amount"])
                    if role_data["total_amount"]
                    else None
                ),
            }
            for role_data in financial_summary["role_breakdown"]
        ]

        return Response(
            {
                "entity": entity_data,
                "statistics": statistics,
                "available_roles": available_roles,
            }
        )

    except AFMEntity.DoesNotExist:
        return Response({"error": "AFM entity not found"}, status=404)


@api_view(["GET"])
@permission_classes([AllowAny if settings.DEBUG else IsAuthenticated])
@monitor_query_performance(include_context=True)
def afm_entity_decisions(request, afm):
    """Get decisions related to an AFM entity."""
    try:
        entity = AFMEntity.objects.get(afm=afm)

        # Get query parameters
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 20))
        sort_by = request.GET.get("sort", "recent")
        roles_filter = (
            request.GET.get("roles", "").split(",") if request.GET.get("roles") else []
        )

        # Base query with optimized joins
        relationships = (
            DecisionEntityRelationship.objects.filter(entity=entity)
            .select_related(
                "decision", "decision__organization", "decision__decision_type"
            )
            .prefetch_related("linked_amounts")
        )

        # Apply role filter
        if roles_filter and roles_filter != [""]:
            relationships = relationships.filter(role__in=roles_filter)

        # Apply sorting - now using linked amounts instead of decision.amount
        if sort_by == "recent":
            relationships = relationships.order_by("-decision__issue_date")
        elif sort_by == "oldest":
            relationships = relationships.order_by("decision__issue_date")
        elif sort_by == "amount_desc":
            # Annotate with total linked amount for sorting
            relationships = relationships.annotate(
                total_linked_amount=Sum("linked_amounts__amount")
            ).order_by("-total_linked_amount")
        elif sort_by == "amount_asc":
            relationships = relationships.annotate(
                total_linked_amount=Sum("linked_amounts__amount")
            ).order_by("total_linked_amount")

        # Pagination
        total_items = relationships.count()
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        paginated_relationships = relationships[start_idx:end_idx]

        # Serialize decisions with linked amounts
        decisions = []
        for rel in paginated_relationships:
            decision = rel.decision

            # Calculate total amount from linked amounts
            total_amount = sum(
                amount.amount
                for amount in rel.linked_amounts.all()
                if amount.amount is not None
            )

            decisions.append(
                {
                    "id": decision.id,
                    "ada": decision.ada,
                    "subject": decision.subject,
                    "amount": float(total_amount) if total_amount > 0 else None,
                    "legacy_amount": (
                        float(decision.amount) if decision.amount else None
                    ),  # Keep for comparison
                    "issue_date": decision.issue_date,
                    "status": decision.status,
                    "document_url": decision.document_url,
                    "has_document_content": hasattr(decision, "document_extraction"),
                    "organization": (
                        {
                            "uid": decision.organization.uid,
                            "label": decision.organization.label,
                        }
                        if decision.organization
                        else None
                    ),
                    "decision_type": (
                        {
                            "uid": decision.decision_type.uid,
                            "label": decision.decision_type.label,
                        }
                        if decision.decision_type
                        else None
                    ),
                    "entity_role": rel.role,
                    "confidence_score": rel.confidence_score,
                    "amount_count": rel.linked_amounts.count(),  # Number of amount fields linked
                }
            )

        pagination_info = {
            "current_page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": (total_items + page_size - 1) // page_size,
            "has_next": end_idx < total_items,
            "has_previous": page > 1,
        }

        return Response({"results": decisions, "pagination": pagination_info})

    except AFMEntity.DoesNotExist:
        return Response({"error": "AFM entity not found"}, status=404)
