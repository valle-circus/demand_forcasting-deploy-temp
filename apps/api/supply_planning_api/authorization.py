from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, cast

from .auth import AuthenticatedUser
from .errors import ForbiddenError, RepositoryUnavailableError
from .repository import CanonicalStore, JsonObject, SchemaState

WorkspaceRole = Literal["owner", "admin", "planner", "viewer"]
SystemRole = Literal["user", "system_admin"]

WORKSPACE_SCOPED_TABLES = frozenset(
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

LOCATION_SCOPED_TABLES = frozenset(
    {
        "locations",
        "delivery_rules",
        "forecast_daily",
        "menu_calendar",
        "inventory_snapshots",
        "purchase_order_lines",
        "planning_runs",
        "planning_lines",
        "planning_recommendations",
        "planning_netting_results",
        "planning_projection_days",
    }
)


@dataclass(frozen=True, slots=True)
class AccessScope:
    user_id: str
    email: str | None
    workspace_id: str
    workspace_role: WorkspaceRole
    system_role: SystemRole = "user"
    readable_location_ids: frozenset[str] | None = None
    writable_location_ids: frozenset[str] | None = None

    @property
    def can_admin_workspace(self) -> bool:
        return self.system_role == "system_admin" or self.workspace_role in {
            "owner",
            "admin",
        }

    def require_workspace_admin(self) -> None:
        if not self.can_admin_workspace:
            raise ForbiddenError(
                "workspace_admin_required",
                "Only a workspace owner or administrator can perform this action.",
            )

    def can_read_location(self, location_id: str) -> bool:
        return self.readable_location_ids is None or location_id in self.readable_location_ids

    def can_write_location(self, location_id: str) -> bool:
        if self.workspace_role == "viewer" and self.system_role != "system_admin":
            return False
        return self.writable_location_ids is None or location_id in self.writable_location_ids

    def require_location_read(self, location_id: str) -> None:
        if not self.can_read_location(location_id):
            raise ForbiddenError(
                "location_access_denied",
                "You do not have access to this location.",
            )

    def require_location_write(self, location_id: str) -> None:
        if not self.can_write_location(location_id):
            raise ForbiddenError(
                "location_write_denied",
                "You do not have permission to change or calculate this location.",
            )


class AccessResolver(Protocol):
    async def resolve(self, user: AuthenticatedUser) -> AccessScope: ...


class SupabaseAccessResolver:
    """Resolve one default workspace and current location grants on every request."""

    def __init__(self, store: CanonicalStore) -> None:
        self._store = store

    async def resolve(self, user: AuthenticatedUser) -> AccessScope:
        profiles = await self._store.select_rows(
            "app_user_profiles",
            columns="user_id,system_role",
            filters={"user_id": f"eq.{user.user_id}"},
            limit=1,
        )
        memberships = await self._store.select_rows(
            "workspace_memberships",
            columns="workspace_id,role,status,is_default",
            filters={
                "user_id": f"eq.{user.user_id}",
                "status": "eq.active",
                "is_default": "eq.true",
            },
            limit=2,
        )
        if len(profiles) != 1 or len(memberships) != 1:
            raise ForbiddenError(
                "workspace_access_unavailable",
                "Your private planning workspace is not available. "
                "Ask an administrator to restore access.",
            )

        system_role = str(profiles[0].get("system_role", "user"))
        workspace_role = str(memberships[0].get("role", "viewer"))
        if system_role not in {"user", "system_admin"} or workspace_role not in {
            "owner",
            "admin",
            "planner",
            "viewer",
        }:
            raise RepositoryUnavailableError(
                "The workspace authorization record contains an unsupported role."
            )

        workspace_id = str(memberships[0]["workspace_id"])
        if workspace_role in {"owner", "admin"} or system_role == "system_admin":
            readable: frozenset[str] | None = None
            writable: frozenset[str] | None = None
        else:
            grants = await self._store.select_rows(
                "user_location_access",
                columns="location_id,access_level",
                filters={
                    "workspace_id": f"eq.{workspace_id}",
                    "user_id": f"eq.{user.user_id}",
                },
            )
            readable = frozenset(str(row["location_id"]) for row in grants)
            writable = frozenset(
                str(row["location_id"])
                for row in grants
                if row.get("access_level") == "planner"
            )

        return AccessScope(
            user_id=user.user_id,
            email=user.email,
            workspace_id=workspace_id,
            workspace_role=cast(WorkspaceRole, workspace_role),
            system_role=cast(SystemRole, system_role),
            readable_location_ids=readable,
            writable_location_ids=writable,
        )


def _in_filter(values: frozenset[str]) -> str:
    quoted = []
    for value in sorted(values):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        quoted.append(f'"{escaped}"')
    return f"in.({','.join(quoted)})"


def _eq_filter_value(expression: str | None) -> str | None:
    if expression is None or not expression.startswith("eq."):
        return None
    return expression[3:]


class WorkspaceScopedStore:
    """Fail-closed workspace/location boundary around the server-authority store."""

    def __init__(self, store: CanonicalStore, scope: AccessScope) -> None:
        self._store = store
        self._scope = scope

    async def schema_state(self) -> SchemaState:
        return await self._store.schema_state()

    def _scoped_filters(
        self,
        table: str,
        filters: dict[str, str] | None,
        *,
        require_write: bool = False,
    ) -> dict[str, str] | None:
        if table not in WORKSPACE_SCOPED_TABLES:
            raise ValueError(f"table {table!r} is not available through a workspace scope")
        scoped = dict(filters or {})
        requested_workspace = _eq_filter_value(scoped.get("workspace_id"))
        if requested_workspace is not None and requested_workspace != self._scope.workspace_id:
            raise ForbiddenError()
        scoped["workspace_id"] = f"eq.{self._scope.workspace_id}"

        if table in LOCATION_SCOPED_TABLES:
            requested_location = _eq_filter_value(scoped.get("location_id"))
            if require_write and requested_location is None:
                raise ForbiddenError(
                    "location_write_scope_required",
                    "A single permitted location is required for this write.",
                )
            if require_write:
                assert requested_location is not None
                self._scope.require_location_write(requested_location)
            elif self._scope.readable_location_ids is not None:
                if requested_location is not None:
                    self._scope.require_location_read(requested_location)
                elif not self._scope.readable_location_ids:
                    return None
                else:
                    scoped["location_id"] = _in_filter(
                        self._scope.readable_location_ids
                    )
        return scoped

    async def select_rows(
        self,
        table: str,
        *,
        columns: str = "*",
        filters: dict[str, str] | None = None,
        order: str | None = None,
        limit: int | None = None,
    ) -> list[JsonObject]:
        scoped_filters = self._scoped_filters(table, filters)
        if scoped_filters is None:
            return []
        if table == "source_imports" and self._scope.readable_location_ids is not None:
            if self._scope.readable_location_ids:
                scoped_filters["or"] = (
                    "(location_id.is.null,location_id."
                    f"{_in_filter(self._scope.readable_location_ids)})"
                )
            else:
                scoped_filters["location_id"] = "is.null"
        rows = await self._store.select_rows(
            table,
            columns=columns,
            filters=scoped_filters,
            order=order,
            limit=limit,
        )
        if table == "source_imports" and self._scope.readable_location_ids is not None:
            rows = [
                row
                for row in rows
                if row.get("location_id") is None
                or str(row["location_id"]) in self._scope.readable_location_ids
            ]
        return rows

    def _scope_row(self, row: JsonObject) -> JsonObject:
        existing = row.get("workspace_id")
        if existing is not None and str(existing) != self._scope.workspace_id:
            raise ForbiddenError()
        return {**row, "workspace_id": self._scope.workspace_id}

    def _scope_writable_row(self, table: str, row: JsonObject) -> JsonObject:
        scoped = self._scope_row(row)
        if table in LOCATION_SCOPED_TABLES:
            location_id = scoped.get("location_id")
            if location_id is None:
                raise ForbiddenError(
                    "location_write_scope_required",
                    "A permitted location is required for this write.",
                )
            self._scope.require_location_write(str(location_id))
        return scoped

    def _require_audit_actor(self, row: JsonObject, resource: str) -> None:
        if str(row.get("created_by")) != self._scope.user_id:
            raise ForbiddenError(
                "audit_actor_mismatch",
                f"The {resource} audit actor must match the authenticated user.",
            )

    def _authorize_source_import_row(self, row: JsonObject) -> str:
        self._require_audit_actor(row, "source import")
        dataset_type = str(row.get("dataset_type"))
        if dataset_type in {"master_data", "planning_input"}:
            self._scope.require_workspace_admin()
        elif dataset_type in {"stock", "purchase_orders"}:
            location_id = row.get("location_id")
            if location_id is None:
                raise ForbiddenError(
                    "location_write_scope_required",
                    "A permitted location is required for this import.",
                )
            self._scope.require_location_write(str(location_id))
        else:
            raise ValueError("source-import row has an unsupported dataset type")
        return dataset_type

    async def insert_rows(self, table: str, rows: list[JsonObject]) -> list[JsonObject]:
        if table not in WORKSPACE_SCOPED_TABLES:
            raise ValueError(f"table {table!r} is not available through a workspace scope")
        if table == "source_imports":
            for row in rows:
                self._authorize_source_import_row(row)
        elif table == "master_data_versions":
            self._scope.require_workspace_admin()
            for row in rows:
                self._require_audit_actor(row, "master version")
        elif table == "planning_runs":
            for row in rows:
                self._require_audit_actor(row, "planning run")
        return await self._store.insert_rows(
            table,
            [self._scope_writable_row(table, row) for row in rows],
        )

    async def update_rows(
        self,
        table: str,
        values: JsonObject,
        *,
        filters: dict[str, str],
    ) -> list[JsonObject]:
        scoped_filters = self._scoped_filters(table, filters, require_write=True)
        if scoped_filters is None:
            return []
        return await self._store.update_rows(
            table,
            self._scope_row(values),
            filters=scoped_filters,
        )

    async def delete_rows(self, table: str, *, filters: dict[str, str]) -> None:
        scoped_filters = self._scoped_filters(table, filters, require_write=True)
        if scoped_filters is None:
            return
        await self._store.delete_rows(table, filters=scoped_filters)

    async def activate_master_version(
        self,
        *,
        version_id: str,
        actor_id: str,
        environment: str,
    ) -> JsonObject:
        if actor_id != self._scope.user_id:
            raise ForbiddenError()
        self._scope.require_workspace_admin()
        return await self._store.activate_master_version(
            version_id=version_id,
            actor_id=actor_id,
            environment=environment,
        )

    def _scope_payload_rows(self, payload: JsonObject) -> JsonObject:
        scoped: JsonObject = {}
        for key, value in payload.items():
            if isinstance(value, dict):
                scoped[key] = self._scope_row(value)
            elif isinstance(value, list):
                scoped[key] = [
                    self._scope_row(row) if isinstance(row, dict) else row
                    for row in value
                ]
            else:
                scoped[key] = value
        return scoped

    async def persist_master_import(self, payload: JsonObject) -> JsonObject:
        self._scope.require_workspace_admin()
        source_import = payload.get("source_import")
        master_version = payload.get("master_data_version")
        if not isinstance(source_import, dict) or not isinstance(master_version, dict):
            raise ValueError("master-import payload is missing root metadata")
        self._authorize_source_import_row(source_import)
        self._require_audit_actor(master_version, "master version")
        return await self._store.persist_master_import(self._scope_payload_rows(payload))

    async def persist_source_import(self, payload: JsonObject) -> JsonObject:
        source_import = payload.get("source_import")
        if not isinstance(source_import, dict):
            raise ValueError("source-import payload is missing source metadata")
        dataset_type = self._authorize_source_import_row(source_import)
        if dataset_type in {"stock", "purchase_orders"}:
            location_id = source_import.get("location_id")
            assert location_id is not None
            child_key = (
                "inventory_snapshots"
                if dataset_type == "stock"
                else "purchase_order_lines"
            )
            child_rows = payload.get(child_key, [])
            if not isinstance(child_rows, list) or any(
                not isinstance(row, dict)
                or str(row.get("location_id")) != str(location_id)
                for row in child_rows
            ):
                raise ForbiddenError(
                    "source_location_mismatch",
                    "Every imported row must belong to the permitted source location.",
                )
        return await self._store.persist_source_import(self._scope_payload_rows(payload))

    def _namespace_run_payload(self, payload: JsonObject) -> JsonObject:
        scoped = self._scope_payload_rows(payload)
        run = scoped.get("run")
        if not isinstance(run, dict):
            raise ValueError("planning payload is missing run metadata")
        original_run_id = str(run["run_id"])
        suffix = self._scope.workspace_id.replace("-", "")
        namespaced_run_id = f"{original_run_id}-ws{suffix}"
        run["run_id"] = namespaced_run_id

        line_ids: dict[str, str] = {}
        lines = scoped.get("planning_lines", [])
        if isinstance(lines, list):
            for row in lines:
                if not isinstance(row, dict):
                    continue
                old_line_id = str(row["planning_line_id"])
                new_line_id = f"{old_line_id}-ws{suffix}"
                line_ids[old_line_id] = new_line_id
                row["planning_line_id"] = new_line_id

        for key in (
            "run_inputs",
            "planning_lines",
            "recommendations",
            "exceptions",
            "netting_results",
            "projection_days",
        ):
            rows = scoped.get(key, [])
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if "run_id" in row:
                    row["run_id"] = namespaced_run_id
                if row.get("planning_line_id") in line_ids:
                    row["planning_line_id"] = line_ids[str(row["planning_line_id"])]
                if row.get("record_ref") in line_ids:
                    row["record_ref"] = line_ids[str(row["record_ref"])]
                for identifier in ("recommendation_id", "exception_id"):
                    if identifier in row:
                        row[identifier] = f"{row[identifier]}-ws{suffix}"
        return scoped

    async def persist_planning_run(self, payload: JsonObject) -> str:
        run = payload.get("run")
        if not isinstance(run, dict) or run.get("location_id") is None:
            raise ValueError("planning payload is missing run location metadata")
        self._require_audit_actor(run, "planning run")
        run_location_id = str(run["location_id"])
        self._scope.require_location_write(run_location_id)
        for key in (
            "planning_lines",
            "recommendations",
            "netting_results",
            "projection_days",
        ):
            rows = payload.get(key, [])
            if not isinstance(rows, list) or any(
                not isinstance(row, dict)
                or str(row.get("location_id")) != run_location_id
                for row in rows
            ):
                raise ForbiddenError(
                    "run_location_mismatch",
                    "Every planning result row must belong to the permitted run location.",
                )
        return await self._store.persist_planning_run(
            self._namespace_run_payload(payload)
        )
