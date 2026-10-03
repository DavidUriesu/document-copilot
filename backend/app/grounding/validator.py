"""Validate that an answer's citations map to retrieved source text."""

from __future__ import annotations

import re
from uuid import UUID

from app.assistant.outputs import CitationView, GroundedAnswer
from app.retrieval.models import SourcePassage

CITATION_MARKER = re.compile(r"\[(\d+)]")
INSUFFICIENCY_LANGUAGE = (
    "insufficient",
    "not enough",
    "cannot answer",
    "can't answer",
)


class GroundingError(ValueError):
    """Raised when an answer violates the grounding contract."""


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _substantive_blocks(answer: str) -> list[str]:
    blocks = []
    for block in re.split(r"\n\s*\n", answer):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        for line in lines:
            if line.startswith("#") or re.fullmatch(r"[-|: ]+", line):
                continue
            blocks.append(line)
    return blocks


def validate_grounded_answer(
    answer: GroundedAnswer,
    evidence: dict[UUID, SourcePassage],
) -> list[CitationView]:
    """Return trusted citations or fail closed on any provenance violation."""
    citation_ids = [citation.chunk_id for citation in answer.citations]
    if len(citation_ids) != len(set(citation_ids)):
        raise GroundingError("Citation chunk IDs must be unique")
    if answer.status == "grounded" and not answer.citations:
        raise GroundingError("A grounded answer must include citations")

    views = []
    for index, citation in enumerate(answer.citations, start=1):
        passage = evidence.get(citation.chunk_id)
        if passage is None:
            raise GroundingError("Citation references evidence not retrieved this run")
        if _normalized(citation.excerpt) not in _normalized(passage.content):
            raise GroundingError("Citation excerpt is not verbatim source text")
        views.append(
            CitationView(
                index=index,
                chunk_id=passage.chunk_id,
                excerpt=_normalized(citation.excerpt),
                ticker=passage.ticker,
                company_name=passage.company_name,
                filing_type=passage.filing_type,
                filing_date=passage.filing_date,
                fiscal_year=passage.fiscal_year,
                page_number=passage.page_number,
                section=passage.section,
                source_url=passage.source_url,
            )
        )

    markers = [int(value) for value in CITATION_MARKER.findall(answer.answer)]
    expected = set(range(1, len(answer.citations) + 1))
    if any(marker not in expected for marker in markers):
        raise GroundingError("Answer contains an out-of-range citation marker")
    if set(markers) != expected:
        raise GroundingError(
            "Every citation must be referenced exactly by list position"
        )

    if answer.status == "grounded":
        uncited = [
            block
            for block in _substantive_blocks(answer.answer)
            if not CITATION_MARKER.search(block)
        ]
        if uncited:
            raise GroundingError(
                "Every substantive answer block must contain a citation"
            )
    elif not any(
        phrase in answer.answer.lower() for phrase in INSUFFICIENCY_LANGUAGE
    ):
        raise GroundingError("Insufficient-evidence answers must state the limitation")

    return views
