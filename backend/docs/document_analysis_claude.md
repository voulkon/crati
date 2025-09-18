# DiavgeiaApp: Data Ingestion & Document Analysis Pipeline

This project provides a system for importing data from the Greek Diavgeia (Transparency) portal, storing it in a structured database, and processing associated PDF documents for text extraction and AI analysis.

## Core Components

### 1. Data Import Pipeline

The database is populated with core Diavgeia entities using the seeding command:

```bash
python manage.py seed_data [--types] [--organizations] [--decisions] [--force]
```

- **Modular Design:** Separate importers for each entity type (ActTypes, Organizations, Units, etc.)
- **Foreign Key Management:** Handles complex relationships between entities
- **Idempotent Operations:** Updates existing records or creates new ones
- **Data Models:** ActType, Organization, Unit, Signer, Decision, etc.

### 2. PDF Document Processing

Processes PDF documents associated with decisions:

```bash
python manage.py process_documents [--ada ADA_ID] [--limit N] [--async]
```

**Processing Flow:**
1. **Download:** Fetches PDF from Decision's `document_url`
2. **Text Extraction:** Uses PyPDF initially with heuristics to detect scanned documents
3. **Status Tracking:** Records progress in DocumentExtraction model
4. **Analysis (Future):** Summary generation, embeddings creation, etc.

**Key Components:**
- **Data Models:**
  - `DocumentExtraction`: Tracks extraction status and stores raw text
  - `DocumentAnalysis`: Stores AI-generated outputs (summaries, classifications)
  - `DocumentEmbedding`: Contains text chunks and vector embeddings

- **API Endpoints:**
  - `POST /api/document-analysis/{ada}/process/`: Queue document for processing
  - `GET /api/document-analysis/{ada}/status/`: Check processing status
  - `GET /api/document-analysis/{ada}/extraction/`: Access extracted text

### 3. Asynchronous Processing

- **Celery Tasks:** For heavy processing operations
  - `process_document_task`: Processes a single document
  - `process_document_batch`: Handles multiple documents with controlled concurrency
  - Support for different task queues (I/O tasks vs. API calls)

### 4. Extensibility & Configuration

- **Provider Registry:** Pluggable architecture for different:
  - Text extractors (PyPDF, Tesseract OCR, etc.)
  - AI analyzers (OpenAI, Anthropic, etc.)
  - Embedding generators (OpenAI, Sentence Transformers, etc.)

- **Environment Configuration:** API keys and settings managed via environment variables

### 5. Monitoring & Error Handling

- **Status Tracking:** Detailed processing status in database
- **Retry Logic:** Built-in for failed operations
- **Task Monitoring:** Celery task IDs linked to extractions

## Usage Examples

1. **Seed initial data:**
   ```bash
   python manage.py seed_data --types --organizations
   ```

2. **Process documents for specific dates:**
   ```bash
   python manage.py process_documents --from-date 2023-01-01 --to-date 2023-01-31 --limit 100 --async
   ```

3. **Process unprocessed documents:**
   ```bash
   python manage.py process_documents --unprocessed-only --limit 50
   ```

4. **Via API:**
   ```
   POST /api/document-analysis/ABC12345/process/
   ```

---

This architecture provides a scalable foundation for ingesting Diavgeia data and using AI to extract insights from government documents.