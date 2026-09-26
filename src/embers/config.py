"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Backend configuration.

    Required variables: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, DATABASE_URL,
    DEFAULT_WORKSPACE_ID. Everything else is optional.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    supabase_url: str
    supabase_service_role_key: SecretStr
    database_url: str
    default_workspace_id: UUID

    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None

    # "*" (the default) allows any origin. Set a comma-separated list to restrict it.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["*"])
    providers_file: Path = Path("config/providers.yaml")

    agent_runtime: Literal["strands", "fake"] = "strands"
    fake_runtime_delay_s: float = Field(default=3.0, ge=0)
    task_timeout_s: float = Field(default=600, gt=0)
    ask_timeout_s: float = Field(default=1800, gt=0)
    max_questions_per_task: int = Field(default=3, ge=0)

    artifacts_bucket: str = "artifacts"
    signed_url_ttl_s: int = Field(default=3600, gt=0)
    artifact_url_ttl_s: int = Field(default=604800, gt=0)
    pptx_template_path: Path | None = None

    @field_validator("pptx_template_path", mode="before")
    @classmethod
    def _empty_template_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if value is None or value == "":
            return ["*"]
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    def provider_key(self, provider: str) -> str | None:
        """The API key for `provider`, or None when unset or blank."""
        keys: dict[str, SecretStr | None] = {
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
            "gemini": self.gemini_api_key,
        }
        key = keys.get(provider)
        if key is None or key.get_secret_value().strip() == "":
            return None
        return key.get_secret_value()

    def has_provider_key(self, provider: str) -> bool:
        """True when the API key for `provider` is set and not blank. Never exposes the key."""
        return self.provider_key(provider) is not None


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance for use as a FastAPI dependency default."""
    return Settings()
