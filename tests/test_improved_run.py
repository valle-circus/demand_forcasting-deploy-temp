from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from supply_planning.adapters.canonical_csv import load_canonical_bundle
from supply_planning.application.run_improved import run_improved_plan
from supply_planning.cli import main
from supply_planning.domain.issues import ExceptionCode, Severity
from supply_planning.domain.models import RunMode, RunStatus

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_improved"
AS_OF = datetime.fromisoformat("2026-08-25T00:00:00+02:00")


class ImprovedRunTests(unittest.TestCase):
    def test_synthetic_run_is_deterministic_and_reconciles_netting(self) -> None:
        bundle = load_canonical_bundle(FIXTURE)

        first = run_improved_plan(bundle, planning_as_of_at=AS_OF, run_mode=RunMode.SCENARIO)
        second = run_improved_plan(bundle, planning_as_of_at=AS_OF, run_mode=RunMode.SCENARIO)

        self.assertEqual(first.as_dict(), second.as_dict())
        self.assertEqual(first.status, RunStatus.COMPLETED)
        self.assertEqual(len(first.netting_results), 3)
        self.assertEqual(
            sum((result.net_requirement_g for result in first.netting_results), Decimal("0")),
            Decimal("2600"),
        )
        keys = [(result.location_id, result.item_id) for result in first.netting_results]
        self.assertEqual(
            keys,
            [
                ("LOC_A", "ITEM_COMPONENT"),
                ("LOC_A", "ITEM_SHARED"),
                ("LOC_B", "ITEM_SHARED"),
            ],
        )
        self.assertIn(
            ExceptionCode.OPEN_PO_AFTER_HORIZON,
            {issue.code for issue in first.issues},
        )

    def test_empty_placeholder_po_blocks_strict_mode_but_not_scenario(self) -> None:
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

            scenario = run_improved_plan(
                bundle, planning_as_of_at=AS_OF, run_mode=RunMode.SCENARIO
            )
            production = run_improved_plan(
                bundle, planning_as_of_at=AS_OF, run_mode=RunMode.PRODUCTION
            )

            self.assertEqual(scenario.status, RunStatus.COMPLETED)
            self.assertEqual(len(scenario.netting_results), 3)
            po_warning = next(
                issue for issue in scenario.issues if issue.dataset == "purchase_orders"
            )
            self.assertEqual(po_warning.severity, Severity.WARNING)
            self.assertEqual(production.status, RunStatus.BLOCKED)
            self.assertEqual(production.netting_results, ())
            po_blocker = next(
                issue for issue in production.issues if issue.dataset == "purchase_orders"
            )
            self.assertEqual(po_blocker.severity, Severity.BLOCKER)
            self.assertEqual(po_blocker.code, ExceptionCode.UNKNOWN_CRITICAL_SOURCE)

    def test_improved_cli_writes_byte_stable_audit_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first_path = Path(directory) / "first.json"
            second_path = Path(directory) / "second.json"
            args = [
                "improved-run",
                "--input-dir",
                str(FIXTURE),
                "--planning-as-of",
                AS_OF.isoformat(),
                "--run-mode",
                "scenario",
            ]
            with redirect_stdout(io.StringIO()):
                first_code = main([*args, "--output", str(first_path)])
                second_code = main([*args, "--output", str(second_path)])

            self.assertEqual(first_code, 0)
            self.assertEqual(second_code, 0)
            self.assertEqual(first_path.read_bytes(), second_path.read_bytes())
            payload = json.loads(first_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["profile"], "improved_file/v1")
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["summary"]["netting_line_count"], 3)
            self.assertEqual(payload["summary"]["net_requirement_g"], "2600")

    def test_stale_inventory_warns_in_scenario_and_blocks_production(self) -> None:
        bundle = load_canonical_bundle(FIXTURE)
        stale_bundle = replace(
            bundle,
            inventory_snapshots=tuple(
                replace(snapshot, counted_at=snapshot.counted_at - timedelta(days=1))
                for snapshot in bundle.inventory_snapshots
            ),
        )

        scenario = run_improved_plan(
            stale_bundle, planning_as_of_at=AS_OF, run_mode=RunMode.SCENARIO
        )
        production = run_improved_plan(
            stale_bundle, planning_as_of_at=AS_OF, run_mode=RunMode.PRODUCTION
        )

        stale_scenario_issues = [
            issue
            for issue in scenario.issues
            if issue.code is ExceptionCode.STALE_INVENTORY_SNAPSHOT
        ]
        self.assertEqual(len(stale_scenario_issues), 3)
        self.assertTrue(
            all(issue.severity is Severity.WARNING for issue in stale_scenario_issues)
        )
        self.assertEqual(scenario.status, RunStatus.COMPLETED)
        self.assertEqual(production.status, RunStatus.BLOCKED)
        self.assertEqual(production.netting_results, ())

    def test_improved_cli_returns_blocked_exit_for_unknown_po_pipeline(self) -> None:
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
            output_path = Path(directory) / "blocked.json"

            with redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "improved-run",
                        "--input-dir",
                        str(copied),
                        "--output",
                        str(output_path),
                        "--planning-as-of",
                        AS_OF.isoformat(),
                        "--run-mode",
                        "production",
                    ]
                )

            self.assertEqual(code, 3)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked")
            self.assertEqual(payload["netting_results"], [])
            self.assertEqual(payload["summary"]["blocker_count"], 1)


if __name__ == "__main__":
    unittest.main()
