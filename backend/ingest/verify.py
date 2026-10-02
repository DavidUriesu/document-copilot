"""Verify the retrieval corpus stored in Supabase."""

from __future__ import annotations

import asyncio
from typing import Any

from app.config import settings
from app.database.supabase import create_service_role_client


async def verify_corpus() -> None:
    client = await create_service_role_client()
    documents_response = await (
        client.table("source_documents")
        .select("id,ticker,fiscal_year,accession_number")
        .order("ticker")
        .order("fiscal_year")
        .execute()
    )
    documents: list[dict[str, Any]] = documents_response.data
    if not documents:
        raise RuntimeError("No source documents exist in Supabase")

    total_chunks = 0
    for document in documents:
        chunks_response = await (
            client.table("document_chunks")
            .select("chunk_index,section,search_vector,metadata")
            .eq("document_id", document["id"])
            .order("chunk_index")
            .execute()
        )
        chunks: list[dict[str, Any]] = chunks_response.data
        indexes = [chunk["chunk_index"] for chunk in chunks]
        if indexes != list(range(len(chunks))):
            raise RuntimeError(
                f"Non-contiguous chunks for {document['accession_number']}"
            )
        if any(not chunk["search_vector"] for chunk in chunks):
            raise RuntimeError(
                f"Missing search vector for {document['accession_number']}"
            )
        if not any(chunk["section"] for chunk in chunks):
            raise RuntimeError(
                f"Missing SEC sections for {document['accession_number']}"
            )
        if any(
            chunk["metadata"].get("embedding_model")
            != settings.openai_embedding_model
            or chunk["metadata"].get("embedding_dimensions")
            != settings.openai_embedding_dimensions
            for chunk in chunks
        ):
            raise RuntimeError(
                f"Wrong embedding configuration for {document['accession_number']}"
            )
        total_chunks += len(chunks)
        print(
            f"{document['ticker']} {document['fiscal_year']}: "
            f"{len(chunks)} chunks"
        )

    apple_ids = [
        document["id"] for document in documents if document["ticker"] == "AAPL"
    ]
    passage_response = await (
        client.table("document_chunks")
        .select("id,section,content")
        .in_("document_id", apple_ids)
        .ilike("content", "%net sales%")
        .not_.is_("section", "null")
        .limit(1)
        .execute()
    )
    if not passage_response.data:
        raise RuntimeError("Could not find an Apple net sales passage")

    passage = passage_response.data[0]
    print(f"Documents verified: {len(documents)}")
    print(f"Chunks verified: {total_chunks}")
    print(f"Apple passage verified: {passage['id']} ({passage['section']})")


if __name__ == "__main__":
    asyncio.run(verify_corpus())
