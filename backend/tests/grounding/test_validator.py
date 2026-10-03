"""Tests for deterministic citation grounding enforcement."""

from datetime import date
from uuid import UUID

import pytest

from app.assistant.outputs import CitationRef, GroundedAnswer
from app.grounding.validator import GroundingError, validate_grounded_answer
from app.retrieval.models import SourcePassage

CHUNK = UUID("00000000-0000-0000-0000-000000000001")


def passage() -> SourcePassage:
    return SourcePassage(
        chunk_id=CHUNK,
        document_id=UUID("10000000-0000-0000-0000-000000000001"),
        chunk_index=4,
        content="Services net sales increased during 2025 due to growth.",
        page_number=31,
        section="Item 8",
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        filing_date=date(2025, 10, 31),
        report_date=date(2025, 9, 27),
        fiscal_year=2025,
        accession_number="0000320193-25-000079",
        source_url="https://example.com/filing",
        rrf_score=0.03,
        is_seed=True,
    )


def grounded(**changes) -> GroundedAnswer:
    values = {
        "status": "grounded",
        "answer": "Services net sales increased in 2025. [1]",
        "citations": [
            CitationRef(
                chunk_id=CHUNK,
                excerpt="Services net sales increased during 2025",
            )
        ],
    }
    values.update(changes)
    return GroundedAnswer(**values)


def test_valid_answer_returns_trusted_metadata() -> None:
    views = validate_grounded_answer(grounded(), {CHUNK: passage()})
    assert views[0].index == 1
    assert views[0].ticker == "AAPL"
    assert views[0].page_number == 31


@pytest.mark.parametrize(
    ("answer", "evidence", "message"),
    [
        (grounded(), {}, "not retrieved"),
        (
            grounded(
                citations=[CitationRef(chunk_id=CHUNK, excerpt="fabricated words")]
            ),
            {CHUNK: passage()},
            "verbatim",
        ),
        (
            grounded(answer="Services increased without a marker."),
            {CHUNK: passage()},
            "referenced",
        ),
        (
            grounded(answer="Services increased. [2]"),
            {CHUNK: passage()},
            "out-of-range",
        ),
    ],
)
def test_invalid_grounding_fails_closed(
    answer: GroundedAnswer,
    evidence: dict[UUID, SourcePassage],
    message: str,
) -> None:
    with pytest.raises(GroundingError, match=message):
        validate_grounded_answer(answer, evidence)


def test_uncited_substantive_paragraph_fails() -> None:
    answer = grounded(
        answer="Services increased. [1]\n\nThis second factual paragraph is uncited."
    )
    with pytest.raises(GroundingError, match="substantive"):
        validate_grounded_answer(answer, {CHUNK: passage()})


def test_insufficient_evidence_can_have_no_citations() -> None:
    answer = GroundedAnswer(
        status="insufficient_evidence",
        answer="The corpus contains insufficient evidence to answer reliably.",
        citations=[],
    )
    assert validate_grounded_answer(answer, {}) == []


def test_clear_cannot_answer_language_is_an_insufficient_response() -> None:
    answer = GroundedAnswer(
        status="insufficient_evidence",
        answer="I cannot answer without a company and reporting period.",
        citations=[],
    )
    assert validate_grounded_answer(answer, {}) == []
