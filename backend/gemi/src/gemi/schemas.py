from pydantic import BaseModel, Field, AnyUrl
from datetime import date
from typing import List, Optional

# Models for company data
class Announcement(BaseModel):
    """Details of an announcement related to a company organ decision."""
    decision_date: date = Field(alias="decisionDate")
    subject: str = Field(alias="decisionSubject")
    announcement_date: date = Field(alias="announcementDate")
    announcement_file: Optional[AnyUrl] = Field(alias="announcementFile", description="URL of the announcement document")
    completion_date: Optional[date] = Field(alias="completionDate")

class OrganDecision(BaseModel):
    """Represents a decision by a company organ (e.g., Board or General Meeting) with related publication info."""
    decision_date: date = Field(alias="decisionDate")
    organ_type: str = Field(alias="organType")               # e.g., type of organ (Board, General Assembly):contentReference[oaicite:9]{index=9}
    protocol_number: Optional[str] = Field(alias="protocolNumber")
    submission_date: Optional[date] = Field(alias="submissionDate")
    minutes_text: Optional[str] = Field(alias="minutes", description="Minutes of the meeting (if available)")
    decision_summary: Optional[str] = Field(alias="decisionSummary")
    invitation_posted: Optional[bool] = Field(alias="invitationPost", description="Whether an invitation was posted")
    invitation_post_date: Optional[date] = Field(alias="invitationPostDate")
    publication: Optional[str] = Field(alias="publicationPaper", description="Newspaper or medium of publication")
    publication_date: Optional[date] = Field(alias="publicationPaperDate")
    announcements: Optional[List[Announcement]] = Field(alias="announcementRecords", default_factory=list)

class PublicDocument(BaseModel):
    """Represents a public document filed for the company (e.g., filings, certificates)."""
    document_id: Optional[str] = Field(alias="documentId")
    document_type: Optional[str] = Field(alias="documentType")
    title: Optional[str] = Field(alias="title")
    publish_date: Optional[date] = Field(alias="date")
    url: Optional[AnyUrl] = Field(alias="url", description="Download link for the document")

class CompanyDetail(BaseModel):
    """Full public profile of a company from the GEMI OpenData API."""
    gemh_number: str = Field(alias="gemhNumber")
    name: str = Field(alias="name")
    trade_name: Optional[str] = Field(alias="distinctiveTitle")
    vat_number: Optional[str] = Field(alias="afm")  # 'afm' (Greek Tax ID):contentReference[oaicite:10]{index=10}
    local_office: Optional[str] = Field(alias="gemiOffice", description="Name of the local GEMI service")
    status: Optional[str] = Field(alias="status")
    registration_date: Optional[date] = Field(alias="registrationDate", description="Date of GEMI registration")
    publicity_documents: List[PublicDocument] = Field(alias="publicityDocuments", default_factory=list)
    organ_decisions: List[OrganDecision] = Field(alias="organDecisions", default_factory=list)

class CompanySummary(BaseModel):
    """Summary information for a company (used in search results)."""
    gemh_number: str = Field(alias="gemhNumber")
    name: str = Field(alias="name")
    trade_name: Optional[str] = Field(alias="distinctiveTitle")
    vat_number: Optional[str] = Field(alias="afm")
    status: Optional[str] = Field(alias="status")

# Models for reference (parametric) data lists
class LocalOffice(BaseModel):
    """A local GEMI registry office (Chamber)."""
    id: int
    name: str

class Prefecture(BaseModel):
    """A regional unit (nomos) for company location."""
    id: int
    name: str

class Municipality(BaseModel):
    """A municipality for company location."""
    id: int
    name: str

class BusinessStatus(BaseModel):
    """A possible status of a business (e.g., Active, Inactive)."""
    id: int
    name: str

class LegalForm(BaseModel):
    """A legal form of a company (e.g., SA, LLC, sole proprietorship)."""
    id: int
    name: str

class OrganType(BaseModel):
    """Type of company organ (e.g., Board of Directors, General Meeting)."""
    id: int
    name: str

class DocumentType(BaseModel):
    """Type of public document in GEMI (e.g., Announcement, Decision)."""
    id: int
    name: str

class DecisionType(BaseModel):
    """Type of company decision (category of decisions in GEMI)."""
    id: int
    name: str
