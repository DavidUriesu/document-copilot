"""FastAPI dependencies for authenticating Supabase users."""

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import AuthApiError

from app.database.supabase import create_user_client


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """Authenticated user data needed by request handlers."""

    id: UUID
    email: str | None
    access_token: str


bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUser:
    """Verify a Supabase access token and return its authenticated user."""
    if credentials is None:
        raise _unauthorized()

    access_token = credentials.credentials
    client = await create_user_client(access_token)

    try:
        response = await client.auth.get_user(access_token)
    except AuthApiError as exc:
        raise _unauthorized() from exc

    if response is None:
        raise _unauthorized()

    return CurrentUser(
        id=UUID(response.user.id),
        email=response.user.email,
        access_token=access_token,
    )
