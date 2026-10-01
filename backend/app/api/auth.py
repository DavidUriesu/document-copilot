"""Authenticated user API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import CurrentUser, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class CurrentUserResponse(BaseModel):
    """Public identity fields for the authenticated user."""

    id: UUID
    email: str | None


@router.get("/me", response_model=CurrentUserResponse)
async def read_current_user(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUserResponse:
    """Return the identity verified from the request bearer token."""
    return CurrentUserResponse(id=current_user.id, email=current_user.email)
