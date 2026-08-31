"""
Application configuration.
All settings are read from environment variables via pydantic-settings.
No hardcoded secrets or credentials.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    app_version: str = "0.1.0"

    # Server
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]

    # Supabase (required for Phase 2+; validated as non-empty when not in development)
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    database_url: str = ""

    # AI / Gemini Configuration (Phase 5+)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance. Loaded once at startup."""
    return Settings()
