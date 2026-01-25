"""
Pipeline Orchestrator Settings.

Contains configuration for the DecisionPipelineOrchestrator and related settings.
"""

import os
import sys
from .orchestrator_utils import validate_and_format_public_key

# Import from base module for FRONTEND_HOSTNAMES and DEBUG
from .base import FRONTEND_HOSTNAMES, DEBUG
from loguru import logger

# ============================================================================
# Pipeline Orchestrator Settings
# ============================================================================

# Use DecisionPipelineOrchestrator as single source of truth
# When True: Disables legacy signals that auto-process documents/entities
# When False: Uses old signal-based approach (for backward compatibility)
USE_ORCHESTRATOR_MODE = os.environ.get("USE_ORCHESTRATOR_MODE", "True").lower() == "true"

# Enable legacy signals for backward compatibility
# Only used when USE_ORCHESTRATOR_MODE=False
ENABLE_LEGACY_DOCUMENT_SIGNALS = not USE_ORCHESTRATOR_MODE

if USE_ORCHESTRATOR_MODE:
    
    # logger.debug("=" * 50,
    # "🎯 Orchestrator Mode ENABLED:",
    # "   - Legacy document processing signals DISABLED",
    # "   - Use run_decision_pipeline_task for processing",
    # "   - No automatic document/entity processing on save",
    # "=" * 50)
    ...

# ============================================================================
# Clerk Authentication Settings
# ============================================================================

CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")

try:
    CLERK_JWT_PUBLIC_KEY = validate_and_format_public_key(
        os.getenv("CLERK_JWT_PUBLIC_KEY")
    )
except ValueError as e:
    logger.error(f"❌ Failed to load CLERK_JWT_PUBLIC_KEY: {e}")
    logger.error(
        "Please check your Coolify environment variable configuration. "
        "The key should be pasted as-is with actual newlines, not escaped \\n. "
        "Alternatively, you can paste it as a single line (without the newlines in the middle)."
    )
    # Set to None to prevent authentication from silently failing
    CLERK_JWT_PUBLIC_KEY = None

# Use the first frontend hostname, or localhost:3000 in debug
# Auto-derive from frontend domains
if FRONTEND_HOSTNAMES:
    default_clerk_audience = FRONTEND_HOSTNAMES[0]
else:
    default_clerk_audience = "localhost:3000" if DEBUG else "your-domain.com"

CLERK_JWT_AUDIENCE = os.getenv("CLERK_JWT_AUDIENCE", default_clerk_audience)
