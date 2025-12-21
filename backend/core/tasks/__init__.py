"""
Import all tasks to maintain backward compatibility
"""

# Import all tasks from sub-modules
from .tasks_documents import (
    process_document_task,
    process_scanned_document_task,
    generate_summary_task,
    process_document_batch,
    collect_batch_results,
    process_document_task_enhanced,
    process_documents_task_enhanced,
    process_documents_task,
)

from .tasks_decisions_import import (
    fetch_daily_decisions_to_pickle,
    store_decisions_from_pickle,
    fetch_daily_decisions_distributed,
)

from .tasks_decisions import (
    fetch_decisions_for_increment,
    process_fetch_period,
    collect_results,
    import_ministry_decisions_task,
    import_decisions_task,
    update_coverage_stats,
    daily_decisions_sync_task,
    reconcile_daily_counts,
)

from .tasks_opensearch import (
    index_recent_documents,
    check_opensearch_sync,
    create_opensearch_backup,
    daily_opensearch_backup,
    bulk_reindex_missing_documents,
    reindex_specific_adas,
)

from .tasks_entities import (
    fetch_company_data_for_entities,
    process_entities_needing_company_data,
    fetch_company_data_for_single_afm,
)

from .tasks_misc import (
    ping,
    test_tracing,
)

# This ensures all tasks are available when importing from core.tasks
__all__ = [
    # Documents
    "process_document_task",
    "process_scanned_document_task",
    "generate_summary_task",
    "process_document_batch",
    "collect_batch_results",
    "process_document_task_enhanced",
    "process_documents_task_enhanced",
    "process_documents_task",
    # Decisions Import (New)
    "fetch_daily_decisions_to_pickle",
    "store_decisions_from_pickle", 
    "fetch_daily_decisions_distributed",
    # Decisions (Legacy)
    "fetch_decisions_for_increment",
    "process_fetch_period",
    "collect_results",
    "import_ministry_decisions_task",
    "import_decisions_task",
    "update_coverage_stats",
    "daily_decisions_sync_task",
    "reconcile_daily_counts",
    # OpenSearch
    "index_recent_documents",
    "check_opensearch_sync",
    "create_opensearch_backup",
    "daily_opensearch_backup",
    "bulk_reindex_missing_documents",
    "reindex_specific_adas",
    # Entities
    "fetch_company_data_for_entities",
    "process_entities_needing_company_data",
    # Misc
    "ping",
    "test_tracing",
]
