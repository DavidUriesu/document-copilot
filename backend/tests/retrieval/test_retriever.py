"""Tests for hybrid retrieval orchestration."""

import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.config import settings
from app.retrieval.models import ChunkWindowRow, RankedChunk, RetrievalFilters
from app.retrieval.retriever import DocumentRetriever

SEED_A = UUID("00000000-0000-0000-0000-000000000001")
SEED_B = UUID("00000000-0000-0000-0000-000000000002")
NEIGHBOR = UUID("00000000-0000-0000-0000-000000000003")
DOCUMENT = UUID("10000000-0000-0000-0000-000000000001")


def ranked(chunk_id: UUID, chunk_index: int) -> RankedChunk:
    return RankedChunk(chunk_id, DOCUMENT, chunk_index, 0.9)


def window(seed_id: UUID, chunk_id: UUID, chunk_index: int) -> ChunkWindowRow:
    return ChunkWindowRow(
        seed_chunk_id=seed_id,
        chunk_id=chunk_id,
        document_id=DOCUMENT,
        chunk_index=chunk_index,
        content=f"chunk {chunk_index}",
        page_number=10,
        section="Item 8",
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        filing_date=date(2025, 10, 31),
        report_date=date(2025, 9, 27),
        fiscal_year=2025,
        accession_number="0000320193-25-000079",
        source_url="https://example.com/filing",
    )


def openai_client() -> SimpleNamespace:
    response = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.1] * settings.openai_embedding_dimensions)]
    )
    return SimpleNamespace(
        embeddings=SimpleNamespace(create=AsyncMock(return_value=response))
    )


def test_search_fuses_channels_and_deduplicates_windows() -> None:
    openai = openai_client()
    retriever = DocumentRetriever(object(), openai, candidate_limit=12)
    filters = RetrievalFilters(tickers=("AAPL",))
    semantic = [ranked(SEED_A, 5), ranked(SEED_B, 6)]
    lexical = [ranked(SEED_B, 6)]
    rows = [
        window(SEED_B, SEED_B, 6),
        window(SEED_B, NEIGHBOR, 7),
        window(SEED_A, SEED_A, 5),
        window(SEED_A, NEIGHBOR, 7),
    ]

    with (
        patch(
            "app.retrieval.retriever.semantic_search",
            AsyncMock(return_value=semantic),
        ) as semantic_search,
        patch(
            "app.retrieval.retriever.full_text_search",
            AsyncMock(return_value=lexical),
        ) as full_text_search,
        patch(
            "app.retrieval.retriever.fetch_chunk_windows",
            AsyncMock(return_value=rows),
        ) as fetch_windows,
    ):
        result = asyncio.run(
            retriever.search(" revenue mix ", filters, limit=2, neighbor_window=1)
        )

    openai.embeddings.create.assert_awaited_once_with(
        input=["revenue mix"],
        model=settings.openai_embedding_model,
        dimensions=settings.openai_embedding_dimensions,
        encoding_format="float",
    )
    semantic_search.assert_awaited_once_with(
        retriever._database,
        [0.1] * settings.openai_embedding_dimensions,
        filters,
        12,
    )
    full_text_search.assert_awaited_once_with(
        retriever._database, "revenue mix", filters, 12
    )
    fetch_windows.assert_awaited_once()
    assert fetch_windows.await_args.args[0] is retriever._database
    assert fetch_windows.await_args.args[1] == [SEED_B, SEED_A]
    assert [passage.chunk_id for passage in result] == [SEED_B, NEIGHBOR, SEED_A]
    assert [passage.is_seed for passage in result] == [True, False, True]


def test_no_candidates_skips_window_lookup() -> None:
    retriever = DocumentRetriever(object(), openai_client())
    with (
        patch(
            "app.retrieval.retriever.semantic_search", AsyncMock(return_value=[])
        ),
        patch(
            "app.retrieval.retriever.full_text_search", AsyncMock(return_value=[])
        ),
        patch(
            "app.retrieval.retriever.fetch_chunk_windows", AsyncMock()
        ) as fetch_windows,
    ):
        result = asyncio.run(retriever.search("unknown"))

    assert result == []
    fetch_windows.assert_not_awaited()


@pytest.mark.parametrize(
    ("query", "limit", "window", "message"),
    [
        ("  ", 8, 1, "blank"),
        ("query", 0, 1, "limit"),
        ("query", 8, -1, "neighbor_window"),
    ],
)
def test_invalid_search_input_fails_before_embedding(
    query: str, limit: int, window: int, message: str
) -> None:
    openai = openai_client()
    retriever = DocumentRetriever(object(), openai)

    with pytest.raises(ValueError, match=message):
        asyncio.run(retriever.search(query, limit=limit, neighbor_window=window))

    openai.embeddings.create.assert_not_awaited()


def test_wrong_embedding_dimensions_fail_before_database_search() -> None:
    openai = openai_client()
    openai.embeddings.create.return_value = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.1])]
    )
    retriever = DocumentRetriever(object(), openai)

    with (
        patch(
            "app.retrieval.retriever.semantic_search", AsyncMock()
        ) as semantic_search,
        pytest.raises(RuntimeError, match="dimensions"),
    ):
        asyncio.run(retriever.search("query"))

    semantic_search.assert_not_awaited()
