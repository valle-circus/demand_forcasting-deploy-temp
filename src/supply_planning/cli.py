from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from supply_planning.adapters.legacy_csv import (
    InputFileError,
    load_legacy_csv,
    write_legacy_audit_json,
)
from supply_planning.application.run_legacy import run_legacy_kw34
from supply_planning.domain.models import RunMode


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
        help="Compatibility runs are restricted to non-operational modes.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command != "legacy-run":
        return 2

    try:
        rows = load_legacy_csv(args.input)
        result = run_legacy_kw34(rows, run_mode=RunMode(args.run_mode))
        write_legacy_audit_json(args.output, result)
    except (InputFileError, ValueError, OSError) as exc:
        print(f"Planning input error: {exc}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "profile": "legacy_kw34/v1",
                "output": str(args.output),
                **result.as_dict()["summary"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
