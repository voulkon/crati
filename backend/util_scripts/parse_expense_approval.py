#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Parser for Greek Government Expense Approval Documents (ΕΓΚΡΙΣΗ ΔΑΠΑΝΗΣ)
Decomposes documents into structured, searchable components.
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import json


@dataclass
class ExpenseApprovalDocument:
    """Structured representation of an expense approval document."""
    
    # High-value semantic content (index with high weight)
    purpose: Optional[str] = None  # ΑΙΤΙΑ ΠΛΗΡΩΜΗΣ - THE GOLD!
    beneficiary_name: Optional[str] = None
    
    # Structured metadata (filterable, not for semantic search)
    document_id: Optional[str] = None  # ADA code
    document_number: Optional[str] = None  # Αριθμός Εντάλματος
    year: Optional[int] = None
    total_amount: Optional[float] = None
    deductions: Optional[float] = None
    net_amount: Optional[float] = None
    
    # Organization info
    organization: Optional[str] = None  # ΔΗΜΟΣ
    region: Optional[str] = None  # ΠΕΡΙΦΕΡΕΙΑ
    department: Optional[str] = None  # ΔΙΕΥΘΥΝΣΗ
    
    # Beneficiary details
    afm: Optional[str] = None  # ΑΦΜ
    doy: Optional[str] = None  # ΔΟΥ
    beneficiary_address: Optional[str] = None
    
    # Budget codes (secondary searchable)
    budget_codes: List[Dict[str, any]] = None  # [{code, amount, description}]
    
    # References (secondary searchable)
    references: List[str] = None  # ΑΑΥ, Αρ.Παρ., etc.
    
    # Funding info
    funding_source: Optional[str] = None  # Χρηματοδότηση
    account_type: Optional[str] = None  # ΤΑΚΤΙΚΑ, etc.
    
    # Date
    date: Optional[str] = None
    
    # Raw text sections (for debugging/fallback)
    raw_text: Optional[str] = None
    
    def __post_init__(self):
        if self.budget_codes is None:
            self.budget_codes = []
        if self.references is None:
            self.references = []


class ExpenseApprovalParser:
    """Parser for Greek expense approval documents."""
    
    # Regex patterns
    PATTERNS = {
        'document_number': r'Αριθμός Εντάλματος[:\s]+([^\n]+)',
        'year': r'Οικονομικό Έτος[:\s]+(\d{4})',
        'total_amount': r'Σύνολο\s+(?:Εντάλματος)?[:\s]+([0-9.,]+)',
        'deductions': r'Κρατήσεις[:\s]+([0-9.,]+)',
        'net_amount': r'Στο(?:ν)?\s+[Δδ]ικαιούχο[:\s]+([0-9.,]+)',
        'afm': r'Α\.?Φ\.?Μ\.?[:\s]+(\d{9})',
        'doy': r'Δ\.?Ο\.?Υ\.?[:\s]+([^\n]+)',
        'ada_code': r':\s*([Α-ΩA-Z0-9]{4}[Α-ΩA-Z]{4}-[Α-ΩA-Z0-9]{3})',
        'budget_code': r'(\d{2}\.\d{2,4}(?:\.\d{2,4}){1,2})',
        'aay': r'Α\.?Α\.?Υ\.?:\s*([^\n]+)',
        'ar_par': r'Αρ\.?Παρ\.?:\s*([^\n]+)',
        'funding': r'Χρηματοδότηση[:\s]+([^\n]+)',
        'account_type': r'(ΤΑΚΤΙΚΑ|ΕΚΤΑΚΤΑ|ΙΔΙΑ ΕΣΟΔΑ)',
        'date': r'(\d{1,2}/\d{1,2}/\d{4})',
    }
    
    # Stop words for signature section detection
    SIGNATURE_MARKERS = [
        'Ο ΣΥΝΤΑΚΤΗΣ', 'Ο ΣΥΝΤΑΞΑΣ', 'Ο ΛΑΒΩΝ', 'O ΛΑΒΩΝ',
        'ΠΡΟΪΣΤΑΜΕΝΗ', 'ΠΡΟΪΣΤΑΜΕΝΟΣ', 'ΤΑΜΕΙΟΥ', 'ΤΑΜΙΑΣ',
        'ΟΙΚΟΝΟΜΙΚΩΝ ΥΠΗΡΕΣΙΩΝ', 'ΛΟΓΙΣΤΗΡΙΟΥ',
        'έλαβα', 'Α.Δ.Τ:', 'Αρ.Επιταγής',
        'Ministry of', 'Digital', 'Governance', 'Digitally signed'
    ]
    
    # Purpose section markers
    PURPOSE_MARKERS = [
        'ΑΙΤΙΑ ΠΛΗΡΩΜΗΣ', 'ΓΙΑ ΤΙΣ ΑΝΑΓΚΕΣ', 'ΠΡΟΜΗΘΕΙΑ',
        'Συντήρηση', 'Εργασίες', 'ΕΡΓΑΣΙΕΣ'
    ]
    
    def __init__(self):
        self.compiled_patterns = {
            key: re.compile(pattern, re.IGNORECASE | re.MULTILINE)
            for key, pattern in self.PATTERNS.items()
        }
    
    def parse(self, text: str) -> ExpenseApprovalDocument:
        """Parse a document and extract structured data."""
        doc = ExpenseApprovalDocument()
        doc.raw_text = text
        
        # Extract basic metadata
        doc.document_number = self._extract_single(text, 'document_number')
        doc.year = self._extract_year(text)
        doc.total_amount = self._extract_amount(text, 'total_amount')
        doc.deductions = self._extract_amount(text, 'deductions')
        doc.net_amount = self._extract_amount(text, 'net_amount')
        
        # Extract identifiers
        doc.afm = self._extract_single(text, 'afm')
        doc.doy = self._extract_single(text, 'doy')
        doc.document_id = self._extract_ada_code(text)
        
        # Extract funding info
        doc.funding_source = self._extract_single(text, 'funding')
        doc.account_type = self._extract_single(text, 'account_type')
        
        # Extract organization info
        doc.organization = self._extract_organization(text)
        doc.region = self._extract_region(text)
        doc.department = self._extract_department(text)
        
        # Extract THE GOLD - purpose/reason
        doc.purpose = self._extract_purpose(text)
        
        # Extract beneficiary
        doc.beneficiary_name = self._extract_beneficiary(text)
        doc.beneficiary_address = self._extract_beneficiary_address(text)
        
        # Extract budget codes
        doc.budget_codes = self._extract_budget_codes(text)
        
        # Extract references
        doc.references = self._extract_references(text)
        
        # Extract date
        doc.date = self._extract_date(text)
        
        return doc
    
    def _extract_single(self, text: str, pattern_key: str) -> Optional[str]:
        """Extract a single value using a regex pattern."""
        match = self.compiled_patterns[pattern_key].search(text)
        if match:
            value = match.group(1).strip()
            return value if value else None
        return None
    
    def _extract_year(self, text: str) -> Optional[int]:
        """Extract year as integer."""
        year_str = self._extract_single(text, 'year')
        if year_str:
            try:
                return int(year_str)
            except ValueError:
                pass
        return None
    
    def _extract_amount(self, text: str, pattern_key: str) -> Optional[float]:
        """Extract monetary amount and convert to float."""
        amount_str = self._extract_single(text, pattern_key)
        if amount_str:
            # Remove thousand separators and convert comma to dot
            amount_str = amount_str.replace('.', '').replace(',', '.')
            try:
                return float(amount_str)
            except ValueError:
                pass
        return None
    
    def _extract_ada_code(self, text: str) -> Optional[str]:
        """Extract ADA code (document ID)."""
        # Usually at the end of the document
        match = self.compiled_patterns['ada_code'].search(text)
        if match:
            return match.group(1)
        return None
    
    def _extract_organization(self, text: str) -> Optional[str]:
        """Extract organization name (ΔΗΜΟΣ)."""
        # Look for ΔΗΜΟΣ in first 300 chars
        header = text[:300]
        match = re.search(r'ΔΗΜΟΣ\s+([^\n]+)', header, re.IGNORECASE)
        if match:
            org = match.group(1).strip()
            # Clean up
            org = re.sub(r'\s+Α\.?Φ\.?Μ\.?.*', '', org)
            return org
        return None
    
    def _extract_region(self, text: str) -> Optional[str]:
        """Extract region name (ΠΕΡΙΦΕΡΕΙΑ)."""
        header = text[:300]
        match = re.search(r'(ΠΕΡΙΦΕΡΕΙΑ[^\n]+|[^\n]+ΜΑΚΕΔΟΝΙΑΣ|[^\n]+ΗΠΕΙΡΟΥ|[^\n]+ΘΕΣΣΑΛΙΑΣ)', 
                         header, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None
    
    def _extract_department(self, text: str) -> Optional[str]:
        """Extract department name (ΔΙΕΥΘΥΝΣΗ)."""
        header = text[:300]
        match = re.search(r'ΔΙΕΥΘΥΝΣΗ[:\s]+([^\n]+)', header, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None
    
    def _extract_purpose(self, text: str) -> Optional[str]:
        """
        Extract the purpose/reason - THE GOLD!
        This is the most important field for semantic search.
        """
        # Strategy 1: Look for explicit "ΑΙΤΙΑ ΠΛΗΡΩΜΗΣ" section
        match = re.search(
            r'ΑΙΤΙΑ ΠΛΗΡΩΜΗΣ[:\s]*\n(.+?)(?:\n\s*\n|\n[Α-Ω]+\s+[Α-Ω]+\s+(?:του|ΤΟΥ)|Κωδικός|Δ\.Ο\.Υ\.|Α\.Φ\.Μ\.|ΤΗΛ:)',
            text,
            re.DOTALL | re.IGNORECASE
        )
        if match:
            purpose = match.group(1).strip()
            # Clean up
            purpose = self._clean_purpose(purpose)
            if purpose and len(purpose) > 10:
                return purpose
        
        # Strategy 2: Look for descriptive phrases after amounts
        match = re.search(
            r'(?:πληρώσατε|ΠΛΗΡΩΜΗΣ)[^\n]*\n+(.+?)(?:\n\s*\n|[Α-Ω]{3,}\s+[Α-Ω]{3,})',
            text,
            re.DOTALL | re.IGNORECASE
        )
        if match:
            purpose = match.group(1).strip()
            purpose = self._clean_purpose(purpose)
            if purpose and len(purpose) > 20:
                return purpose
        
        # Strategy 3: Look for budget code descriptions
        budget_codes = self._extract_budget_codes(text)
        if budget_codes:
            descriptions = [bc.get('description', '') for bc in budget_codes 
                          if bc.get('description') and len(bc.get('description', '')) > 20]
            if descriptions:
                return descriptions[0]
        
        return None
    
    def _clean_purpose(self, text: str) -> str:
        """Clean up extracted purpose text."""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove numbers at start (from lists)
        text = re.sub(r'^\d+\.?\s*', '', text)
        
        # Remove common boilerplate
        text = re.sub(r'Πληρ\.\s*Κρατ\.\s*Συν\.', '', text, re.IGNORECASE)
        text = re.sub(r'ΠΟΣΟ', '', text, re.IGNORECASE)
        text = re.sub(r'\d+[.,]\d{2}\s*€?', '', text)  # Remove amounts
        
        # Trim
        text = text.strip(' :-\n')
        
        return text
    
    def _extract_beneficiary(self, text: str) -> Optional[str]:
        """Extract beneficiary name."""
        # Strategy 1: Look near "Στον Δικαιούχο" or "Δικαιούχο"
        match = re.search(
            r'(?:Στον\s+)?[Δδ]ικαιούχο[:\s]*[^\n]*\n+([Α-ΩΆ-Ώ][^\n]+?)(?:\n|Α\.Φ\.Μ|ΑΙΑΝΗ|ΘΟΥΚΙΔΙΔΗ|ΜΑΚΡΥ)',
            text,
            re.IGNORECASE
        )
        if match:
            name = match.group(1).strip()
            # Clean up
            name = re.sub(r'\s*Α\.?Φ\.?Μ\.?.*', '', name)
            name = re.sub(r'\s*\d{9}.*', '', name)
            name = re.sub(r'\s*Σύνολο.*', '', name)
            name = re.sub(r'\s*Κρατήσεις.*', '', name)
            name = re.sub(r'\s*\d+[.,]\d+.*', '', name)
            if len(name) > 5:
                return name
        
        # Strategy 2: Look for name in signature section
        match = re.search(
            r'υπογεγραμμένος\s+([Α-ΩΆ-Ώ][^\n]+?)(?:\s+με\s+Α\.Δ\.Τ|ΚΛΠ)',
            text,
            re.IGNORECASE
        )
        if match:
            name = match.group(1).strip()
            if len(name) > 5:
                return name
        
        return None
    
    def _extract_beneficiary_address(self, text: str) -> Optional[str]:
        """Extract beneficiary address."""
        # Look for address-like patterns after beneficiary name
        match = re.search(
            r'(?:Δικαιούχο|beneficiary)[^\n]*\n[^\n]+\n([Α-ΩΆ-Ώ\s\d]+(?:ΚΟΖΑΝΗΣ|ΙΩΑΝΝΙΝΑ|ΑΘΗΝΑ|ΛΑΡΙΣΑ)[^\n]*)',
            text,
            re.IGNORECASE
        )
        if match:
            return match.group(1).strip()
        return None
    
    def _extract_budget_codes(self, text: str) -> List[Dict[str, any]]:
        """Extract budget codes (ΚΑΕ) with amounts and descriptions."""
        codes = []
        
        # Look for budget code sections
        sections = re.finditer(
            r'(\d{2}\.\d{2,4}(?:\.\d{2,4}){1,2})\s*([^\n]*?)\s*([0-9.,]+)',
            text,
            re.MULTILINE
        )
        
        for match in sections:
            code = match.group(1)
            description = match.group(2).strip()
            amount_str = match.group(3)
            
            # Parse amount
            amount = None
            try:
                amount = float(amount_str.replace('.', '').replace(',', '.'))
            except ValueError:
                pass
            
            # Clean description
            description = re.sub(r'^\d+\s+', '', description)
            description = description.strip()
            
            codes.append({
                'code': code,
                'description': description if description else None,
                'amount': amount
            })
        
        return codes
    
    def _extract_references(self, text: str) -> List[str]:
        """Extract reference numbers (ΑΑΥ, Αρ.Παρ., etc.)."""
        refs = []
        
        # Extract AAY references
        for match in self.compiled_patterns['aay'].finditer(text):
            ref = match.group(1).strip()
            if ref:
                refs.append(f"ΑΑΥ: {ref}")
        
        # Extract Ar.Par references
        for match in self.compiled_patterns['ar_par'].finditer(text):
            ref = match.group(1).strip()
            if ref:
                refs.append(f"Αρ.Παρ.: {ref}")
        
        return refs
    
    def _extract_date(self, text: str) -> Optional[str]:
        """Extract document date."""
        # Usually near signatures at the end
        dates = self.compiled_patterns['date'].findall(text)
        if dates:
            # Return the last date found (usually signature date)
            return dates[-1]
        return None
    
    def to_opensearch_doc(self, doc: ExpenseApprovalDocument) -> Dict:
        """
        Convert to OpenSearch document format with weighted fields.
        """
        return {
            # Document ID
            'document_id': doc.document_id,
            
            # High-priority searchable fields (boost: 3.0)
            'purpose': doc.purpose,
            
            # Medium-priority searchable fields (boost: 2.0)
            'beneficiary_name': doc.beneficiary_name,
            
            # Low-priority searchable fields (boost: 1.5)
            'budget_descriptions': [
                bc['description'] for bc in doc.budget_codes 
                if bc.get('description')
            ],
            
            # Structured metadata (filterable, not boosted)
            'metadata': {
                'document_number': doc.document_number,
                'year': doc.year,
                'total_amount': doc.total_amount,
                'deductions': doc.deductions,
                'net_amount': doc.net_amount,
                'organization': doc.organization,
                'region': doc.region,
                'department': doc.department,
                'afm': doc.afm,
                'doy': doc.doy,
                'funding_source': doc.funding_source,
                'account_type': doc.account_type,
                'date': doc.date,
            },
            
            # Secondary searchable (boost: 1.0)
            'budget_codes': [bc['code'] for bc in doc.budget_codes],
            'references': doc.references,
            
            # Not indexed for search (stored only)
            'beneficiary_address': doc.beneficiary_address,
            'budget_details': doc.budget_codes,
        }


def parse_file(filepath: str) -> ExpenseApprovalDocument:
    """Parse a single file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    
    parser = ExpenseApprovalParser()
    return parser.parse(text)


def main():
    """Demo usage."""
    import sys
    from pathlib import Path
    
    if len(sys.argv) < 2:
        print("Usage: python parse_expense_approval.py <file_path>")
        sys.exit(1)
    
    filepath = sys.argv[1]
    
    # Parse document
    doc = parse_file(filepath)
    
    # Convert to OpenSearch format
    parser = ExpenseApprovalParser()
    opensearch_doc = parser.to_opensearch_doc(doc)
    
    # Print results
    print("=" * 80)
    print(f"PARSED: {Path(filepath).name}")
    print("=" * 80)
    print("\n🏆 HIGH-VALUE CONTENT (Purpose):")
    print(f"  {doc.purpose or 'NOT FOUND'}")
    print("\n👤 Beneficiary:")
    print(f"  {doc.beneficiary_name or 'NOT FOUND'}")
    print("\n📊 Metadata:")
    print(f"  Doc ID: {doc.document_id}")
    print(f"  Doc Number: {doc.document_number}")
    print(f"  Year: {doc.year}")
    print(f"  Amount: €{doc.total_amount:,.2f}" if doc.total_amount else "  Amount: N/A")
    print(f"  Net: €{doc.net_amount:,.2f}" if doc.net_amount else "  Net: N/A")
    print(f"  Organization: {doc.organization}")
    print(f"  AFM: {doc.afm}")
    print(f"  DOY: {doc.doy}")
    print("\n💰 Budget Codes:")
    for bc in doc.budget_codes[:3]:  # Show first 3
        print(f"  {bc['code']}: {bc.get('description', 'N/A')[:60]} (€{bc.get('amount', 0):,.2f})")
    if len(doc.budget_codes) > 3:
        print(f"  ... and {len(doc.budget_codes) - 3} more")
    print("\n📎 References:")
    for ref in doc.references[:3]:  # Show first 3
        print(f"  {ref}")
    if len(doc.references) > 3:
        print(f"  ... and {len(doc.references) - 3} more")
    
    print("\n" + "=" * 80)
    print("OPENSEARCH DOCUMENT (JSON):")
    print("=" * 80)
    print(json.dumps(opensearch_doc, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
