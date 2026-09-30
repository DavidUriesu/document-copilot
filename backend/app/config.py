"""Validated application configuration sourced from environment variables."""

from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Environment-backed settings shared by all backend modules."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    supabase_url: str = Field(min_length=1)
    supabase_anon_key: str = Field(min_length=1)
    supabase_service_role_key: str = Field(min_length=1)

    database_url: str = Field(min_length=1)

    openai_api_key: str = Field(min_length=1)
    openai_embedding_model: str = Field(
        default="text-embedding-3-small", min_length=1
    )
    openai_embedding_dimensions: int = Field(default=1536, gt=0)

    allowed_origins: Annotated[list[str], NoDecode]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: object) -> object:
        """Accept the comma-separated format used by deployment environments."""
        if not isinstance(value, str):
            return value

        origins = [origin.strip().rstrip("/") for origin in value.split(",")]
        if not origins or any(not origin for origin in origins):
            raise ValueError("must contain one or more comma-separated origins")
        return origins


settings = Settings()
