from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from supply_planning.adapters.apicbase_stock_xlsx import normalize_apicbase_stock
from supply_planning.adapters.canonical_csv import (
    CanonicalInputBundle,
    load_canonical_bundle,
)
from supply_planning.adapters.errors import InputFileError
from supply_planning.adapters.template_xlsx import (
    load_master_template,
    load_planning_template,
)
from supply_planning.adapters.transgourmet_v1 import normalize_transgourmet_pos
from supply_planning.adapters.v1_outputs import write_canonical_bundle, write_v1_results
from supply_planning.application.run_improved import ImprovedRunResult, run_improved_plan
from supply_planning.domain.issues import ExceptionCode, PlanningIssue, Severity
from supply_planning.domain.models import (
    BomLine,
    ForecastDaily,
    InputSourceStatus,
    Provenance,
    RunMode,
)


def selected_required_items(
    forecasts: tuple[ForecastDaily, ...],
    bom_lines: tuple[BomLine, ...],
) -> set[str]:
    required: set[str] = set()
    for forecast in forecasts:
        for line in bom_lines:
            if line.dish_id == forecast.dish_id and line.is_active_on(forecast.service_date):
                required.add(line.item_id)
    return required


def run_template_v1(
    *,
    master_workbook: Path,
    planning_workbook: Path,
    stock_workbook: Path,
    po_pdf_dir: Path,
    output_dir: Path,
    location_id: str,
    run_mode: RunMode = RunMode.SCENARIO,
    planning_as_of_at: datetime | None = None,
) -> ImprovedRunResult:
    master = load_master_template(master_workbook)
    planning = load_planning_template(planning_workbook)

    locations = {location.location_id: location for location in master.locations}
    location = locations.get(location_id)
    if location is None:
        raise InputFileError(
            f"location_id={location_id!r} is absent from the master template Locations tab"
        )
    if not location.active:
        raise InputFileError(f"location_id={location_id!r} is inactive in Locations")

    forecasts = tuple(
        forecast for forecast in planning.forecasts if forecast.location_id == location_id
    )
    menu_entries = tuple(
        entry for entry in planning.menu_entries if entry.location_id == location_id
    )
    if not forecasts:
        raise InputFileError(
            f"planning template has no Demand_Plan rows for location_id={location_id!r}"
        )
    required_item_ids = selected_required_items(forecasts, planning.bom_lines)

    stock = normalize_apicbase_stock(
        stock_workbook,
        location_id=location_id,
        timezone_name=location.timezone,
        items=master.items,
        item_policies=master.item_policies,
        required_item_ids=required_item_ids,
        assume_zero_for_unmapped=run_mode in {RunMode.FIXTURE, RunMode.SCENARIO},
    )
    selected_as_of = planning_as_of_at or stock.counted_at
    if selected_as_of.tzinfo is None or selected_as_of.utcoffset() is None:
        raise InputFileError("planning_as_of_at must include a timezone offset")
    if selected_as_of < stock.counted_at:
        raise InputFileError(
            "planning_as_of_at is before the stock export timestamp; use the export timestamp "
            "or a later deterministic cutoff"
        )

    po = normalize_transgourmet_pos(
        po_pdf_dir,
        as_of_date=selected_as_of.date(),
        location_id=location_id,
        item_policies=master.item_policies,
        timezone_name=location.timezone,
    )

    statuses = (
        InputSourceStatus(
            "forecast_daily", Provenance.MANUAL, len(forecasts), planning.source_version
        ),
        InputSourceStatus(
            "menu_calendar", Provenance.MANUAL, len(menu_entries), planning.source_version
        ),
        InputSourceStatus(
            "bom_lines", Provenance.MANUAL, len(planning.bom_lines), planning.source_version
        ),
        InputSourceStatus("items", Provenance.MANUAL, len(master.items), master.source_version),
        InputSourceStatus(
            "inventory_snapshots",
            Provenance.OBSERVED,
            len(stock.snapshots),
            stock.source_version,
        ),
        InputSourceStatus(
            "purchase_orders",
            Provenance.OBSERVED,
            len(po.purchase_orders),
            po.source_version,
        ),
        InputSourceStatus(
            "locations", Provenance.MANUAL, len(master.locations), master.source_version
        ),
        InputSourceStatus(
            "item_policies",
            Provenance.MANUAL,
            len(master.item_policies),
            master.source_version,
        ),
        InputSourceStatus(
            "delivery_rules",
            Provenance.MANUAL,
            len(master.delivery_rules),
            master.source_version,
        ),
    )
    bundle = CanonicalInputBundle(
        forecasts=forecasts,
        menu_entries=menu_entries,
        bom_lines=planning.bom_lines,
        items=master.items,
        inventory_snapshots=stock.snapshots,
        purchase_orders=po.purchase_orders,
        source_statuses=statuses,
        locations=master.locations,
        item_policies=master.item_policies,
        delivery_rules=master.delivery_rules,
    )

    normalized_dir = output_dir / "normalized"
    write_canonical_bundle(normalized_dir, bundle)
    validated_bundle = load_canonical_bundle(normalized_dir)
    result = run_improved_plan(
        validated_bundle,
        planning_as_of_at=selected_as_of,
        run_mode=run_mode,
    )

    mapping_issues: list[PlanningIssue] = []
    for review in stock.reviews:
        mapping_issues.append(
            PlanningIssue(
                code=ExceptionCode.STOCK_MAPPING_UNRESOLVED,
                severity=Severity.WARNING,
                dataset="inventory_snapshots",
                record_ref=f"location_id={location_id},item_id={review.item_id}",
                message=review.reason,
                remedy=review.remedy,
            )
        )
    for po_review in po.reviews:
        mapping_issues.append(
            PlanningIssue(
                code=ExceptionCode.PO_MAPPING_UNRESOLVED,
                severity=Severity.WARNING,
                dataset="purchase_orders",
                record_ref=f"po_line_id={po_review.po_line_id}",
                message=(
                    f"Transgourmet article {po_review.supplier_article_number} "
                    f"({po_review.supplier_description}) was excluded: {po_review.reason}."
                ),
                remedy=po_review.remedy,
            )
        )
    result = replace(
        result,
        issues=tuple(
            sorted(
                (*result.issues, *mapping_issues),
                key=lambda issue: (
                    issue.severity.value,
                    issue.code.value,
                    issue.dataset or "",
                    issue.record_ref or "",
                    issue.message,
                ),
            )
        ),
    )
    write_v1_results(
        output_dir,
        result=result,
        bundle=validated_bundle,
        stock_reviews=stock.reviews,
        po_reviews=po.reviews,
    )
    return result
