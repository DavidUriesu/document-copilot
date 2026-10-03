"""Tests for AI SDK streaming event construction."""

import json

from app.chat.streaming import (
    citation_event,
    error_event,
    finish_events,
    reply_chunks,
    start_events,
    status_event,
    text_delta_event,
)


def _payload(event: str) -> dict[str, object]:
    return json.loads(event.removeprefix("data: ").strip())


def test_stream_events_follow_ui_message_protocol() -> None:
    opening = list(start_events("message-id", "text-id"))
    closing = list(finish_events("text-id"))

    assert [_payload(event)["type"] for event in opening] == [
        "start",
        "start-step",
        "text-start",
    ]
    assert _payload(text_delta_event("text-id", "hello")) == {
        "type": "text-delta",
        "id": "text-id",
        "delta": "hello",
    }
    assert [_payload(event)["type"] for event in closing[:-1]] == [
        "text-end",
        "finish-step",
        "finish",
    ]
    assert closing[-1] == "data: [DONE]\n\n"


def test_reply_chunks_reassemble_original_text() -> None:
    assert "".join(reply_chunks("A deterministic reply", chunk_size=4)) == (
        "A deterministic reply"
    )


def test_status_and_citation_parts_follow_data_protocol() -> None:
    assert _payload(status_event("retrieving")) == {
        "type": "data-status",
        "data": {"stage": "retrieving"},
        "transient": True,
    }
    assert _payload(citation_event({"index": 1})) == {
        "type": "data-citation",
        "data": {"index": 1},
    }


def test_error_event_does_not_include_exception_details() -> None:
    payload = _payload(error_event())
    assert payload["type"] == "error"
    assert "provider" not in str(payload).lower()
