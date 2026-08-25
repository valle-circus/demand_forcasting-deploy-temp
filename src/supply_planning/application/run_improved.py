from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from supply_planning.adapters.canonical_csv import CanonicalInputBundle
from supply_planning.domain.issues import ExceptionCode, PlanningIssue, Severity
from supply_planning.domain.models import (
    InputSourceStatus,
    InventorySnapshot,
    RunMode,
    RunStatus,
)
from supply_planning.engine.explode import aggregate_item_demand, explode_bom
from supply_planning.engine.netting import CandidateReceipt, NettingResult, project_inventory
from supply_planning.validation.gates import evaluate_run_mode

PROFILE = "improved_file/v1"


def _normalize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {field.name: _normalize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def _run_hash_payload(
    bundle: CanonicalInputBundle,
    planning_as_of_at: datetime,
    run_mode: RunMode,
    candidate_receipts: tuple[CandidateReceipt, ...],
) -> dict[str, Any]:
    return {
        "profile": PROFILE,
        "planning_as_of_at": planning_as_of_at.isoformat(),
        "run_mode": run_mode.value,
        "source_statuses": _normalize(bundle.source_statuses),
        "forecasts": _normalize(bundle.forecasts),
        "menu_entries": _normalize(bundle.menu_entries),
        "bom_lines": _normalize(bundle.bom_lines),
        "items": _normalize(bundle.items),
        "inventory_snapshots": _normalize(bundle.inventory_snapshots),
        "purchase_orders": _normalize(bundle.purchase_orders),
        "candidate_receipts": _normalize(candidate_receipts),
    }


@dataclass(frozen=True, slots=True)
class ImprovedRunResult:
    run_id: str
    input_hash: str
    planning_as_of_at: datetime
    run_mode: RunMode
    status: RunStatus
    source_statuses: tuple[InputSourceStatus, ...]
    issues: tuple[PlanningIssue, ...]
    netting_results: tuple[NettingResult, ...]

    def as_dict(self) -> dict[str, Any]:
        blocker_count = sum(issue.severity is Severity.BLOCKER for issue in self.issues)
        return {
            "schema_version": 1,
            "profile": PROFILE,
            "run_id": self.run_id,
            "input_hash": self.input_hash,
            "planning_as_of_at": self.planning_as_of_at.isoformat(),
            "run_mode": self.run_mode.value,
            "status": self.status.value,
            "summary": {
                "source_count": len(self.source_statuses),
                "netting_line_count": len(self.netting_results),
                "issue_count": len(self.issues),
                "blocker_count": blocker_count,
                "projected_stockout_lines": sum(
                    result.first_stockout_date is not None
                    for result in self.netting_results
                ),
                "net_requirement_g": str(
                    sum(
                        (result.net_requirement_g for result in self.netting_results),
                        start=Decimal("0"),
                    )
                ),
            },
            "source_statuses": [
                {
                    "dataset": status.dataset,
                    "provenance": status.provenance.value,
                    "record_count": status.record_count,
                    "source_version": status.source_version,
                }
                for status in self.source_statuses
            ],
            "issues": [issue.as_dict() for issue in self.issues],
            "netting_results": [result.as_dict() for result in self.netting_results],
        }


def _blocked_result(
    *,
    run_id: str,
    input_hash: str,
    planning_as_of_at: datetime,
    run_mode: RunMode,
    source_statuses: tuple[InputSourceStatus, ...],
    issues: tuple[PlanningIssue, ...],
) -> ImprovedRunResult:
    return ImprovedRunResult(
        run_id=run_id,
        input_hash=input_hash,
        planning_as_of_at=planning_as_of_at,
        run_mode=run_mode,
        status=RunStatus.BLOCKED,
        source_statuses=source_statuses,
        issues=issues,
        netting_results=(),
    )


def _netting_issues(result: NettingResult) -> tuple[PlanningIssue, ...]:
    record_ref = f"location_id={result.location_id},item_id={result.item_id}"
    issues: list[PlanningIssue] = []
    if result.overdue_open_po_g > 0:
        issues.append(
            PlanningIssue(
                code=ExceptionCode.OVERDUE_OPEN_PO,
                severity=Severity.WARNING,
                dataset="purchase_orders",
                record_ref=record_ref,
                message=(
                    f"{result.overdue_open_po_g} g remains open with an expected receipt "
                    "before the projection start and was not counted as available."
                ),
                remedy="Confirm the receipt, cancel the stale line, or update its expected date.",
            )
        )
    if result.open_po_after_horizon_g > 0:
        issues.append(
            PlanningIssue(
                code=ExceptionCode.OPEN_PO_AFTER_HORIZON,
                severity=Severity.INFO,
                dataset="purchase_orders",
                record_ref=record_ref,
                message=(
                    f"{result.open_po_after_horizon_g} g is expected after the projection "
                    "horizon and was not netted from horizon demand."
                ),
                remedy="Extend the horizon only when the planning policy requires it.",
            )
        )
    if result.open_po_after_final_demand_g > 0:
        issues.append(
            PlanningIssue(
                code=ExceptionCode.OPEN_PO_AFTER_FINAL_DEMAND,
                severity=Severity.WARNING,
                dataset="purchase_orders",
                record_ref=record_ref,
                message=(
                    f"{result.open_po_after_final_demand_g} g is expected after the last "
                    "positive demand date."
                ),
                remedy="Review whether the PO should be cancelled, pulled forward, or retained.",
            )
        )
    if result.unavoidable_pre_candidate_stockout_g > 0:
        issues.append(
            PlanningIssue(
                code=ExceptionCode.UNAVOIDABLE_PRE_ARRIVAL_STOCKOUT,
                severity=Severity.WARNING,
                dataset="inventory_projection",
                record_ref=record_ref,
                message=(
                    f"Projected shortage reaches {result.unavoidable_pre_candidate_stockout_g} "
                    "g before the supplied candidate receipt date."
                ),
                remedy="Escalate, expedite, substitute, or adjust the explicit receipt scenario.",
            )
        )
    if result.first_stockout_date is not None:
        issues.append(
            PlanningIssue(
                code=ExceptionCode.PROJECTED_STOCKOUT,
                severity=Severity.WARNING,
                dataset="inventory_projection",
                record_ref=record_ref,
                message=(
                    f"Projected balance first falls below zero on "
                    f"{result.first_stockout_date.isoformat()}."
                ),
                remedy="Review dated demand, stock, open POs, and any explicit candidate receipt.",
            )
        )
    return tuple(issues)


def run_improved_plan(
    bundle: CanonicalInputBundle,
    *,
    planning_as_of_at: datetime,
    run_mode: RunMode,
    candidate_receipts: tuple[CandidateReceipt, ...] = (),
) -> ImprovedRunResult:
    """Run the file-driven demand explosion and dated netting path."""

    if planning_as_of_at.tzinfo is None or planning_as_of_at.utcoffset() is None:
        raise ValueError("planning_as_of_at must include a timezone offset")
    projection_start = planning_as_of_at.date()
    past_forecasts = [
        forecast
        for forecast in bundle.forecasts
        if forecast.service_date < projection_start
    ]
    if past_forecasts:
        first = min(past_forecasts, key=lambda forecast: forecast.service_date)
        raise ValueError(
            "forecast_daily contains service dates before planning_as_of_at: "
            f"{first.location_id}/{first.dish_id}/{first.service_date.isoformat()}; "
            "provide a forward snapshot or move planning_as_of_at"
        )

    payload = _run_hash_payload(bundle, planning_as_of_at, run_mode, candidate_receipts)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    input_hash = hashlib.sha256(encoded).hexdigest()
    run_id = f"improved-{input_hash[:12]}"

    issues = list(evaluate_run_mode(run_mode, bundle.source_statuses))
    if any(issue.severity is Severity.BLOCKER for issue in issues):
        return _blocked_result(
            run_id=run_id,
            input_hash=input_hash,
            planning_as_of_at=planning_as_of_at,
            run_mode=run_mode,
            source_statuses=bundle.source_statuses,
            issues=tuple(issues),
        )

    exploded = explode_bom(bundle.forecasts, bundle.bom_lines)
    daily_item_demand = aggregate_item_demand(exploded)
    demand_keys = sorted(
        {(demand.location_id, demand.item_id) for demand in daily_item_demand}
    )
    strict = run_mode in {RunMode.SHADOW, RunMode.PRODUCTION}
    selected_snapshots: dict[tuple[str, str], InventorySnapshot] = {}
    for location_id, item_id in demand_keys:
        candidates = [
            snapshot
            for snapshot in bundle.inventory_snapshots
            if snapshot.location_id == location_id
            and snapshot.item_id == item_id
            and snapshot.counted_at <= planning_as_of_at
        ]
        if not candidates:
            issues.append(
                PlanningIssue(
                    code=ExceptionCode.MISSING_INVENTORY_SNAPSHOT,
                    severity=Severity.BLOCKER if strict else Severity.WARNING,
                    dataset="inventory_snapshots",
                    record_ref=f"location_id={location_id},item_id={item_id}",
                    message="No inventory snapshot exists at or before planning_as_of_at.",
                    remedy="Provide a timestamped usable stock snapshot for this location/item.",
                )
            )
            continue
        selected_snapshot = max(
            candidates, key=lambda snapshot: snapshot.counted_at
        )
        selected_snapshots[(location_id, item_id)] = selected_snapshot
        if selected_snapshot.counted_at.date() < projection_start:
            issues.append(
                PlanningIssue(
                    code=ExceptionCode.STALE_INVENTORY_SNAPSHOT,
                    severity=Severity.BLOCKER if strict else Severity.WARNING,
                    dataset="inventory_snapshots",
                    record_ref=f"location_id={location_id},item_id={item_id}",
                    message=(
                        f"Latest stock count is {selected_snapshot.counted_at.isoformat()}, "
                        "before the projection start date."
                    ),
                    remedy=(
                        "Provide a planning-date snapshot or a complete dated event bridge; "
                        "scenario mode otherwise treats this count as the opening balance."
                    ),
                )
            )

    if any(issue.severity is Severity.BLOCKER for issue in issues):
        return _blocked_result(
            run_id=run_id,
            input_hash=input_hash,
            planning_as_of_at=planning_as_of_at,
            run_mode=run_mode,
            source_statuses=bundle.source_statuses,
            issues=tuple(issues),
        )

    items = {item.item_id: item for item in bundle.items}
    demand_provenance = bundle.source_status("forecast_daily").provenance
    results: list[NettingResult] = []
    for location_id, item_id in demand_keys:
        snapshot = selected_snapshots.get((location_id, item_id))
        if snapshot is None:
            continue
        demands = tuple(
            demand
            for demand in daily_item_demand
            if demand.location_id == location_id and demand.item_id == item_id
        )
        projection_end = max(demand.service_date for demand in demands)
        result = project_inventory(
            location_id=location_id,
            item_id=item_id,
            projection_start_date=projection_start,
            projection_end_date=projection_end,
            demands=demands,
            snapshot=snapshot,
            item=items[item_id],
            purchase_orders=(
                po
                for po in bundle.purchase_orders
                if po.location_id == location_id and po.item_id == item_id
            ),
            demand_provenance=demand_provenance,
            candidate_receipts=(
                receipt
                for receipt in candidate_receipts
                if receipt.location_id == location_id and receipt.item_id == item_id
            ),
        )
        results.append(result)
        issues.extend(_netting_issues(result))

    results.sort(key=lambda result: (result.location_id, result.item_id))
    return ImprovedRunResult(
        run_id=run_id,
        input_hash=input_hash,
        planning_as_of_at=planning_as_of_at,
        run_mode=run_mode,
        status=RunStatus.COMPLETED,
        source_statuses=bundle.source_statuses,
        issues=tuple(issues),
        netting_results=tuple(results),
    )
