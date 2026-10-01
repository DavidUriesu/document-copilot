"""Tests for authenticated chat routes."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import CurrentUser, get_current_user
from app.chat.streaming import STUB_REPLY
from app.main import app

USER_ID = UUID("851b7b4c-d38b-4c4f-b52d-3ca3aece1ed0")
OTHER_USER_ID = UUID("92410be2-4f80-4f47-8ca7-1b445c5f39ca")
THREAD_ID = UUID("b49f3659-78af-4853-8494-d40af90a8287")
NOW = datetime(2026, 10, 1, tzinfo=UTC).isoformat()


@pytest.fixture
def authenticated_client() -> TestClient:
    async def authenticated_user() -> CurrentUser:
        return CurrentUser(
            id=USER_ID,
            email="analyst@example.com",
            access_token="access-token",
        )

    app.dependency_overrides[get_current_user] = authenticated_user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_chat_routes_require_authentication() -> None:
    client = TestClient(app)

    assert client.get("/chat/threads").status_code == 401
    assert client.post("/chat/threads", json={"title": "Test"}).status_code == 401
    assert client.get(f"/chat/threads/{THREAD_ID}/messages").status_code == 401
    assert (
        client.post(
            "/chat/stream",
            json={"threadId": str(THREAD_ID), "messages": []},
        ).status_code
        == 401
    )


def test_list_threads(authenticated_client: TestClient) -> None:
    row = {
        "id": str(THREAD_ID),
        "user_id": str(USER_ID),
        "title": "Revenue",
        "created_at": NOW,
        "updated_at": NOW,
    }
    with (
        patch("app.api.chat.create_user_client", AsyncMock(return_value=object())),
        patch("app.api.chat.list_threads", AsyncMock(return_value=[row])),
    ):
        response = authenticated_client.get("/chat/threads")

    assert response.status_code == 200
    assert response.json()[0]["userId"] == str(USER_ID)
    assert response.json()[0]["updatedAt"] == NOW.replace("+00:00", "Z")


def test_create_thread_trims_title(authenticated_client: TestClient) -> None:
    row = {
        "id": str(THREAD_ID),
        "user_id": str(USER_ID),
        "title": "Revenue",
        "created_at": NOW,
        "updated_at": NOW,
    }
    create = AsyncMock(return_value=row)
    with (
        patch("app.api.chat.create_user_client", AsyncMock(return_value=object())),
        patch("app.api.chat.create_thread", create),
    ):
        response = authenticated_client.post(
            "/chat/threads", json={"title": "  Revenue  "}
        )

    assert response.status_code == 201
    assert response.json()["title"] == "Revenue"
    assert create.await_args.args[2] == "Revenue"


@pytest.mark.parametrize(
    "owner, expected_status", [(None, 404), (OTHER_USER_ID, 403)]
)
def test_message_history_enforces_ownership(
    authenticated_client: TestClient, owner: UUID | None, expected_status: int
) -> None:
    with (
        patch("app.api.chat._clients", AsyncMock(return_value=(object(), object()))),
        patch("app.api.chat.get_thread_owner", AsyncMock(return_value=owner)),
    ):
        response = authenticated_client.get(f"/chat/threads/{THREAD_ID}/messages")

    assert response.status_code == expected_status


def test_load_message_history(authenticated_client: TestClient) -> None:
    row = {
        "id": "031b934a-0494-48c6-a276-02bdb57b9fa3",
        "thread_id": str(THREAD_ID),
        "role": "user",
        "sequence_number": 0,
        "content": "Question",
        "parts": [{"type": "text", "text": "Question"}],
        "created_at": NOW,
    }
    with (
        patch("app.api.chat._clients", AsyncMock(return_value=(object(), object()))),
        patch("app.api.chat.get_thread_owner", AsyncMock(return_value=USER_ID)),
        patch("app.api.chat.list_messages", AsyncMock(return_value=[row])),
    ):
        response = authenticated_client.get(f"/chat/threads/{THREAD_ID}/messages")

    assert response.status_code == 200
    assert response.json()[0]["sequenceNumber"] == 0
    assert response.json()[0]["threadId"] == str(THREAD_ID)


def test_streams_reply_then_persists_turn(authenticated_client: TestClient) -> None:
    persist = AsyncMock()
    with (
        patch("app.api.chat._clients", AsyncMock(return_value=(object(), object()))),
        patch("app.api.chat.get_thread_owner", AsyncMock(return_value=USER_ID)),
        patch("app.api.chat.append_turn", persist),
    ):
        response = authenticated_client.post(
            "/chat/stream",
            json={
                "threadId": str(THREAD_ID),
                "messages": [
                    {
                        "id": "message-1",
                        "role": "user",
                        "parts": [{"type": "text", "text": "My question"}],
                    }
                ],
            },
        )

    assert response.status_code == 200
    assert response.headers["x-vercel-ai-ui-message-stream"] == "v1"
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"type":"text-delta"' in response.text
    assert response.text.endswith("data: [DONE]\n\n")
    persist.assert_awaited_once()
    user_message = persist.await_args.args[2]
    assistant_message = persist.await_args.args[3]
    assert user_message.content == "My question"
    assert assistant_message.content == STUB_REPLY


def test_stream_rejects_non_user_final_message(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.post(
        "/chat/stream",
        json={
            "threadId": str(THREAD_ID),
            "messages": [
                {
                    "id": "message-1",
                    "role": "assistant",
                    "parts": [{"type": "text", "text": "Answer"}],
                }
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "The final message must have the user role"
