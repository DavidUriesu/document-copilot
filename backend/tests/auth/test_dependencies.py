"""Tests for Supabase authentication dependencies."""

import asyncio
from types import SimpleNamespace
from typing import Annotated
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from supabase import AuthApiError

from app.auth.dependencies import CurrentUser, get_current_user

USER_ID = UUID("851b7b4c-d38b-4c4f-b52d-3ca3aece1ed0")


def credentials(token: str = "access-token") -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_get_current_user_rejects_missing_credentials() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_current_user(None))

    assert exc_info.value.status_code == 401
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


def test_get_current_user_returns_verified_user() -> None:
    client = SimpleNamespace(
        auth=SimpleNamespace(
            get_user=AsyncMock(
                return_value=SimpleNamespace(
                    user=SimpleNamespace(id=str(USER_ID), email="analyst@example.com")
                )
            )
        )
    )

    with patch(
        "app.auth.dependencies.create_user_client",
        AsyncMock(return_value=client),
    ) as create_client:
        user = asyncio.run(get_current_user(credentials()))

    create_client.assert_awaited_once_with("access-token")
    client.auth.get_user.assert_awaited_once_with("access-token")
    assert user.id == USER_ID
    assert user.email == "analyst@example.com"
    assert user.access_token == "access-token"


def test_get_current_user_rejects_invalid_token() -> None:
    client = SimpleNamespace(
        auth=SimpleNamespace(
            get_user=AsyncMock(side_effect=AuthApiError("invalid JWT", 401, "bad_jwt"))
        )
    )

    with (
        patch(
            "app.auth.dependencies.create_user_client",
            AsyncMock(return_value=client),
        ),
        pytest.raises(HTTPException) as exc_info,
    ):
        asyncio.run(get_current_user(credentials("invalid-token")))

    assert exc_info.value.status_code == 401
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


def test_protected_work_does_not_run_without_token() -> None:
    app = FastAPI()
    work_started = False

    @app.get("/protected")
    async def protected(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> dict[str, str]:
        nonlocal work_started
        work_started = True
        return {"user_id": str(current_user.id)}

    response = TestClient(app).get("/protected")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert work_started is False


def test_protected_work_does_not_run_with_expired_token() -> None:
    app = FastAPI()
    work_started = False

    @app.get("/protected")
    async def protected(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> dict[str, str]:
        nonlocal work_started
        work_started = True
        return {"user_id": str(current_user.id)}

    client = SimpleNamespace(
        auth=SimpleNamespace(
            get_user=AsyncMock(side_effect=AuthApiError("JWT expired", 401, "bad_jwt"))
        )
    )

    with patch(
        "app.auth.dependencies.create_user_client",
        AsyncMock(return_value=client),
    ):
        response = TestClient(app).get(
            "/protected",
            headers={"Authorization": "Bearer expired-token"},
        )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert work_started is False
