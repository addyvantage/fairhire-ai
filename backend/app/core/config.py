from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    project_name: str = "FairHire-AI"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "change-this-secret-key"
    access_token_expire_minutes: int = 60
    database_url: str = "postgresql+asyncpg://fairhire:fairhire@db:5432/fairhire"
    upload_dir: str = "app/storage/uploads"
    allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # "json" | "console"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
