"""Tests for the Supabase retrieval RPC boundary."""

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from postgrest.exceptions import APIError

from app.retrieval.models import RetrievalFilters
from app.retrieval.queries import (
    fetch_chunk_windows,
    full_text_search,
    semantic_search,
)

CHUNK_ID = "00000000-0000-0000-0000-000000000001"
DOCUMENT_ID = "10000000-0000-0000-0000-000000000001"


@dataclass
class Response:
    data: list[dict[str, Any]]


class RpcCall:
    def __init__(self, response: Response) -> None:
        self.response = response

    async def execute(self) -> Response:
        return self.response


class FakeClient:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, dict[str, object]]] = []

    def rpc(self, name: str, params: dict[str, object]) -> RpcCall:
        self.calls.append((name, params))
        return RpcCall(Response(self.rows))


def ranked_row() -> dict[str, Any]:
    return {
        "chunk_id": CHUNK_ID,
        "document_id": DOCUMENT_ID,
        "chunk_index": 7,
        "score": 0.75,
    }


def window_row() -> dict[str, Any]:
    return {
        "seed_chunk_id": CHUNK_ID,
        "chunk_id": CHUNK_ID,
        "document_id": DOCUMENT_ID,
        "chunk_index": 7,
        "content": "Revenue passage",
        "page_number": 12,
        "section": "Item 8",
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "filing_type": "10-K",
        "filing_date": "2025-10-31",
        "report_date": "2025-09-27",
        "fiscal_year": 2025,
        "accession_number": "0000320193-25-000079",
        "source_url": "https://example.com/filing",
    }


def test_semantic_search_assembles_filters_and_parses_rows() -> None:
    client = FakeClient([ranked_row()])
    filters = RetrievalFilters(
        tickers=("aapl",),
        filing_types=("10-K",),
        fiscal_year_from=2023,
        fiscal_year_to=2025,
    )

    results = asyncio.run(semantic_search(client, [0.1, 0.2], filters, 30))

    assert results[0].chunk_id == UUID(CHUNK_ID)
    assert client.calls == [
        (
            "match_document_chunks_semantic",
            {
                "query_embedding": [0.1, 0.2],
                "candidate_limit": 30,
                "filter_tickers": ["AAPL"],
                "filter_filing_types": ["10-K"],
                "filter_year_from": 2023,
                "filter_year_to": 2025,
            },
        )
    ]


def test_full_text_search_sends_null_optional_filters() -> None:
    client = FakeClient([ranked_row()])

    results = asyncio.run(full_text_search(client, "AWS income", RetrievalFilters(), 20))

    assert results[0].score == 0.75
    assert client.calls[0] == (
        "match_document_chunks_full_text",
        {
            "query_text": "AWS income",
            "candidate_limit": 20,
            "filter_tickers": None,
            "filter_filing_types": None,
            "filter_year_from": None,
            "filter_year_to": None,
        },
    )


def test_fetch_chunk_windows_parses_citation_metadata() -> None:
    client = FakeClient([window_row()])

    rows = asyncio.run(fetch_chunk_windows(client, [UUID(CHUNK_ID)], 1))

    assert rows[0].ticker == "AAPL"
    assert rows[0].filing_date.isoformat() == "2025-10-31"
    assert client.calls[0][1] == {
        "seed_chunk_ids": [CHUNK_ID],
        "window_size": 1,
    }


def test_malformed_rpc_row_fails_at_boundary() -> None:
    client = FakeClient([{"chunk_id": "not-a-uuid"}])

    with pytest.raises(ValueError):
        asyncio.run(full_text_search(client, "query", RetrievalFilters(), 10))


def test_transient_supabase_jwt_clock_skew_is_retried() -> None:
    class FlakyRpcCall:
        attempts = 0

        async def execute(self) -> Response:
            self.attempts += 1
            if self.attempts == 1:
                raise APIError(
                    {
                        "message": "JWT issued at future",
                        "code": "PGRST303",
                        "hint": None,
                        "details": None,
                    }
                )
            return Response([ranked_row()])

    call = FlakyRpcCall()
    client = FakeClient([])
    client.rpc = lambda _name, _params: call

    with patch("app.retrieval.queries.asyncio.sleep", AsyncMock()) as sleep:
        results = asyncio.run(
            full_text_search(client, "query", RetrievalFilters(), 10)
        )

    assert results[0].chunk_id == UUID(CHUNK_ID)
    assert call.attempts == 2
    sleep.assert_awaited_once_with(1.0)


def test_other_api_errors_are_not_retried() -> None:
    class FailingRpcCall:
        attempts = 0

        async def execute(self) -> Response:
            self.attempts += 1
            raise APIError(
                {
                    "message": "permission denied",
                    "code": "42501",
                    "hint": None,
                    "details": None,
                }
            )

    call = FailingRpcCall()
    client = FakeClient([])
    client.rpc = lambda _name, _params: call

    with pytest.raises(APIError, match="permission denied"):
        asyncio.run(full_text_search(client, "query", RetrievalFilters(), 10))

    assert call.attempts == 1
