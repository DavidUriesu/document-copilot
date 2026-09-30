"""Assistant-message citation model."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base

if TYPE_CHECKING:
    from app.database.models.chat_message import ChatMessage
    from app.database.models.document_chunk import DocumentChunk


class MessageCitation(Base):
    """A passage cited by an assistant message."""

    __tablename__ = "message_citations"
    __table_args__ = (UniqueConstraint("message_id", "citation_index"),)

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    message_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="CASCADE"), index=True
    )
    chunk_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="RESTRICT"), index=True
    )
    citation_index: Mapped[int] = mapped_column(Integer)
    excerpt: Mapped[str] = mapped_column(Text)

    message: Mapped[ChatMessage] = relationship(back_populates="citations")
    chunk: Mapped[DocumentChunk] = relationship(back_populates="citations")
