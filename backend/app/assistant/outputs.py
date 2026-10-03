"""Structured agent output and trusted citation presentation models."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CitationRef(BaseModel):
    """Model-provided reference to evidence seen during this run."""

    chunk_id: UUID
    excerpt: str = Field(min_length=1, max_length=600)


class GroundedAnswer(BaseModel):
    """Schema-constrained final answer from the document agent."""

    status: Literal["grounded", "insufficient_evidence"]
    answer: str = Field(min_length=1)
    citations: list[CitationRef]


class CitationView(BaseModel):
    """Validated citation metadata derived from stored corpus records."""

    index: int
    chunk_id: UUID
    excerpt: str
    ticker: str
    company_name: str
    filing_type: str
    filing_date: date
    fiscal_year: int
    page_number: int | None
    section: str | None
    source_url: str
