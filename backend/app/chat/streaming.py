"""AI SDK-compatible streaming for the stubbed chat slice."""

import json
from collections.abc import Iterable
from uuid import uuid4

STUB_REPLY = (
    "This is a stubbed response. Document retrieval and grounded answers "
    "will be added in a later phase."
)


def _event(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"


def reply_chunks(reply: str = STUB_REPLY, chunk_size: int = 24) -> Iterable[str]:
    """Split a reply into stable text deltas without breaking the wire contract."""
    for offset in range(0, len(reply), chunk_size):
        yield reply[offset : offset + chunk_size]


def start_events(message_id: str, text_id: str) -> Iterable[str]:
    """Emit the opening events for an AI SDK UI message stream."""
    yield _event({"type": "start", "messageId": message_id})
    yield _event({"type": "start-step"})
    yield _event({"type": "text-start", "id": text_id})


def text_delta_event(text_id: str, delta: str) -> str:
    """Encode one assistant text delta."""
    return _event({"type": "text-delta", "id": text_id, "delta": delta})


def finish_events(text_id: str) -> Iterable[str]:
    """Emit the terminal events for a successful AI SDK UI message stream."""
    yield _event({"type": "text-end", "id": text_id})
    yield _event({"type": "finish-step"})
    yield _event({"type": "finish"})
    yield "data: [DONE]\n\n"


def stream_ids() -> tuple[str, str]:
    """Create identifiers for a streamed assistant message and text part."""
    return str(uuid4()), str(uuid4())
