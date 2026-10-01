"""Supabase persistence for chat threads and messages."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from supabase import AsyncClient

from app.chat.messages import PersistedMessage

THREAD_FIELDS = "id,user_id,title,created_at,updated_at"
MESSAGE_FIELDS = "id,thread_id,role,sequence_number,content,parts,created_at"


async def list_threads(client: AsyncClient) -> list[dict[str, Any]]:
    """List the authenticated user's threads by most recent activity."""
    response = await (
        client.table("chat_threads")
        .select(THREAD_FIELDS)
        .order("updated_at", desc=True)
        .execute()
    )
    return response.data


async def create_thread(
    client: AsyncClient, user_id: UUID, title: str
) -> dict[str, Any]:
    """Create a thread owned by the authenticated user."""
    response = await (
        client.table("chat_threads")
        .insert({"user_id": str(user_id), "title": title})
        .execute()
    )
    return response.data[0]


async def get_thread_owner(client: AsyncClient, thread_id: UUID) -> UUID | None:
    """Look up ownership with a service-role client, bypassing RLS visibility."""
    response = await (
        client.table("chat_threads")
        .select("user_id")
        .eq("id", str(thread_id))
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return UUID(response.data[0]["user_id"])


async def list_messages(
    client: AsyncClient, thread_id: UUID
) -> list[dict[str, Any]]:
    """Load a thread's messages in conversational order."""
    response = await (
        client.table("chat_messages")
        .select(MESSAGE_FIELDS)
        .eq("thread_id", str(thread_id))
        .order("sequence_number")
        .execute()
    )
    return response.data


async def append_turn(
    client: AsyncClient,
    thread_id: UUID,
    user_message: PersistedMessage,
    assistant_message: PersistedMessage,
) -> None:
    """Persist one complete user/assistant turn and refresh thread activity."""
    response = await (
        client.table("chat_messages")
        .select("sequence_number")
        .eq("thread_id", str(thread_id))
        .order("sequence_number", desc=True)
        .limit(1)
        .execute()
    )
    next_sequence = response.data[0]["sequence_number"] + 1 if response.data else 0
    messages = [
        {
            "id": str(uuid4()),
            "thread_id": str(thread_id),
            "role": "user",
            "sequence_number": next_sequence,
            "content": user_message.content,
            "parts": user_message.parts,
        },
        {
            "id": str(uuid4()),
            "thread_id": str(thread_id),
            "role": "assistant",
            "sequence_number": next_sequence + 1,
            "content": assistant_message.content,
            "parts": assistant_message.parts,
        },
    ]
    await client.table("chat_messages").insert(messages).execute()
    await (
        client.table("chat_threads")
        .update({"updated_at": datetime.now(UTC).isoformat()})
        .eq("id", str(thread_id))
        .execute()
    )
