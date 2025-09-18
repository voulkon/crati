# DiavgeiaApp: PDF Ingestion & Analysis Pipeline

This project fetches open data from the Greek Diavgeia API, imports it into Django models, and provides an asynchronous pipeline for PDF text extraction, AI‑powered analysis (summaries, embeddings), and monitoring.

---

## 1. Data Import (Seed Service)

1. `python manage.py seed_data [--types] [--organizations] [--dictionaries] [--units] [--positions] [--signers] [--decisions] [--force]`
   - Fetches lists and details via the Diavgeia SDK (act types, organizations, dictionaries, units, positions, signers, decisions).
   - Calls dedicated importers (`ActTypeImporter`, `OrganizationImporter`, etc.) to update or create records.
   - `--force` forces re‑import even if records exist.

2. Models Created
   - **ActType**, **ExtraField** (and nested fields)
   - **Organization**, **Unit**, **UnitDomain**, **Signer**, **Position**
   - **Dictionary**, **DictionaryItem**
   - **Decision** (with FKs to ActType, Organization; M2M to Signer & Unit)
   - **DecisionAmountKAE**, **Attachment**

3. Tests
   - Unit tests under unit cover each importer’s mapping and DB operations.
   - Integration tests under integration mock API responses and verify end‑to‑end seeding.

---

## 2. PDF Extraction & AI Analysis

1. **Models**  
   - `DocumentExtraction` (one‑to‑one with Decision)  
   - `DocumentAnalysis` (AI outputs: summaries, classifications)  
   - `DocumentEmbedding` (text chunks + vector embeddings)  

2. **Async Processing**  
   - Management command:
     ```bash
     python manage.py process_documents \
       [--ada ADA_ID] \
       [--limit N] \
       [--from-date YYYY-MM-DD] [--to-date YYYY-MM-DD] \
       [--unprocessed-only] [--async]
     ```
   - API endpoints (`ViewSet` at `/api/document-analysis/{ada}/`):
     - `POST /process/` → queues `process_document_task`
     - `GET  /status/`  → returns `extraction_status`, Celery task status, errors
     - `GET  /extraction/`, `/analysis/` → fetch raw text or AI results

3. **Celery Tasks**  
   - `process_document_task`  
   - `process_document_batch`  
   - Extension stubs: `process_scanned_document_task`, `generate_summary_task`, `process_embeddings_task`

4. **Text Extraction & OCR**  
   - `TextExtractionProcessor` (PyPDF2 ➔ raw text + scanned‑doc heuristic)  
   - Falls back to vision‑based OCR for scanned PDFs

5. **AI Analysis & Embeddings**  
   - `DocumentAnalysisService` orchestrates extraction → vision (if needed) → summary/embedding  
   - Pluggable analyzers & embedders via `ProviderRegistry`

---

## 3. Configuration & Secrets

- Environment variables managed with **python‑decouple** or Vault:
  ```
  OPENAI_API_KEY=
  ANTHROPIC_API_KEY=
  GOOGLE_VISION_CREDENTIALS=
  DEFAULT_TEXT_EXTRACTION_PROVIDER=PYPDF
  ```
- Provider settings in provider_settings.py.
- Register new providers in provider_registry.py (or in your app’s `ready()`).

---

## 4. Scaling & Monitoring

- Separate Celery queues/workers by task type:
  - I/O‑bound PDF download & text extraction
  - CPU‑bound OCR (Tesseract)
  - External AI/API calls
- Use chunked batches (`process_document_batch`) to control concurrency.
- Instrument with Prometheus/Grafana: track task durations, queue lengths, retry rates.
- Alert on extraction failures or stalled tasks.

---

## 5. Extending the Pipeline

1. **New OCR Providers**  
   - Implement a class under document_processor.py, register via `ProviderRegistry.register_extractor(...)`.

2. **Additional Analyses**  
   - Create subclasses of `AbstractAnalyzer`, wire them into `DocumentAnalysisService`.

3. **Batch Ingestion**  
   - Use `fetch_decisions_for_increment` & `process_fetch_period` Celery tasks to parallelize decision fetching by date range.

---

With this setup, you can rapidly seed your local DB with Diavgeia data, process hundreds of PDFs asynchronously, and experiment with different AI providers without touching the core pipeline.