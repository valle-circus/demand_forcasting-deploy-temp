from __future__ import annotations

import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from apps.api.supply_planning_api.auth import AuthenticatedUser
from apps.api.supply_planning_api.config import Settings
from apps.api.supply_planning_api.errors import ConflictError
from apps.api.supply_planning_api.repository import CanonicalStore, JsonObject, SchemaState
from apps.api.supply_planning_api.schemas import CreatePlanningRunRequest
from apps.api.supply_planning_api.services import (
    LoadedLocationMaster,
    LoadedMaster,
    PlanningBackend,
    SelectedSources,
)
from supply_planning.adapters.canonical_csv import CanonicalInputBundle, load_canonical_bundle
from supply_planning.domain.models import (
    DeliveryCoverageRule,
    InputSourceStatus,
    Item,
    ItemPlanningPolicy,
    ItemType,
    Location,
    Provenance,
    RunMode,
    ShelfLifeAnchor,
    StockQuantityUnit,
    StorageClass,
)

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
        self.select_calls: list[tuple[str, dict[str, str]]] = []

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
        del columns
        self.select_calls.append((table, dict(filters or {})))
        rows = [dict(row) for row in self.tables.get(table, [])]
        for key, expression in (filters or {}).items():
            if expression.startswith("eq."):
                expected_value = expression[3:]
                rows = [
                    row for row in rows if str(row.get(key)) == expected_value
                ]
            elif expression.startswith("in.(") and expression.endswith(")"):
                expected_values = {
                    value.strip().strip('"')
                    for value in expression[4:-1].split(",")
                }
                rows = [
                    row for row in rows if str(row.get(key)) in expected_values
                ]
            elif expression == "not.is.null":
                rows = [row for row in rows if row.get(key) is not None]
            else:
                raise AssertionError(f"unsupported test filter {key}={expression}")
        for clause in reversed((order or "").split(",")):
            if not clause:
                continue
            field, direction = clause.split(".", maxsplit=1)
            rows.sort(
                key=lambda row: str(row.get(field, "")),
                reverse=direction == "desc",
            )
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

    async def _load_master(self, version_id: str | None = None) -> LoadedMaster:
        if version_id is not None:
            self.assert_master_version(version_id)
        return self._sources.master

    @staticmethod
    def assert_master_version(version_id: str) -> None:
        if version_id != MASTER_VERSION_ID:
            raise AssertionError(f"unexpected master version {version_id}")


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

    async def _load_location_master(
        self, version_id: str | None = None
    ) -> LoadedLocationMaster:
        del version_id
        return LoadedLocationMaster(
            version=self._master_fixture.version,
            locations=self._master_fixture.locations,
        )

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

    async def _latest_planning_imports_for_locations(
        self, location_ids: tuple[str, ...]
    ) -> dict[str, JsonObject]:
        return {location_id: self.planning_import for location_id in location_ids}

    async def _latest_location_imports(
        self, location_ids: tuple[str, ...]
    ) -> dict[tuple[str, str], JsonObject]:
        return {
            (dataset_type, location_id): source
            for location_id in location_ids
            for dataset_type, source in (
                ("stock", self.stock_import),
                ("purchase_orders", self.po_import),
            )
        }

    async def _latest_runs_for_locations(
        self, location_ids: tuple[str, ...]
    ) -> dict[str, JsonObject]:
        return {
            location_id: {
                "run_id": "run-currentness",
                "location_id": location_id,
                "master_data_version_id": MASTER_VERSION_ID,
            }
            for location_id in location_ids
        }


class _OverviewBackend(PlanningBackend):
    async def _load_location_master(
        self, version_id: str | None = None
    ) -> LoadedLocationMaster:
        del version_id
        return LoadedLocationMaster(
            version={"id": MASTER_VERSION_ID},
            locations=(Location("LOC_A", "Location A", "Europe/Berlin"),),
        )

    async def list_locations(self) -> JsonObject:
        return {
            "locations": [
                {
                    "location_id": "LOC_A",
                    "location_name": "Location A",
                    "timezone": "Europe/Berlin",
                    "active": True,
                }
            ]
        }

    async def planning_status(self, location_id: str) -> JsonObject:
        return {
            "location_id": location_id,
            "ready": True,
            "blockers": [],
            "sources": {
                "master_data_version": {"id": MASTER_VERSION_ID},
                "planning_input": {"id": PLANNING_IMPORT_ID},
                "stock": {"id": STOCK_IMPORT_ID},
                "purchase_orders": None,
            },
            "latest_run": {
                "run_id": "run-risk-contract",
                "created_at": "2026-08-30T08:00:00+00:00",
            },
            "latest_run_is_current": True,
        }

    async def _planning_statuses(
        self,
        location_ids: tuple[str, ...],
        *,
        master: LoadedMaster | LoadedLocationMaster | None,
        master_blocker: str | None = None,
    ) -> list[JsonObject]:
        del master, master_blocker
        return [await self.planning_status(location_id) for location_id in location_ids]


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


def _overview_backend(location_count: int) -> tuple[PlanningBackend, _RunStore]:
    settings = Settings.model_validate(
        {"APP_ENV": "test", "CORS_ORIGINS": "http://localhost:5173"}
    )
    store = _RunStore()
    location_ids = tuple(f"LOC_{index}" for index in range(location_count))
    store.tables["master_data_versions"] = [
        {
            "id": MASTER_VERSION_ID,
            "environment": "test",
            "status": "active",
        }
    ]
    store.tables["locations"] = [
        {
            "version_id": MASTER_VERSION_ID,
            "location_id": location_id,
            "location_name": f"Location {location_id}",
            "timezone": "Europe/Berlin",
            "active": True,
        }
        for location_id in location_ids
    ]
    store.tables["source_imports"] = [
        {
            "id": PLANNING_IMPORT_ID,
            "dataset_type": "planning_input",
            "location_id": None,
            "status": "accepted",
            "created_at": "2026-09-03T08:00:00+00:00",
            "metadata": {"location_ids": list(location_ids)},
        },
        *[
            {
                "id": f"stock-{location_id}",
                "dataset_type": "stock",
                "location_id": location_id,
                "status": "accepted",
                "created_at": "2026-09-03T09:00:00+00:00",
            }
            for location_id in location_ids
        ],
        *[
            {
                "id": f"po-{location_id}",
                "dataset_type": "purchase_orders",
                "location_id": location_id,
                "status": "accepted",
                "created_at": "2026-09-03T09:00:00+00:00",
            }
            for location_id in location_ids
        ],
    ]
    store.tables["planning_runs"] = [
        {
            "run_id": f"run-{location_id}",
            "location_id": location_id,
            "master_data_version_id": MASTER_VERSION_ID,
            "created_at": "2026-09-03T10:00:00+00:00",
        }
        for location_id in location_ids
    ]
    store.tables["planning_run_inputs"] = [
        {
            "run_id": f"run-{location_id}",
            "source_import_id": source_import_id,
        }
        for location_id in location_ids
        for source_import_id in (
            PLANNING_IMPORT_ID,
            f"stock-{location_id}",
            f"po-{location_id}",
        )
    ]
    store.tables["purchase_order_lines"] = [
        {
            "po_line_id": f"po-line-{location_id}",
            "import_id": f"po-{location_id}",
            "derived_status": "open",
        }
        for location_id in location_ids
    ]
    return PlanningBackend(cast(CanonicalStore, store), settings), store


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
        persisted_lines = store.persisted_payload["planning_lines"]
        if persisted_lines:
            self.assertIn("candidate_expiry_date", persisted_lines[0])
            self.assertIn(
                "projected_candidate_residual_at_expiry_g",
                persisted_lines[0],
            )
            self.assertIn("constraint_status", persisted_lines[0])
        persisted_netting = store.persisted_payload["netting_results"][0]
        self.assertIn("actionable_risk_status", persisted_netting)
        self.assertIn("risk_horizon_end_date", persisted_netting)
        self.assertIn("first_stockout_within_horizon_date", persisted_netting)
        self.assertEqual(persisted_netting["coverage_contract_version"], 1)
        self.assertIn("on_hand_coverage_days", persisted_netting)
        self.assertIn("with_open_po_coverage_days", persisted_netting)
        self.assertIn("with_proposal_coverage_days", persisted_netting)
        self.assertIn("protection_horizon_days", persisted_netting)
        self.assertEqual(
            persisted_netting["with_open_po_coverage_days"],
            persisted_netting["on_hand_coverage_days"]
            + persisted_netting["open_po_coverage_extension_days"],
        )
        self.assertEqual(
            persisted_netting["with_proposal_coverage_days"],
            persisted_netting["with_open_po_coverage_days"]
            + persisted_netting["proposal_coverage_extension_days"],
        )
        self.assertIn(
            persisted_netting["open_po_coverage_extension_status"],
            {"exact", "lower_bound", "not_observable"},
        )
        self.assertIn(
            persisted_netting["proposal_coverage_extension_status"],
            {"exact", "lower_bound", "not_observable"},
        )
        self.assertEqual(store.persisted_payload["run"]["schema_version"], 3)
        self.assertEqual(
            result["explanation_context"]["calculation_owner"],
            "python_backend",
        )
        self.assertEqual(
            result["explanation_context"]["field_lineage"]["gross_requirement_g"],
            ["forecast_daily", "menu_calendar", "bom_lines"],
        )
        self.assertEqual(result["coverage_context"]["contract_version"], 1)
        self.assertTrue(result["coverage_context"]["available_for_all_items"])
        self.assertFalse(result["coverage_context"]["requires_fresh_schema_v3_run"])
        self.assertEqual(
            result["coverage_context"]["unit"],
            "continuous_calendar_days",
        )
        self.assertTrue(
            result["coverage_context"]["forecast_limited_values_are_lower_bounds"]
        )
        self.assertTrue(result["proposal_only"])

    async def test_line_explanation_exposes_exact_versioned_policy_context(self) -> None:
        settings = Settings.model_validate(
            {"APP_ENV": "test", "CORS_ORIGINS": "http://localhost:5173"}
        )
        item = Item(
            "ITEM_A",
            "Item A",
            StorageClass.RT,
            Decimal("1000"),
            shelf_life_days=30,
            min_safety_days=Decimal("2"),
            max_cover_days=Decimal("14"),
        )
        policy = ItemPlanningPolicy(
            "ITEM_A",
            ItemType.INGREDIENT,
            "Transgourmet",
            "TRANSGOURMET",
            "TRANSGOURMET",
            None,
            None,
            Decimal("1"),
            "PACK",
            StockQuantityUnit.PACK,
            None,
            None,
            3,
            ShelfLifeAnchor.RECEIPT_DATE,
            Decimal("1"),
            Decimal("1"),
            Decimal("1"),
            "SOURCE_VALUE",
        )
        rule = DeliveryCoverageRule(
            "RULE",
            "LOC_A",
            "TRANSGOURMET",
            StorageClass.RT,
            None,
            (),
            None,
            7,
            AS_OF.date(),
            None,
            True,
            "SOURCE_VALUE",
        )
        backend = _StatusBackend(
            cast(CanonicalStore, _RunStore()),
            settings,
            LoadedMaster(
                version={"id": MASTER_VERSION_ID},
                locations=(Location("LOC_A", "Location A", "Europe/Berlin"),),
                items=(item,),
                policies=(policy,),
                rules=(rule,),
            ),
        )

        explanations = await backend._planning_line_explanations(
            run={"master_data_version_id": MASTER_VERSION_ID},
            lines=[
                {
                    "planning_line_id": "LINE-EXPLAIN",
                    "item_id": item.item_id,
                    "schedule_rule_id": rule.delivery_rule_id,
                    "shelf_life_cap_basis": "policy_approximation",
                    "forecast_through_expiry": True,
                    "forecast_through_max_cover": True,
                }
            ],
        )

        explanation = explanations[0]
        self.assertEqual(explanation["planning_line_id"], "LINE-EXPLAIN")
        self.assertEqual(explanation["item"]["item_name"], item.item_name)
        self.assertEqual(
            explanation["planning_policy"]["lead_time_calendar_days"],
            policy.lead_time_calendar_days,
        )
        self.assertEqual(
            explanation["delivery_rule"]["review_period_days"],
            rule.review_period_days,
        )
        self.assertFalse(
            explanation["evidence_scope"]["exact_candidate_lot_expiry"]
        )
        self.assertFalse(
            explanation["evidence_scope"][
                "existing_inventory_lot_expiry_available"
            ]
        )

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

    async def test_run_summary_does_not_count_future_replan_as_current_risk(self) -> None:
        settings = Settings.model_validate(
            {"APP_ENV": "test", "CORS_ORIGINS": "http://localhost:5173"}
        )
        store = _RunStore()
        store.tables.update(
            {
                "planning_runs": [{"run_id": "run-risk-contract"}],
                "planning_run_inputs": [],
                "planning_lines": [],
                "planning_recommendations": [],
                "planning_exceptions": [],
                "planning_projection_days": [],
                "planning_netting_results": [
                    {
                        "run_id": "run-risk-contract",
                        "item_id": "FUTURE",
                        "first_stockout_date": "2026-09-20",
                        "first_stockout_within_horizon_date": None,
                        "actionable_risk_status": "covered",
                        "coverage_contract_version": 1,
                        "risk_horizon_end_date": "2026-09-08",
                        "risk_horizon_fully_observed": True,
                        "with_open_po_first_uncovered_date": "2026-09-20",
                    },
                    {
                        "run_id": "run-risk-contract",
                        "item_id": "NOW",
                        "first_stockout_date": "2026-09-02",
                        "first_stockout_within_horizon_date": "2026-09-02",
                        "actionable_risk_status": "at_risk",
                        "coverage_contract_version": 1,
                        "risk_horizon_end_date": "2026-09-08",
                        "risk_horizon_fully_observed": True,
                        "with_open_po_first_uncovered_date": "2026-09-02",
                    },
                    {
                        "run_id": "run-risk-contract",
                        "item_id": "SOLVED_BY_PROPOSAL",
                        "first_stockout_date": None,
                        "first_stockout_within_horizon_date": None,
                        "actionable_risk_status": "covered",
                        "coverage_contract_version": 1,
                        "risk_horizon_end_date": "2026-09-08",
                        "risk_horizon_fully_observed": True,
                        "with_open_po_first_uncovered_date": "2026-09-04",
                    },
                    {
                        "run_id": "run-risk-contract",
                        "item_id": "UNKNOWN",
                        "first_stockout_date": None,
                        "first_stockout_within_horizon_date": None,
                        "actionable_risk_status": "not_evaluated",
                        "coverage_contract_version": 1,
                        "risk_horizon_end_date": "2026-09-08",
                        "risk_horizon_fully_observed": False,
                        "with_open_po_first_uncovered_date": None,
                    },
                ],
            }
        )
        backend = PlanningBackend(cast(CanonicalStore, store), settings)

        result = await backend.get_planning_run("run-risk-contract")

        self.assertEqual(result["summary"]["items_at_risk"], 1)
        self.assertEqual(result["summary"]["items_requiring_order"], 2)
        self.assertEqual(result["summary"]["items_risk_not_evaluated"], 1)
        self.assertEqual(result["summary"]["future_stockout_items"], 1)
        statuses = {
            row["item_id"]: row["order_requirement_status"]
            for row in result["netting_results"]
        }
        self.assertEqual(statuses["SOLVED_BY_PROPOSAL"], "needs_order")
        self.assertEqual(statuses["FUTURE"], "covered_without_order")
        self.assertEqual(statuses["UNKNOWN"], "not_evaluated")
        self.assertTrue(result["coverage_context"]["available_for_all_items"])
        self.assertFalse(result["coverage_context"]["requires_fresh_schema_v3_run"])

    async def test_legacy_run_does_not_invent_an_order_requirement_status(self) -> None:
        settings = Settings.model_validate(
            {"APP_ENV": "test", "CORS_ORIGINS": "http://localhost:5173"}
        )
        store = _RunStore()
        store.tables.update(
            {
                "planning_runs": [{"run_id": "legacy-run"}],
                "planning_run_inputs": [],
                "planning_lines": [],
                "planning_recommendations": [],
                "planning_exceptions": [],
                "planning_projection_days": [],
                "planning_netting_results": [
                    {
                        "run_id": "legacy-run",
                        "item_id": "LEGACY",
                        "actionable_risk_status": "covered",
                        "coverage_contract_version": None,
                        "risk_horizon_end_date": "2026-09-08",
                        "risk_horizon_fully_observed": True,
                        "with_open_po_first_uncovered_date": None,
                        "first_stockout_date": None,
                    }
                ],
            }
        )
        backend = PlanningBackend(cast(CanonicalStore, store), settings)

        result = await backend.get_planning_run("legacy-run")

        self.assertEqual(result["summary"]["items_requiring_order"], 0)
        self.assertEqual(result["summary"]["items_risk_not_evaluated"], 1)
        self.assertEqual(
            result["netting_results"][0]["order_requirement_status"],
            "not_evaluated",
        )

    async def test_overview_separates_order_need_from_post_proposal_risk(self) -> None:
        settings = Settings.model_validate(
            {"APP_ENV": "test", "CORS_ORIGINS": "http://localhost:5173"}
        )
        store = _RunStore()
        store.tables["planning_netting_results"] = [
            {
                "run_id": "run-risk-contract",
                "item_id": "FUTURE",
                "first_stockout_date": "2026-09-20",
                "actionable_risk_status": "covered",
                "coverage_contract_version": 1,
                "risk_horizon_end_date": "2026-09-08",
                "risk_horizon_fully_observed": True,
                "with_open_po_first_uncovered_date": "2026-09-20",
            },
            {
                "run_id": "run-risk-contract",
                "item_id": "NOW",
                "first_stockout_date": "2026-09-02",
                "first_stockout_within_horizon_date": "2026-09-02",
                "actionable_risk_status": "at_risk",
                "coverage_contract_version": 1,
                "risk_horizon_end_date": "2026-09-08",
                "risk_horizon_fully_observed": True,
                "with_open_po_first_uncovered_date": "2026-09-02",
            },
            {
                "run_id": "run-risk-contract",
                "item_id": "SOLVED_BY_PROPOSAL",
                "first_stockout_date": None,
                "first_stockout_within_horizon_date": None,
                "actionable_risk_status": "covered",
                "coverage_contract_version": 1,
                "risk_horizon_end_date": "2026-09-08",
                "risk_horizon_fully_observed": True,
                "with_open_po_first_uncovered_date": "2026-09-04",
            },
            {
                "run_id": "run-risk-contract",
                "item_id": "UNKNOWN",
                "first_stockout_date": None,
                "actionable_risk_status": "not_evaluated",
                "coverage_contract_version": 1,
                "risk_horizon_end_date": "2026-09-08",
                "risk_horizon_fully_observed": False,
                "with_open_po_first_uncovered_date": None,
            },
        ]
        backend = _OverviewBackend(cast(CanonicalStore, store), settings)

        result = await backend.overview()

        self.assertEqual(result["kpis"]["items_at_risk"], 1)
        self.assertEqual(result["kpis"]["items_requiring_order"], 2)
        self.assertEqual(result["kpis"]["items_risk_not_evaluated"], 1)
        self.assertEqual(result["kpis"]["locations_at_risk"], 1)
        self.assertEqual(result["kpis"]["locations_requiring_order"], 1)
        self.assertEqual(result["locations"][0]["items_at_risk"], 1)
        self.assertEqual(result["locations"][0]["items_requiring_order"], 2)
        self.assertEqual(result["locations"][0]["items_risk_not_evaluated"], 1)
        self.assertEqual(result["locations"][0]["location_name"], "Location A")
        self.assertEqual(result["locations"][0]["timezone"], "Europe/Berlin")
        self.assertEqual(result["locations"][0]["earliest_risk_date"], "2026-09-02")
        self.assertEqual(
            result["locations"][0]["earliest_order_required_date"],
            "2026-09-02",
        )
        self.assertEqual(
            result["locations"][0]["sources"]["stock"]["id"], STOCK_IMPORT_ID
        )

    async def test_overview_query_count_is_constant_across_location_count(self) -> None:
        two_location_backend, two_location_store = _overview_backend(2)
        six_location_backend, six_location_store = _overview_backend(6)

        two_location_result = await two_location_backend.overview()
        six_location_result = await six_location_backend.overview()

        self.assertEqual(10, len(two_location_store.select_calls))
        self.assertEqual(10, len(six_location_store.select_calls))
        self.assertEqual(2, two_location_result["kpis"]["locations_total"])
        self.assertEqual(6, six_location_result["kpis"]["locations_total"])
        self.assertEqual(2, two_location_result["kpis"]["open_purchase_order_lines"])
        self.assertEqual(6, six_location_result["kpis"]["open_purchase_order_lines"])

    async def test_location_view_removes_the_browser_status_to_run_waterfall(self) -> None:
        backend, store = _overview_backend(1)

        result = await backend.location_view("LOC_0")

        self.assertEqual(16, len(store.select_calls))
        self.assertEqual("LOC_0", result["status"]["location_id"])
        self.assertEqual("run-LOC_0", result["planning_run"]["run"]["run_id"])
        self.assertIsNotNone(result["inventory"])
        self.assertTrue(result["proposal_only"])

    async def test_planning_import_batch_falls_back_for_legacy_metadata(self) -> None:
        settings = Settings.model_validate(
            {"APP_ENV": "test", "CORS_ORIGINS": "http://localhost:5173"}
        )
        store = _RunStore()
        store.tables["source_imports"] = [
            {
                "id": PLANNING_IMPORT_ID,
                "dataset_type": "planning_input",
                "status": "accepted",
                "created_at": "2026-09-03T08:00:00+00:00",
                "metadata": {},
            }
        ]
        store.tables["forecast_daily"] = [
            {"import_id": PLANNING_IMPORT_ID, "location_id": "LOC_A"}
        ]
        backend = PlanningBackend(cast(CanonicalStore, store), settings)

        result = await backend._latest_planning_imports_for_locations(("LOC_A",))

        self.assertEqual(PLANNING_IMPORT_ID, result["LOC_A"]["id"])
        self.assertEqual(
            ["source_imports", "forecast_daily"],
            [table for table, _filters in store.select_calls],
        )


if __name__ == "__main__":
    unittest.main()
