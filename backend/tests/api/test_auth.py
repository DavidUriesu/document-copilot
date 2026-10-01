"""Tests for the authenticated user API."""

from uuid import UUID

from fastapi.testclient import TestClient

from app.auth.dependencies import CurrentUser, get_current_user
from app.main import app

USER_ID = UUID("851b7b4c-d38b-4c4f-b52d-3ca3aece1ed0")


def test_read_current_user_requires_authentication() -> None:
    response = TestClient(app).get("/auth/me")

    assert response.status_code == 401


def test_read_current_user_returns_verified_identity() -> None:
    async def authenticated_user() -> CurrentUser:
        return CurrentUser(
            id=USER_ID,
            email="analyst@example.com",
            access_token="access-token",
        )

    app.dependency_overrides[get_current_user] = authenticated_user
    try:
        response = TestClient(app).get("/auth/me")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "id": str(USER_ID),
        "email": "analyst@example.com",
    }
