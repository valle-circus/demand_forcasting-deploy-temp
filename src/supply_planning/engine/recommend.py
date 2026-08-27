from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING
from typing import Iterable

from supply_planning.domain.issues import ExceptionCode, PlanningIssue, Severity
from supply_planning.domain.models import (
    DeliveryCoverageRule,
    InventorySnapshot,
    Item,
    ItemDemandDaily,
    ItemPlanningPolicy,
    PlanningLine,
    PlanningRecommendation,
    Provenance,
    PurchaseOrderLine,
    ShelfLifeAnchor,
    StorageClass,
)


@dataclass(frozen=True, slots=True)
class RecommendationEngineResult:
    planning_lines: tuple[PlanningLine, ...]
    recommendations: tuple[PlanningRecommendation, ...]
    issues: tuple[PlanningIssue, ...]


@dataclass(frozen=True, slots=True)
class _Balance:
    ending_g: Decimal
    minimum_g: Decimal
    open_po_due_g: Decimal


def _dates(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _ceil_to_multiple(value: Decimal, multiple: Decimal) -> Decimal:
    if value <= 0:
        return Decimal("0")
    return (value / multiple).to_integral_value(rounding=ROUND_CEILING) * multiple


def _next_weekday_after(value: date, weekday: int) -> date:
    offset = (weekday - value.weekday()) % 7
    if offset == 0:
        offset = 7
    return value + timedelta(days=offset)


def _balance_through(
    *,
    start_date: date,
    end_date: date,
    opening_stock_g: Decimal,
    adjusted_demand_by_date: dict[date, Decimal],
    purchase_orders: tuple[PurchaseOrderLine, ...],
    item: Item,
    planned_receipts: dict[date, Decimal],
) -> _Balance:
    po_by_date: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    for po in purchase_orders:
        if po.status.is_open and start_date <= po.expected_receipt_at.date() <= end_date:
            po_by_date[po.expected_receipt_at.date()] += po.open_qty_units * item.pack_size_g

    balance = opening_stock_g
    minimum = opening_stock_g
    for value in _dates(start_date, end_date):
        balance += po_by_date[value] + planned_receipts.get(value, Decimal("0"))
        balance -= adjusted_demand_by_date.get(value, Decimal("0"))
        minimum = min(minimum, balance)
    return _Balance(
        ending_g=balance,
        minimum_g=minimum,
        open_po_due_g=sum(po_by_date.values(), start=Decimal("0")),
    )


def _constraint_caps(
    *,
    raw_order_g: Decimal,
    item: Item,
    policy: ItemPlanningPolicy,
    order_date: date,
    receipt_date: date,
    average_daily_adjusted_g: Decimal,
    adjusted_demand_by_date: dict[date, Decimal],
    last_demand_date: date,
) -> tuple[Decimal | None, Decimal | None, Decimal]:
    shelf_life_cap_g: Decimal | None = None
    if item.shelf_life_days is not None and policy.shelf_life_anchor is not None:
        if policy.shelf_life_anchor is ShelfLifeAnchor.ORDER_DATE:
            expiry_date = order_date + timedelta(days=item.shelf_life_days - 1)
        elif policy.shelf_life_anchor is ShelfLifeAnchor.RECEIPT_DATE:
            expiry_date = receipt_date + timedelta(days=item.shelf_life_days - 1)
        else:
            expiry_date = None
        if expiry_date is not None and expiry_date <= last_demand_date:
            shelf_life_cap_g = sum(
                (
                    quantity
                    for demand_date, quantity in adjusted_demand_by_date.items()
                    if receipt_date <= demand_date <= min(expiry_date, last_demand_date)
                ),
                start=Decimal("0"),
            )

    max_cover_cap_g = (
        average_daily_adjusted_g * item.max_cover_days
        if item.max_cover_days is not None
        else None
    )
    capped = max(Decimal("0"), raw_order_g)
    if shelf_life_cap_g is not None:
        capped = min(capped, shelf_life_cap_g)
    if max_cover_cap_g is not None:
        capped = min(capped, max_cover_cap_g)
    return shelf_life_cap_g, max_cover_cap_g, capped


def _round_order(
    *,
    capped_order_g: Decimal,
    item: Item,
    policy: ItemPlanningPolicy,
) -> tuple[Decimal, Decimal, Decimal]:
    order_unit_size_g = item.pack_size_g * policy.packs_per_order_unit
    if capped_order_g <= 0:
        return order_unit_size_g, Decimal("0"), Decimal("0")
    exact_units = capped_order_g / order_unit_size_g
    units_after_moq = max(exact_units, policy.moq_order_units)
    proposed_units = _ceil_to_multiple(
        units_after_moq, policy.case_multiple_order_units
    )
    rounding_delta_g = proposed_units * order_unit_size_g - capped_order_g
    return order_unit_size_g, proposed_units, rounding_delta_g


def _constraint_issues(
    *,
    line_ref: str,
    raw_order_g: Decimal,
    shelf_life_cap_g: Decimal | None,
    max_cover_cap_g: Decimal | None,
    capped_order_g: Decimal,
    proposed_order_units: Decimal,
    order_unit_size_g: Decimal,
    policy: ItemPlanningPolicy,
) -> list[PlanningIssue]:
    issues: list[PlanningIssue] = []
    if shelf_life_cap_g is not None and shelf_life_cap_g < raw_order_g:
        issues.append(
            PlanningIssue(
                code=ExceptionCode.SHELF_LIFE_CAP_BINDING,
                severity=Severity.WARNING,
                dataset="planning_recommendations",
                record_ref=line_ref,
                message=(
                    f"Shelf-life cap reduced raw order from {raw_order_g} g to at most "
                    f"{shelf_life_cap_g} g."
                ),
                remedy="Review forecast coverage, shelf life, delivery frequency, or substitution.",
            )
        )
    if max_cover_cap_g is not None and max_cover_cap_g < raw_order_g:
        issues.append(
            PlanningIssue(
                code=ExceptionCode.MAX_COVER_CAP_BINDING,
                severity=Severity.WARNING,
                dataset="planning_recommendations",
                record_ref=line_ref,
                message=(
                    f"Max-cover cap reduced raw order from {raw_order_g} g to at most "
                    f"{max_cover_cap_g} g."
                ),
                remedy="Review the approved max-cover rule or accept the visible shortage risk.",
            )
        )
    if capped_order_g > 0:
        exact_units = capped_order_g / order_unit_size_g
        if exact_units < policy.moq_order_units:
            issues.append(
                PlanningIssue(
                    code=ExceptionCode.MOQ_INFLATED_ORDER,
                    severity=Severity.WARNING,
                    dataset="planning_recommendations",
                    record_ref=line_ref,
                    message=(
                        f"MOQ increased {exact_units} order units to "
                        f"{policy.moq_order_units}."
                    ),
                    remedy="Confirm the supplier MOQ and accept or revise the resulting cover.",
                )
            )
        if proposed_order_units > max(exact_units, policy.moq_order_units):
            issues.append(
                PlanningIssue(
                    code=ExceptionCode.CASE_ROUNDING_APPLIED,
                    severity=Severity.INFO,
                    dataset="planning_recommendations",
                    record_ref=line_ref,
                    message=(
                        f"Final order-unit/case rounding increased the proposal to "
                        f"{proposed_order_units} order units."
                    ),
                    remedy="No action unless pack or case metadata is incorrect.",
                )
            )
    binding_cap = min(
        (
            cap
            for cap in (shelf_life_cap_g, max_cover_cap_g)
            if cap is not None
        ),
        default=None,
    )
    if (
        binding_cap is not None
        and proposed_order_units * order_unit_size_g > binding_cap
        and proposed_order_units > 0
    ):
        issues.append(
            PlanningIssue(
                code=ExceptionCode.INFEASIBLE_ORDER_CONSTRAINTS,
                severity=Severity.WARNING,
                dataset="planning_recommendations",
                record_ref=line_ref,
                message="MOQ/case rounding exceeds a shelf-life or max-cover cap.",
                remedy="Resolve the supplier-pack constraint or approve the excess explicitly.",
            )
        )
    return issues


def _build_line(
    *,
    run_id: str,
    sequence: int,
    location_id: str,
    item: Item,
    policy: ItemPlanningPolicy,
    schedule_rule_id: str,
    order_date: date,
    receipt_date: date,
    coverage_start_date: date,
    coverage_end_date: date,
    protection_days: int,
    base_requirement_g: Decimal,
    adjusted_requirement_g: Decimal,
    safety_stock_g: Decimal,
    opening_stock_g: Decimal,
    open_po_due_g: Decimal,
    raw_order_g: Decimal,
    shelf_life_cap_g: Decimal | None,
    max_cover_cap_g: Decimal | None,
    capped_order_g: Decimal,
    order_unit_size_g: Decimal,
    proposed_order_units: Decimal,
    rounding_delta_g: Decimal,
) -> PlanningLine:
    return PlanningLine(
        planning_line_id=(
            f"LINE-{run_id}-{location_id}-{item.item_id}-{receipt_date.isoformat()}-{sequence:02d}"
        ),
        run_id=run_id,
        location_id=location_id,
        item_id=item.item_id,
        supplier_id=policy.supplier_id,
        gross_requirement_g=base_requirement_g,
        yield_factor=policy.yield_factor,
        yield_factor_provenance=policy.provenance,
        safety_stock_g=safety_stock_g,
        safety_stock_provenance=item.provenance,
        usable_on_hand_g=opening_stock_g,
        open_po_due_g=open_po_due_g,
        raw_order_g=raw_order_g,
        shelf_life_cap_g=shelf_life_cap_g,
        max_cover_cap_g=max_cover_cap_g,
        capped_order_g=capped_order_g,
        proposed_order_units=proposed_order_units,
        rounding_delta_g=rounding_delta_g,
        order_date=order_date,
        expected_delivery_date=receipt_date,
        schedule_rule_id=schedule_rule_id,
        coverage_start_date=coverage_start_date,
        coverage_end_date=coverage_end_date,
        protection_days=protection_days,
        adjusted_requirement_g=adjusted_requirement_g,
        order_unit_size_g=order_unit_size_g,
        moq_order_units=policy.moq_order_units,
        case_multiple_order_units=policy.case_multiple_order_units,
        data_status=policy.data_status,
    )


def _recommendation(line: PlanningLine) -> PlanningRecommendation | None:
    if line.proposed_order_units <= 0 or line.supplier_id is None:
        return None
    return PlanningRecommendation(
        recommendation_id=f"REC-{line.planning_line_id[5:]}",
        planning_line_id=line.planning_line_id,
        run_id=line.run_id,
        location_id=line.location_id,
        supplier_id=line.supplier_id,
        item_id=line.item_id,
        order_date=line.order_date,
        expected_delivery_date=line.expected_delivery_date,
        proposed_qty_units=line.proposed_order_units,
    )


def schedule_recommendations(
    *,
    run_id: str,
    planning_as_of_date: date,
    daily_item_demand: Iterable[ItemDemandDaily],
    items: Iterable[Item],
    item_policies: Iterable[ItemPlanningPolicy],
    delivery_rules: Iterable[DeliveryCoverageRule],
    snapshots: Iterable[InventorySnapshot],
    purchase_orders: Iterable[PurchaseOrderLine],
) -> RecommendationEngineResult:
    demands = tuple(daily_item_demand)
    items_by_id = {item.item_id: item for item in items}
    policies_by_id = {policy.item_id: policy for policy in item_policies}
    snapshots_by_key = {
        (snapshot.location_id, snapshot.item_id): snapshot for snapshot in snapshots
    }
    pos_by_key: dict[tuple[str, str], list[PurchaseOrderLine]] = defaultdict(list)
    for po in purchase_orders:
        pos_by_key[(po.location_id, po.item_id)].append(po)
    demand_by_key: dict[tuple[str, str], list[ItemDemandDaily]] = defaultdict(list)
    for demand in demands:
        demand_by_key[(demand.location_id, demand.item_id)].append(demand)

    planning_lines: list[PlanningLine] = []
    recommendations: list[PlanningRecommendation] = []
    issues: list[PlanningIssue] = []
    for location_id, item_id in sorted(demand_by_key):
        item = items_by_id[item_id]
        policy = policies_by_id.get(item_id)
        record_ref = f"location_id={location_id},item_id={item_id}"
        if policy is None:
            issues.append(
                PlanningIssue(
                    code=ExceptionCode.MISSING_PLANNING_POLICY,
                    severity=Severity.WARNING,
                    dataset="item_policies",
                    record_ref=record_ref,
                    message="No item planning policy exists, so no order recommendation was calculated.",
                    remedy="Add the item policy row in the master template and rerun.",
                )
            )
            continue
        snapshot = snapshots_by_key.get((location_id, item_id))
        if snapshot is None:
            continue
        if policy.data_status != "SOURCE_VALUE":
            issues.append(
                PlanningIssue(
                    code=ExceptionCode.UNAPPROVED_MASTER_DATA,
                    severity=Severity.WARNING,
                    dataset="item_policies",
                    record_ref=record_ref,
                    message=(
                        f"Recommendation uses item policy status {policy.data_status!r}; "
                        "this is not an approved production value."
                    ),
                    remedy="Review the highlighted Items fields and issue an approved template version.",
                )
            )

        item_demands = sorted(
            demand_by_key[(location_id, item_id)], key=lambda row: row.service_date
        )
        base_by_date: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
        for demand in item_demands:
            base_by_date[demand.service_date] += demand.required_g
        adjusted_by_date = {
            value: quantity * policy.yield_factor
            for value, quantity in base_by_date.items()
        }
        last_demand_date = max(base_by_date)
        opening_stock_g = (
            snapshot.usable_on_hand_units * item.pack_size_g + snapshot.partial_pack_g
        )
        scoped_pos = tuple(pos_by_key[(location_id, item_id)])
        matching_rules = sorted(
            (
                rule
                for rule in delivery_rules
                if rule.location_id == location_id
                and rule.ordering_channel == policy.ordering_channel
                and rule.storage_class is item.storage_class
                and rule.is_active_on(planning_as_of_date)
            ),
            key=lambda rule: rule.delivery_rule_id,
        )
        if not matching_rules:
            issues.append(
                PlanningIssue(
                    code=ExceptionCode.MISSING_DELIVERY_RULE,
                    severity=Severity.WARNING,
                    dataset="delivery_rules",
                    record_ref=record_ref,
                    message="No active location/storage delivery rule exists; no recommendation was calculated.",
                    remedy="Add or activate the location-aware Delivery_Rules row and rerun.",
                )
            )
            continue

        if item.storage_class is not StorageClass.FRISCH:
            rule = matching_rules[0]
            protection_days = policy.lead_time_calendar_days + rule.review_period_days
            if protection_days <= 0:
                raise ValueError(f"{record_ref}: lead time plus review period must be positive")
            coverage_end = planning_as_of_date + timedelta(days=protection_days - 1)
            base_requirement_g = sum(
                (
                    quantity
                    for demand_date, quantity in base_by_date.items()
                    if planning_as_of_date <= demand_date <= coverage_end
                ),
                start=Decimal("0"),
            )
            adjusted_requirement_g = base_requirement_g * policy.yield_factor
            average_daily_base_g = base_requirement_g / Decimal(protection_days)
            average_daily_adjusted_g = adjusted_requirement_g / Decimal(protection_days)
            safety_stock_g = average_daily_base_g * (item.min_safety_days or Decimal("0"))
            balance = _balance_through(
                start_date=planning_as_of_date,
                end_date=coverage_end,
                opening_stock_g=opening_stock_g,
                adjusted_demand_by_date=adjusted_by_date,
                purchase_orders=scoped_pos,
                item=item,
                planned_receipts={},
            )
            raw_order_g = max(
                Decimal("0"),
                safety_stock_g - balance.ending_g,
                -balance.minimum_g,
            )
            receipt_date = planning_as_of_date + timedelta(
                days=policy.lead_time_calendar_days
            )
            shelf_cap, max_cover_cap, capped_order_g = _constraint_caps(
                raw_order_g=raw_order_g,
                item=item,
                policy=policy,
                order_date=planning_as_of_date,
                receipt_date=receipt_date,
                average_daily_adjusted_g=average_daily_adjusted_g,
                adjusted_demand_by_date=adjusted_by_date,
                last_demand_date=last_demand_date,
            )
            order_unit_size_g, proposed_units, rounding_delta_g = _round_order(
                capped_order_g=capped_order_g, item=item, policy=policy
            )
            line = _build_line(
                run_id=run_id,
                sequence=1,
                location_id=location_id,
                item=item,
                policy=policy,
                schedule_rule_id=rule.delivery_rule_id,
                order_date=planning_as_of_date,
                receipt_date=receipt_date,
                coverage_start_date=planning_as_of_date,
                coverage_end_date=coverage_end,
                protection_days=protection_days,
                base_requirement_g=base_requirement_g,
                adjusted_requirement_g=adjusted_requirement_g,
                safety_stock_g=safety_stock_g,
                opening_stock_g=opening_stock_g,
                open_po_due_g=balance.open_po_due_g,
                raw_order_g=raw_order_g,
                shelf_life_cap_g=shelf_cap,
                max_cover_cap_g=max_cover_cap,
                capped_order_g=capped_order_g,
                order_unit_size_g=order_unit_size_g,
                proposed_order_units=proposed_units,
                rounding_delta_g=rounding_delta_g,
            )
            planning_lines.append(line)
            recommendation = _recommendation(line)
            if recommendation is not None:
                recommendations.append(recommendation)
            issues.extend(
                _constraint_issues(
                    line_ref=line.planning_line_id,
                    raw_order_g=raw_order_g,
                    shelf_life_cap_g=shelf_cap,
                    max_cover_cap_g=max_cover_cap,
                    capped_order_g=capped_order_g,
                    proposed_order_units=proposed_units,
                    order_unit_size_g=order_unit_size_g,
                    policy=policy,
                )
            )
            continue

        fresh_rules = [rule for rule in matching_rules if rule.delivery_weekday is not None]
        if not fresh_rules:
            issues.append(
                PlanningIssue(
                    code=ExceptionCode.MISSING_DELIVERY_RULE,
                    severity=Severity.WARNING,
                    dataset="delivery_rules",
                    record_ref=record_ref,
                    message="Fresh rules have no delivery weekday/service-window mapping.",
                    remedy="Complete the fresh Delivery_Rules fields and rerun.",
                )
            )
            continue

        cycles: list[tuple[date, DeliveryCoverageRule, tuple[date, ...]]] = []
        for delivery_date in _dates(planning_as_of_date, last_demand_date):
            for rule in fresh_rules:
                if delivery_date.weekday() != rule.delivery_weekday or not rule.is_active_on(delivery_date):
                    continue
                coverage_dates = tuple(
                    sorted(
                        _next_weekday_after(delivery_date, weekday)
                        for weekday in rule.covered_service_weekdays
                    )
                )
                if any(base_by_date.get(value, Decimal("0")) > 0 for value in coverage_dates):
                    cycles.append((delivery_date, rule, coverage_dates))
        cycles.sort(key=lambda row: (row[0], row[1].delivery_rule_id))

        coverage_count: dict[date, int] = defaultdict(int)
        planned_receipts: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
        for sequence, (receipt_date, rule, coverage_dates) in enumerate(cycles, start=1):
            for value in coverage_dates:
                if base_by_date.get(value, Decimal("0")) > 0:
                    coverage_count[value] += 1
            covered_demands = [base_by_date.get(value, Decimal("0")) for value in coverage_dates]
            base_requirement_g = sum(covered_demands, start=Decimal("0"))
            adjusted_requirement_g = base_requirement_g * policy.yield_factor
            coverage_day_count = max(1, len(coverage_dates))
            average_daily_base_g = base_requirement_g / Decimal(coverage_day_count)
            average_daily_adjusted_g = adjusted_requirement_g / Decimal(coverage_day_count)
            safety_stock_g = average_daily_base_g * (item.min_safety_days or Decimal("0"))
            coverage_end = max(coverage_dates)
            balance = _balance_through(
                start_date=planning_as_of_date,
                end_date=coverage_end,
                opening_stock_g=opening_stock_g,
                adjusted_demand_by_date=adjusted_by_date,
                purchase_orders=scoped_pos,
                item=item,
                planned_receipts=planned_receipts,
            )
            raw_order_g = max(
                Decimal("0"),
                safety_stock_g - balance.ending_g,
                -balance.minimum_g,
            )
            order_date = receipt_date - timedelta(days=policy.lead_time_calendar_days)
            shelf_cap, max_cover_cap, capped_order_g = _constraint_caps(
                raw_order_g=raw_order_g,
                item=item,
                policy=policy,
                order_date=order_date,
                receipt_date=receipt_date,
                average_daily_adjusted_g=average_daily_adjusted_g,
                adjusted_demand_by_date=adjusted_by_date,
                last_demand_date=last_demand_date,
            )
            order_unit_size_g, proposed_units, rounding_delta_g = _round_order(
                capped_order_g=capped_order_g, item=item, policy=policy
            )
            line = _build_line(
                run_id=run_id,
                sequence=sequence,
                location_id=location_id,
                item=item,
                policy=policy,
                schedule_rule_id=rule.delivery_rule_id,
                order_date=order_date,
                receipt_date=receipt_date,
                coverage_start_date=min(coverage_dates),
                coverage_end_date=coverage_end,
                protection_days=coverage_day_count,
                base_requirement_g=base_requirement_g,
                adjusted_requirement_g=adjusted_requirement_g,
                safety_stock_g=safety_stock_g,
                opening_stock_g=opening_stock_g,
                open_po_due_g=balance.open_po_due_g,
                raw_order_g=raw_order_g,
                shelf_life_cap_g=shelf_cap,
                max_cover_cap_g=max_cover_cap,
                capped_order_g=capped_order_g,
                order_unit_size_g=order_unit_size_g,
                proposed_order_units=proposed_units,
                rounding_delta_g=rounding_delta_g,
            )
            planning_lines.append(line)
            recommendation = _recommendation(line)
            if recommendation is not None:
                recommendations.append(recommendation)
                planned_receipts[receipt_date] += proposed_units * order_unit_size_g
            issues.extend(
                _constraint_issues(
                    line_ref=line.planning_line_id,
                    raw_order_g=raw_order_g,
                    shelf_life_cap_g=shelf_cap,
                    max_cover_cap_g=max_cover_cap,
                    capped_order_g=capped_order_g,
                    proposed_order_units=proposed_units,
                    order_unit_size_g=order_unit_size_g,
                    policy=policy,
                )
            )
            if order_date < planning_as_of_date and proposed_units > 0:
                issues.append(
                    PlanningIssue(
                        code=ExceptionCode.MISSED_ORDER_DATE,
                        severity=Severity.WARNING,
                        dataset="planning_recommendations",
                        record_ref=line.planning_line_id,
                        message=(
                            f"The calculated order date {order_date.isoformat()} is before the "
                            f"planning cutoff {planning_as_of_date.isoformat()}."
                        ),
                        remedy="Confirm an existing PO, expedite, transfer stock, substitute, or revise demand.",
                    )
                )

        for demand_date, quantity in sorted(base_by_date.items()):
            if quantity <= 0:
                continue
            count = coverage_count.get(demand_date, 0)
            if count != 1:
                issues.append(
                    PlanningIssue(
                        code=ExceptionCode.UNCOVERED_FRESH_DEMAND,
                        severity=Severity.WARNING,
                        dataset="delivery_rules",
                        record_ref=f"{record_ref},service_date={demand_date.isoformat()}",
                        message=(
                            f"Fresh demand date is covered by {count} delivery windows; expected exactly one."
                        ),
                        remedy="Correct the location-aware fresh delivery-to-service rules.",
                    )
                )

    planning_lines.sort(
        key=lambda line: (
            line.location_id,
            line.order_date,
            line.item_id,
            line.expected_delivery_date,
            line.planning_line_id,
        )
    )
    recommendations.sort(
        key=lambda row: (
            row.location_id,
            row.order_date,
            row.item_id,
            row.expected_delivery_date,
            row.recommendation_id,
        )
    )
    issues.sort(
        key=lambda issue: (
            issue.severity.value,
            issue.code.value,
            issue.dataset or "",
            issue.record_ref or "",
        )
    )
    return RecommendationEngineResult(
        planning_lines=tuple(planning_lines),
        recommendations=tuple(recommendations),
        issues=tuple(issues),
    )
