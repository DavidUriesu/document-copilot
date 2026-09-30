"""Shared SQLAlchemy declarative base and external table references."""

from sqlalchemy import Column, Table
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all application database models."""


auth_users = Table(
    "users",
    Base.metadata,
    Column("id", PostgreSQLUUID(as_uuid=True), primary_key=True),
    schema="auth",
    info={"skip_autogenerate": True},
)
