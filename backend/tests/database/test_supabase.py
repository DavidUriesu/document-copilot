"""Tests for Supabase client construction."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.config import settings
from app.database.supabase import create_service_role_client, create_user_client


def test_create_user_client_uses_anon_key_and_user_token() -> None:
    client = object()

    with patch(
        "app.database.supabase.acreate_client", AsyncMock(return_value=client)
    ) as create_client:
        result = asyncio.run(create_user_client("user-access-token"))

    assert result is client
    url, key, options = create_client.await_args.args
    assert url == settings.supabase_url
    assert key == settings.supabase_anon_key
    assert options.headers == {"Authorization": "Bearer user-access-token"}
    assert options.auto_refresh_token is False
    assert options.persist_session is False


def test_create_service_role_client_uses_service_role_credentials() -> None:
    client = SimpleNamespace(
        options=SimpleNamespace(
            headers={
                "apiKey": settings.supabase_service_role_key,
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
            }
        )
    )

    with patch(
        "app.database.supabase.acreate_client", AsyncMock(return_value=client)
    ) as create_client:
        result = asyncio.run(create_service_role_client())

    assert result is client
    url, key, options = create_client.await_args.args
    assert url == settings.supabase_url
    assert key == settings.supabase_service_role_key
    assert options.auto_refresh_token is False
    assert options.persist_session is False
    if settings.supabase_service_role_key.startswith("sb_secret_"):
        assert client.options.headers == {
            "apiKey": settings.supabase_service_role_key
        }
    else:
        assert client.options.headers["Authorization"] == (
            f"Bearer {settings.supabase_service_role_key}"
        )
