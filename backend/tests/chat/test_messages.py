"""Tests for AI SDK message conversion."""

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse

from app.chat.messages import UIMessage, model_history, submitted_user_message


def test_submitted_user_message_joins_text_parts() -> None:
    message = UIMessage(
        id="message-1",
        role="user",
        parts=[
            {"type": "text", "text": "Hello "},
            {"type": "file", "url": "https://example.com/file"},
            {"type": "text", "text": "world"},
        ],
    )

    result = submitted_user_message([message])

    assert result.content == "Hello world"
    assert result.parts == message.parts


@pytest.mark.parametrize(
    "message, expected",
    [
        (
            UIMessage(
                id="message-1",
                role="assistant",
                parts=[{"type": "text", "text": "Not a submission"}],
            ),
            "The final message must have the user role",
        ),
        (
            UIMessage(
                id="message-1",
                role="user",
                parts=[{"type": "text", "text": "   "}],
            ),
            "The final user message must contain text",
        ),
    ],
)
def test_submitted_user_message_rejects_invalid_final_message(
    message: UIMessage, expected: str
) -> None:
    with pytest.raises(ValueError, match=expected):
        submitted_user_message([message])


def test_model_history_converts_authoritative_rows() -> None:
    history = model_history(
        [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Answer [1]"},
        ]
    )
    assert isinstance(history[0], ModelRequest)
    assert history[0].parts[0].content == "Question"
    assert isinstance(history[1], ModelResponse)
    assert history[1].parts[0].content == "Answer [1]"
