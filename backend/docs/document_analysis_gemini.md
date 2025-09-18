

# DiavgeiaApp: Data Ingestion & PDF Analysis Pipeline

This project provides a comprehensive system for fetching open data from the Greek Diavgeia API, importing it into a structured Django database, and asynchronously processing associated PDF documents for text extraction and AI-powered analysis.

---

## 1. Data Import (Seeding)

The initial population of the database with core Diavgeia entities is handled by a Django management command:

```bash
python manage.py seed_data [options]
```

**Key Features:**

*   **Modular Fetching:** Uses flags like `--types`, `--organizations`, `--decisions`, etc., to selectively fetch data categories (Act Types, Organizations, Dictionaries, Units, Positions, Signers, Decisions).
*   **Importers:** Dedicated importer classes (e.g., `ActTypeImporter`, `OrganizationImporter`, `DecisionImporter`) handle the mapping from Diavgeia API DTOs to Django models, including relationship lookups (ForeignKeys, ManyToMany).
*   **Idempotency:** The process updates existing records based on unique identifiers (like ADA for decisions) or creates new ones.
*   **`--force` Flag:** Allows re-fetching and updating all data, even if it already exists.

**Core Models Created:**

*   `ActType`, `ExtraField`
*   `Organization`, `Unit`, `UnitDomain`, `Signer`, `Position`
*   `Dictionary`, `DictionaryItem`
*   `Decision` (linked via FK/M2M to `ActType`, `Organization`, `Signer`, `Unit`)
*   `Attachment`, `DecisionAmountKAE` (related to `Decision`)

---

## 2. PDF Document Processing Pipeline

Decisions often link to PDF documents (`document_url`). This pipeline asynchronously processes these PDFs:

**Models:**

*   `DocumentExtraction`: Stores status, extracted text, metadata (page count, scanned status), provider info, and any errors for each decision's PDF. (OneToOne with `Decision`)
*   `DocumentAnalysis`: Stores results from AI models (e.g., summaries, classifications) linked to a decision, tracking the provider and model used. (ForeignKey to `Decision`)
*   `DocumentEmbedding`: Stores text chunks and their vector embeddings for semantic search capabilities. (ForeignKey to `Decision`)

**Workflow:**

1.  **Triggering:**
    *   **Management Command:**
        ```bash
        python manage.py process_documents [options]
        ```
        *   `--ada <ADA>`: Process a single document.
        *   `--limit <N>`: Process a batch of N documents.
        *   `--from-date/--to-date`: Filter documents by publication date.
        *   `--unprocessed-only`: Skip already processed documents.
        *   `--async`: Queues tasks to Celery instead of processing synchronously.
    *   **API Endpoint:**
        *   `POST /api/document-analysis/{ada}/process/`: Triggers async processing for a specific ADA via Celery.

2.  **Asynchronous Execution (Celery):**
    *   `process_document_task`: Handles a single document. Triggered directly or by the batch task.
        *   Downloads PDF from `document_url`.
        *   Uses `TextExtractionProcessor` (initially PyPDF) to extract text.
        *   Applies heuristics to detect potentially scanned documents (low text yield).
        *   Updates `DocumentExtraction` with status (`PENDING`, `PROCESSING`, `COMPLETED`, `NEEDS_VISION`, `FAILED`), extracted text, metadata, and `task_id`.
        *   Handles retries on failure.
    *   `process_document_batch`: Takes a list of ADAs and chunks them, dispatching `process_document_task` calls, often using Celery groups for controlled concurrency.
    *   *(Future Tasks):* `process_scanned_document_task` (for OCR), `generate_summary_task`, `generate_embeddings_task`.

3.  **Monitoring:**
    *   **API Endpoint:**
        *   `GET /api/document-analysis/{ada}/status/`: Check the current `extraction_status`, Celery task status (if available via `task_id`), and any errors.
    *   **Database:** Query the `DocumentExtraction` table directly.

---

## 3. Configuration & Extensibility

*   **Secrets Management:** API keys (e.g., `OPENAI_API_KEY`) and sensitive credentials are loaded from environment variables using `python-decouple`. Vault or other secret managers can be integrated.
*   **Provider Settings:** Non-sensitive settings (default models, timeouts) are configured in `core/settings/provider_settings.py`.
*   **Extensibility (`ProviderRegistry`):** A registry pattern (`core/services/provider_registry.py`) allows easily adding and selecting different implementations for:
    *   Text Extractors (e.g., PyPDF, Tesseract, Cloud OCR)
    *   AI Analyzers (e.g., OpenAI, Anthropic, local models via Ollama)
    *   Embedding Generators (e.g., OpenAI, Sentence Transformers)
    *   Providers are registered (e.g., in `apps.py`) and selected via settings or dynamically.

---

## 4. Scaling & Operations

*   **Celery Workers:** Run separate Celery workers, potentially routing tasks to different queues based on resource needs (I/O-bound, CPU-bound, API-bound).
*   **Concurrency Control:** The `process_document_batch` task helps manage concurrency when processing large numbers of documents.
*   **Monitoring:** Integrate with tools like Prometheus/Grafana (using `celery-exporter`) to monitor task queues, execution times, and failure rates.
*   **Error Handling:** Tasks include retries, and errors are logged in the `DocumentExtraction` model for targeted reprocessing.

---

This architecture provides a robust and scalable foundation for ingesting Diavgeia data and leveraging AI to extract insights from the associated documents.
