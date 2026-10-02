# Document Copilot Backend

## Setup

From `backend/`, install the locked dependencies and create `.env` from the example:

```powershell
uv sync
Copy-Item .env.example .env
```

Fill in every required value in `.env` before starting the app.

## Run

Start from the terminal:

```powershell
uv run uvicorn app.main:app --reload
```

Alternatively, run `app/main.py` using your IDE's Run button. The API is available at:

- Health check: <http://127.0.0.1:8000/health>
- API documentation: <http://127.0.0.1:8000/docs>

Stop the server with `Ctrl+C` or your IDE's Stop button.

## Ingest source documents

After converting the downloaded filings to Markdown, load them into Supabase:

```powershell
uv run python ingest/source_documents.py
```

The loader upserts filings by accession number, so it is safe to rerun.

Preview chunking locally without making API calls or database writes:

```powershell
uv run python ingest/pipeline.py
```

Exercise the paid ingestion path with exactly one chunk:

```powershell
uv run python ingest/pipeline.py --accession <accession> --max-chunks 1 --upload
```

Only after that check succeeds, ingest the complete corpus explicitly:

```powershell
uv run python ingest/pipeline.py --upload --full
```

Verify chunk continuity, embedding metadata, full-text vectors, and a known Apple
passage:

```powershell
uv run python ingest/verify.py
```

## Maintain

```powershell
uv add <package>       # Add a dependency
uv run ruff check app # Lint the application
uv run pytest         # Run tests
```

Run backend commands from `backend/`. If another virtual environment is active, run `deactivate` first and let `uv` use `backend/.venv`.
