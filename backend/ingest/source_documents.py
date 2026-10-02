"""Load normalized filing Markdown into Supabase source_documents."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from postgrest.types import ReturnMethod

from app.database.supabase import create_service_role_client

MARKDOWN_DIR = Path(__file__).resolve().parents[2] / "data" / "markdown"
COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "AMZN": "Amazon.com, Inc.",
    "GOOGL": "Alphabet Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
}


def load_source_documents(markdown_dir: Path = MARKDOWN_DIR) -> list[dict[str, Any]]:
    """Build source_documents rows from a converted corpus manifest."""
    manifest_path = markdown_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    documents = []

    for filing in manifest["filings"]:
        markdown_path = markdown_dir / filing["local_path"]
        ticker = filing["ticker"]
        documents.append(
            {
                "ticker": ticker,
                "company_name": COMPANY_NAMES[ticker],
                "cik": filing["cik"],
                "filing_type": filing["form"],
                "filing_date": filing["filing_date"],
                "report_date": filing["report_date"],
                "fiscal_year": int(filing["report_date"][:4]),
                "accession_number": filing["accession_number"],
                "source_url": filing["source_url"],
                "normalized_markdown": markdown_path.read_text(encoding="utf-8"),
                "metadata": {
                    "primary_document": filing["primary_document"],
                    "local_path": filing["local_path"],
                },
            }
        )

    return documents


async def ingest_source_documents() -> int:
    """Upsert all source documents and return the resulting database count."""
    documents = load_source_documents()
    client = await create_service_role_client()

    for index, document in enumerate(documents, start=1):
        print(
            f"[{index}/{len(documents)}] "
            f"{document['ticker']} {document['fiscal_year']}"
        )
        await (
            client.table("source_documents")
            .upsert(
                document,
                on_conflict="accession_number",
                returning=ReturnMethod.minimal,
            )
            .execute()
        )

    response = await client.table("source_documents").select("id").execute()
    return len(response.data)


async def main() -> None:
    count = await ingest_source_documents()
    print(f"Source documents in database: {count}")


if __name__ == "__main__":
    asyncio.run(main())
