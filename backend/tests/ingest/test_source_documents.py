"""Tests for source document manifest ingestion."""

import json
from pathlib import Path

from ingest.source_documents import load_source_documents


def test_load_source_documents_maps_manifest_and_markdown(tmp_path: Path) -> None:
    year_dir = tmp_path / "2025"
    year_dir.mkdir()
    (year_dir / "aapl.md").write_text("# Apple filing\n", encoding="utf-8")
    manifest = {
        "filings": [
            {
                "ticker": "AAPL",
                "cik": "0000320193",
                "form": "10-K",
                "filing_date": "2025-10-31",
                "report_date": "2025-09-27",
                "accession_number": "0000320193-25-000079",
                "primary_document": "aapl-20250927.htm",
                "source_url": "https://example.com/aapl.htm",
                "local_path": "2025/aapl.md",
            }
        ]
    }
    (tmp_path / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    documents = load_source_documents(tmp_path)

    assert documents == [
        {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "cik": "0000320193",
            "filing_type": "10-K",
            "filing_date": "2025-10-31",
            "report_date": "2025-09-27",
            "fiscal_year": 2025,
            "accession_number": "0000320193-25-000079",
            "source_url": "https://example.com/aapl.htm",
            "normalized_markdown": "# Apple filing\n",
            "metadata": {
                "primary_document": "aapl-20250927.htm",
                "local_path": "2025/aapl.md",
            },
        }
    ]
