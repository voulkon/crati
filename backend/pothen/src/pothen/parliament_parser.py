"""Parliament HTML parser for extracting declaration links."""

import re
import logging
from typing import List, Dict, Set, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, Tag

from .base_scraper import BaseScraperClient
from .constants import PARLIAMENT_BASE_URL, DECLARATIONS_YEAR_URL_TEMPLATE
from .exceptions import PothenParsingError, PothenScrapingError
from .schemas import DeclarationEntry, YearlyDeclarations, DeclarationType

logger = logging.getLogger(__name__)


class ParliamentParser:
    """Parser for Hellenic Parliament declaration pages."""
    
    def __init__(self, scraper_client: BaseScraperClient):
        self.scraper = scraper_client
    
    def get_available_years(self, landing_url: str) -> List[int]:
        """
        Extract available declaration years from the landing page.
        
        Looks for links like:
        <a href="...Diloseis-Periousiakis-Katastasis2024">ΔΗΛΩΣΕΙΣ...2024...</a>
        """
        logger.info(f"Fetching available years from {landing_url}")
        
        try:
            response = self.scraper.get(landing_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            years = set()
            
            # Look for links containing "Diloseis-Periousiakis-Katastasis" followed by year
            year_pattern = re.compile(r'Diloseis-Periousiakis-Katastasis(\d{4})')
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                match = year_pattern.search(href)
                if match:
                    year = int(match.group(1))
                    years.add(year)
                    logger.debug(f"Found year {year} in link: {href}")
            
            if not years:
                raise PothenParsingError("No declaration years found on landing page")
            
            sorted_years = sorted(years, reverse=True)
            logger.info(f"Found {len(sorted_years)} available years: {sorted_years}")
            return sorted_years
            
        except Exception as e:
            raise PothenScrapingError(f"Failed to parse available years: {str(e)}") from e
    
    def parse_year_page(self, year: int) -> YearlyDeclarations:
        """
        Parse a year-specific declarations page to extract all PDF links.
        
        Expected HTML structure:
        <tr>
            <td><a name="K">KUNEVA</a></td>
            <td>KOSTADINKA</td>
            <td><a href="...pdf" target="_blank">Δήλωση</a></td>
        </tr>
        """
        url = DECLARATIONS_YEAR_URL_TEMPLATE.format(year=year)
        logger.info(f"Parsing declarations for year {year} from {url}")\n        \n        try:\n            response = self.scraper.get(url)\n            soup = BeautifulSoup(response.text, 'html.parser')\n            \n            declarations = YearlyDeclarations(\n                year=year,\n                page_url=url\n            )\n            \n            # Find all table rows with declaration data\n            rows = soup.find_all('tr')\n            \n            for row in rows:\n                entry = self._parse_declaration_row(row, year)\n                if entry:\n                    declarations.entries.append(entry)\n            \n            logger.info(f"Found {len(declarations.entries)} declarations for {year}")\n            \n            if not declarations.entries:\n                raise PothenParsingError(f"No declarations found for year {year}")\n            \n            return declarations\n            \n        except Exception as e:\n            raise PothenScrapingError(f"Failed to parse year {year} page: {str(e)}") from e\n    \n    def _parse_declaration_row(self, row: Tag, year: int) -> Optional[DeclarationEntry]:\n        """Parse a single table row to extract declaration information."""\n        try:\n            cells = row.find_all('td')\n            \n            # Need at least 3 cells: last_name, first_name, pdf_link\n            if len(cells) < 3:\n                return None\n            \n            # Extract names\n            last_name_cell = cells[0]\n            first_name_cell = cells[1]\n            pdf_link_cell = cells[2]\n            \n            # Get last name (might be in <a> tag or direct text)\n            last_name_elem = last_name_cell.find('a')\n            if last_name_elem:\n                last_name = last_name_elem.get_text(strip=True)\n            else:\n                last_name = last_name_cell.get_text(strip=True)\n            \n            # Get first name\n            first_name = first_name_cell.get_text(strip=True)\n            \n            # Get PDF link\n            pdf_link = pdf_link_cell.find('a', href=True)\n            if not pdf_link:\n                return None\n            \n            pdf_url = pdf_link['href']\n            \n            # Convert relative URLs to absolute\n            if not pdf_url.startswith('http'):\n                pdf_url = urljoin(PARLIAMENT_BASE_URL, pdf_url)\n            \n            # Skip if not a PDF\n            if not pdf_url.lower().endswith('.pdf'):\n                return None\n            \n            # Extract metadata from filename\n            afm, file_id, declaration_type = self._parse_pdf_filename(pdf_url)\n            \n            return DeclarationEntry(\n                last_name=last_name,\n                first_name=first_name,\n                pdf_url=pdf_url,\n                year=year,\n                declaration_type=declaration_type,\n                afm=afm,\n                file_id=file_id\n            )\n            \n        except Exception as e:\n            logger.debug(f"Failed to parse row: {str(e)}")\n            return None\n    \n    def _parse_pdf_filename(self, pdf_url: str) -> tuple[Optional[str], Optional[str], DeclarationType]:\n        """Extract AFM, file ID, and declaration type from PDF filename."""\n        filename = urlparse(pdf_url).path.split('/')[-1]\n        \n        # Remove .pdf extension\n        name_without_ext = filename.replace('.pdf', '')\n        \n        # Split by underscores: LASTNAME_FIRSTNAME_AFM_YEARx.pdf\n        # where x might be 'a' (arxiki) or 'e' (ethsia)\n        parts = name_without_ext.split('_')\n        \n        afm = None\n        file_id = None\n        declaration_type = DeclarationType.ANNUAL  # Default\n        \n        if len(parts) >= 3:\n            # Try to find AFM (should be numeric)\n            for part in parts:\n                if part.isdigit() and len(part) >= 6:  # AFM is typically 9 digits\n                    afm = part\n                    break\n        \n        # Check last part for declaration type indicator\n        if parts:\n            last_part = parts[-1].lower()\n            if last_part.endswith('a'):\n                declaration_type = DeclarationType.INITIAL\n            elif last_part.endswith('e'):\n                declaration_type = DeclarationType.ANNUAL\n        \n        # Use full filename as file_id for uniqueness\n        file_id = name_without_ext\n        \n        return afm, file_id, declaration_type\n    \n    def get_declarations_for_years(self, years: List[int]) -> Dict[int, YearlyDeclarations]:\n        """Parse declarations for multiple years."""\n        results = {}\n        \n        for year in years:\n            try:\n                declarations = self.parse_year_page(year)\n                results[year] = declarations\n                logger.info(f"Successfully parsed {len(declarations.entries)} declarations for {year}")\n                \n            except Exception as e:\n                logger.error(f"Failed to parse declarations for year {year}: {str(e)}")\n                continue\n        \n        return results