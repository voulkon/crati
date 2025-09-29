"""GEMI OpenData API Python Client Library."""

from .client import GemiDataClient
from .exceptions import (
    GemiAPIError, GemiAuthenticationError, GemiRateLimitError,
    GemiValidationError, GemiNotFoundError, GemiServerError,
    GemiConnectionError, GemiTimeoutError
)
from .schemas.company import (
    # CompanyDetail, CompanySummary, LocalOffice, 
    Prefecture, Municipality, CompanyResponse
    # BusinessStatus, LegalForm, OrganType, DocumentType, DecisionType,
    # OrganDecision, PublicDocument, Announcement
)

__version__ = "1.0.0"
__author__ = "Konstantinos Voulgaropoulos"

__all__ = [
    "GemiDataClient",
    # Exceptions
    "GemiAPIError", "GemiAuthenticationError", "GemiRateLimitError",
    "GemiValidationError", "GemiNotFoundError", "GemiServerError", 
    "GemiConnectionError", "GemiTimeoutError",
    # Schemas
    # "CompanySummary", "LocalOffice", 
    "Prefecture", 
    "Municipality", "CompanyResponse"
    # "BusinessStatus", 
    # "LegalForm", "OrganType", 
    # "DocumentType", "DecisionType", "OrganDecision", "PublicDocument", 
    # "Announcement"
]
