"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.chunking import DEFAULT_CHUNKING_VERSION, validate_chunking_config


class DatabaseSettings(BaseSettings):
    """Settings required by database tooling and sessions."""

    database_url: str = "postgresql+psycopg://ddrag:ddrag_dev_password@127.0.0.1:55432/ddrag"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class Settings(DatabaseSettings):
    """Settings required by the application."""

    app_name: str = "DDRAG"
    app_env: str = "development"
    log_level: str = "INFO"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    document_storage_path: str = "storage/documents"
    max_upload_size_bytes: int = 10 * 1024 * 1024
    chunk_size_chars: int = 1000
    chunk_overlap_chars: int = 200
    chunking_version: str = DEFAULT_CHUNKING_VERSION

    @model_validator(mode="after")
    def _validate_chunking_settings(self) -> "Settings":
        validate_chunking_config(self.chunk_size_chars, self.chunk_overlap_chars)
        if not self.chunking_version.strip():
            raise ValueError("chunking_version must not be blank")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""

    return Settings()
