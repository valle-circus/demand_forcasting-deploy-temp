from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

from supply_planning.adapters.canonical_csv import load_canonical_bundle
from supply_planning.adapters.errors import InputFileError
from supply_planning.adapters.improved_json import write_improved_audit_json
from supply_planning.adapters.legacy_csv import (
    load_legacy_csv,
    write_legacy_audit_json,
)
from supply_planning.application.run_improved import run_improved_plan
from supply_planning.application.run_legacy import run_legacy_kw34
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
        else:
            return 2
    except (InputFileError, ValueError, OSError) as exc:
        print(f"Planning input error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(payload, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
