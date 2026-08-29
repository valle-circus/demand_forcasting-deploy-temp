from __future__ import annotations

import hashlib
import tempfile
import unittest
from datetime import date
from pathlib import Path
from typing import cast

from openpyxl import Workbook  # type: ignore[import-untyped]

from apps.api.supply_planning_api.auth import AuthenticatedUser
from apps.api.supply_planning_api.config import Settings
from apps.api.supply_planning_api.repository import CanonicalStore, JsonObject, SchemaState
from apps.api.supply_planning_api.services import PlanningBackend
from apps.api.supply_planning_api.uploads import SavedUpload
from supply_planning.adapters.template_xlsx import (
    DELIVERY_HEADERS,
    ITEM_HEADERS,
    LOCATION_HEADERS,
)


class _ImportStore:
    def __init__(self) -> None:
        self.master_payload: JsonObject | None = None

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
        del table, columns, filters, order, limit
        return []

    async def insert_rows(self, table: str, rows: list[JsonObject]) -> list[JsonObject]:
        del table
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
        self.master_payload = payload
        source = dict(payload["source_import"])
        source["status"] = payload["final_status"]
        return source

    async def persist_source_import(self, payload: JsonObject) -> JsonObject:
        del payload
        raise AssertionError("not used")

    async def persist_planning_run(self, payload: JsonObject) -> str:
        del payload
        raise AssertionError("not used")


def _master_workbook(path: Path) -> None:
    workbook = Workbook()
    workbook.remove(workbook.active)
    items = workbook.create_sheet("Items")
    items.append(ITEM_HEADERS)
    items.append(
        (
            "ITEM_1",
            "Test item",
            "INGREDIENT",
            "Transgourmet",
            "TRANSGOURMET",
            "123",
            "Test item",
            "",
            "",
            "",
            "RT",
            1000,
            1,
            "PACK",
            "PACK",
            "UID-1",
            "Test item",
            3,
            30,
            "RECEIPT_DATE",
            2,
            1,
            14,
            1,
            1,
            True,
            "SOURCE_VALUE",
            "test",
        )
    )
    locations = workbook.create_sheet("Locations")
    locations.append(LOCATION_HEADERS)
    locations.append(
        ("LOC_1", "Demo", "Europe/Berlin", True, "SOURCE_VALUE", "test")
    )
    rules = workbook.create_sheet("Delivery_Rules")
    rules.append(DELIVERY_HEADERS)
    rules.append(
        (
            "RULE_1",
            "LOC_1",
            "TRANSGOURMET",
            "RT",
            "",
            "",
            "",
            "",
            "",
            7,
            date(2026, 8, 26),
            "",
            True,
            "SOURCE_VALUE",
            "test",
        )
    )
    workbook.save(path)


class BackendImportServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_master_workbook_becomes_one_atomic_draft_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "master.xlsx"
            _master_workbook(path)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            saved = SavedUpload(path, path.name, path.stat().st_size, digest)
            store = _ImportStore()
            backend = PlanningBackend(
                cast(CanonicalStore, store),
                Settings.model_validate(
                    {"APP_ENV": "test", "CORS_ORIGINS": "http://localhost:5173"}
                ),
            )

            result = await backend.import_master_data(
                saved,
                AuthenticatedUser(
                    "00000000-0000-0000-0000-000000000301",
                    "maintainer@example.test",
                ),
            )

        self.assertEqual("accepted", result["status"])
        assert store.master_payload is not None
        self.assertEqual("draft", store.master_payload["master_data_version"]["status"])
        self.assertEqual(1, len(store.master_payload["items"]))
        self.assertEqual(1, len(store.master_payload["item_policy_overrides"]))
        self.assertEqual(1, len(store.master_payload["locations"]))
        self.assertEqual(1, len(store.master_payload["delivery_rules"]))
        self.assertEqual(
            store.master_payload["source_import"]["id"],
            store.master_payload["master_data_version"]["source_import_id"],
        )


if __name__ == "__main__":
    unittest.main()
