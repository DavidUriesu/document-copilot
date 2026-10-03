"""Run a visible grounded-agent turn against the ingested corpus."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from uuid import UUID

from openai import AsyncOpenAI
from pydantic_ai.usage import UsageLimits

from app.assistant.agent import (
    MAX_AGENT_REQUESTS,
    MAX_AGENT_TOOL_CALLS,
    document_agent,
)
from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import GroundedAnswer
from app.config import settings
from app.database.supabase import create_service_role_client
from app.grounding.validator import validate_grounded_answer
from app.retrieval.models import SourcePassage
from app.retrieval.retriever import DocumentRetriever


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", help="Question to ask the filing agent")
    parser.add_argument(
        "--evidence-chars",
        type=int,
        default=500,
        help="Maximum characters printed for each retrieved chunk (default: 500)",
    )
    args = parser.parse_args(argv)
    if args.evidence_chars < 1:
        parser.error("--evidence-chars must be positive")
    return args


def _one_line(text: str, limit: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3]}..."


def format_evidence(position: int, passage: SourcePassage, limit: int) -> str:
    location = f"page {passage.page_number}" if passage.page_number else "page unknown"
    section = passage.section or "section unknown"
    return (
        f"[{position}] {passage.ticker} {passage.filing_type} FY{passage.fiscal_year} | "
        f"{location} | {section}\n"
        f"    chunk={passage.chunk_id} seed={passage.is_seed}\n"
        f"    {_one_line(passage.content, limit)}"
    )


def format_result(
    answer: GroundedAnswer,
    evidence: dict[UUID, SourcePassage],
    evidence_chars: int,
) -> str:
    citations = validate_grounded_answer(answer, evidence)
    cited_ids = {citation.chunk_id for citation in citations}
    lines = [
        "GROUNDING VALIDATION: PASSED",
        f"STATUS: {answer.status}",
        f"EVIDENCE LEDGER: {len(evidence)} chunks",
        f"CITATIONS: {len(citations)} chunks",
        "",
        "ANSWER",
        answer.answer,
        "",
        "VALIDATED CITATIONS",
    ]
    if citations:
        for citation in citations:
            lines.extend(
                [
                    f"[{citation.index}] chunk={citation.chunk_id}",
                    (
                        f"    {citation.ticker} {citation.filing_type} "
                        f"FY{citation.fiscal_year} | "
                        f"page {citation.page_number or 'unknown'} | "
                        f"{citation.section or 'section unknown'}"
                    ),
                    f"    excerpt={citation.excerpt}",
                    f"    source={citation.source_url}",
                ]
            )
    else:
        lines.append("(none; this is valid only for an insufficient-evidence response)")

    lines.extend(["", "RETRIEVED EVIDENCE"])
    for position, passage in enumerate(evidence.values(), start=1):
        label = "CITED" if passage.chunk_id in cited_ids else "available"
        lines.append(f"{format_evidence(position, passage, evidence_chars)} [{label}]")
    if not evidence:
        lines.append("(none)")
    return "\n".join(lines)


async def run(args: argparse.Namespace) -> None:
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
        args.question,
        deps=deps,
        usage_limits=UsageLimits(
            request_limit=MAX_AGENT_REQUESTS,
            tool_calls_limit=MAX_AGENT_TOOL_CALLS,
        ),
    )
    print(format_result(result.output, deps.evidence, args.evidence_chars))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(run(parse_args()))


if __name__ == "__main__":
    main()
