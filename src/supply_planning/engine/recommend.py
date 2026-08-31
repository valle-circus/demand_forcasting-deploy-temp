from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from supply_planning.domain.issues import ExceptionCode, PlanningIssue, Severity
from supply_planning.domain.models import (
    BindingConstraint,
    ConstraintStatus,
    DeliveryCoverageRule,
    InventorySnapshot,
    Item,
    ItemDemandDaily,
    ItemPlanningPolicy,
    PlanningLine,
    PlanningRecommendation,
    PurchaseOrderLine,
    RoundingDirection,
    ShelfLifeAnchor,
    ShelfLifeCapBasis,
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


@dataclass(frozen=True, slots=True)
class _ConstraintCaps:
    shelf_life_cap_g: Decimal | None
    max_cover_cap_g: Decimal | None
    capped_order_g: Decimal
    candidate_expiry_date: date | None
    shelf_life_cap_basis: ShelfLifeCapBasis
    forecast_through_expiry: bool | None
    max_cover_end_date: date | None
    forecast_through_max_cover: bool | None
    hard_cap_g: Decimal | None
    hard_cap_constraint: BindingConstraint


@dataclass(frozen=True, slots=True)
class _RoundedOrder:
    order_unit_size_g: Decimal
    proposed_order_units: Decimal
    rounding_delta_g: Decimal
    rounding_direction: RoundingDirection
    constraint_status: ConstraintStatus


def _dates(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _ceil_to_multiple(value: Decimal, multiple: Decimal) -> Decimal:
    if value <= 0:
        return Decimal("0")
    return (value / multiple).to_integral_value(rounding=ROUND_CEILING) * multiple


def _floor_to_multiple(value: Decimal, multiple: Decimal) -> Decimal:
    if value <= 0:
        return Decimal("0")
    return (value / multiple).to_integral_value(rounding=ROUND_FLOOR) * multiple


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


def _balance_for_candidate(
    *,
    start_date: date,
    end_date: date,
    candidate_receipt_date: date,
    opening_stock_g: Decimal,
    adjusted_demand_by_date: dict[date, Decimal],
    purchase_orders: tuple[PurchaseOrderLine, ...],
    item: Item,
    planned_receipts: dict[date, Decimal],
) -> _Balance:
    """Return the quantity a receipt can still influence.

    Unmet demand before the candidate arrives is discarded from the available
    stock position instead of being carried forward as backlog that the new
    receipt could appear to repair.
    """

    po_by_date: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    for po in purchase_orders:
        if po.status.is_open and start_date <= po.expected_receipt_at.date() <= end_date:
            po_by_date[po.expected_receipt_at.date()] += po.open_qty_units * item.pack_size_g

    balance = opening_stock_g
    minimum_after_receipt = Decimal("0")
    for value in _dates(start_date, end_date):
        balance += po_by_date[value] + planned_receipts.get(value, Decimal("0"))
        balance -= adjusted_demand_by_date.get(value, Decimal("0"))
        if value < candidate_receipt_date:
            balance = max(Decimal("0"), balance)
        else:
            minimum_after_receipt = min(minimum_after_receipt, balance)
    return _Balance(
        ending_g=balance,
        minimum_g=minimum_after_receipt,
        open_po_due_g=sum(po_by_date.values(), start=Decimal("0")),
    )


def _other_receipts_by_date(
    *,
    start_date: date,
    end_date: date,
    purchase_orders: tuple[PurchaseOrderLine, ...],
    item: Item,
    planned_receipts: dict[date, Decimal],
) -> dict[date, Decimal]:
    receipts: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    for po in purchase_orders:
        receipt_date = po.expected_receipt_at.date()
        if po.status.is_open and start_date <= receipt_date <= end_date:
            receipts[receipt_date] += po.open_qty_units * item.pack_size_g
    for receipt_date, quantity_g in planned_receipts.items():
        if start_date <= receipt_date <= end_date:
            receipts[receipt_date] += quantity_g
    return receipts


def _candidate_absorption(
    *,
    start_date: date,
    receipt_date: date,
    window_end_date: date,
    opening_stock_g: Decimal,
    adjusted_demand_by_date: dict[date, Decimal],
    purchase_orders: tuple[PurchaseOrderLine, ...],
    item: Item,
    planned_receipts: dict[date, Decimal],
    candidate_quantity_g: Decimal | None = None,
    final_day_demand_factor: Decimal = Decimal("1"),
) -> tuple[Decimal, Decimal | None]:
    """Return candidate demand capacity and optional residual at window end.

    Without lot-level MHD data, other supply is consumed first. Daily unmet
    demand is not carried into a later date, so neither a candidate nor a later
    PO can retroactively satisfy an earlier shortage.
    """

    if window_end_date < receipt_date:
        return Decimal("0"), candidate_quantity_g
    receipts = _other_receipts_by_date(
        start_date=start_date,
        end_date=window_end_date,
        purchase_orders=purchase_orders,
        item=item,
        planned_receipts=planned_receipts,
    )
    other_balance = opening_stock_g
    candidate_balance = candidate_quantity_g
    capacity_g = Decimal("0")
    for value in _dates(start_date, window_end_date):
        other_balance += receipts.get(value, Decimal("0"))
        demand_g = adjusted_demand_by_date.get(value, Decimal("0"))
        if value == window_end_date:
            demand_g *= final_day_demand_factor
        if value < receipt_date:
            other_balance = max(Decimal("0"), other_balance - demand_g)
            continue
        other_used_g = min(other_balance, demand_g)
        other_balance -= other_used_g
        candidate_demand_g = demand_g - other_used_g
        capacity_g += candidate_demand_g
        if candidate_balance is not None:
            candidate_used_g = min(candidate_balance, candidate_demand_g)
            candidate_balance -= candidate_used_g
    return capacity_g, candidate_balance


def _max_cover_window(
    receipt_date: date, max_cover_days: Decimal
) -> tuple[date, Decimal]:
    whole_days = int(max_cover_days.to_integral_value(rounding=ROUND_FLOOR))
    partial_day = max_cover_days - Decimal(whole_days)
    if partial_day > 0:
        return receipt_date + timedelta(days=whole_days), partial_day
    if whole_days <= 0:
        return receipt_date, Decimal("0")
    return receipt_date + timedelta(days=whole_days - 1), Decimal("1")


def _constraint_caps(
    *,
    raw_order_g: Decimal,
    item: Item,
    policy: ItemPlanningPolicy,
    order_date: date,
    receipt_date: date,
    planning_start_date: date,
    opening_stock_g: Decimal,
    purchase_orders: tuple[PurchaseOrderLine, ...],
    planned_receipts: dict[date, Decimal],
    adjusted_demand_by_date: dict[date, Decimal],
    forecast_end_date: date,
) -> _ConstraintCaps:
    shelf_life_cap_g: Decimal | None = None
    expiry_date: date | None = None
    shelf_life_cap_basis = ShelfLifeCapBasis.NOT_CONFIGURED
    forecast_through_expiry: bool | None = None
    if item.shelf_life_days is not None and policy.shelf_life_anchor is not None:
        if policy.shelf_life_anchor is ShelfLifeAnchor.ORDER_DATE:
            expiry_date = order_date + timedelta(days=item.shelf_life_days - 1)
        elif policy.shelf_life_anchor is ShelfLifeAnchor.RECEIPT_DATE:
            expiry_date = receipt_date + timedelta(days=item.shelf_life_days - 1)
        if expiry_date is not None:
            shelf_life_cap_basis = ShelfLifeCapBasis.POLICY_APPROXIMATION
            forecast_through_expiry = forecast_end_date >= expiry_date
            shelf_window_end = min(expiry_date, forecast_end_date)
            shelf_life_cap_g, _ = _candidate_absorption(
                start_date=planning_start_date,
                receipt_date=receipt_date,
                window_end_date=shelf_window_end,
                opening_stock_g=opening_stock_g,
                adjusted_demand_by_date=adjusted_demand_by_date,
                purchase_orders=purchase_orders,
                item=item,
                planned_receipts=planned_receipts,
            )

    max_cover_cap_g: Decimal | None = None
    max_cover_end_date: date | None = None
    forecast_through_max_cover: bool | None = None
    if item.max_cover_days is not None:
        max_cover_end_date, final_day_factor = _max_cover_window(
            receipt_date, item.max_cover_days
        )
        forecast_through_max_cover = forecast_end_date >= max_cover_end_date
        max_cover_window_end = min(max_cover_end_date, forecast_end_date)
        max_cover_cap_g, _ = _candidate_absorption(
            start_date=planning_start_date,
            receipt_date=receipt_date,
            window_end_date=max_cover_window_end,
            opening_stock_g=opening_stock_g,
            adjusted_demand_by_date=adjusted_demand_by_date,
            purchase_orders=purchase_orders,
            item=item,
            planned_receipts=planned_receipts,
            final_day_demand_factor=(
                final_day_factor
                if max_cover_window_end == max_cover_end_date
                else Decimal("1")
            ),
        )

    capped = max(Decimal("0"), raw_order_g)
    if shelf_life_cap_g is not None:
        capped = min(capped, shelf_life_cap_g)
    if max_cover_cap_g is not None:
        capped = min(capped, max_cover_cap_g)
    hard_cap_g = min(
        (cap for cap in (shelf_life_cap_g, max_cover_cap_g) if cap is not None),
        default=None,
    )
    if hard_cap_g is None:
        hard_cap_constraint = BindingConstraint.NONE
    elif shelf_life_cap_g == hard_cap_g and max_cover_cap_g == hard_cap_g:
        hard_cap_constraint = BindingConstraint.SHELF_LIFE_AND_MAX_COVER
    elif shelf_life_cap_g == hard_cap_g:
        hard_cap_constraint = BindingConstraint.SHELF_LIFE
    else:
        hard_cap_constraint = BindingConstraint.MAX_COVER
    return _ConstraintCaps(
        shelf_life_cap_g=shelf_life_cap_g,
        max_cover_cap_g=max_cover_cap_g,
        capped_order_g=capped,
        candidate_expiry_date=expiry_date,
        shelf_life_cap_basis=shelf_life_cap_basis,
        forecast_through_expiry=forecast_through_expiry,
        max_cover_end_date=max_cover_end_date,
        forecast_through_max_cover=forecast_through_max_cover,
        hard_cap_g=hard_cap_g,
        hard_cap_constraint=hard_cap_constraint,
    )


def _round_order(
    *,
    capped_order_g: Decimal,
    item: Item,
    policy: ItemPlanningPolicy,
    hard_cap_g: Decimal | None,
    raw_order_g: Decimal,
) -> _RoundedOrder:
    order_unit_size_g = item.pack_size_g * policy.packs_per_order_unit
    if capped_order_g <= 0:
        return _RoundedOrder(
            order_unit_size_g,
            Decimal("0"),
            Decimal("0"),
            RoundingDirection.NONE,
            (
                ConstraintStatus.NO_SAFE_POSITIVE_ORDER
                if raw_order_g > 0 and hard_cap_g is not None
                else ConstraintStatus.FEASIBLE
            ),
        )
    exact_units = capped_order_g / order_unit_size_g
    units_after_moq = max(exact_units, policy.moq_order_units)
    rounded_up_units = _ceil_to_multiple(
        units_after_moq, policy.case_multiple_order_units
    )
    proposed_units = rounded_up_units
    status = ConstraintStatus.FEASIBLE
    if (
        hard_cap_g is not None
        and rounded_up_units * order_unit_size_g > hard_cap_g
    ):
        safe_units = _floor_to_multiple(
            hard_cap_g / order_unit_size_g,
            policy.case_multiple_order_units,
        )
        if safe_units > 0 and safe_units >= policy.moq_order_units:
            proposed_units = safe_units
            status = ConstraintStatus.REDUCED_TO_SAFE_MULTIPLE
        else:
            proposed_units = Decimal("0")
            status = ConstraintStatus.NO_SAFE_POSITIVE_ORDER
    proposed_g = proposed_units * order_unit_size_g
    if proposed_g > capped_order_g:
        direction = RoundingDirection.UP
    elif proposed_g < capped_order_g:
        direction = RoundingDirection.DOWN
    else:
        direction = RoundingDirection.NONE
    return _RoundedOrder(
        order_unit_size_g=order_unit_size_g,
        proposed_order_units=proposed_units,
        rounding_delta_g=abs(proposed_g - capped_order_g),
        rounding_direction=direction,
        constraint_status=status,
    )


def _constraint_issues(
    *,
    line: PlanningLine,
    policy: ItemPlanningPolicy,
) -> list[PlanningIssue]:
    issues: list[PlanningIssue] = []
    if (
        line.shelf_life_cap_g is not None
        and line.shelf_life_cap_g < line.raw_order_g
    ):
        issues.append(
            PlanningIssue(
                code=ExceptionCode.SHELF_LIFE_CAP_BINDING,
                severity=Severity.WARNING,
                dataset="planning_recommendations",
                record_ref=line.planning_line_id,
                message=(
                    f"Supply-position-aware shelf-life cap reduced raw order from "
                    f"{line.raw_order_g} g to at most {line.shelf_life_cap_g} g."
                ),
                remedy=(
                    "Review projected competing stock, forecast coverage, shelf life, "
                    "delivery frequency, or substitution."
                ),
            )
        )
    if line.forecast_through_expiry is False:
        issues.append(
            PlanningIssue(
                code=ExceptionCode.SHELF_LIFE_COVERAGE_INCOMPLETE,
                severity=Severity.WARNING,
                dataset="planning_recommendations",
                record_ref=line.planning_line_id,
                message=(
                    f"Forecast evidence ends before estimated candidate expiry "
                    f"{line.candidate_expiry_date}. The shelf-life cap uses only "
                    "known demand and is conservative, but expiry safety is not fully evidenced."
                ),
                remedy="Upload forecast coverage through expiry or review the proposal manually.",
            )
        )
    if line.max_cover_cap_g is not None and line.max_cover_cap_g < line.raw_order_g:
        issues.append(
            PlanningIssue(
                code=ExceptionCode.MAX_COVER_CAP_BINDING,
                severity=Severity.WARNING,
                dataset="planning_recommendations",
                record_ref=line.planning_line_id,
                message=(
                    f"Supply-position-aware max-cover cap reduced raw order from "
                    f"{line.raw_order_g} g to at most {line.max_cover_cap_g} g."
                ),
                remedy="Review the approved max-cover rule or accept the visible shortage risk.",
            )
        )
    if line.forecast_through_max_cover is False:
        issues.append(
            PlanningIssue(
                code=ExceptionCode.MAX_COVER_COVERAGE_INCOMPLETE,
                severity=Severity.WARNING,
                dataset="planning_recommendations",
                record_ref=line.planning_line_id,
                message=(
                    f"Forecast evidence ends before max-cover end "
                    f"{line.max_cover_end_date}. The cap uses only known demand."
                ),
                remedy="Upload forecast coverage through the max-cover window.",
            )
        )
    if line.capped_order_g > 0:
        exact_units = line.capped_order_g / line.order_unit_size_g
        if (
            exact_units < policy.moq_order_units
            and line.proposed_order_units > exact_units
        ):
            issues.append(
                PlanningIssue(
                    code=ExceptionCode.MOQ_INFLATED_ORDER,
                    severity=Severity.WARNING,
                    dataset="planning_recommendations",
                    record_ref=line.planning_line_id,
                    message=(
                        f"MOQ increased {exact_units} order units to "
                        f"{policy.moq_order_units}."
                    ),
                    remedy="Confirm the supplier MOQ and accept or revise the resulting cover.",
                )
            )
        if line.rounding_direction is RoundingDirection.UP:
            issues.append(
                PlanningIssue(
                    code=ExceptionCode.CASE_ROUNDING_APPLIED,
                    severity=Severity.INFO,
                    dataset="planning_recommendations",
                    record_ref=line.planning_line_id,
                    message=(
                        f"Final order-unit/case rounding increased the proposal to "
                        f"{line.proposed_order_units} order units."
                    ),
                    remedy="No action unless pack or case metadata is incorrect.",
                )
            )
    if line.constraint_status is ConstraintStatus.REDUCED_TO_SAFE_MULTIPLE:
        issues.append(
            PlanningIssue(
                code=ExceptionCode.INFEASIBLE_ORDER_CONSTRAINTS,
                severity=Severity.WARNING,
                dataset="planning_recommendations",
                record_ref=line.planning_line_id,
                message=(
                    "Rounding the target upward would exceed a hard shelf-life or "
                    "max-cover cap, so the proposal was reduced to the largest safe "
                    f"purchasable multiple ({line.proposed_order_units} order units)."
                ),
                remedy="Review the residual shortage or change an approved pack/policy rule.",
            )
        )
    elif line.constraint_status is ConstraintStatus.NO_SAFE_POSITIVE_ORDER:
        issues.append(
            PlanningIssue(
                code=ExceptionCode.INFEASIBLE_ORDER_CONSTRAINTS,
                severity=Severity.WARNING,
                dataset="planning_recommendations",
                record_ref=line.planning_line_id,
                message=(
                    "No positive MOQ/case multiple fits within the hard shelf-life "
                    "or max-cover cap, so no ordinary proposal was emitted."
                ),
                remedy=(
                    "Make a manual exception decision, revise the pack/MOQ rule, "
                    "split the delivery, expedite, or substitute."
                ),
            )
        )
    if (
        line.projected_candidate_residual_at_expiry_g is not None
        and line.projected_candidate_residual_at_expiry_g > 0
    ):
        issues.append(
            PlanningIssue(
                code=ExceptionCode.INFEASIBLE_ORDER_CONSTRAINTS,
                severity=Severity.WARNING,
                dataset="planning_recommendations",
                record_ref=line.planning_line_id,
                message=(
                    f"The candidate retains "
                    f"{line.projected_candidate_residual_at_expiry_g} g at estimated expiry."
                ),
                remedy="Do not treat this as a normal safe proposal; revise the constraint inputs.",
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
    rounding_direction: RoundingDirection,
    constraint_status: ConstraintStatus,
    binding_constraint: BindingConstraint,
    candidate_expiry_date: date | None,
    shelf_life_cap_basis: ShelfLifeCapBasis,
    forecast_through_expiry: bool | None,
    projected_candidate_residual_at_expiry_g: Decimal | None,
    max_cover_end_date: date | None,
    forecast_through_max_cover: bool | None,
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
        candidate_expiry_date=candidate_expiry_date,
        shelf_life_cap_basis=shelf_life_cap_basis,
        forecast_through_expiry=forecast_through_expiry,
        projected_candidate_residual_at_expiry_g=(
            projected_candidate_residual_at_expiry_g
        ),
        max_cover_end_date=max_cover_end_date,
        forecast_through_max_cover=forecast_through_max_cover,
        binding_constraint=binding_constraint,
        constraint_status=constraint_status,
        rounding_direction=rounding_direction,
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
    forecast_end_by_location: dict[str, date] = {}
    for demand in demands:
        current = forecast_end_by_location.get(demand.location_id)
        if current is None or demand.service_date > current:
            forecast_end_by_location[demand.location_id] = demand.service_date

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
                    message=(
                        "No item planning policy exists, so no order recommendation "
                        "was calculated."
                    ),
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
                    remedy=(
                        "Review the highlighted Items fields and issue an approved "
                        "template version."
                    ),
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
        forecast_end_date = forecast_end_by_location[location_id]
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
                    message=(
                        "No active location/storage delivery rule exists; no "
                        "recommendation was calculated."
                    ),
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
            safety_stock_g = average_daily_base_g * (item.min_safety_days or Decimal("0"))
            receipt_date = planning_as_of_date + timedelta(
                days=policy.lead_time_calendar_days
            )
            balance = _balance_for_candidate(
                start_date=planning_as_of_date,
                end_date=coverage_end,
                candidate_receipt_date=receipt_date,
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
            caps = _constraint_caps(
                raw_order_g=raw_order_g,
                item=item,
                policy=policy,
                order_date=planning_as_of_date,
                receipt_date=receipt_date,
                planning_start_date=planning_as_of_date,
                opening_stock_g=opening_stock_g,
                purchase_orders=scoped_pos,
                planned_receipts={},
                adjusted_demand_by_date=adjusted_by_date,
                forecast_end_date=forecast_end_date,
            )
            rounded = _round_order(
                capped_order_g=caps.capped_order_g,
                item=item,
                policy=policy,
                hard_cap_g=caps.hard_cap_g,
                raw_order_g=raw_order_g,
            )
            projected_residual_at_expiry_g: Decimal | None = None
            if caps.candidate_expiry_date is not None:
                _, projected_residual_at_expiry_g = _candidate_absorption(
                    start_date=planning_as_of_date,
                    receipt_date=receipt_date,
                    window_end_date=min(
                        caps.candidate_expiry_date, forecast_end_date
                    ),
                    opening_stock_g=opening_stock_g,
                    adjusted_demand_by_date=adjusted_by_date,
                    purchase_orders=scoped_pos,
                    item=item,
                    planned_receipts={},
                    candidate_quantity_g=(
                        rounded.proposed_order_units * rounded.order_unit_size_g
                    ),
                )
            binding_constraint = (
                caps.hard_cap_constraint
                if caps.capped_order_g < raw_order_g
                or rounded.constraint_status is not ConstraintStatus.FEASIBLE
                else BindingConstraint.NONE
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
                shelf_life_cap_g=caps.shelf_life_cap_g,
                max_cover_cap_g=caps.max_cover_cap_g,
                capped_order_g=caps.capped_order_g,
                order_unit_size_g=rounded.order_unit_size_g,
                proposed_order_units=rounded.proposed_order_units,
                rounding_delta_g=rounded.rounding_delta_g,
                rounding_direction=rounded.rounding_direction,
                constraint_status=rounded.constraint_status,
                binding_constraint=binding_constraint,
                candidate_expiry_date=caps.candidate_expiry_date,
                shelf_life_cap_basis=caps.shelf_life_cap_basis,
                forecast_through_expiry=caps.forecast_through_expiry,
                projected_candidate_residual_at_expiry_g=(
                    projected_residual_at_expiry_g
                ),
                max_cover_end_date=caps.max_cover_end_date,
                forecast_through_max_cover=caps.forecast_through_max_cover,
            )
            planning_lines.append(line)
            recommendation = _recommendation(line)
            if recommendation is not None:
                recommendations.append(recommendation)
            issues.extend(
                _constraint_issues(
                    line=line,
                    policy=policy,
                )
            )
            if forecast_end_date < coverage_end:
                issues.append(
                    PlanningIssue(
                        code=ExceptionCode.RECOMMENDATION_HORIZON_COVERAGE_INCOMPLETE,
                        severity=Severity.WARNING,
                        dataset="forecast_daily",
                        record_ref=line.planning_line_id,
                        message=(
                            f"Forecast evidence ends on {forecast_end_date.isoformat()}, "
                            f"before recommendation horizon end {coverage_end.isoformat()}."
                        ),
                        remedy="Upload forecast coverage through the item protection horizon.",
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
        for delivery_date in _dates(planning_as_of_date, forecast_end_date):
            for rule in fresh_rules:
                if (
                    delivery_date.weekday() != rule.delivery_weekday
                    or not rule.is_active_on(delivery_date)
                ):
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
            safety_stock_g = average_daily_base_g * (item.min_safety_days or Decimal("0"))
            coverage_end = max(coverage_dates)
            balance = _balance_for_candidate(
                start_date=planning_as_of_date,
                end_date=coverage_end,
                candidate_receipt_date=receipt_date,
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
            caps = _constraint_caps(
                raw_order_g=raw_order_g,
                item=item,
                policy=policy,
                order_date=order_date,
                receipt_date=receipt_date,
                planning_start_date=planning_as_of_date,
                opening_stock_g=opening_stock_g,
                purchase_orders=scoped_pos,
                planned_receipts=planned_receipts,
                adjusted_demand_by_date=adjusted_by_date,
                forecast_end_date=forecast_end_date,
            )
            rounded = _round_order(
                capped_order_g=caps.capped_order_g,
                item=item,
                policy=policy,
                hard_cap_g=caps.hard_cap_g,
                raw_order_g=raw_order_g,
            )
            projected_residual_at_expiry_g = None
            if caps.candidate_expiry_date is not None:
                _, projected_residual_at_expiry_g = _candidate_absorption(
                    start_date=planning_as_of_date,
                    receipt_date=receipt_date,
                    window_end_date=min(
                        caps.candidate_expiry_date, forecast_end_date
                    ),
                    opening_stock_g=opening_stock_g,
                    adjusted_demand_by_date=adjusted_by_date,
                    purchase_orders=scoped_pos,
                    item=item,
                    planned_receipts=planned_receipts,
                    candidate_quantity_g=(
                        rounded.proposed_order_units * rounded.order_unit_size_g
                    ),
                )
            binding_constraint = (
                caps.hard_cap_constraint
                if caps.capped_order_g < raw_order_g
                or rounded.constraint_status is not ConstraintStatus.FEASIBLE
                else BindingConstraint.NONE
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
                shelf_life_cap_g=caps.shelf_life_cap_g,
                max_cover_cap_g=caps.max_cover_cap_g,
                capped_order_g=caps.capped_order_g,
                order_unit_size_g=rounded.order_unit_size_g,
                proposed_order_units=rounded.proposed_order_units,
                rounding_delta_g=rounded.rounding_delta_g,
                rounding_direction=rounded.rounding_direction,
                constraint_status=rounded.constraint_status,
                binding_constraint=binding_constraint,
                candidate_expiry_date=caps.candidate_expiry_date,
                shelf_life_cap_basis=caps.shelf_life_cap_basis,
                forecast_through_expiry=caps.forecast_through_expiry,
                projected_candidate_residual_at_expiry_g=(
                    projected_residual_at_expiry_g
                ),
                max_cover_end_date=caps.max_cover_end_date,
                forecast_through_max_cover=caps.forecast_through_max_cover,
            )
            planning_lines.append(line)
            recommendation = _recommendation(line)
            if recommendation is not None:
                recommendations.append(recommendation)
                planned_receipts[receipt_date] += (
                    rounded.proposed_order_units * rounded.order_unit_size_g
                )
            issues.extend(
                _constraint_issues(
                    line=line,
                    policy=policy,
                )
            )
            if order_date < planning_as_of_date and rounded.proposed_order_units > 0:
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
                        remedy=(
                            "Confirm an existing PO, expedite, transfer stock, "
                            "substitute, or revise demand."
                        ),
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
                            f"Fresh demand date is covered by {count} delivery "
                            "windows; expected exactly one."
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
