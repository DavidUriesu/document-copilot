# Data

Local data artifacts for development live here.

- `downloads/` holds raw source files fetched from SEC EDGAR, grouped by year.
- `markdown/` holds Docling conversions with the same year-based structure and an
  updated manifest.
- `docling/` holds lossless Docling JSON parsed directly from the source HTML for
  structure-aware chunking.
- Downloaded payloads are gitignored because the corpus can get large.
- Fetch a sample corpus with `uv run data/download.py`.
- Convert downloaded HTML filings with
  `uv run --project backend python data/convert_to_markdown.py`.
- Preserve the structured Docling representation with
  `uv run --project backend python data/convert_to_docling.py`.
