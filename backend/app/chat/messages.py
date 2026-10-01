"""AI SDK message models and conversion helpers."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class UIMessage(BaseModel):
    """The subset of an AI SDK UI message accepted by the backend."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1)
    role: Literal["system", "user", "assistant"]
    parts: list[dict[str, Any]]


class ChatStreamRequest(BaseModel):
    """One AI SDK chat submission."""

    model_config = ConfigDict(populate_by_name=True)

    thread_id: str = Field(alias="threadId", min_length=1)
    messages: list[UIMessage] = Field(min_length=1)


class PersistedMessage:
    """Text and AI SDK parts ready for persistence."""

    def __init__(self, content: str, parts: list[dict[str, Any]]) -> None:
        self.content = content
        self.parts = parts


def submitted_user_message(messages: list[UIMessage]) -> PersistedMessage:
    """Extract the final submitted user message from an AI SDK message list."""
    message = messages[-1]
    if message.role != "user":
        raise ValueError("The final message must have the user role")

    text = "".join(
        part.get("text", "")
        for part in message.parts
        if part.get("type") == "text" and isinstance(part.get("text"), str)
    ).strip()
    if not text:
        raise ValueError("The final user message must contain text")

    return PersistedMessage(content=text, parts=message.parts)
