# Decision Health Check System - Implementation Summary

## Overview

I've created a comprehensive decision health monitoring system for your complex ingestion pipeline. This system provides visibility and control over each stage of the decision processing flow, helping you quickly identify and resolve issues.

## What Was Built

### 1. Core Models (`core/models/decision_health.py`)

- **DecisionHealthCheck**: Stores health status for each decision across all pipeline components
- **DecisionHealthSummary**: Aggregated statistics for dashboard reporting  
- **HealthStatus**: Enumeration (HEALTHY, WARNING, ERROR, UNKNOWN)

### 2. Health Check Service (`core/services/decision_health_service.py`)

Comprehensive service that checks:
- **Ingestion**: Basic decision data completeness
- **Relations**: Signers, units, organization properly linked
- **Entities**: AFM entities extracted and associated
- **Document Extraction**: PDF downloaded and text extracted  
- **OpenSearch**: Document indexed and searchable
- **Coverage**: DateCoverage records updated

### 3. Enhanced OpenSearch Service 

Added verification methods to existing service:
- `health_check()`: Test connectivity and functionality
- `document_exists()`: Check if specific decision is indexed
- `verify_document_searchability()`: Test actual search functionality
- `analyze_index_health()`: Overall system health analysis

### 4. Admin Interface (`core/admin_decision_health.py`)

Rich Django admin integration with:
- **Health Dashboard**: Visual overview with statistics
- **Bulk Operations**: Run health checks on multiple decisions
- **Detailed Investigation**: Inspect findings with JSON details
- **Export Capabilities**: JSON reports for external analysis
- **Quick Actions**: Refresh, filter, and navigate easily

### 5. Management Commands

#### `check_decision_health.py`
```bash
# Check specific decision
python manage.py check_decision_health --ada "ΑΔΑ123456"

# Check recent decisions  
python manage.py check_decision_health --days 7 --limit 100

# Export health report
python manage.py check_decision_health --days 30 --export-json report.json
```

#### `investigate_decision_issues.py`
```bash
# Find and investigate problematic decisions
python manage.py investigate_decision_issues --status ERROR --limit 50

# Auto-fix issues where possible
python manage.py investigate_decision_issues --auto-fix --component opensearch

# Detailed analysis with report
python manage.py investigate_decision_issues --detailed-analysis --export-report issues.json
```

### 6. Templates

- **Health Dashboard**: Visual overview with component breakdowns
- **Bulk Check Interface**: Easy form for running batch operations

## Key Features

### Comprehensive Pipeline Coverage
Each decision is checked across 6 critical components:
1. **Ingestion** - Basic data validation
2. **Relations** - Linked entities (signers, units, org)
3. **Entities** - AFM extraction and company data
4. **Document Extraction** - PDF processing status  
5. **OpenSearch** - Indexing and searchability
6. **Coverage** - Statistics tracking

### Smart Issue Detection
- Automatically categorizes issues by severity
- Provides specific error messages and details
- Suggests concrete fix actions where possible
- Tests actual functionality (not just existence)

### Admin Integration  
- Seamlessly integrates with your existing Django admin
- Color-coded status indicators for quick visual assessment
- Bulk operations for efficiency
- Direct links to related records for investigation

### Automated Fixes
The investigation command can automatically attempt fixes for:
- Re-queuing document processing tasks
- Re-triggering OpenSearch indexing
- Updating coverage records
- Fetching missing company data

### Export and Reporting
- JSON exports for external analysis
- Detailed findings with technical information
- Summary statistics and trends
- Integration-ready data format

## Usage Scenarios

### Daily Monitoring
```bash
# Quick check of recent decisions
python manage.py check_decision_health --days 1 --problems-only
```

### Issue Investigation
```bash
# Find OpenSearch problems and fix them
python manage.py investigate_decision_issues --component opensearch --auto-fix
```

### Periodic Health Reports
```bash  
# Weekly comprehensive report
python manage.py check_decision_health --days 7 --export-json weekly_health.json
```

### Emergency Debugging
1. Go to Admin → Decision Health Checks → Health Dashboard
2. Identify problem areas from component breakdown
3. Use "Bulk Health Check" to focus on specific timeframe
4. Investigate individual decisions with detailed findings
5. Use management commands for bulk fixes

## Integration Points

### With Existing Pipeline
- Uses existing models (Decision, DocumentExtraction, etc.)
- Leverages your OpenSearch service
- Integrates with Celery task system
- Respects your signal architecture

### With Admin Interface
- Registered in your custom admin site
- Follows your existing admin patterns  
- Uses your styling and navigation
- Provides additional dashboard views

### With Monitoring
- Can be integrated with your logging system
- Provides metrics for alerting
- Exportable data for external monitoring
- Command-line tools for automation

## Benefits for Your Use Case

### Immediate Problem Identification
Instead of being "in the dark" about missing OpenSearch documents, you can now:
- Quickly identify which decisions have indexing issues
- See exactly where in the pipeline problems occur
- Get specific error messages and fix suggestions

### Proactive Monitoring
- Run daily checks to catch issues early
- Monitor pipeline health trends over time
- Get alerts about systematic problems

### Efficient Debugging  
- Focus investigation on specific components
- Get technical details for troubleshooting
- Attempt automated fixes where safe

### Operational Control
- Bulk operations for efficiency
- Export capabilities for reporting
- Integration with existing admin workflow

This system gives you the visibility and control you need to confidently operate your complex decision ingestion pipeline, with the ability to quickly identify and resolve issues before they impact your users.

## Next Steps

1. **Database Migration**: Run migrations to create the health check tables
2. **Initial Health Check**: Run a bulk health check to establish baseline
3. **Admin Access**: Navigate to the health dashboard to see current status
4. **Automation Setup**: Add periodic health checks to your cron jobs
5. **Team Training**: Show your team how to use the investigation tools

The system is designed to be immediately useful while providing room for future enhancements based on your operational experience.