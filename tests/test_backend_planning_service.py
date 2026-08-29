from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from apps.api.supply_planning_api.auth import AuthenticatedUser
from apps.api.supply_planning_api.config import Settings
from apps.api.supply_planning_api.errors import ConflictError
from apps.api.supply_planning_api.repository import CanonicalStore, JsonObject, SchemaState
from apps.api.supply_planning_api.schemas import CreatePlanningRunRequest
from apps.api.supply_planning_api.services import (
    LoadedMaster,
    PlanningBackend,
    SelectedSources,
)
from supply_planning.adapters.canonical_csv import CanonicalInputBundle, load_canonical_bundle
from supply_planning.domain.models import InputSourceStatus, Location, Provenance, RunMode

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_improved"
AS_OF = datetime.fromisoformat("2026-08-25T00:00:00+02:00")
MASTER_IMPORT_ID = "00000000-0000-0000-0000-000000000101"
PLANNING_IMPORT_ID = "00000000-0000-0000-0000-000000000102"
STOCK_IMPORT_ID = "00000000-0000-0000-0000-000000000103"
PO_IMPORT_ID = "00000000-0000-0000-0000-000000000104"
MASTER_VERSION_ID = "00000000-0000-0000-0000-000000000201"
USER_ID = "00000000-0000-0000-0000-000000000301"


class _RunStore:
    def __init__(self) -> None:
        self.tables: dict[str, list[JsonObject]] = {}
        self.persisted_payload: JsonObject | None = None

    async def schema_state(self) -> SchemaState:
        return SchemaState(True)

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
        rows = [dict(row) for row in self.tables.get(table, [])]
        for key, expression in (filters or {}).items():
            if expression.startswith("eq."):
                expected = expression[3:]
                rows = [row for row in rows if str(row.get(key)) == expected]
            elif expression == "not.is.null":
                rows = [row for row in rows if row.get(key) is not None]
            else:
                raise AssertionError(f"unsupported test filter {key}={expression}")
        return rows[:limit] if limit is not None else rows

    async def insert_rows(
        self,
        table: str,
        rows: list[JsonObject],
    ) -> list[JsonObject]:
        self.tables.setdefault(table, []).extend(dict(row) for row in rows)
        return rows

    async def update_rows(
        self,
        table: str,
        values: JsonObject,
        *,
        filters: dict[str, str],
    ) -> list[JsonObject]:
        del table, values, filters
        raise AssertionError("not used")

    async def delete_rows(self, table: str, *, filters: dict[str, str]) -> None:
        del table, filters
        raise AssertionError("not used")

    async def activate_master_version(
        self,
        *,
        version_id: str,
        actor_id: str,
        environment: str,
    ) -> JsonObject:
        del version_id, actor_id, environment
        raise AssertionError("not used")

    async def persist_master_import(self, payload: JsonObject) -> JsonObject:
        del payload
        raise AssertionError("not used")

    async def persist_source_import(self, payload: JsonObject) -> JsonObject:
        del payload
        raise AssertionError("not used")

    async def persist_planning_run(self, payload: JsonObject) -> str:
        self.persisted_payload = payload
        self.tables.setdefault("planning_runs", []).append(dict(payload["run"]))
        for payload_key, table in (
            ("run_inputs", "planning_run_inputs"),
            ("planning_lines", "planning_lines"),
            ("recommendations", "planning_recommendations"),
            ("exceptions", "planning_exceptions"),
            ("netting_results", "planning_netting_results"),
            ("projection_days", "planning_projection_days"),
        ):
            raw_rows: Any = payload[payload_key]
            assert isinstance(raw_rows, list)
            self.tables.setdefault(table, []).extend(dict(row) for row in raw_rows)
        return str(payload["run"]["run_id"])


class _FixtureBackend(PlanningBackend):
    def __init__(
        self,
        store: CanonicalStore,
        settings: Settings,
        sources: SelectedSources,
    ) -> None:
        super().__init__(store, settings)
        self._sources = sources

    async def _assemble_sources(
        self,
        request: CreatePlanningRunRequest,
    ) -> SelectedSources:
        if request.location_id != "LOC_A":
            raise AssertionError("unexpected location")
        return self._sources


class _StatusBackend(PlanningBackend):
    def __init__(
        self,
        store: CanonicalStore,
        settings: Settings,
        master: LoadedMaster,
    ) -> None:
        super().__init__(store, settings)
        self._master_fixture = master
        self.planning_import: JsonObject = {"id": PLANNING_IMPORT_ID}
        self.stock_import: JsonObject = {"id": STOCK_IMPORT_ID}
        self.po_import: JsonObject = {"id": PO_IMPORT_ID}

    async def _load_master(self, version_id: str | None = None) -> LoadedMaster:
        del version_id
        return self._master_fixture

    async def _latest_planning_import_for_location(
        self,
        location_id: str,
    ) -> JsonObject | None:
        del location_id
        return self.planning_import

    async def _latest_import(
        self,
        dataset_type: str,
        *,
        location_id: str | None,
    ) -> JsonObject | None:
        del location_id
        return {
            "stock": self.stock_import,
            "purchase_orders": self.po_import,
        }.get(dataset_type)

    async def _latest_run(self, location_id: str) -> JsonObject | None:
        return {
            "run_id": "run-currentness",
            "location_id": location_id,
            "master_data_version_id": MASTER_VERSION_ID,
        }


def _sources() -> SelectedSources:
    fixture = load_canonical_bundle(FIXTURE)
    forecasts = tuple(row for row in fixture.forecasts if row.location_id == "LOC_A")
    menu = tuple(row for row in fixture.menu_entries if row.location_id == "LOC_A")
    snapshots = tuple(
        row for row in fixture.inventory_snapshots if row.location_id == "LOC_A"
    )
    purchase_orders = tuple(
        row for row in fixture.purchase_orders if row.location_id == "LOC_A"
    )
    statuses = (
        InputSourceStatus("forecast_daily", Provenance.MANUAL, len(forecasts), "plan-v1"),
        InputSourceStatus("menu_calendar", Provenance.MANUAL, len(menu), "plan-v1"),
        InputSourceStatus("bom_lines", Provenance.MANUAL, len(fixture.bom_lines), "plan-v1"),
        InputSourceStatus("items", Provenance.MANUAL, len(fixture.items), "master-v1"),
        InputSourceStatus(
            "inventory_snapshots", Provenance.OBSERVED, len(snapshots), "stock-v1"
        ),
        InputSourceStatus(
            "purchase_orders", Provenance.OBSERVED, len(purchase_orders), "po-v1"
        ),
        InputSourceStatus(
            "locations", Provenance.MANUAL, len(fixture.locations), "master-v1"
        ),
        InputSourceStatus(
            "item_policies", Provenance.MANUAL, len(fixture.item_policies), "master-v1"
        ),
        InputSourceStatus(
            "delivery_rules", Provenance.MANUAL, len(fixture.delivery_rules), "master-v1"
        ),
    )
    bundle = CanonicalInputBundle(
        forecasts=forecasts,
        menu_entries=menu,
        bom_lines=fixture.bom_lines,
        items=fixture.items,
        inventory_snapshots=snapshots,
        purchase_orders=purchase_orders,
        source_statuses=statuses,
        locations=fixture.locations,
        item_policies=fixture.item_policies,
        delivery_rules=fixture.delivery_rules,
    )
    master = LoadedMaster(
        version={
            "id": MASTER_VERSION_ID,
            "status": "active",
            "version_label": "master-v1",
            "config_hash": "master-hash",
            "source_import_id": MASTER_IMPORT_ID,
        },
        locations=fixture.locations,
        items=fixture.items,
        policies=fixture.item_policies,
        rules=fixture.delivery_rules,
    )

    def source(import_id: str, version: str, content_hash: str) -> JsonObject:
        return {
            "id": import_id,
            "source_version": version,
            "content_hash": content_hash,
            "validation_issues": [],
        }

    return SelectedSources(
        master=master,
        planning_import=source(PLANNING_IMPORT_ID, "plan-v1", "plan-hash"),
        stock_import=source(STOCK_IMPORT_ID, "stock-v1", "stock-hash"),
        purchase_orders_import=source(PO_IMPORT_ID, "po-v1", "po-hash"),
        bundle=bundle,
    )


class BackendPlanningServiceTests(unittest.IsolatedAsyncioTestCase):
    def _backend(self) -> tuple[_FixtureBackend, _RunStore]:
        settings = Settings.model_validate(
            {"APP_ENV": "test", "CORS_ORIGINS": "http://localhost:5173"}
        )
        store = _RunStore()
        backend = _FixtureBackend(cast(CanonicalStore, store), settings, _sources())
        return backend, store

    async def test_run_is_calculated_and_persisted_as_one_complete_payload(self) -> None:
        backend, store = self._backend()
        request = CreatePlanningRunRequest(
            location_id="LOC_A",
            planning_as_of_at=AS_OF,
            run_mode=RunMode.SCENARIO,
        )
        result = await backend.create_planning_run(
            request,
            AuthenticatedUser(USER_ID, "maintainer@example.test"),
        )

        self.assertEqual("completed", result["run"]["status"])
        self.assertGreater(len(result["netting_results"]), 0)
        self.assertGreater(len(result["projection_days"]), 0)
        assert store.persisted_payload is not None
        self.assertEqual(9, len(store.persisted_payload["run_inputs"]))
        self.assertEqual(
            len(result["projection_days"]),
            len(store.persisted_payload["projection_days"]),
        )
        self.assertTrue(result["proposal_only"])

    async def test_production_mode_is_explicitly_disabled(self) -> None:
        backend, store = self._backend()
        request = CreatePlanningRunRequest(
            location_id="LOC_A",
            planning_as_of_at=AS_OF,
            run_mode=RunMode.PRODUCTION,
        )

        with self.assertRaisesRegex(ConflictError, "Production mode is disabled"):
            await backend.create_planning_run(
                request,
                AuthenticatedUser(USER_ID, "maintainer@example.test"),
            )
        self.assertIsNone(store.persisted_payload)

    async def test_newer_accepted_source_marks_latest_run_stale(self) -> None:
        settings = Settings.model_validate(
            {"APP_ENV": "test", "CORS_ORIGINS": "http://localhost:5173"}
        )
        store = _RunStore()
        store.tables["planning_run_inputs"] = [
            {
                "run_id": "run-currentness",
                "source_import_id": source_id,
            }
            for source_id in (PLANNING_IMPORT_ID, STOCK_IMPORT_ID, PO_IMPORT_ID)
        ]
        backend = _StatusBackend(
            cast(CanonicalStore, store),
            settings,
            LoadedMaster(
                version=_sources().master.version,
                locations=(Location("LOC_A", "Location A", "Europe/Berlin"),),
                items=_sources().master.items,
                policies=_sources().master.policies,
                rules=_sources().master.rules,
            ),
        )

        current = await backend.planning_status("LOC_A")
        backend.stock_import = {"id": "00000000-0000-0000-0000-000000000999"}
        stale = await backend.planning_status("LOC_A")

        self.assertTrue(current["latest_run_is_current"])
        self.assertFalse(stale["latest_run_is_current"])


if __name__ == "__main__":
    unittest.main()
