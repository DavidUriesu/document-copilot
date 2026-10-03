"""Async Supabase clients for user-scoped and privileged database access."""

from supabase import AsyncClient, AsyncClientOptions, acreate_client

from app.config import settings


def _client_options(access_token: str) -> AsyncClientOptions:
    return AsyncClientOptions(
        headers={"Authorization": f"Bearer {access_token}"},
        auto_refresh_token=False,
        persist_session=False,
    )


async def create_user_client(access_token: str) -> AsyncClient:
    """Create a client whose database requests are subject to the user's RLS."""
    return await acreate_client(
        settings.supabase_url,
        settings.supabase_anon_key,
        _client_options(access_token),
    )


async def create_service_role_client() -> AsyncClient:
    """Create a privileged backend client that bypasses row-level security."""
    key = settings.supabase_service_role_key
    client = await acreate_client(
        settings.supabase_url,
        key,
        AsyncClientOptions(auto_refresh_token=False, persist_session=False),
    )
    if key.startswith("sb_secret_"):
        # supabase-py 2.31 still copies API keys into Authorization. Modern
        # secret keys authenticate through apikey and must not be parsed as JWTs.
        client.options.headers.pop("Authorization", None)
    return client
