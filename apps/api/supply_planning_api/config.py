from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or root `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_environment: str = Field(default="development", alias="APP_ENV")
    cors_origins_csv: str = Field(
        default="http://localhost:5173",
        alias="CORS_ORIGINS",
    )
    supabase_url: str | None = Field(default=None, alias="SUPABASE_URL")
    supabase_secret_key: SecretStr | None = Field(
        default=None,
        alias="SUPABASE_SECRET_KEY",
    )

    @field_validator("cors_origins_csv")
    @classmethod
    def reject_wildcard_cors(cls, value: str) -> str:
        if "*" in {origin.strip() for origin in value.split(",")}:
            raise ValueError("CORS_ORIGINS must list exact origins; wildcard is not allowed")
        return value

    @property
    def cors_origins(self) -> tuple[str, ...]:
        return tuple(
            origin.rstrip("/")
            for value in self.cors_origins_csv.split(",")
            if (origin := value.strip())
        )

    @property
    def supabase_configured(self) -> bool:
        return bool(
            self.supabase_url
            and self.supabase_secret_key
            and self.supabase_secret_key.get_secret_value()
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
