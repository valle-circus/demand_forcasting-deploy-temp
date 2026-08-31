from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from .config import Settings
from .errors import ConflictError, RepositoryUnavailableError

type JsonObject = dict[str, Any]

CANONICAL_TABLES = frozenset(
    {
        "source_imports",
        "master_data_versions",
        "locations",
        "items",
        "item_policy_overrides",
        "delivery_rules",
        "forecast_daily",
        "menu_calendar",
        "bom_lines",
        "inventory_snapshots",
        "purchase_order_lines",
        "planning_runs",
        "planning_run_inputs",
        "planning_lines",
        "planning_recommendations",
        "planning_exceptions",
        "planning_netting_results",
        "planning_projection_days",
    }
)
REQUIRED_SCHEMA_TABLES = tuple(sorted(CANONICAL_TABLES))
REQUIRED_SCHEMA_FUNCTIONS = (
    "activate_master_data_version_v1",
    "persist_master_import_v1",
    "persist_planning_run_v2",
    "persist_source_import_v1",
)


@dataclass(frozen=True, slots=True)
class SchemaState:
    ready: bool
    missing_tables: tuple[str, ...] = ()
    missing_functions: tuple[str, ...] = ()


class CanonicalStore(Protocol):
    async def schema_state(self) -> SchemaState: ...

    async def select_rows(
        self,
        table: str,
        *,
        columns: str = "*",
        filters: dict[str, str] | None = None,
        order: str | None = None,
        limit: int | None = None,
    ) -> list[JsonObject]: ...

    async def insert_rows(
        self,
        table: str,
        rows: list[JsonObject],
    ) -> list[JsonObject]: ...

    async def update_rows(
        self,
        table: str,
        values: JsonObject,
        *,
        filters: dict[str, str],
    ) -> list[JsonObject]: ...

    async def delete_rows(
        self,
        table: str,
        *,
        filters: dict[str, str],
    ) -> None: ...

    async def activate_master_version(
        self,
        *,
        version_id: str,
        actor_id: str,
        environment: str,
    ) -> JsonObject: ...

    async def persist_master_import(self, payload: JsonObject) -> JsonObject: ...

    async def persist_source_import(self, payload: JsonObject) -> JsonObject: ...

    async def persist_planning_run(self, payload: JsonObject) -> str: ...


class SupabaseCanonicalStore:
    """Server-only PostgREST adapter for the portable canonical table contract."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    def _configuration(self) -> tuple[str, str]:
        if not self._settings.supabase_configured:
            raise RepositoryUnavailableError(
                "Add SUPABASE_URL and SUPABASE_SECRET_KEY on the API service."
            )
        assert self._settings.supabase_url is not None
        assert self._settings.supabase_secret_key is not None
        return (
            self._settings.supabase_url.rstrip("/"),
            self._settings.supabase_secret_key.get_secret_value(),
        )

    @staticmethod
    def _table(table: str) -> str:
        if table not in CANONICAL_TABLES:
            raise ValueError(f"unsupported canonical table {table!r}")
        return table

    def _headers(self, *, prefer: str | None = None) -> dict[str, str]:
        _, secret = self._configuration()
        headers = {
            "apikey": secret,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if not secret.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {secret}"
        if prefer is not None:
            headers["Prefer"] = prefer
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        payload: Any = None,
        prefer: str | None = None,
        accept: str | None = None,
    ) -> httpx.Response:
        base_url, _ = self._configuration()
        headers = self._headers(prefer=prefer)
        if accept is not None:
            headers["Accept"] = accept
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.supabase_timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.request(
                    method,
                    f"{base_url}/rest/v1/{path}",
                    params=params,
                    json=payload,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise RepositoryUnavailableError(
                "Supabase could not be reached from the API service."
            ) from exc
        if response.status_code == 409:
            raise ConflictError(
                "persistence_conflict",
                "The requested record conflicts with an existing persisted version.",
            )
        if not 200 <= response.status_code < 300:
            raise RepositoryUnavailableError(
                "Supabase rejected a canonical persistence operation. Check the applied "
                "migrations and the server-side key."
            )
        return response

    @staticmethod
    def _json_rows(response: httpx.Response) -> list[JsonObject]:
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise RepositoryUnavailableError(
                "Supabase returned an invalid persistence response."
            ) from exc
        if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
            raise RepositoryUnavailableError(
                "Supabase returned an unexpected persistence response."
            )
        return [dict(row) for row in payload]

    async def schema_state(self) -> SchemaState:
        try:
            response = await self._request(
                "GET",
                "",
                accept="application/openapi+json",
            )
            payload: Any = response.json()
            paths = payload.get("paths") if isinstance(payload, dict) else None
            if not isinstance(paths, dict):
                raise ValueError("missing OpenAPI paths")
        except (RepositoryUnavailableError, ValueError):
            return SchemaState(
                ready=False,
                missing_tables=REQUIRED_SCHEMA_TABLES,
                missing_functions=REQUIRED_SCHEMA_FUNCTIONS,
            )

        missing_tables = [
            table for table in REQUIRED_SCHEMA_TABLES if f"/{table}" not in paths
        ]
        missing_functions = [
            function
            for function in REQUIRED_SCHEMA_FUNCTIONS
            if f"/rpc/{function}" not in paths
        ]

        return SchemaState(
            ready=not missing_tables and not missing_functions,
            missing_tables=tuple(missing_tables),
            missing_functions=tuple(dict.fromkeys(missing_functions)),
        )

    async def select_rows(
        self,
        table: str,
        *,
        columns: str = "*",
        filters: dict[str, str] | None = None,
        order: str | None = None,
        limit: int | None = None,
    ) -> list[JsonObject]:
        params = {"select": columns}
        if filters:
            params.update(filters)
        if order is not None:
            params["order"] = order
        if limit is not None:
            params["limit"] = str(limit)
        response = await self._request("GET", self._table(table), params=params)
        return self._json_rows(response)

    async def insert_rows(
        self,
        table: str,
        rows: list[JsonObject],
    ) -> list[JsonObject]:
        if not rows:
            return []
        response = await self._request(
            "POST",
            self._table(table),
            payload=rows,
            prefer="return=representation",
        )
        return self._json_rows(response)

    async def update_rows(
        self,
        table: str,
        values: JsonObject,
        *,
        filters: dict[str, str],
    ) -> list[JsonObject]:
        response = await self._request(
            "PATCH",
            self._table(table),
            params=filters,
            payload=values,
            prefer="return=representation",
        )
        return self._json_rows(response)

    async def delete_rows(
        self,
        table: str,
        *,
        filters: dict[str, str],
    ) -> None:
        await self._request(
            "DELETE",
            self._table(table),
            params=filters,
            prefer="return=minimal",
        )

    async def _rpc(self, function: str, payload: JsonObject) -> Any:
        if function not in REQUIRED_SCHEMA_FUNCTIONS:
            raise ValueError(f"unsupported persistence function {function!r}")
        response = await self._request(
            "POST",
            f"rpc/{function}",
            payload=payload,
            prefer="return=representation",
        )
        try:
            return response.json()
        except ValueError as exc:
            raise RepositoryUnavailableError(
                "Supabase returned an invalid transaction response."
            ) from exc

    async def activate_master_version(
        self,
        *,
        version_id: str,
        actor_id: str,
        environment: str,
    ) -> JsonObject:
        payload = await self._rpc(
            "activate_master_data_version_v1",
            {
                "p_version_id": version_id,
                "p_actor_id": actor_id,
                "p_environment": environment,
            },
        )
        if isinstance(payload, list) and len(payload) == 1 and isinstance(payload[0], dict):
            return dict(payload[0])
        if isinstance(payload, dict):
            return dict(payload)
        raise RepositoryUnavailableError(
            "Supabase returned an unexpected master activation response."
        )

    async def _persist_import_rpc(
        self,
        function: str,
        payload: JsonObject,
    ) -> JsonObject:
        result = await self._rpc(function, {"p_payload": payload})
        if isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict):
            return dict(result[0])
        if isinstance(result, dict):
            return dict(result)
        raise RepositoryUnavailableError(
            "Supabase returned an unexpected source-import transaction response."
        )

    async def persist_master_import(self, payload: JsonObject) -> JsonObject:
        return await self._persist_import_rpc("persist_master_import_v1", payload)

    async def persist_source_import(self, payload: JsonObject) -> JsonObject:
        return await self._persist_import_rpc("persist_source_import_v1", payload)

    async def persist_planning_run(self, payload: JsonObject) -> str:
        result = await self._rpc(
            "persist_planning_run_v2",
            {"p_payload": payload},
        )
        if isinstance(result, str):
            return result
        if isinstance(result, list) and len(result) == 1:
            value = result[0]
            if isinstance(value, str):
                return value
            if isinstance(value, dict):
                candidate = value.get("persist_planning_run_v2")
                if isinstance(candidate, str):
                    return candidate
        raise RepositoryUnavailableError(
            "Supabase returned an unexpected planning transaction response."
        )
