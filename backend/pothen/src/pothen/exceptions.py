"""Custom exceptions for the POTHEN scraper package."""


class PothenError(Exception):
    """Base exception for all POTHEN-related errors."""
    pass


class PothenScrapingError(PothenError):
    """Exception raised when web scraping operations fail."""
    pass


class PothenParsingError(PothenError):
    """Exception raised when parsing HTML or PDF content fails."""
    pass


class PothenNetworkError(PothenError):
    """Exception raised when network operations fail."""
    pass


class PothenValidationError(PothenError):
    """Exception raised when data validation fails."""
    pass


class PothenDownloadError(PothenError):
    """Exception raised when PDF download operations fail."""
    pass


class PothenRateLimitError(PothenError):
    """Exception raised when rate limits are exceeded."""
    pass