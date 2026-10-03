"""Application facade for hybrid filing retrieval."""

from __future__ import annotations

import asyncio
from uuid import UUID

from openai import AsyncOpenAI
from supabase import AsyncClient

from app.config import settings
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.models import ChunkWindowRow, RetrievalFilters, SourcePassage
from app.retrieval.queries import (
    fetch_chunk_windows,
    full_text_search,
    semantic_search,
)

DEFAULT_CANDIDATE_LIMIT = 30
DEFAULT_RESULT_LIMIT = 8
DEFAULT_NEIGHBOR_WINDOW = 1


class DocumentRetriever:
    """Retrieve ranked, hydrated passages from both search channels."""

    def __init__(
        self,
        database: AsyncClient,
        openai: AsyncOpenAI,
        candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
    ) -> None:
        if candidate_limit < 1:
            raise ValueError("candidate_limit must be positive")
        self._database = database
        self._openai = openai
        self._candidate_limit = candidate_limit

    async def search(
        self,
        query: str,
        filters: RetrievalFilters | None = None,
        limit: int = DEFAULT_RESULT_LIMIT,
        neighbor_window: int = DEFAULT_NEIGHBOR_WINDOW,
    ) -> list[SourcePassage]:
        """Run hybrid search and expand the best chunks with local context."""
        query = query.strip()
        if not query:
            raise ValueError("query must not be blank")
        if limit < 1:
            raise ValueError("limit must be positive")
        if neighbor_window < 0:
            raise ValueError("neighbor_window must not be negative")

        active_filters = filters or RetrievalFilters()
        query_embedding = await self._embed_query(query)
        semantic, lexical = await asyncio.gather(
            semantic_search(
                self._database,
                query_embedding,
                active_filters,
                self._candidate_limit,
            ),
            full_text_search(
                self._database,
                query,
                active_filters,
                self._candidate_limit,
            ),
        )
        fused = reciprocal_rank_fusion([semantic, lexical])[:limit]
        if not fused:
            return []

        fused_scores = {result.chunk_id: result.score for result in fused}
        seed_order = {result.chunk_id: rank for rank, result in enumerate(fused)}
        rows = await fetch_chunk_windows(
            self._database,
            [result.chunk_id for result in fused],
            neighbor_window,
        )

        # A neighbor may occur in several overlapping windows. Associate it with
        # the highest-ranked seed so output order and diagnostics stay stable.
        best_rows = {}
        for row in rows:
            current = best_rows.get(row.chunk_id)
            if (
                current is None
                or seed_order[row.seed_chunk_id] < seed_order[current.seed_chunk_id]
            ):
                best_rows[row.chunk_id] = row

        ordered_rows = sorted(
            best_rows.values(),
            key=lambda row: (
                seed_order[row.seed_chunk_id],
                row.document_id,
                row.chunk_index,
            ),
        )
        return [
            self._source_passage(
                row, fused_scores[row.seed_chunk_id], row.chunk_id in fused_scores
            )
            for row in ordered_rows
        ]

    async def read_chunk(self, chunk_id: UUID) -> SourcePassage | None:
        """Read one exact corpus chunk by its stable ID."""
        passages = await self.read_surrounding_chunks(chunk_id, 0)
        return passages[0] if passages else None

    async def read_surrounding_chunks(
        self, chunk_id: UUID, window: int = DEFAULT_NEIGHBOR_WINDOW
    ) -> list[SourcePassage]:
        """Read a bounded same-document window around one chunk."""
        if window < 0:
            raise ValueError("window must not be negative")
        rows = await fetch_chunk_windows(self._database, [chunk_id], window)
        return [
            self._source_passage(row, rrf_score=0.0, is_seed=row.chunk_id == chunk_id)
            for row in rows
        ]

    @staticmethod
    def _source_passage(
        row: ChunkWindowRow, rrf_score: float, is_seed: bool
    ) -> SourcePassage:
        return SourcePassage(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            chunk_index=row.chunk_index,
            content=row.content,
            page_number=row.page_number,
            section=row.section,
            ticker=row.ticker,
            company_name=row.company_name,
            filing_type=row.filing_type,
            filing_date=row.filing_date,
            report_date=row.report_date,
            fiscal_year=row.fiscal_year,
            accession_number=row.accession_number,
            source_url=row.source_url,
            rrf_score=rrf_score,
            is_seed=is_seed,
        )

    async def _embed_query(self, query: str) -> list[float]:
        response = await self._openai.embeddings.create(
            input=[query],
            model=settings.openai_embedding_model,
            dimensions=settings.openai_embedding_dimensions,
            encoding_format="float",
        )
        if len(response.data) != 1:
            raise RuntimeError("OpenAI returned an unexpected embedding count")
        embedding = response.data[0].embedding
        if len(embedding) != settings.openai_embedding_dimensions:
            raise RuntimeError("OpenAI returned an embedding with wrong dimensions")
        return embedding
