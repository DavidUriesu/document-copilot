"""Coordinate one grounded assistant turn from history through persistence."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits
from supabase import AsyncClient

from app.assistant.agent import (
    MAX_AGENT_REQUESTS,
    MAX_AGENT_TOOL_CALLS,
    document_agent,
)
from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import CitationView, GroundedAnswer
from app.chat.messages import PersistedMessage, model_history
from app.database.chats import append_grounded_turn, list_messages
from app.grounding.validator import validate_grounded_answer
from app.retrieval.retriever import DocumentRetriever


@dataclass(frozen=True)
class CompletedTurn:
    """Validated and persisted assistant output ready for streaming."""

    message_id: UUID
    answer: str
    parts: list[dict[str, object]]
    citations: list[CitationView]


async def run_chat_turn(
    *,
    user_id: UUID,
    thread_id: UUID,
    user_message: PersistedMessage,
    user_client: AsyncClient,
    openai_client: AsyncOpenAI,
    assistant_message_id: UUID,
    agent: Agent = document_agent,
) -> CompletedTurn:
    """Generate, validate, and atomically persist one complete chat turn."""
    rows = await list_messages(user_client, thread_id)
    deps = DocumentAgentDeps(
        user_id=user_id,
        thread_id=thread_id,
        retriever=DocumentRetriever(user_client, openai_client),
    )
    result = await agent.run(
        user_message.content,
        deps=deps,
        message_history=model_history(rows),
        usage_limits=UsageLimits(
            request_limit=MAX_AGENT_REQUESTS,
            tool_calls_limit=MAX_AGENT_TOOL_CALLS,
        ),
    )
    output: GroundedAnswer = result.output
    citations = validate_grounded_answer(output, deps.evidence)
    parts: list[dict[str, object]] = [{"type": "text", "text": output.answer}]
    parts.extend(
        {
            "type": "data-citation",
            "data": citation.model_dump(mode="json"),
        }
        for citation in citations
    )
    assistant_message = PersistedMessage(content=output.answer, parts=parts)
    _, assistant_message_id = await append_grounded_turn(
        user_client,
        thread_id,
        user_message,
        assistant_message,
        citations,
        assistant_message_id=assistant_message_id,
    )
    return CompletedTurn(
        message_id=assistant_message_id,
        answer=output.answer,
        parts=parts,
        citations=citations,
    )
