from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import (
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
)


def _parse_str_or_list(value: Any, *, cast: type = str) -> list:
    """Parse a value that may arrive as a JSON list, comma-separated string,
    empty string, or already-parsed list.  Handles the case where
    pydantic-settings' EnvSettingsSource fails to JSON-parse the raw env
    value and passes it through as a string."""
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        raise ValueError(f"expected str or list, got {type(value).__name__}")
    stripped = value.strip()
    if not stripped:
        return []
    # Try JSON first (handles '["http://localhost:3000"]' style)
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, list):
            return [cast(item) for item in parsed]
    except (json.JSONDecodeError, ValueError):
        pass
    # Fall back to comma-separated
    return [cast(item.strip()) for item in stripped.split(",") if item.strip()]


class _LenientPrepareFieldMixin:
    """Mixin that catches JSON decode errors in ``prepare_field_value`` and
    passes the raw string through so that field validators can handle
    comma-separated and other non-JSON formats."""

    def prepare_field_value(
        self, field_name: str, field: Any, value: Any, value_is_complex: bool
    ) -> Any:
        try:
            return super().prepare_field_value(field_name, field, value, value_is_complex)  # type: ignore[misc]
        except Exception:
            return value


class _LenientEnvSource(_LenientPrepareFieldMixin, EnvSettingsSource):
    pass


class _LenientDotEnvSource(_LenientPrepareFieldMixin, DotEnvSettingsSource):
    pass


class Settings(BaseSettings):
    project_name: str = "FairHire-AI"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "change-this-secret-key"
    access_token_expire_minutes: int = 60
    database_url: str = "postgresql+asyncpg://fairhire:fairhire@db:5432/fairhire"
    upload_dir: str = "app/storage/uploads"
    studio_export_dir: str = "app/storage/exports"
    studio_max_upload_mb: int = 10
    allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Redis
    redis_url: str = Field(
        default="redis://redis:6379/0",
        validation_alias=AliasChoices("REDIS_URL", "RQ_REDIS_URL"),
    )
    redis_socket_timeout_seconds: int = 600

    # Embedding
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_cache_l1_size: int = 1000
    embedding_cache_ttl_seconds: int = 86400

    # Optional local open-weights reasoner (llama.cpp compatible)
    open_weights_reasoner_model_path: str = ""
    open_weights_reasoner_max_tokens: int = 320
    open_weights_reasoner_temperature: float = 0.1

    # Async job queue
    queue_name: str = "fairhire:analysis"
    async_job_retry_max: int = 3
    async_job_retry_interval: list[int] = [10, 30, 60]
    analysis_stale_after_minutes: int = 15

    # Worker
    worker_heartbeat_interval_seconds: int = 30
    worker_heartbeat_ttl_seconds: int = 90

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # "json" | "console"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            _LenientEnvSource(settings_cls),
            _LenientDotEnvSource(
                settings_cls,
                env_file=cls.model_config.get("env_file", ".env"),
                env_file_encoding=cls.model_config.get("env_file_encoding", "utf-8"),
            ),
            file_secret_settings,
        )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: Any) -> list[str]:
        return _parse_str_or_list(value, cast=str)

    @field_validator("async_job_retry_interval", mode="before")
    @classmethod
    def parse_retry_interval(cls, value: Any) -> list[int]:
        return _parse_str_or_list(value, cast=int)


@lru_cache
def get_settings() -> Settings:
    return Settings()
