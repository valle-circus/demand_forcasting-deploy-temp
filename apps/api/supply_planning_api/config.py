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
    allowed_email_domains_csv: str = Field(
        default="circuskitchens.com",
        alias="ALLOWED_EMAIL_DOMAINS",
    )
    supabase_url: str | None = Field(default=None, alias="SUPABASE_URL")
    supabase_secret_key: SecretStr | None = Field(
        default=None,
        alias="SUPABASE_SECRET_KEY",
    )
    supabase_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        le=60,
        alias="SUPABASE_TIMEOUT_SECONDS",
    )
    max_upload_bytes: int = Field(
        default=25 * 1024 * 1024,
        gt=0,
        le=250 * 1024 * 1024,
        alias="MAX_UPLOAD_BYTES",
    )
    max_po_files: int = Field(
        default=100,
        gt=0,
        le=500,
        alias="MAX_PO_FILES",
    )

    @field_validator("cors_origins_csv")
    @classmethod
    def reject_wildcard_cors(cls, value: str) -> str:
        if "*" in {origin.strip() for origin in value.split(",")}:
            raise ValueError("CORS_ORIGINS must list exact origins; wildcard is not allowed")
        return value

    @field_validator("allowed_email_domains_csv")
    @classmethod
    def reject_open_email_allowlist(cls, value: str) -> str:
        """
        An empty or wildcard allowlist is refused rather than read as "allow
        everyone". Self-service sign-up means anyone who reaches the deployed
        URL can create a Supabase account, and every valid account is a
        maintainer to this API, so a blank value here would silently publish
        planning data.
        """
        domains = [item.strip() for item in value.split(",") if item.strip()]
        if not domains:
            raise ValueError(
                "ALLOWED_EMAIL_DOMAINS must list at least one domain; "
                "an empty value would let any address reach planning data"
            )
        if any("*" in domain for domain in domains):
            raise ValueError(
                "ALLOWED_EMAIL_DOMAINS must list exact domains; wildcard is not allowed"
            )
        return value

    @property
    def allowed_email_domains(self) -> tuple[str, ...]:
        return tuple(
            domain.lower().lstrip("@")
            for item in self.allowed_email_domains_csv.split(",")
            if (domain := item.strip())
        )

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
