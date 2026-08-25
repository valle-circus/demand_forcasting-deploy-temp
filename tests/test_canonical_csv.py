from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from supply_planning.adapters.canonical_csv import load_canonical_bundle
from supply_planning.adapters.errors import InputFileError
from supply_planning.domain.models import Provenance

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_improved"


class CanonicalCsvTests(unittest.TestCase):
    def test_loads_typed_bundle_and_source_statuses(self) -> None:
        bundle = load_canonical_bundle(FIXTURE)

        self.assertEqual(len(bundle.forecasts), 5)
        self.assertEqual(len(bundle.menu_entries), 5)
        self.assertEqual(len(bundle.bom_lines), 3)
        self.assertEqual(len(bundle.items), 2)
        self.assertEqual(len(bundle.inventory_snapshots), 3)
        self.assertEqual(len(bundle.purchase_orders), 2)
        po_status = bundle.source_status("purchase_orders")
        self.assertEqual(po_status.provenance, Provenance.MANUAL)
        self.assertEqual(po_status.record_count, 2)
        self.assertTrue(all(row.provenance is Provenance.MANUAL for row in bundle.forecasts))

    def test_duplicate_key_error_has_file_row_key_and_remedy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "fixture"
            shutil.copytree(FIXTURE, copied)
            forecast_path = copied / "forecast_daily.csv"
            lines = forecast_path.read_text(encoding="utf-8").splitlines()
            forecast_path.write_text("\n".join([*lines, lines[1]]) + "\n", encoding="utf-8")

            with self.assertRaises(InputFileError) as context:
                load_canonical_bundle(copied)

            message = str(context.exception)
            self.assertIn("forecast_daily.csv row 7", message)
            self.assertIn("duplicate forecast_daily", message)
            self.assertIn("first seen at row 2", message)
            self.assertIn("keep exactly one", message)

    def test_empty_open_po_file_uses_manifest_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "fixture"
            shutil.copytree(FIXTURE, copied)
            manifest_path = copied / "source_manifest.csv"
            manifest_path.write_text(
                manifest_path.read_text(encoding="utf-8").replace(
                    "purchase_orders,manual,synthetic-open-pos-v1",
                    "purchase_orders,empty_placeholder,not-available-v1",
                ),
                encoding="utf-8",
            )
            open_pos_path = copied / "open_pos.csv"
            header = open_pos_path.read_text(encoding="utf-8").splitlines()[0]
            open_pos_path.write_text(f"{header}\n", encoding="utf-8")

            bundle = load_canonical_bundle(copied)

            self.assertEqual(bundle.purchase_orders, ())
            status = bundle.source_status("purchase_orders")
            self.assertEqual(status.provenance, Provenance.EMPTY_PLACEHOLDER)
            self.assertEqual(status.record_count, 0)

    def test_placeholder_provenance_cannot_hide_supplied_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "fixture"
            shutil.copytree(FIXTURE, copied)
            manifest_path = copied / "source_manifest.csv"
            manifest_path.write_text(
                manifest_path.read_text(encoding="utf-8").replace(
                    "purchase_orders,manual,synthetic-open-pos-v1",
                    "purchase_orders,empty_placeholder,not-available-v1",
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                InputFileError, "purchase_orders.*empty_placeholder.*2 rows"
            ):
                load_canonical_bundle(copied)

    def test_forecast_without_active_menu_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "fixture"
            shutil.copytree(FIXTURE, copied)
            menu_path = copied / "menu_calendar.csv"
            menu_path.write_text(
                menu_path.read_text(encoding="utf-8").replace(
                    "LOC_A,DISH_A,2026-08-25,menu-v1,true",
                    "LOC_A,DISH_A,2026-08-25,menu-v1,false",
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                InputFileError, "no single active menu_calendar row"
            ):
                load_canonical_bundle(copied)

    def test_orphan_bom_item_names_the_bad_stable_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "fixture"
            shutil.copytree(FIXTURE, copied)
            bom_path = copied / "bom_lines.csv"
            bom_path.write_text(
                bom_path.read_text(encoding="utf-8").replace(
                    "SILO_PREMIX,ITEM_COMPONENT", "SILO_PREMIX,ITEM_UNKNOWN"
                ),
                encoding="utf-8",
            )

            with self.assertRaises(InputFileError) as context:
                load_canonical_bundle(copied)

            message = str(context.exception)
            self.assertIn("bom_line_id='BOM_A_COMPONENT'", message)
            self.assertIn("item_id='ITEM_UNKNOWN'", message)
            self.assertIn("add the item or correct the stable ID", message)

    def test_inventory_timestamp_requires_timezone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "fixture"
            shutil.copytree(FIXTURE, copied)
            inventory_path = copied / "inventory_snapshots.csv"
            inventory_path.write_text(
                inventory_path.read_text(encoding="utf-8").replace(
                    "2026-08-25T00:00:00+02:00", "2026-08-25T00:00:00", 1
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(InputFileError, "has no timezone offset"):
                load_canonical_bundle(copied)


if __name__ == "__main__":
    unittest.main()
