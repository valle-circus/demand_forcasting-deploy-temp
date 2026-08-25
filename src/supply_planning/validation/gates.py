from __future__ import annotations

from collections.abc import Iterable

from supply_planning.domain.issues import ExceptionCode, PlanningIssue, Severity
from supply_planning.domain.models import InputSourceStatus, Provenance, RunMode

CRITICAL_DATASETS = (
    "forecast_daily",
    "menu_calendar",
    "bom_lines",
    "items",
    "inventory_snapshots",
    "purchase_orders",
)

UNKNOWN_PROVENANCE = {Provenance.EMPTY_PLACEHOLDER, Provenance.UNAVAILABLE}


def evaluate_run_mode(
    run_mode: RunMode,
    source_statuses: Iterable[InputSourceStatus],
) -> tuple[PlanningIssue, ...]:
    """Return visible source issues; strict modes fail closed on unknown critical inputs."""

    by_dataset = {status.dataset: status for status in source_statuses}
    issues: list[PlanningIssue] = []
    strict = run_mode in {RunMode.SHADOW, RunMode.OPERATIONAL}

    for dataset in CRITICAL_DATASETS:
        status = by_dataset.get(dataset)
        is_unknown = status is None or status.provenance in UNKNOWN_PROVENANCE
        if not is_unknown:
            continue

        severity = Severity.BLOCKER if strict else Severity.WARNING
        code = (
            ExceptionCode.UNKNOWN_CRITICAL_SOURCE
            if strict
            else ExceptionCode.PLACEHOLDER_SOURCE
        )
        provenance = status.provenance.value if status is not None else "missing"
        issues.append(
            PlanningIssue(
                code=code,
                severity=severity,
                dataset=dataset,
                message=(
                    f"{dataset} is {provenance}; this is not verified operational input."
                ),
                remedy=(
                    "Provide an observed or manually verified snapshot before shadow or "
                    "operational use."
                ),
            )
        )

    return tuple(issues)
