from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Sequence

from supply_planning.adapters.canonical_csv import load_canonical_bundle
from supply_planning.adapters.errors import InputFileError
from supply_planning.adapters.improved_json import write_improved_audit_json
from supply_planning.adapters.legacy_csv import (
    load_legacy_csv,
    write_legacy_audit_json,
)
from supply_planning.adapters.transgourmet_pdf import import_transgourmet_pdfs
from supply_planning.application.run_improved import run_improved_plan
from supply_planning.application.run_legacy import run_legacy_kw34
from supply_planning.application.run_template_v1 import run_template_v1
from supply_planning.domain.models import RunMode, RunStatus


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="supply-plan",
        description="Run deterministic Phase 2 supply-planning profiles.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    legacy = subparsers.add_parser(
        "legacy-run",
        help="Run the isolated legacy_kw34 compatibility profile.",
    )
    legacy.add_argument("--input", required=True, type=Path, help="Legacy input CSV path")
    legacy.add_argument("--output", required=True, type=Path, help="Audit JSON output path")
    legacy.add_argument(
        "--run-mode",
        choices=[RunMode.FIXTURE.value, RunMode.SCENARIO.value],
        default=RunMode.FIXTURE.value,
        help="Compatibility runs are restricted to fixture and scenario modes.",
    )
    improved = subparsers.add_parser(
        "improved-run",
        help="Run canonical daily files through BOM explosion and dated netting.",
    )
    improved.add_argument(
        "--input-dir",
        required=True,
        type=Path,
        help="Directory containing source_manifest.csv and canonical CSV files.",
    )
    improved.add_argument("--output", required=True, type=Path, help="Audit JSON path")
    improved.add_argument(
        "--planning-as-of",
        required=True,
        help="Timezone-aware ISO timestamp used as the deterministic planning cutoff.",
    )
    improved.add_argument(
        "--run-mode",
        choices=[mode.value for mode in RunMode],
        default=RunMode.SCENARIO.value,
        help="Shadow and production modes fail closed on unknown critical sources.",
    )
    transgourmet = subparsers.add_parser(
        "transgourmet-import",
        help="Extract Transgourmet Bestelldetails PDFs into history and open-PO CSVs.",
    )
    transgourmet.add_argument(
        "--input-dir", required=True, type=Path, help="Directory containing downloaded PDFs."
    )
    transgourmet.add_argument(
        "--output-dir", required=True, type=Path, help="Private/local CSV output directory."
    )
    transgourmet.add_argument(
        "--as-of-date",
        required=True,
        type=_iso_date,
        help="Inclusive YYYY-MM-DD cutoff used to select scheduled open-PO rows.",
    )
    transgourmet.add_argument(
        "--location-id", required=True, help="Stable receiving/planning location ID."
    )
    transgourmet.add_argument(
        "--supplier-id", default="TRANSGOURMET", help="Canonical supplier ID."
    )
    transgourmet.add_argument(
        "--timezone", default="Europe/Berlin", help="Timezone for PDF order timestamps."
    )
    item_ids = transgourmet.add_mutually_exclusive_group(required=True)
    item_ids.add_argument(
        "--item-map",
        type=Path,
        help="CSV with supplier_article_number,item_id columns.",
    )
    item_ids.add_argument(
        "--allow-supplier-item-ids",
        action="store_true",
        help="Use provisional TG-<article number> IDs until an approved mapping exists.",
    )
    v1 = subparsers.add_parser(
        "v1-run",
        help="Normalize the two fixed templates, stock XLSX and PO PDFs, then recommend orders.",
    )
    v1.add_argument("--master-workbook", required=True, type=Path)
    v1.add_argument("--planning-workbook", required=True, type=Path)
    v1.add_argument("--stock-workbook", required=True, type=Path)
    v1.add_argument("--po-pdf-dir", required=True, type=Path)
    v1.add_argument("--output-dir", required=True, type=Path)
    v1.add_argument("--location-id", required=True)
    v1.add_argument(
        "--planning-as-of",
        help="Optional timezone-aware cutoff; defaults to the stock export timestamp.",
    )
    v1.add_argument(
        "--run-mode",
        choices=[mode.value for mode in RunMode],
        default=RunMode.SCENARIO.value,
    )
    return parser


def _planning_as_of(value: str) -> datetime:
    normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise InputFileError(
            f"--planning-as-of {value!r} is not an ISO timestamp; "
            "use e.g. 2026-08-25T00:00:00+02:00"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InputFileError(
            f"--planning-as-of {value!r} has no timezone offset; "
            "use e.g. 2026-08-25T00:00:00+02:00"
        )
    return parsed


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} is not a YYYY-MM-DD date") from exc


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "legacy-run":
            rows = load_legacy_csv(args.input)
            result = run_legacy_kw34(rows, run_mode=RunMode(args.run_mode))
            write_legacy_audit_json(args.output, result)
            payload = {
                "run_id": result.run_id,
                "profile": "legacy_kw34/v1",
                "output": str(args.output),
                **result.as_dict()["summary"],
            }
            exit_code = 0
        elif args.command == "improved-run":
            bundle = load_canonical_bundle(args.input_dir)
            improved_result = run_improved_plan(
                bundle,
                planning_as_of_at=_planning_as_of(args.planning_as_of),
                run_mode=RunMode(args.run_mode),
            )
            write_improved_audit_json(args.output, improved_result)
            payload = {
                "run_id": improved_result.run_id,
                "profile": "improved_file/v1",
                "status": improved_result.status.value,
                "output": str(args.output),
                **improved_result.as_dict()["summary"],
            }
            exit_code = 3 if improved_result.status is RunStatus.BLOCKED else 0
        elif args.command == "transgourmet-import":
            payload = import_transgourmet_pdfs(
                args.input_dir,
                args.output_dir,
                as_of_date=args.as_of_date,
                location_id=args.location_id,
                supplier_id=args.supplier_id,
                item_map_path=args.item_map,
                allow_supplier_item_ids=args.allow_supplier_item_ids,
                timezone_name=args.timezone,
            )
            exit_code = 0
        elif args.command == "v1-run":
            v1_result = run_template_v1(
                master_workbook=args.master_workbook,
                planning_workbook=args.planning_workbook,
                stock_workbook=args.stock_workbook,
                po_pdf_dir=args.po_pdf_dir,
                output_dir=args.output_dir,
                location_id=args.location_id,
                run_mode=RunMode(args.run_mode),
                planning_as_of_at=(
                    _planning_as_of(args.planning_as_of)
                    if args.planning_as_of
                    else None
                ),
            )
            payload = {
                "run_id": v1_result.run_id,
                "profile": "template_v1/v1",
                "status": v1_result.status.value,
                "output_dir": str(args.output_dir),
                **v1_result.as_dict()["summary"],
            }
            exit_code = 3 if v1_result.status is RunStatus.BLOCKED else 0
        else:
            return 2
    except (InputFileError, ValueError, OSError) as exc:
        print(f"Planning input error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(payload, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
