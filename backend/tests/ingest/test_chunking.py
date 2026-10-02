"""Tests for SEC-aware Docling chunk preparation."""

from pathlib import Path

from docling_core.types.doc import DocItemLabel, DoclingDocument

from ingest.chunking import (
    FINAL_MAX_TOKENS,
    FilingMetadata,
    build_chunks,
    detect_sec_section,
)


def test_detect_sec_section_from_text_heading() -> None:
    assert detect_sec_section("Item 7. Management's Discussion and Analysis") == (
        "Item 7. Management's Discussion and Analysis"
    )


def test_detect_sec_section_after_introductory_text() -> None:
    assert detect_sec_section(
        "Introductory material.\nPART I\nItem 1. Business\nCompany Background"
    ) == "Item 1. Business"


def test_detect_sec_section_from_table_heading() -> None:
    assert detect_sec_section(
        "| ITEM 1A. | ITEM 1A. | R ISK FACTORS |"
    ) == "Item 1A. Risk Factors"


def test_detect_sec_section_from_multiline_table_heading() -> None:
    assert detect_sec_section("Item 1.\nItem 1.\nBusiness\nBusiness") == (
        "Item 1. Business"
    )


def test_detect_sec_section_ignores_inline_reference() -> None:
    assert detect_sec_section("See Item 8 for the financial statements.") is None


def test_build_chunks_adds_filing_metadata_and_respects_limit(
    tmp_path: Path,
) -> None:
    document = DoclingDocument(name="sample")
    document.add_text(DocItemLabel.TEXT, "Item 1. Business")
    document.add_text(DocItemLabel.TEXT, "A material business description. " * 50)
    document_path = tmp_path / "sample.json"
    document.save_as_json(document_path)
    filing = FilingMetadata(
        accession_number="0000320193-25-000079",
        ticker="AAPL",
        filing_type="10-K",
        fiscal_year=2025,
        local_path="2025/sample.json",
    )

    chunks = build_chunks(document_path, filing)

    assert chunks
    assert max(chunk.token_count for chunk in chunks) <= FINAL_MAX_TOKENS
    assert chunks[0].section == "Item 1. Business"
    assert chunks[0].metadata["ticker"] == "AAPL"
    assert chunks[0].metadata["fiscal_year"] == 2025
    assert chunks[0].metadata["content_hash"]
