"""Opt-in checks against the ingested Supabase corpus."""

import asyncio

import pytest
from openai import AsyncOpenAI

from app.config import settings
from app.database.supabase import create_service_role_client
from app.retrieval.models import RetrievalFilters
from app.retrieval.retriever import DocumentRetriever


@pytest.mark.integration
def test_retrieves_filtered_passages_from_ingested_corpus() -> None:
    async def run_search():
        database = await create_service_role_client()
        retriever = DocumentRetriever(
            database,
            AsyncOpenAI(api_key=settings.openai_api_key),
        )
        return await retriever.search(
            "How did the revenue mix between iPhone and Services change?",
            RetrievalFilters(
                tickers=("AAPL",),
                filing_types=("10-K",),
                fiscal_year_from=2021,
                fiscal_year_to=2025,
            ),
        )

    passages = asyncio.run(run_search())

    assert passages
    assert len({passage.chunk_id for passage in passages}) == len(passages)
    assert all(passage.ticker == "AAPL" for passage in passages)
    assert all(passage.filing_type == "10-K" for passage in passages)
    assert all(2021 <= passage.fiscal_year <= 2025 for passage in passages)
    assert all(passage.accession_number for passage in passages)
    assert all(passage.source_url for passage in passages)
    assert any(
        term in passage.content.lower()
        for passage in passages
        for term in ("iphone", "services", "net sales")
    )
