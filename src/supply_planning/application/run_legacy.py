from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from supply_planning.domain.issues import ExceptionCode, PlanningIssue, Severity
from supply_planning.domain.models import RunMode
from supply_planning.engine.legacy_kw34 import (
    LegacyKw34Input,
    LegacyKw34Result,
    calculate_legacy_kw34,
)

PROFILE = "legacy_kw34/v1"


def _input_payload(rows: tuple[LegacyKw34Input, ...]) -> list[dict[str, Any]]:
    return [
        {
            "item_id": row.item_id,
            "grams_per_day": str(row.grams_per_day),
            "pack_size_g": str(row.pack_size_g),
            "previous_daily_units": str(row.previous_daily_units),
            "stock_units": str(row.stock_units),
            "observed_order_units": row.observed_order_units,
            "source_row": row.source_row,
        }
        for row in rows
    ]


def _line_issues(result: LegacyKw34Result) -> tuple[PlanningIssue, ...]:
    record_ref = f"item_id={result.item_id}"
    if result.observed_order_units is None and result.calculated_order_units > 0:
        return (
            PlanningIssue(
                code=ExceptionCode.UNEXPLAINED_BLANK_ORDER,
                severity=Severity.WARNING,
                dataset="legacy_inputs",
                record_ref=record_ref,
                message=(
                    f"Calculated order is {result.calculated_order_units} units, but the "
                    "observed Order cell is blank."
                ),
                remedy=(
                    "Confirm whether the item was already in transit, deliberately suppressed, "
                    "or missed."
                ),
            ),
        )
    if (
        result.observed_order_units is not None
        and result.observed_order_units != result.calculated_order_units
    ):
        return (
            PlanningIssue(
                code=ExceptionCode.OBSERVED_ORDER_DIFFERS,
                severity=Severity.WARNING,
                dataset="legacy_inputs",
                record_ref=record_ref,
                message=(
                    f"Calculated order is {result.calculated_order_units} units; observed "
                    f"Order is {result.observed_order_units} units."
                ),
                remedy="Preserve the difference and obtain the planner's reason before acceptance.",
            ),
        )
    return ()


@dataclass(frozen=True, slots=True)
class LegacyLineAudit:
    calculation: LegacyKw34Result
    issues: tuple[PlanningIssue, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.calculation.as_dict(),
            "issues": [issue.as_dict() for issue in self.issues],
        }


@dataclass(frozen=True, slots=True)
class LegacyRunResult:
    run_id: str
    input_hash: str
    run_mode: RunMode
    lines: tuple[LegacyLineAudit, ...]

    def as_dict(self) -> dict[str, Any]:
        issue_count = sum(len(line.issues) for line in self.lines)
        blocker_count = sum(
            issue.severity is Severity.BLOCKER
            for line in self.lines
            for issue in line.issues
        )
        return {
            "schema_version": 1,
            "profile": PROFILE,
            "run_id": self.run_id,
            "run_mode": self.run_mode.value,
            "input_hash": self.input_hash,
            "summary": {
                "line_count": len(self.lines),
                "issue_count": issue_count,
                "blocker_count": blocker_count,
                "calculated_order_units": sum(
                    line.calculation.calculated_order_units for line in self.lines
                ),
            },
            "lines": [line.as_dict() for line in self.lines],
        }


def run_legacy_kw34(
    rows: tuple[LegacyKw34Input, ...],
    *,
    run_mode: RunMode = RunMode.FIXTURE,
) -> LegacyRunResult:
    """Run the compatibility profile and produce a deterministic audit envelope."""

    item_ids = [row.item_id for row in rows]
    duplicates = sorted({item_id for item_id in item_ids if item_ids.count(item_id) > 1})
    if duplicates:
        raise ValueError(f"duplicate item_id values are not allowed: {', '.join(duplicates)}")

    encoded = json.dumps(
        _input_payload(rows),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    input_hash = hashlib.sha256(encoded).hexdigest()
    lines = tuple(
        LegacyLineAudit(calculation=result, issues=_line_issues(result))
        for row in rows
        for result in (calculate_legacy_kw34(row),)
    )
    return LegacyRunResult(
        run_id=f"legacy_kw34-{input_hash[:12]}",
        input_hash=input_hash,
        run_mode=run_mode,
        lines=lines,
    )
