"""Tests for readable retrieval verification output."""

from datetime import date
from uuid import UUID

from app.retrieval.models import SourcePassage
from app.retrieval.verify import format_passage, parse_args


def test_parse_args_builds_repeatable_filters() -> None:
    args = parse_args(
        [
            "revenue mix",
            "--ticker",
            "AAPL",
            "--ticker",
            "MSFT",
            "--year-from",
            "2023",
        ]
    )

    assert args.query == "revenue mix"
    assert args.ticker == ["AAPL", "MSFT"]
    assert args.year_from == 2023


def test_format_passage_shows_source_and_excerpt() -> None:
    passage = SourcePassage(
        chunk_id=UUID("00000000-0000-0000-0000-000000000001"),
        document_id=UUID("10000000-0000-0000-0000-000000000001"),
        chunk_index=7,
        content="Services net sales increased during 2025.",
        page_number=31,
        section="Item 8. Financial Statements",
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        filing_date=date(2025, 10, 31),
        report_date=date(2025, 9, 27),
        fiscal_year=2025,
        accession_number="0000320193-25-000079",
        source_url="https://example.com/filing",
        rrf_score=0.0325,
        is_seed=True,
    )

    output = format_passage(1, passage)

    assert "[1] seed | RRF 0.032500" in output
    assert "AAPL 10-K FY2025 | page 31" in output
    assert "Services net sales increased" in output
