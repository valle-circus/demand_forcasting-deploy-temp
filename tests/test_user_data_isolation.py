from __future__ import annotations

import csv
import unittest
from copy import deepcopy
from typing import cast

import httpx

from apps.api.supply_planning_api.auth import AuthenticatedUser, IdentityVerifier
from apps.api.supply_planning_api.authorization import (
    LOCATION_SCOPED_TABLES,
    WORKSPACE_SCOPED_TABLES,
    AccessScope,
    SupabaseAccessResolver,
    WorkspaceScopedStore,
)
from apps.api.supply_planning_api.config import Settings
from apps.api.supply_planning_api.errors import ForbiddenError
from apps.api.supply_planning_api.main import create_app
from apps.api.supply_planning_api.repository import CanonicalStore, JsonObject, SchemaState
from apps.api.supply_planning_api.supabase import DependencyState, ReadinessProbe

USER_A = "11111111-1111-1111-1111-111111111111"
USER_B = "22222222-2222-2222-2222-222222222222"
WORKSPACE_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
WORKSPACE_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
IMPORT_A = "33333333-3333-3333-3333-333333333333"
IMPORT_B = "44444444-4444-4444-4444-444444444444"


def _matches(row: JsonObject, filters: dict[str, str] | None) -> bool:
    for field, expression in (filters or {}).items():
        actual = str(row.get(field))
        if expression.startswith("eq.") and actual != expression[3:]:
            return False
        if expression.startswith("in.("):
            accepted = next(csv.reader([expression[4:-1]]))
            if actual not in accepted:
                return False
    return True


class _MemoryStore:
    def __init__(self, rows: dict[str, list[JsonObject]] | None = None) -> None:
        self.rows = deepcopy(rows or {})
        self.calls: list[tuple[str, str, object]] = []
        self.persisted_source: JsonObject | None = None
        self.persisted_run: JsonObject | None = None

    async def schema_state(self) -> SchemaState:
        return SchemaState(ready=True)

    async def select_rows(
        self,
        table: str,
        *,
        columns: str = "*",
        filters: dict[str, str] | None = None,
        order: str | None = None,
        limit: int | None = None,
    ) -> list[JsonObject]:
        del columns, order
        self.calls.append(("select", table, deepcopy(filters)))
        selected = [row for row in self.rows.get(table, []) if _matches(row, filters)]
        return deepcopy(selected[:limit] if limit is not None else selected)

    async def insert_rows(
        self, table: str, rows: list[JsonObject]
    ) -> list[JsonObject]:
        self.calls.append(("insert", table, deepcopy(rows)))
        self.rows.setdefault(table, []).extend(deepcopy(rows))
        return deepcopy(rows)

    async def update_rows(
        self,
        table: str,
        values: JsonObject,
        *,
        filters: dict[str, str],
    ) -> list[JsonObject]:
        self.calls.append(("update", table, deepcopy(filters)))
        updated = []
        for row in self.rows.get(table, []):
            if _matches(row, filters):
                row.update(deepcopy(values))
                updated.append(deepcopy(row))
        return updated

    async def delete_rows(self, table: str, *, filters: dict[str, str]) -> None:
        self.calls.append(("delete", table, deepcopy(filters)))
        self.rows[table] = [
            row for row in self.rows.get(table, []) if not _matches(row, filters)
        ]

    async def activate_master_version(
        self,
        *,
        version_id: str,
        actor_id: str,
        environment: str,
    ) -> JsonObject:
        return {
            "id": version_id,
            "activated_by": actor_id,
            "environment": environment,
        }

    async def persist_master_import(self, payload: JsonObject) -> JsonObject:
        return deepcopy(cast(JsonObject, payload["source_import"]))

    async def persist_source_import(self, payload: JsonObject) -> JsonObject:
        self.persisted_source = deepcopy(payload)
        return deepcopy(cast(JsonObject, payload["source_import"]))

    async def persist_planning_run(self, payload: JsonObject) -> str:
        self.persisted_run = deepcopy(payload)
        run = cast(JsonObject, payload["run"])
        return str(run["run_id"])


class _TokenVerifier:
    async def verify(self, access_token: str) -> AuthenticatedUser:
        if access_token == "token-a":
            return AuthenticatedUser(USER_A, "a@example.test")
        if access_token == "token-b":
            return AuthenticatedUser(USER_B, "b@example.test")
        raise AssertionError("unexpected test token")


class _ReadyProbe:
    async def check(self) -> DependencyState:
        return DependencyState("ready", "Ready.")


class UserDataIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_accounts_cannot_fetch_known_import_run_or_export_ids(
        self,
    ) -> None:
        store = _MemoryStore(
            {
                "app_user_profiles": [
                    {"user_id": USER_A, "system_role": "user"},
                    {"user_id": USER_B, "system_role": "user"},
                ],
                "workspace_memberships": [
                    {
                        "workspace_id": WORKSPACE_A,
                        "user_id": USER_A,
                        "role": "owner",
                        "status": "active",
                        "is_default": "true",
                    },
                    {
                        "workspace_id": WORKSPACE_B,
                        "user_id": USER_B,
                        "role": "owner",
                        "status": "active",
                        "is_default": "true",
                    },
                ],
                "source_imports": [
                    {
                        "id": IMPORT_A,
                        "workspace_id": WORKSPACE_A,
                        "dataset_type": "planning_input",
                        "location_id": None,
                    },
                    {
                        "id": IMPORT_B,
                        "workspace_id": WORKSPACE_B,
                        "dataset_type": "planning_input",
                        "location_id": None,
                    },
                ],
                "planning_runs": [
                    {
                        "run_id": "run-a",
                        "workspace_id": WORKSPACE_A,
                        "location_id": "LOC_A",
                    },
                    {
                        "run_id": "run-b",
                        "workspace_id": WORKSPACE_B,
                        "location_id": "LOC_B",
                    },
                ],
            }
        )
        settings = Settings.model_validate(
            {
                "APP_ENV": "test",
                "CORS_ORIGINS": "http://localhost:5173",
                "SUPABASE_URL": None,
                "SUPABASE_SECRET_KEY": None,
            }
        )
        app = create_app(
            settings=settings,
            supabase_probe=cast(ReadinessProbe, _ReadyProbe()),
            store=cast(CanonicalStore, store),
            identity_verifier=cast(IdentityVerifier, _TokenVerifier()),
            access_resolver=SupabaseAccessResolver(cast(CanonicalStore, store)),
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            own_import = await client.get(
                f"/api/v1/imports/{IMPORT_A}",
                headers={"Authorization": "Bearer token-a"},
            )
            other_import = await client.get(
                f"/api/v1/imports/{IMPORT_A}",
                headers={"Authorization": "Bearer token-b"},
            )
            own_export = await client.get(
                "/api/v1/planning-runs/run-a/export.json",
                headers={"Authorization": "Bearer token-a"},
            )
            other_export = await client.get(
                "/api/v1/planning-runs/run-a/export.json",
                headers={"Authorization": "Bearer token-b"},
            )

        self.assertEqual(200, own_import.status_code)
        self.assertEqual(404, other_import.status_code)
        self.assertEqual(200, own_export.status_code)
        self.assertEqual(404, other_export.status_code)
        self.assertNotIn(WORKSPACE_A, other_import.text)
        self.assertNotIn(WORKSPACE_A, other_export.text)

    async def test_access_resolver_gives_existing_users_distinct_private_workspaces(
        self,
    ) -> None:
        store = _MemoryStore(
            {
                "app_user_profiles": [
                    {"user_id": USER_A, "system_role": "user"},
                    {"user_id": USER_B, "system_role": "user"},
                ],
                "workspace_memberships": [
                    {
                        "workspace_id": WORKSPACE_A,
                        "user_id": USER_A,
                        "role": "owner",
                        "status": "active",
                        "is_default": "true",
                    },
                    {
                        "workspace_id": WORKSPACE_B,
                        "user_id": USER_B,
                        "role": "owner",
                        "status": "active",
                        "is_default": "true",
                    },
                ],
            }
        )
        resolver = SupabaseAccessResolver(cast(CanonicalStore, store))

        scope_a = await resolver.resolve(AuthenticatedUser(USER_A, "a@example.test"))
        scope_b = await resolver.resolve(AuthenticatedUser(USER_B, "b@example.test"))

        self.assertEqual(WORKSPACE_A, scope_a.workspace_id)
        self.assertEqual(WORKSPACE_B, scope_b.workspace_id)
        self.assertNotEqual(scope_a.workspace_id, scope_b.workspace_id)

    async def test_same_underlying_table_is_filtered_to_each_workspace(self) -> None:
        store = _MemoryStore(
            {
                "locations": [
                    {
                        "workspace_id": WORKSPACE_A,
                        "location_id": "LOC_A",
                        "location_name": "Kitchen A",
                    },
                    {
                        "workspace_id": WORKSPACE_B,
                        "location_id": "LOC_B",
                        "location_name": "Kitchen B",
                    },
                ]
            }
        )
        scoped_a = WorkspaceScopedStore(
            cast(CanonicalStore, store),
            AccessScope(USER_A, "a@example.test", WORKSPACE_A, "owner"),
        )
        scoped_b = WorkspaceScopedStore(
            cast(CanonicalStore, store),
            AccessScope(USER_B, "b@example.test", WORKSPACE_B, "owner"),
        )

        rows_a = await scoped_a.select_rows("locations")
        rows_b = await scoped_b.select_rows("locations")

        self.assertEqual(["LOC_A"], [row["location_id"] for row in rows_a])
        self.assertEqual(["LOC_B"], [row["location_id"] for row in rows_b])
        with self.assertRaises(ForbiddenError):
            await scoped_a.select_rows(
                "locations", filters={"workspace_id": f"eq.{WORKSPACE_B}"}
            )

    async def test_every_domain_relation_is_filtered_by_workspace(self) -> None:
        seeded: dict[str, list[JsonObject]] = {}
        for table in WORKSPACE_SCOPED_TABLES:
            location = {"location_id": "LOC"} if table in LOCATION_SCOPED_TABLES else {}
            seeded[table] = [
                {"workspace_id": WORKSPACE_A, "marker": "A", **location},
                {"workspace_id": WORKSPACE_B, "marker": "B", **location},
            ]
        store = _MemoryStore(seeded)
        scoped = WorkspaceScopedStore(
            cast(CanonicalStore, store),
            AccessScope(USER_A, "a@example.test", WORKSPACE_A, "owner"),
        )

        for table in WORKSPACE_SCOPED_TABLES:
            with self.subTest(table=table):
                rows = await scoped.select_rows(table)
                self.assertEqual(["A"], [row["marker"] for row in rows])

    async def test_access_resolution_fails_closed_without_one_default_membership(
        self,
    ) -> None:
        store = _MemoryStore(
            {"app_user_profiles": [{"user_id": USER_A, "system_role": "user"}]}
        )
        resolver = SupabaseAccessResolver(cast(CanonicalStore, store))

        with self.assertRaises(ForbiddenError):
            await resolver.resolve(AuthenticatedUser(USER_A, "a@example.test"))

    async def test_planner_reads_and_writes_only_granted_locations(self) -> None:
        store = _MemoryStore(
            {
                "inventory_snapshots": [
                    {"workspace_id": WORKSPACE_A, "location_id": "LOC_A"},
                    {"workspace_id": WORKSPACE_A, "location_id": "LOC_B"},
                ]
            }
        )
        scoped = WorkspaceScopedStore(
            cast(CanonicalStore, store),
            AccessScope(
                USER_A,
                "a@example.test",
                WORKSPACE_A,
                "planner",
                readable_location_ids=frozenset({"LOC_A"}),
                writable_location_ids=frozenset({"LOC_A"}),
            ),
        )

        visible = await scoped.select_rows("inventory_snapshots")
        self.assertEqual(["LOC_A"], [row["location_id"] for row in visible])
        inserted = await scoped.insert_rows(
            "inventory_snapshots", [{"location_id": "LOC_A", "item_id": "ITEM"}]
        )
        self.assertEqual(WORKSPACE_A, inserted[0]["workspace_id"])
        with self.assertRaises(ForbiddenError):
            await scoped.select_rows(
                "inventory_snapshots", filters={"location_id": "eq.LOC_B"}
            )
        with self.assertRaises(ForbiddenError):
            await scoped.insert_rows(
                "inventory_snapshots", [{"location_id": "LOC_B"}]
            )
        with self.assertRaises(ForbiddenError):
            await scoped.delete_rows(
                "inventory_snapshots", filters={"location_id": "eq.LOC_B"}
            )

    async def test_import_and_run_payloads_are_scoped_and_run_ids_are_namespaced(
        self,
    ) -> None:
        stores = (_MemoryStore(), _MemoryStore())
        scopes = (
            AccessScope(USER_A, "a@example.test", WORKSPACE_A, "owner"),
            AccessScope(USER_B, "b@example.test", WORKSPACE_B, "owner"),
        )
        run_ids: list[str] = []
        for store, scope in zip(stores, scopes, strict=True):
            scoped = WorkspaceScopedStore(cast(CanonicalStore, store), scope)
            await scoped.persist_source_import(
                {
                    "source_import": {
                        "id": "33333333-3333-3333-3333-333333333333",
                        "dataset_type": "stock",
                        "location_id": "LOC_SHARED_NAME",
                        "created_by": scope.user_id,
                    },
                    "inventory_snapshots": [
                        {"location_id": "LOC_SHARED_NAME", "item_id": "ITEM"}
                    ],
                    "final_status": "accepted",
                }
            )
            run_ids.append(
                await scoped.persist_planning_run(
                    {
                        "run": {
                            "run_id": "deterministic-run",
                            "location_id": "LOC_SHARED_NAME",
                            "created_by": scope.user_id,
                        },
                        "planning_lines": [
                            {
                                "planning_line_id": "LINE-1",
                                "run_id": "deterministic-run",
                                "location_id": "LOC_SHARED_NAME",
                            }
                        ],
                        "recommendations": [
                            {
                                "recommendation_id": "REC-1",
                                "planning_line_id": "LINE-1",
                                "run_id": "deterministic-run",
                                "location_id": "LOC_SHARED_NAME",
                            }
                        ],
                    }
                )
            )
            assert store.persisted_source is not None
            source = cast(JsonObject, store.persisted_source["source_import"])
            inventory = cast(list[JsonObject], store.persisted_source["inventory_snapshots"])
            self.assertEqual(scope.workspace_id, source["workspace_id"])
            self.assertEqual(scope.workspace_id, inventory[0]["workspace_id"])
            assert store.persisted_run is not None
            persisted_run = cast(JsonObject, store.persisted_run["run"])
            self.assertEqual(scope.workspace_id, persisted_run["workspace_id"])

        self.assertNotEqual(run_ids[0], run_ids[1])
        self.assertTrue(run_ids[0].endswith("-wsaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"))
        self.assertTrue(run_ids[1].endswith("-wsbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"))

    async def test_planner_cannot_persist_workspace_wide_inputs(self) -> None:
        scoped = WorkspaceScopedStore(
            cast(CanonicalStore, _MemoryStore()),
            AccessScope(
                USER_A,
                "a@example.test",
                WORKSPACE_A,
                "planner",
                readable_location_ids=frozenset({"LOC_A"}),
                writable_location_ids=frozenset({"LOC_A"}),
            ),
        )

        with self.assertRaises(ForbiddenError):
            await scoped.persist_source_import(
                {
                    "source_import": {
                        "dataset_type": "planning_input",
                        "created_by": USER_A,
                    },
                    "final_status": "accepted",
                }
            )
        with self.assertRaises(ForbiddenError):
            await scoped.insert_rows(
                "source_imports",
                [
                    {
                        "dataset_type": "master_data",
                        "created_by": USER_A,
                        "location_id": None,
                    }
                ],
            )

    async def test_cross_location_children_and_spoofed_audit_actor_are_rejected(
        self,
    ) -> None:
        scoped = WorkspaceScopedStore(
            cast(CanonicalStore, _MemoryStore()),
            AccessScope(USER_A, "a@example.test", WORKSPACE_A, "owner"),
        )

        with self.assertRaises(ForbiddenError):
            await scoped.persist_source_import(
                {
                    "source_import": {
                        "dataset_type": "stock",
                        "location_id": "LOC_A",
                        "created_by": USER_B,
                    },
                    "inventory_snapshots": [],
                }
            )
        with self.assertRaises(ForbiddenError):
            await scoped.persist_source_import(
                {
                    "source_import": {
                        "dataset_type": "stock",
                        "location_id": "LOC_A",
                        "created_by": USER_A,
                    },
                    "inventory_snapshots": [{"location_id": "LOC_B"}],
                }
            )
        with self.assertRaises(ForbiddenError):
            await scoped.persist_planning_run(
                {
                    "run": {
                        "run_id": "run",
                        "location_id": "LOC_A",
                        "created_by": USER_A,
                    },
                    "planning_lines": [{"location_id": "LOC_B"}],
                }
            )


if __name__ == "__main__":
    unittest.main()
