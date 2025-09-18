from loguru import logger
from core.protocols.extraction_protocol import ExtractionResult
import os


class DoclingExtractor:
    """
    Text extractor using Docling library for advanced document processing.
    """

    def __init__(self, split_into_pages=True):
        """
        Initialize with configuration options

        Args:
            split_into_pages: Whether to split into pages/chunks (default: True)
        """
        self.split_into_pages = split_into_pages

    def extract_text(self, file_path: str) -> ExtractionResult:
        """Extract text using Docling"""
        try:
            from docling.document_converter import DocumentConverter
            from docling.chunking import HybridChunker

            # Initialize the Docling document converter
            converter = DocumentConverter()

            # Process the document
            result = converter.convert(file_path)
            doc = result.document

            # Extract text
            full_text = doc.export_to_text()

            # Count pages if available, or estimate
            page_count = len(doc.pages) if hasattr(doc, "pages") and doc.pages else 1

            # Determine if scanned (heuristic)
            is_scanned = len(full_text.strip()) < 100

            # Initial metadata
            metadata = {
                "provider": "DOCLING",
                "file_size_bytes": os.path.getsize(file_path),
            }

            # If not splitting into pages, return just the full text
            if not self.split_into_pages:
                metadata["skip_page_splitting"] = True
                return ExtractionResult(
                    text=full_text,
                    page_count=page_count,
                    is_scanned=is_scanned,
                    # Important: Set pages_data to None to skip page creation
                    pages_data=None,
                    metadata=metadata,
                )

            # Otherwise, use chunker to create "pages"
            chunker = HybridChunker(tokenizer="BAAI/bge-small-en-v1.5")
            chunk_iter = chunker.chunk(doc)

            pages_data = []
            for i, chunk in enumerate(chunk_iter):
                enriched_text = chunker.contextualize(chunk=chunk)
                for_page_data = {
                    "page_number": i + 1,  # This is a chunk number, not a page number
                    "text": enriched_text,
                    "character_count": len(enriched_text),
                }
                pages_data.append(for_page_data)

            # Add chunking details to metadata
            metadata["chunk_count"] = len(pages_data)
            metadata["chunking_method"] = "hybrid_chunker"

            return ExtractionResult(
                text=full_text,
                page_count=page_count,
                is_scanned=is_scanned,
                pages_data=pages_data if pages_data else None,
                metadata=metadata,
            )

        except ImportError:
            raise ImportError(
                "Docling is not installed. Please install it with 'pip install docling'."
            )

        except Exception as e:
            logger.error(f"Error in Docling extraction: {e}")
            raise
