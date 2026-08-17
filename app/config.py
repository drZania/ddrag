"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""

    return Settings()
