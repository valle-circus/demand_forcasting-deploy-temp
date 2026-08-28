from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import httpx

from .config import Settings

DependencyStatus = Literal["ready", "not_configured", "unavailable"]


@dataclass(frozen=True, slots=True)
class DependencyState:
    status: DependencyStatus
    message: str


class ReadinessProbe(Protocol):
    async def check(self) -> DependencyState: ...


class SupabaseReadinessProbe:
    """Verify the server-side Supabase REST boundary without exposing secrets."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def check(self) -> DependencyState:
        if not self._settings.supabase_configured:
            return DependencyState(
                status="not_configured",
                message="Add SUPABASE_URL and SUPABASE_SECRET_KEY on the API service.",
            )

        assert self._settings.supabase_url is not None
        assert self._settings.supabase_secret_key is not None
        secret = self._settings.supabase_secret_key.get_secret_value()
        headers = {"apikey": secret, "Accept": "application/json"}
        # Legacy service-role keys are JWTs and still require the bearer header.
        # New sb_secret_ keys are intentionally sent only through `apikey`.
        if not secret.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {secret}"

        endpoint = (
            f"{self._settings.supabase_url.rstrip('/')}"
            "/rest/v1/master_data_versions"
        )
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    endpoint,
                    params={"select": "id", "limit": "1"},
                    headers=headers,
                )
        except httpx.HTTPError:
            return DependencyState(
                status="unavailable",
                message="Supabase could not be reached from the API service.",
            )

        if 200 <= response.status_code < 300:
            return DependencyState(
                status="ready",
                message="Supabase REST and the foundation migration are reachable.",
            )
        return DependencyState(
            status="unavailable",
            message=(
                "Supabase responded, but the connection is not ready. "
                "Check the server key and apply the repository migrations."
            ),
        )
