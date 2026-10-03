"""Opt-in live check for the grounded document agent."""

import asyncio
from uuid import UUID

import pytest
from openai import AsyncOpenAI
from pydantic_ai.usage import UsageLimits

from app.assistant.agent import (
    MAX_AGENT_REQUESTS,
    MAX_AGENT_TOOL_CALLS,
    document_agent,
)
from app.assistant.deps import DocumentAgentDeps
from app.config import settings
from app.database.supabase import create_service_role_client
from app.grounding.validator import validate_grounded_answer
from app.retrieval.retriever import DocumentRetriever


@pytest.mark.integration
def test_agent_returns_validated_citations_for_a_corpus_question() -> None:
    async def run_agent():
        database = await create_service_role_client()
        deps = DocumentAgentDeps(
            user_id=UUID(int=0),
            thread_id=UUID(int=0),
            retriever=DocumentRetriever(
                database,
                AsyncOpenAI(api_key=settings.openai_api_key),
            ),
        )
        result = await document_agent.run(
            "According to Apple's 2025 10-K, what happened to Services net sales?",
            deps=deps,
            usage_limits=UsageLimits(
                request_limit=MAX_AGENT_REQUESTS,
                tool_calls_limit=MAX_AGENT_TOOL_CALLS,
            ),
        )
        return result.output, deps.evidence

    answer, evidence = asyncio.run(run_agent())
    citations = validate_grounded_answer(answer, evidence)

    assert answer.answer
    assert answer.status == "grounded"
    assert citations
    assert all(citation.ticker == "AAPL" for citation in citations)
