"""Tests for atomic grounded-turn persistence calls."""

import asyncio
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from app.assistant.outputs import CitationView
from app.chat.messages import PersistedMessage
from app.database.chats import append_grounded_turn

THREAD = UUID("20000000-0000-0000-0000-000000000001")
USER_MESSAGE = UUID("30000000-0000-0000-0000-000000000001")
ASSISTANT_MESSAGE = UUID("40000000-0000-0000-0000-000000000001")
CHUNK = UUID("00000000-0000-0000-0000-000000000001")


@dataclass
class Response:
    data: list[dict[str, Any]]


class RpcCall:
    async def execute(self) -> Response:
        return Response(
            [
                {
                    "user_message_id": str(USER_MESSAGE),
                    "assistant_message_id": str(ASSISTANT_MESSAGE),
                }
            ]
        )


class FakeClient:
    def __init__(self) -> None:
        self.name = ""
        self.params: dict[str, object] = {}

    def rpc(self, name: str, params: dict[str, object]) -> RpcCall:
        self.name = name
        self.params = params
        return RpcCall()


def test_append_grounded_turn_sends_messages_and_ordered_citations() -> None:
    client = FakeClient()
    user = PersistedMessage("Question", [{"type": "text", "text": "Question"}])
    assistant = PersistedMessage("Answer [1]", [{"type": "text", "text": "Answer [1]"}])
    citation = CitationView(
        index=1,
        chunk_id=CHUNK,
        excerpt="verbatim excerpt",
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        filing_date=date(2025, 10, 31),
        fiscal_year=2025,
        page_number=31,
        section="Item 8",
        source_url="https://example.com/filing",
    )

    result = asyncio.run(
        append_grounded_turn(
            client,
            THREAD,
            user,
            assistant,
            [citation],
            user_message_id=USER_MESSAGE,
            assistant_message_id=ASSISTANT_MESSAGE,
        )
    )

    assert result == (USER_MESSAGE, ASSISTANT_MESSAGE)
    assert client.name == "append_grounded_turn"
    assert client.params["p_assistant_content"] == "Answer [1]"
    assert client.params["p_citations"] == [
        {
            "chunk_id": str(CHUNK),
            "citation_index": 1,
            "excerpt": "verbatim excerpt",
        }
    ]
