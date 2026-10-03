"""Tests for the visible grounding smoke command."""

from datetime import date
from uuid import UUID

import pytest

from app.assistant.outputs import CitationRef, GroundedAnswer
from app.grounding.verify import format_result, parse_args
from app.retrieval.models import SourcePassage

CHUNK_ID = UUID("00000000-0000-0000-0000-000000000001")


def passage() -> SourcePassage:
    return SourcePassage(
        chunk_id=CHUNK_ID,
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


def test_format_result_exposes_answer_citations_and_evidence() -> None:
    answer = GroundedAnswer(
        status="grounded",
        answer="Services net sales increased in 2025. [1]",
        citations=[
            CitationRef(
                chunk_id=CHUNK_ID,
                excerpt="Services net sales increased during 2025",
            )
        ],
    )

    output = format_result(answer, {CHUNK_ID: passage()}, evidence_chars=200)

    assert "GROUNDING VALIDATION: PASSED" in output
    assert "EVIDENCE LEDGER: 1 chunks" in output
    assert "CITATIONS: 1 chunks" in output
    assert "[CITED]" in output
    assert str(CHUNK_ID) in output


def test_parse_args_rejects_non_positive_excerpt_limit() -> None:
    with pytest.raises(SystemExit):
        parse_args(["question", "--evidence-chars", "0"])
