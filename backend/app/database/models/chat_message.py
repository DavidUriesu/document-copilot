"""Chat message model."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base

if TYPE_CHECKING:
    from app.database.models.chat_thread import ChatThread
    from app.database.models.message_citation import MessageCitation


class MessageRole(StrEnum):
    """Roles accepted by the chat persistence layer."""

    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(Base):
    """An ordered user or assistant message in a thread."""

    __tablename__ = "chat_messages"
    __table_args__ = (UniqueConstraint("thread_id", "sequence_number"),)

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    thread_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(
            MessageRole,
            name="message_role",
            native_enum=False,
            length=20,
            values_callable=lambda role: [member.value for member in role],
        )
    )
    sequence_number: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    parts: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    thread: Mapped[ChatThread] = relationship(back_populates="messages")
    citations: Mapped[list[MessageCitation]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        order_by="MessageCitation.citation_index",
    )
