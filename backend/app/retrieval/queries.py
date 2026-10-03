"""Typed Supabase RPC boundary for corpus retrieval."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from supabase import AsyncClient

from app.retrieval.models import ChunkWindowRow, RankedChunk, RetrievalFilters


def _filter_params(filters: RetrievalFilters) -> dict[str, object]:
    return {
        "filter_tickers": [ticker.upper() for ticker in filters.tickers] or None,
        "filter_filing_types": list(filters.filing_types) or None,
        "filter_year_from": filters.fiscal_year_from,
        "filter_year_to": filters.fiscal_year_to,
    }


def _ranked_chunk(row: dict[str, Any]) -> RankedChunk:
    return RankedChunk(
        chunk_id=UUID(row["chunk_id"]),
        document_id=UUID(row["document_id"]),
        chunk_index=int(row["chunk_index"]),
        score=float(row["score"]),
    )


async def semantic_search(
    client: AsyncClient,
    query_embedding: list[float],
    filters: RetrievalFilters,
    candidate_limit: int,
) -> list[RankedChunk]:
    """Return chunks ordered by cosine similarity."""
    response = await client.rpc(
        "match_document_chunks_semantic",
        {
            "query_embedding": query_embedding,
            "candidate_limit": candidate_limit,
            **_filter_params(filters),
        },
    ).execute()
    return [_ranked_chunk(row) for row in response.data]


async def full_text_search(
    client: AsyncClient,
    query: str,
    filters: RetrievalFilters,
    candidate_limit: int,
) -> list[RankedChunk]:
    """Return chunks ordered by PostgreSQL full-text relevance."""
    response = await client.rpc(
        "match_document_chunks_full_text",
        {
            "query_text": query,
            "candidate_limit": candidate_limit,
            **_filter_params(filters),
        },
    ).execute()
    return [_ranked_chunk(row) for row in response.data]


def _window_row(row: dict[str, Any]) -> ChunkWindowRow:
    return ChunkWindowRow(
        seed_chunk_id=UUID(row["seed_chunk_id"]),
        chunk_id=UUID(row["chunk_id"]),
        document_id=UUID(row["document_id"]),
        chunk_index=int(row["chunk_index"]),
        content=str(row["content"]),
        page_number=(
            int(row["page_number"]) if row["page_number"] is not None else None
        ),
        section=(str(row["section"]) if row["section"] is not None else None),
        ticker=str(row["ticker"]),
        company_name=str(row["company_name"]),
        filing_type=str(row["filing_type"]),
        filing_date=date.fromisoformat(row["filing_date"]),
        report_date=date.fromisoformat(row["report_date"]),
        fiscal_year=int(row["fiscal_year"]),
        accession_number=str(row["accession_number"]),
        source_url=str(row["source_url"]),
    )


async def fetch_chunk_windows(
    client: AsyncClient,
    seed_chunk_ids: list[UUID],
    window_size: int,
) -> list[ChunkWindowRow]:
    """Hydrate seed chunks and their same-document neighbors."""
    response = await client.rpc(
        "get_document_chunk_window",
        {
            "seed_chunk_ids": [str(chunk_id) for chunk_id in seed_chunk_ids],
            "window_size": window_size,
        },
    ).execute()
    return [_window_row(row) for row in response.data]
