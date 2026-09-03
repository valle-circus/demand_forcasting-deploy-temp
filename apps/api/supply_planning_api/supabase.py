from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from .config import Settings
from .repository import CanonicalStore

DependencyStatus = Literal["ready", "not_configured", "unavailable"]


@dataclass(frozen=True, slots=True)
class DependencyState:
    status: DependencyStatus
    message: str


class ReadinessProbe(Protocol):
    async def check(self) -> DependencyState: ...


class SupabaseReadinessProbe:
    """Verify the server-side Supabase REST boundary without exposing secrets."""

    def __init__(self, settings: Settings, store: CanonicalStore) -> None:
        self._settings = settings
        self._store = store

    async def check(self) -> DependencyState:
        if not self._settings.supabase_configured:
            return DependencyState(
                status="not_configured",
                message="Add SUPABASE_URL and SUPABASE_SECRET_KEY on the API service.",
            )

        try:
            schema = await self._store.schema_state()
        except Exception:
            return DependencyState(
                status="unavailable",
                message="Supabase could not be reached from the API service.",
            )

        if schema.ready:
            return DependencyState(
                status="ready",
                message="Supabase REST and all required backend migrations are reachable.",
            )
        return DependencyState(
            status="unavailable",
            message=(
                "Supabase responded, but the server key cannot see every required backend "
                "table/function. Check the key and apply all migrations in order."
            ),
        )
