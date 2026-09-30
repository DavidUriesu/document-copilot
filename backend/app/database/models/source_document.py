"""Source filing model."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base

if TYPE_CHECKING:
    from app.database.models.document_chunk import DocumentChunk


class SourceDocument(Base):
    """Normalized SEC filing and its identifying metadata."""

    __tablename__ = "source_documents"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    company_name: Mapped[str] = mapped_column(String(255))
    cik: Mapped[str] = mapped_column(String(10), index=True)
    filing_type: Mapped[str] = mapped_column(String(10))
    filing_date: Mapped[date] = mapped_column(Date)
    report_date: Mapped[date] = mapped_column(Date)
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True)
    accession_number: Mapped[str] = mapped_column(String(25), unique=True)
    source_url: Mapped[str] = mapped_column(Text)
    normalized_markdown: Mapped[str] = mapped_column(Text)
    document_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
