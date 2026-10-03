"""Bounded filing-retrieval tools exposed to the document agent."""

from typing import Annotated
from uuid import UUID

from pydantic import Field
from pydantic_ai import RunContext

from app.assistant.deps import DocumentAgentDeps
from app.retrieval.models import RetrievalFilters, SourcePassage

MAX_SEARCH_RESULTS = 12
MAX_NEIGHBOR_WINDOW = 2
SearchLimit = Annotated[int, Field(ge=1, le=MAX_SEARCH_RESULTS)]
NeighborWindow = Annotated[int, Field(ge=0, le=MAX_NEIGHBOR_WINDOW)]


async def search_filings(
    ctx: RunContext[DocumentAgentDeps],
    query: str,
    tickers: list[str] | None = None,
    filing_types: list[str] | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    limit: SearchLimit = 8,
) -> list[SourcePassage]:
    """Search filings using a concise evidence phrase and explicit scope filters.

    Do not pass the user's complete conversational question. Use a few terms
    likely to occur in one passage and issue separate searches for independent
    topics, companies, or periods.
    """
    if not 1 <= limit <= MAX_SEARCH_RESULTS:
        raise ValueError(f"limit must be between 1 and {MAX_SEARCH_RESULTS}")
    passages = await ctx.deps.retriever.search(
        query,
        RetrievalFilters(
            tickers=tuple(tickers or ()),
            filing_types=tuple(filing_types or ()),
            fiscal_year_from=start_year,
            fiscal_year_to=end_year,
        ),
        limit=limit,
    )
    ctx.deps.evidence.update((passage.chunk_id, passage) for passage in passages)
    return passages


async def read_chunk(
    ctx: RunContext[DocumentAgentDeps], chunk_id: UUID
) -> SourcePassage:
    """Read an exact chunk that was already returned by a filing search."""
    passage = ctx.deps.evidence.get(chunk_id)
    if passage is None:
        raise ValueError("Search for a chunk before reading it")
    return passage


async def read_surrounding_chunks(
    ctx: RunContext[DocumentAgentDeps],
    chunk_id: UUID,
    window: NeighborWindow = 1,
) -> list[SourcePassage]:
    """Expand an already-seen chunk with bounded same-filing context."""
    if chunk_id not in ctx.deps.evidence:
        raise ValueError("Search for a chunk before expanding it")
    if not 0 <= window <= MAX_NEIGHBOR_WINDOW:
        raise ValueError(f"window must be between 0 and {MAX_NEIGHBOR_WINDOW}")
    passages = await ctx.deps.retriever.read_surrounding_chunks(chunk_id, window)
    ctx.deps.evidence.update((passage.chunk_id, passage) for passage in passages)
    return passages
