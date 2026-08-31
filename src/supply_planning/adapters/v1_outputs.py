from __future__ import annotations

import csv
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from pathlib import Path

from supply_planning.adapters.apicbase_stock_xlsx import StockMappingReview
from supply_planning.adapters.canonical_csv import (
    BOM_FIELDS,
    DELIVERY_RULE_FIELDS,
    FORECAST_FIELDS,
    INVENTORY_FIELDS,
    ITEM_FIELDS,
    ITEM_POLICY_FIELDS,
    LOCATION_FIELDS,
    MANIFEST_FIELDS,
    MENU_FIELDS,
    PURCHASE_ORDER_FIELDS,
    CanonicalInputBundle,
)
from supply_planning.adapters.improved_json import write_improved_audit_json
from supply_planning.adapters.transgourmet_v1 import PoMappingReview
from supply_planning.application.run_improved import ImprovedRunResult
from supply_planning.domain.issues import PlanningIssue

RECOMMENDATION_FIELDS = (
    "recommendation_id",
    "planning_line_id",
    "run_id",
    "location_id",
    "supplier_id",
    "item_id",
    "order_date",
    "expected_delivery_date",
    "proposed_qty_order_units",
    "order_unit",
    "packs_per_order_unit",
    "proposed_qty_packs",
    "proposed_qty_g",
)
DERIVATION_FIELDS = (
    "planning_line_id",
    "run_id",
    "location_id",
    "item_id",
    "supplier_id",
    "schedule_rule_id",
    "order_date",
    "expected_delivery_date",
    "coverage_start_date",
    "coverage_end_date",
    "protection_days",
    "gross_requirement_g",
    "yield_factor",
    "adjusted_requirement_g",
    "safety_stock_g",
    "usable_on_hand_g",
    "open_po_due_g",
    "raw_order_g",
    "shelf_life_cap_g",
    "max_cover_cap_g",
    "capped_order_g",
    "order_unit_size_g",
    "moq_order_units",
    "case_multiple_order_units",
    "proposed_order_units",
    "rounding_delta_g",
    "rounding_direction",
    "candidate_expiry_date",
    "shelf_life_cap_basis",
    "forecast_through_expiry",
    "projected_candidate_residual_at_expiry_g",
    "max_cover_end_date",
    "forecast_through_max_cover",
    "binding_constraint",
    "constraint_status",
    "data_status",
)
EXCEPTION_FIELDS = (
    "exception_id",
    "run_id",
    "severity",
    "code",
    "dataset",
    "record_ref",
    "message",
    "remedy",
)


def _text(value: object | None) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value, "f")
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[no-any-return,union-attr]
    if hasattr(value, "value"):
        return str(value.value)  # type: ignore[union-attr]
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _atomic_csv(
    path: Path,
    fields: Sequence[str],
    rows: Iterable[Mapping[str, object]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    temporary.replace(path)


def write_canonical_bundle(path: Path, bundle: CanonicalInputBundle) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _atomic_csv(
        path / "source_manifest.csv",
        MANIFEST_FIELDS,
        (
            {
                "dataset": status.dataset,
                "provenance": status.provenance.value,
                "source_version": status.source_version or "unknown",
            }
            for status in bundle.source_statuses
        ),
    )
    _atomic_csv(
        path / "forecast_daily.csv",
        FORECAST_FIELDS,
        (
            {
                "location_id": row.location_id,
                "dish_id": row.dish_id,
                "service_date": row.service_date.isoformat(),
                "forecast_portions": _text(row.forecast_portions),
                "forecast_version": row.forecast_version,
            }
            for row in bundle.forecasts
        ),
    )
    _atomic_csv(
        path / "menu_calendar.csv",
        MENU_FIELDS,
        (
            {
                "location_id": row.location_id,
                "dish_id": row.dish_id,
                "service_date": row.service_date.isoformat(),
                "menu_version": row.menu_version,
                "active": _text(row.active),
            }
            for row in bundle.menu_entries
        ),
    )
    _atomic_csv(
        path / "bom_lines.csv",
        BOM_FIELDS,
        (
            {
                "bom_line_id": row.bom_line_id,
                "dish_id": row.dish_id,
                "silo_id": row.silo_id,
                "item_id": row.item_id,
                "grams_per_portion": _text(row.grams_per_portion),
                "effective_from": row.effective_from.isoformat(),
                "effective_to": _text(row.effective_to),
            }
            for row in bundle.bom_lines
        ),
    )
    _atomic_csv(
        path / "items.csv",
        ITEM_FIELDS,
        (
            {
                "item_id": row.item_id,
                "item_name": row.item_name,
                "storage_class": row.storage_class.value,
                "pack_size_g": _text(row.pack_size_g),
                "shelf_life_days": _text(row.shelf_life_days),
                "min_safety_days": _text(row.min_safety_days),
                "max_cover_days": _text(row.max_cover_days),
                "active": _text(row.active),
            }
            for row in bundle.items
        ),
    )
    _atomic_csv(
        path / "inventory_snapshots.csv",
        (*INVENTORY_FIELDS, "provenance"),
        (
            {
                "location_id": row.location_id,
                "item_id": row.item_id,
                "counted_at": row.counted_at.isoformat(),
                "usable_on_hand_units": _text(row.usable_on_hand_units),
                "partial_pack_g": _text(row.partial_pack_g),
                "provenance": row.provenance.value,
            }
            for row in bundle.inventory_snapshots
        ),
    )
    _atomic_csv(
        path / "open_pos.csv",
        PURCHASE_ORDER_FIELDS,
        (
            {
                "po_id": row.po_id,
                "po_line_id": row.po_line_id,
                "location_id": row.location_id,
                "supplier_id": row.supplier_id,
                "item_id": row.item_id,
                "ordered_at": row.ordered_at.isoformat(),
                "expected_receipt_at": row.expected_receipt_at.isoformat(),
                "open_qty_units": _text(row.open_qty_units),
                "status": row.status.value,
            }
            for row in bundle.purchase_orders
        ),
    )
    _atomic_csv(
        path / "locations.csv",
        LOCATION_FIELDS,
        (
            {
                "location_id": row.location_id,
                "location_name": row.location_name,
                "timezone": row.timezone,
                "active": _text(row.active),
            }
            for row in bundle.locations
        ),
    )
    _atomic_csv(
        path / "item_policies.csv",
        ITEM_POLICY_FIELDS,
        (
            {
                "item_id": row.item_id,
                "item_type": row.item_type.value,
                "official_supplier": row.official_supplier,
                "ordering_channel": row.ordering_channel,
                "supplier_id": row.supplier_id,
                "supplier_article_number": _text(row.supplier_article_number),
                "supplier_description_match": _text(row.supplier_description_match),
                "packs_per_order_unit": _text(row.packs_per_order_unit),
                "order_unit": row.order_unit,
                "stock_qty_unit": row.stock_qty_unit.value,
                "apicbase_uid": _text(row.apicbase_uid),
                "apicbase_stock_item_name": _text(row.apicbase_stock_item_name),
                "lead_time_calendar_days": row.lead_time_calendar_days,
                "shelf_life_anchor": _text(row.shelf_life_anchor),
                "yield_factor": _text(row.yield_factor),
                "moq_order_units": _text(row.moq_order_units),
                "case_multiple_order_units": _text(row.case_multiple_order_units),
                "data_status": row.data_status,
            }
            for row in bundle.item_policies
        ),
    )
    _atomic_csv(
        path / "delivery_rules.csv",
        DELIVERY_RULE_FIELDS,
        (
            {
                "delivery_rule_id": row.delivery_rule_id,
                "location_id": row.location_id,
                "ordering_channel": row.ordering_channel,
                "storage_class": row.storage_class.value,
                "delivery_weekday": _text(row.delivery_weekday),
                "covered_service_weekdays": "|".join(
                    str(value) for value in row.covered_service_weekdays
                ),
                "order_weekday": _text(row.order_weekday),
                "review_period_days": row.review_period_days,
                "effective_from": row.effective_from.isoformat(),
                "effective_to": _text(row.effective_to),
                "active": _text(row.active),
                "data_status": row.data_status,
            }
            for row in bundle.delivery_rules
        ),
    )


def _exception_rows(run_id: str, issues: Iterable[PlanningIssue]) -> list[dict[str, str]]:
    ordered = sorted(
        issues,
        key=lambda issue: (
            issue.severity.value,
            issue.code.value,
            issue.dataset or "",
            issue.record_ref or "",
            issue.message,
        ),
    )
    return [
        {
            "exception_id": f"EXC-{run_id}-{index:04d}",
            "run_id": run_id,
            "severity": issue.severity.value,
            "code": issue.code.value,
            "dataset": issue.dataset or "",
            "record_ref": issue.record_ref or "",
            "message": issue.message,
            "remedy": issue.remedy,
        }
        for index, issue in enumerate(ordered, start=1)
    ]


def write_v1_results(
    path: Path,
    *,
    result: ImprovedRunResult,
    bundle: CanonicalInputBundle,
    stock_reviews: Iterable[StockMappingReview],
    po_reviews: Iterable[PoMappingReview],
) -> None:
    path.mkdir(parents=True, exist_ok=True)
    stock_reviews = tuple(stock_reviews)
    po_reviews = tuple(po_reviews)
    policy_by_id = {policy.item_id: policy for policy in bundle.item_policies}
    item_by_id = {item.item_id: item for item in bundle.items}
    line_by_id = {line.planning_line_id: line for line in result.planning_lines}
    _atomic_csv(
        path / "planning_recommendations.csv",
        RECOMMENDATION_FIELDS,
        (
            {
                "recommendation_id": row.recommendation_id,
                "planning_line_id": row.planning_line_id,
                "run_id": row.run_id,
                "location_id": row.location_id,
                "supplier_id": row.supplier_id,
                "item_id": row.item_id,
                "order_date": row.order_date.isoformat(),
                "expected_delivery_date": row.expected_delivery_date.isoformat(),
                "proposed_qty_order_units": _text(row.proposed_qty_units),
                "order_unit": policy_by_id[row.item_id].order_unit,
                "packs_per_order_unit": _text(
                    policy_by_id[row.item_id].packs_per_order_unit
                ),
                "proposed_qty_packs": _text(
                    row.proposed_qty_units
                    * policy_by_id[row.item_id].packs_per_order_unit
                ),
                "proposed_qty_g": _text(
                    row.proposed_qty_units
                    * line_by_id[row.planning_line_id].order_unit_size_g
                ),
            }
            for row in result.recommendations
        ),
    )
    _atomic_csv(
        path / "planning_derivations.csv",
        DERIVATION_FIELDS,
        (
            {
                field: _text(getattr(row, field))
                for field in DERIVATION_FIELDS
            }
            for row in result.planning_lines
        ),
    )
    _atomic_csv(
        path / "planning_exceptions.csv",
        EXCEPTION_FIELDS,
        _exception_rows(result.run_id, result.issues),
    )
    _atomic_csv(
        path / "stock_mapping_review.csv",
        (
            "item_id",
            "item_name",
            "apicbase_uid",
            "apicbase_stock_item_name",
            "reason",
            "remedy",
        ),
        (row.as_dict() for row in stock_reviews),
    )
    _atomic_csv(
        path / "po_mapping_review.csv",
        (
            "po_id",
            "po_line_id",
            "supplier_article_number",
            "supplier_description",
            "ordered_qty_order_units",
            "expected_receipt_date",
            "reason",
            "remedy",
        ),
        (row.as_dict() for row in po_reviews),
    )
    write_improved_audit_json(path / "run_audit.json", result)

    recommendations_by_item: dict[str, list] = defaultdict(list)
    for recommendation in result.recommendations:
        recommendations_by_item[recommendation.item_id].append(recommendation)
    exception_counts = Counter(issue.code.value for issue in result.issues)
    blocker_count = sum(issue.severity.value == "blocker" for issue in result.issues)
    lines = [
        "# Local V1 maintainer review summary",
        "",
        "> DEMO ONLY - do not place orders from this run. Master-data proposals and mapping gaps still require maintainer review.",
        "",
        f"- Run: `{result.run_id}`",
        f"- Planning cutoff: `{result.planning_as_of_at.isoformat()}`",
        f"- Mode/status: `{result.run_mode.value}` / `{result.status.value}`",
        f"- Recommendations: **{len(result.recommendations)} dated lines** across **{len(recommendations_by_item)} items**",
        f"- Blocking exceptions: **{blocker_count}**",
        "",
        "## Initial recommendation result",
        "",
        "| Item | Type | Deliveries | Receipt range | Proposed order units | Unit | Proposed grams |",
        "|---|---:|---:|---|---:|---|---:|",
    ]
    for item_id in sorted(recommendations_by_item):
        rows = recommendations_by_item[item_id]
        policy = policy_by_id[item_id]
        item = item_by_id[item_id]
        total_units = sum((row.proposed_qty_units for row in rows), start=Decimal("0"))
        total_grams = sum(
            (
                row.proposed_qty_units
                * item.pack_size_g
                * policy.packs_per_order_unit
                for row in rows
            ),
            start=Decimal("0"),
        )
        receipts = sorted(row.expected_delivery_date for row in rows)
        receipt_range = receipts[0].isoformat()
        if receipts[-1] != receipts[0]:
            receipt_range = f"{receipt_range} to {receipts[-1].isoformat()}"
        lines.append(
            "| "
            + " | ".join(
                (
                    f"{item.item_name} (`{item_id}`)",
                    policy.item_type.value,
                    str(len(rows)),
                    receipt_range,
                    _text(total_units),
                    policy.order_unit,
                    _text(total_grams),
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Visible exceptions and what they mean",
            "",
        ]
    )
    for code, count in sorted(exception_counts.items()):
        lines.append(f"- `{code}`: {count}")
    lines.extend(
        [
            "",
            "The pod pre-arrival shortages are expected in this zero-stock demo: a 28-calendar-day lead cannot cover demand beginning before the first possible receipt. The fresh constraint exceptions expose pack rounding that exceeds the proposed max-cover cap; they are not hidden.",
            "",
            "## Stock mappings requiring review",
            "",
        ]
    )
    if stock_reviews:
        for review in stock_reviews:
            lines.append(f"- `{review.item_id}`: {review.reason}. {review.remedy}")
    else:
        lines.append("- None.")
    lines.extend(["", "## Open-PO mappings requiring review", ""])
    if po_reviews:
        for review in po_reviews:
            receipt = review.expected_receipt_date or "undated"
            lines.append(
                f"- Article `{review.supplier_article_number}` - {review.supplier_description} "
                f"(receipt {receipt}): {review.reason}."
            )
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Maintainer decisions requested",
            "",
            "1. Confirm that the two fixed workbook schemas are practical and return corrected rows without renaming tabs or columns.",
            "2. Approve or correct lead time, review period, safety days, yield, shelf life, max cover, MOQ, case multiple, pack size, and order unit for each item.",
            "3. Confirm Apicbase stock quantity units and stable UID/exact-name mappings, including whether fractional quantities represent partial packs.",
            "4. Complete Transgourmet article/description mappings for every ordered item, including pods ordered through Transgourmet although Circus is the official supplier.",
            "5. Confirm the fresh delivery weekdays/service-day coverage and whether orders are available at the start of the receipt day.",
            "",
            "After the approved templates are returned, rerun the same command and require zero blockers before operational/shadow use. UI and Supabase configuration work may start in parallel, but demo assumptions must remain visibly unapproved until this gate passes.",
        ]
    )
    _atomic_text(path / "maintainer_review_summary.md", "\n".join(lines) + "\n")
