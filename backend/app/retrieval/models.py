"""Types shared across retrieval database queries and orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True)
class RetrievalFilters:
    """Optional filing metadata constraints applied to both search channels."""

    tickers: tuple[str, ...] = ()
    filing_types: tuple[str, ...] = ()
    fiscal_year_from: int | None = None
    fiscal_year_to: int | None = None


@dataclass(frozen=True)
class RankedChunk:
    """A chunk returned by one retrieval channel."""

    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    score: float


@dataclass(frozen=True)
class FusedChunk:
    """A chunk identity with its rank-fusion score."""

    chunk_id: UUID
    score: float


@dataclass(frozen=True)
class ChunkWindowRow:
    """A hydrated chunk associated with the seed that selected its window."""

    seed_chunk_id: UUID
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    page_number: int | None
    section: str | None
    ticker: str
    company_name: str
    filing_type: str
    filing_date: date
    report_date: date
    fiscal_year: int
    accession_number: str
    source_url: str


@dataclass(frozen=True)
class SourcePassage:
    """Citation-ready source text returned by the public retriever."""

    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    page_number: int | None
    section: str | None
    ticker: str
    company_name: str
    filing_type: str
    filing_date: date
    report_date: date
    fiscal_year: int
    accession_number: str
    source_url: str
    rrf_score: float
    is_seed: bool
