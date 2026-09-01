from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any

from supply_planning.domain.models import (
    InventorySnapshot,
    Item,
    ItemDemandDaily,
    Provenance,
    PurchaseOrderLine,
)


class InventoryEventKind(StrEnum):
    OPENING_BALANCE = "opening_balance"
    OPEN_PO_RECEIPT = "open_po_receipt"
    CANDIDATE_RECEIPT = "candidate_receipt"
    DEMAND = "demand"


class ActionableRiskStatus(StrEnum):
    AT_RISK = "at_risk"
    COVERED = "covered"
    NOT_EVALUATED = "not_evaluated"


class CoverageExtensionStatus(StrEnum):
    EXACT = "exact"
    LOWER_BOUND = "lower_bound"
    NOT_OBSERVABLE = "not_observable"


@dataclass(frozen=True, slots=True)
class CandidateReceipt:
    candidate_receipt_id: str
    location_id: str
    item_id: str
    receipt_date: date
    quantity_g: Decimal
    provenance: Provenance = Provenance.MANUAL

    def __post_init__(self) -> None:
        if not self.candidate_receipt_id.strip():
            raise ValueError("candidate_receipt_id must not be blank")
        if not self.location_id.strip():
            raise ValueError("location_id must not be blank")
        if not self.item_id.strip():
            raise ValueError("item_id must not be blank")
        if self.quantity_g < 0:
            raise ValueError("quantity_g must be greater than or equal to zero")


@dataclass(frozen=True, slots=True)
class InventoryEvent:
    event_date: date
    location_id: str
    item_id: str
    kind: InventoryEventKind
    quantity_g: Decimal
    source_ref: str
    provenance: Provenance

    @property
    def delta_g(self) -> Decimal:
        return -self.quantity_g if self.kind is InventoryEventKind.DEMAND else self.quantity_g

    def as_dict(self) -> dict[str, str]:
        return {
            "event_date": self.event_date.isoformat(),
            "location_id": self.location_id,
            "item_id": self.item_id,
            "kind": self.kind.value,
            "quantity_g": str(self.quantity_g),
            "delta_g": str(self.delta_g),
            "source_ref": self.source_ref,
            "provenance": self.provenance.value,
        }


@dataclass(frozen=True, slots=True)
class InventoryProjectionDay:
    projection_date: date
    opening_balance_g: Decimal
    demand_g: Decimal
    open_po_receipts_g: Decimal
    candidate_receipts_g: Decimal
    closing_balance_g: Decimal
    stockout_g: Decimal

    def as_dict(self) -> dict[str, str]:
        return {
            "projection_date": self.projection_date.isoformat(),
            "opening_balance_g": str(self.opening_balance_g),
            "demand_g": str(self.demand_g),
            "open_po_receipts_g": str(self.open_po_receipts_g),
            "candidate_receipts_g": str(self.candidate_receipts_g),
            "closing_balance_g": str(self.closing_balance_g),
            "stockout_g": str(self.stockout_g),
        }


@dataclass(frozen=True, slots=True)
class CoverageRunway:
    """Continuous calendar-day coverage before the first unmet-demand day.

    ``forecast_limited`` means the projection ended before a shortage was
    observed, so ``coverage_days`` is a lower bound rather than an exact
    depletion estimate.
    """

    coverage_days: int
    coverage_through_date: date | None
    first_uncovered_date: date | None
    forecast_limited: bool


@dataclass(frozen=True, slots=True)
class NettingResult:
    location_id: str
    item_id: str
    projection_start_date: date
    projection_end_date: date
    opening_on_hand_g: Decimal
    gross_requirement_g: Decimal
    open_po_due_g: Decimal
    net_requirement_g: Decimal
    candidate_receipt_g: Decimal
    overdue_open_po_g: Decimal
    open_po_after_horizon_g: Decimal
    open_po_after_final_demand_g: Decimal
    ending_projected_balance_g: Decimal
    minimum_projected_balance_g: Decimal
    first_stockout_date: date | None
    unavoidable_pre_candidate_stockout_g: Decimal
    events: tuple[InventoryEvent, ...]
    days: tuple[InventoryProjectionDay, ...]
    risk_horizon_end_date: date | None = None
    risk_evaluated_through_date: date | None = None
    risk_horizon_fully_observed: bool = False
    actionable_risk_status: ActionableRiskStatus = ActionableRiskStatus.NOT_EVALUATED
    first_stockout_within_horizon_date: date | None = None
    projected_balance_at_risk_horizon_end_g: Decimal | None = None
    max_stockout_within_horizon_g: Decimal = Decimal("0")
    coverage_contract_version: int | None = None
    on_hand_coverage_days: int | None = None
    on_hand_coverage_through_date: date | None = None
    on_hand_first_uncovered_date: date | None = None
    on_hand_coverage_forecast_limited: bool | None = None
    with_open_po_coverage_days: int | None = None
    with_open_po_coverage_through_date: date | None = None
    with_open_po_first_uncovered_date: date | None = None
    with_open_po_coverage_forecast_limited: bool | None = None
    with_proposal_coverage_days: int | None = None
    with_proposal_coverage_through_date: date | None = None
    with_proposal_first_uncovered_date: date | None = None
    with_proposal_coverage_forecast_limited: bool | None = None
    open_po_coverage_extension_days: int | None = None
    open_po_coverage_extension_status: CoverageExtensionStatus | None = None
    proposal_coverage_extension_days: int | None = None
    proposal_coverage_extension_status: CoverageExtensionStatus | None = None
    open_po_receipts_at_or_after_gap: bool | None = None
    proposal_receipts_at_or_after_gap: bool | None = None
    protection_horizon_days: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "location_id": self.location_id,
            "item_id": self.item_id,
            "projection_start_date": self.projection_start_date.isoformat(),
            "projection_end_date": self.projection_end_date.isoformat(),
            "opening_on_hand_g": str(self.opening_on_hand_g),
            "gross_requirement_g": str(self.gross_requirement_g),
            "open_po_due_g": str(self.open_po_due_g),
            "net_requirement_g": str(self.net_requirement_g),
            "candidate_receipt_g": str(self.candidate_receipt_g),
            "overdue_open_po_g": str(self.overdue_open_po_g),
            "open_po_after_horizon_g": str(self.open_po_after_horizon_g),
            "open_po_after_final_demand_g": str(self.open_po_after_final_demand_g),
            "ending_projected_balance_g": str(self.ending_projected_balance_g),
            "minimum_projected_balance_g": str(self.minimum_projected_balance_g),
            "first_stockout_date": (
                self.first_stockout_date.isoformat() if self.first_stockout_date else None
            ),
            "unavoidable_pre_candidate_stockout_g": str(
                self.unavoidable_pre_candidate_stockout_g
            ),
            "risk_horizon_end_date": (
                self.risk_horizon_end_date.isoformat()
                if self.risk_horizon_end_date
                else None
            ),
            "risk_evaluated_through_date": (
                self.risk_evaluated_through_date.isoformat()
                if self.risk_evaluated_through_date
                else None
            ),
            "risk_horizon_fully_observed": self.risk_horizon_fully_observed,
            "actionable_risk_status": self.actionable_risk_status.value,
            "first_stockout_within_horizon_date": (
                self.first_stockout_within_horizon_date.isoformat()
                if self.first_stockout_within_horizon_date
                else None
            ),
            "projected_balance_at_risk_horizon_end_g": (
                str(self.projected_balance_at_risk_horizon_end_g)
                if self.projected_balance_at_risk_horizon_end_g is not None
                else None
            ),
            "max_stockout_within_horizon_g": str(
                self.max_stockout_within_horizon_g
            ),
            "coverage_contract_version": self.coverage_contract_version,
            "on_hand_coverage_days": self.on_hand_coverage_days,
            "on_hand_coverage_through_date": (
                self.on_hand_coverage_through_date.isoformat()
                if self.on_hand_coverage_through_date
                else None
            ),
            "on_hand_first_uncovered_date": (
                self.on_hand_first_uncovered_date.isoformat()
                if self.on_hand_first_uncovered_date
                else None
            ),
            "on_hand_coverage_forecast_limited": (
                self.on_hand_coverage_forecast_limited
            ),
            "with_open_po_coverage_days": self.with_open_po_coverage_days,
            "with_open_po_coverage_through_date": (
                self.with_open_po_coverage_through_date.isoformat()
                if self.with_open_po_coverage_through_date
                else None
            ),
            "with_open_po_first_uncovered_date": (
                self.with_open_po_first_uncovered_date.isoformat()
                if self.with_open_po_first_uncovered_date
                else None
            ),
            "with_open_po_coverage_forecast_limited": (
                self.with_open_po_coverage_forecast_limited
            ),
            "with_proposal_coverage_days": self.with_proposal_coverage_days,
            "with_proposal_coverage_through_date": (
                self.with_proposal_coverage_through_date.isoformat()
                if self.with_proposal_coverage_through_date
                else None
            ),
            "with_proposal_first_uncovered_date": (
                self.with_proposal_first_uncovered_date.isoformat()
                if self.with_proposal_first_uncovered_date
                else None
            ),
            "with_proposal_coverage_forecast_limited": (
                self.with_proposal_coverage_forecast_limited
            ),
            "open_po_coverage_extension_days": self.open_po_coverage_extension_days,
            "open_po_coverage_extension_status": (
                self.open_po_coverage_extension_status.value
                if self.open_po_coverage_extension_status
                else None
            ),
            "proposal_coverage_extension_days": self.proposal_coverage_extension_days,
            "proposal_coverage_extension_status": (
                self.proposal_coverage_extension_status.value
                if self.proposal_coverage_extension_status
                else None
            ),
            "open_po_receipts_at_or_after_gap": (
                self.open_po_receipts_at_or_after_gap
            ),
            "proposal_receipts_at_or_after_gap": (
                self.proposal_receipts_at_or_after_gap
            ),
            "protection_horizon_days": self.protection_horizon_days,
            "events": [event.as_dict() for event in self.events],
            "days": [day.as_dict() for day in self.days],
        }


def classify_actionable_risk(
    result: NettingResult,
    *,
    risk_horizon_end_date: date | None,
) -> NettingResult:
    """Attach the policy-owned risk window without changing the full projection.

    A shortage after the current recommendation horizon remains visible through
    ``first_stockout_date`` but is not actionable for this run. When forecast
    evidence ends before the policy horizon, a no-stockout result is explicitly
    ``not_evaluated`` rather than incorrectly reported as covered.
    """

    if risk_horizon_end_date is None:
        return replace(
            result,
            risk_horizon_end_date=None,
            risk_evaluated_through_date=None,
            risk_horizon_fully_observed=False,
            actionable_risk_status=ActionableRiskStatus.NOT_EVALUATED,
            first_stockout_within_horizon_date=None,
            projected_balance_at_risk_horizon_end_g=None,
            max_stockout_within_horizon_g=Decimal("0"),
        )
    if risk_horizon_end_date < result.projection_start_date:
        raise ValueError("risk_horizon_end_date must not be before projection start")

    evaluated_through = min(risk_horizon_end_date, result.projection_end_date)
    scoped_days = tuple(
        day for day in result.days if day.projection_date <= evaluated_through
    )
    stockout_days = tuple(day for day in scoped_days if day.stockout_g > 0)
    fully_observed = result.projection_end_date >= risk_horizon_end_date
    if stockout_days:
        status = ActionableRiskStatus.AT_RISK
    elif fully_observed:
        status = ActionableRiskStatus.COVERED
    else:
        status = ActionableRiskStatus.NOT_EVALUATED
    balance_at_horizon = (
        next(
            (
                day.closing_balance_g
                for day in scoped_days
                if day.projection_date == risk_horizon_end_date
            ),
            None,
        )
        if fully_observed
        else None
    )
    return replace(
        result,
        risk_horizon_end_date=risk_horizon_end_date,
        risk_evaluated_through_date=evaluated_through,
        risk_horizon_fully_observed=fully_observed,
        actionable_risk_status=status,
        first_stockout_within_horizon_date=(
            stockout_days[0].projection_date if stockout_days else None
        ),
        projected_balance_at_risk_horizon_end_g=balance_at_horizon,
        max_stockout_within_horizon_g=max(
            (day.stockout_g for day in stockout_days),
            default=Decimal("0"),
        ),
    )


def continuous_coverage_runway(
    days: Iterable[InventoryProjectionDay],
) -> CoverageRunway:
    """Summarize event-aware continuous coverage without averaging demand.

    The first day with ``stockout_g > 0`` is not covered. A zero closing balance
    remains covered when all demand on that day was served. Projection rows must
    be one contiguous, ascending calendar-day series.
    """

    scoped_days = tuple(days)
    if not scoped_days:
        raise ValueError("coverage runway requires at least one projection day")
    for previous, current in zip(scoped_days, scoped_days[1:], strict=False):
        if current.projection_date != previous.projection_date + timedelta(days=1):
            raise ValueError("coverage runway requires contiguous ascending days")

    for index, day in enumerate(scoped_days):
        if day.stockout_g <= 0:
            continue
        return CoverageRunway(
            coverage_days=index,
            coverage_through_date=(
                scoped_days[index - 1].projection_date if index > 0 else None
            ),
            first_uncovered_date=day.projection_date,
            forecast_limited=False,
        )

    return CoverageRunway(
        coverage_days=len(scoped_days),
        coverage_through_date=scoped_days[-1].projection_date,
        first_uncovered_date=None,
        forecast_limited=True,
    )


def attach_supply_coverage(
    projected: NettingResult,
    *,
    on_hand_only: NettingResult,
    with_open_pos: NettingResult,
) -> NettingResult:
    """Attach three comparable runways to the final projected result.

    The scenarios are nested: usable stock only, stock plus accepted open POs,
    and the final projection including proposed receipts. Extensions are based
    on continuous service from the run date; a receipt after an earlier gap
    therefore cannot inflate the displayed runway.
    """

    scenarios = (on_hand_only, with_open_pos, projected)
    scope = (
        projected.location_id,
        projected.item_id,
        projected.projection_start_date,
        projected.projection_end_date,
    )
    for scenario in scenarios:
        if (
            scenario.location_id,
            scenario.item_id,
            scenario.projection_start_date,
            scenario.projection_end_date,
        ) != scope:
            raise ValueError("coverage scenarios must have the same scope")
        if tuple(day.demand_g for day in scenario.days) != tuple(
            day.demand_g for day in projected.days
        ):
            raise ValueError("coverage scenarios must use the same dated demand")
    if on_hand_only.open_po_due_g != 0 or on_hand_only.candidate_receipt_g != 0:
        raise ValueError("on-hand coverage scenario must not include receipts")
    if with_open_pos.candidate_receipt_g != 0:
        raise ValueError("open-PO coverage scenario must not include proposals")

    on_hand = continuous_coverage_runway(on_hand_only.days)
    open_po = continuous_coverage_runway(with_open_pos.days)
    proposal = continuous_coverage_runway(projected.days)
    if not (
        on_hand.coverage_days
        <= open_po.coverage_days
        <= proposal.coverage_days
    ):
        raise ValueError("non-negative receipts must not reduce continuous coverage")

    open_po_after_gap = (
        open_po.first_uncovered_date is not None
        and any(
            day.projection_date >= open_po.first_uncovered_date
            and day.open_po_receipts_g > 0
            for day in with_open_pos.days
        )
    )
    proposal_after_gap = (
        proposal.first_uncovered_date is not None
        and any(
            day.projection_date >= proposal.first_uncovered_date
            and day.candidate_receipts_g > 0
            for day in projected.days
        )
    )
    protection_horizon_days = (
        (projected.risk_horizon_end_date - projected.projection_start_date).days
        + 1
        if projected.risk_horizon_end_date is not None
        else None
    )

    def extension_status(
        baseline: CoverageRunway,
        augmented: CoverageRunway,
    ) -> CoverageExtensionStatus:
        if baseline.forecast_limited:
            return CoverageExtensionStatus.NOT_OBSERVABLE
        if augmented.forecast_limited:
            return CoverageExtensionStatus.LOWER_BOUND
        return CoverageExtensionStatus.EXACT

    return replace(
        projected,
        coverage_contract_version=1,
        on_hand_coverage_days=on_hand.coverage_days,
        on_hand_coverage_through_date=on_hand.coverage_through_date,
        on_hand_first_uncovered_date=on_hand.first_uncovered_date,
        on_hand_coverage_forecast_limited=on_hand.forecast_limited,
        with_open_po_coverage_days=open_po.coverage_days,
        with_open_po_coverage_through_date=open_po.coverage_through_date,
        with_open_po_first_uncovered_date=open_po.first_uncovered_date,
        with_open_po_coverage_forecast_limited=open_po.forecast_limited,
        with_proposal_coverage_days=proposal.coverage_days,
        with_proposal_coverage_through_date=proposal.coverage_through_date,
        with_proposal_first_uncovered_date=proposal.first_uncovered_date,
        with_proposal_coverage_forecast_limited=proposal.forecast_limited,
        open_po_coverage_extension_days=(
            open_po.coverage_days - on_hand.coverage_days
        ),
        open_po_coverage_extension_status=extension_status(on_hand, open_po),
        proposal_coverage_extension_days=(
            proposal.coverage_days - open_po.coverage_days
        ),
        proposal_coverage_extension_status=extension_status(open_po, proposal),
        open_po_receipts_at_or_after_gap=open_po_after_gap,
        proposal_receipts_at_or_after_gap=proposal_after_gap,
        protection_horizon_days=protection_horizon_days,
    )


def _dates(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _validate_scope(
    location_id: str,
    item_id: str,
    projection_start_date: date,
    projection_end_date: date,
    demands: tuple[ItemDemandDaily, ...],
    snapshot: InventorySnapshot,
    item: Item,
    purchase_orders: tuple[PurchaseOrderLine, ...],
    candidate_receipts: tuple[CandidateReceipt, ...],
) -> None:
    if projection_end_date < projection_start_date:
        raise ValueError("projection_end_date must not be before projection_start_date")
    if snapshot.location_id != location_id or snapshot.item_id != item_id:
        raise ValueError("inventory snapshot does not match the requested location/item")
    if snapshot.counted_at.date() > projection_start_date:
        raise ValueError("inventory snapshot is later than projection_start_date")
    if item.item_id != item_id:
        raise ValueError("item master does not match the requested item_id")

    for demand in demands:
        if demand.location_id != location_id or demand.item_id != item_id:
            raise ValueError("daily demand contains a different location/item")
        if not projection_start_date <= demand.service_date <= projection_end_date:
            raise ValueError("daily demand falls outside the requested projection horizon")
        if demand.required_g < 0:
            raise ValueError("daily demand required_g must be non-negative")

    for po in purchase_orders:
        if po.location_id != location_id or po.item_id != item_id:
            raise ValueError("purchase order contains a different location/item")

    for receipt in candidate_receipts:
        if receipt.location_id != location_id or receipt.item_id != item_id:
            raise ValueError("candidate receipt contains a different location/item")
        if not projection_start_date <= receipt.receipt_date <= projection_end_date:
            raise ValueError("candidate receipt falls outside the requested projection horizon")


def project_inventory(
    *,
    location_id: str,
    item_id: str,
    projection_start_date: date,
    projection_end_date: date,
    demands: Iterable[ItemDemandDaily],
    snapshot: InventorySnapshot,
    item: Item,
    purchase_orders: Iterable[PurchaseOrderLine],
    demand_provenance: Provenance,
    candidate_receipts: Iterable[CandidateReceipt] = (),
) -> NettingResult:
    """Project a dated balance without I/O or policy inference.

    The supplied snapshot is the opening balance for ``projection_start_date``.
    Receipts are available before daily demand on their receipt date. Open POs
    expected before the horizon are reported as overdue and are not silently
    counted as available; POs after the horizon are also reported separately.
    """

    scoped_demands = tuple(demands)
    scoped_pos = tuple(purchase_orders)
    scoped_candidates = tuple(candidate_receipts)
    _validate_scope(
        location_id,
        item_id,
        projection_start_date,
        projection_end_date,
        scoped_demands,
        snapshot,
        item,
        scoped_pos,
        scoped_candidates,
    )

    opening_on_hand_g = (
        snapshot.usable_on_hand_units * item.pack_size_g + snapshot.partial_pack_g
    )
    demand_by_date: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    demand_lines_by_date: dict[date, int] = defaultdict(int)
    for demand in scoped_demands:
        demand_by_date[demand.service_date] += demand.required_g
        demand_lines_by_date[demand.service_date] += demand.source_line_count

    positive_demand_dates = [day for day, quantity in demand_by_date.items() if quantity > 0]
    final_demand_date = max(positive_demand_dates, default=None)

    due_pos: list[PurchaseOrderLine] = []
    overdue_open_po_g = Decimal("0")
    open_po_after_horizon_g = Decimal("0")
    open_po_after_final_demand_g = Decimal("0")
    for po in scoped_pos:
        if not po.status.is_open or po.open_qty_units == 0:
            continue
        quantity_g = po.open_qty_units * item.pack_size_g
        receipt_date = po.expected_receipt_at.date()
        if final_demand_date is not None and receipt_date > final_demand_date:
            open_po_after_final_demand_g += quantity_g
        if receipt_date < projection_start_date:
            overdue_open_po_g += quantity_g
        elif receipt_date > projection_end_date:
            open_po_after_horizon_g += quantity_g
        else:
            due_pos.append(po)

    events: list[InventoryEvent] = [
        InventoryEvent(
            event_date=projection_start_date,
            location_id=location_id,
            item_id=item_id,
            kind=InventoryEventKind.OPENING_BALANCE,
            quantity_g=opening_on_hand_g,
            source_ref=f"inventory:{snapshot.counted_at.isoformat()}",
            provenance=snapshot.provenance,
        )
    ]
    for po in due_pos:
        events.append(
            InventoryEvent(
                event_date=po.expected_receipt_at.date(),
                location_id=location_id,
                item_id=item_id,
                kind=InventoryEventKind.OPEN_PO_RECEIPT,
                quantity_g=po.open_qty_units * item.pack_size_g,
                source_ref=f"po_line:{po.po_line_id}",
                provenance=po.provenance,
            )
        )
    for receipt in scoped_candidates:
        events.append(
            InventoryEvent(
                event_date=receipt.receipt_date,
                location_id=location_id,
                item_id=item_id,
                kind=InventoryEventKind.CANDIDATE_RECEIPT,
                quantity_g=receipt.quantity_g,
                source_ref=f"candidate:{receipt.candidate_receipt_id}",
                provenance=receipt.provenance,
            )
        )
    for demand_date in sorted(demand_by_date):
        events.append(
            InventoryEvent(
                event_date=demand_date,
                location_id=location_id,
                item_id=item_id,
                kind=InventoryEventKind.DEMAND,
                quantity_g=demand_by_date[demand_date],
                source_ref=f"demand_lines:{demand_lines_by_date[demand_date]}",
                provenance=demand_provenance,
            )
        )

    event_priority = {
        InventoryEventKind.OPENING_BALANCE: 0,
        InventoryEventKind.OPEN_PO_RECEIPT: 1,
        InventoryEventKind.CANDIDATE_RECEIPT: 2,
        InventoryEventKind.DEMAND: 3,
    }
    events.sort(key=lambda event: (event.event_date, event_priority[event.kind], event.source_ref))

    open_po_by_date: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    candidate_by_date: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    for event in events:
        if event.kind is InventoryEventKind.OPEN_PO_RECEIPT:
            open_po_by_date[event.event_date] += event.quantity_g
        elif event.kind is InventoryEventKind.CANDIDATE_RECEIPT:
            candidate_by_date[event.event_date] += event.quantity_g

    balance = opening_on_hand_g
    minimum_balance = opening_on_hand_g
    first_stockout_date: date | None = None
    days: list[InventoryProjectionDay] = []
    earliest_candidate_date = min(
        (receipt.receipt_date for receipt in scoped_candidates), default=None
    )
    unavoidable_pre_candidate_stockout_g = Decimal("0")
    for projection_date in _dates(projection_start_date, projection_end_date):
        opening_balance = balance
        open_po_receipts_g = open_po_by_date[projection_date]
        candidate_receipts_g = candidate_by_date[projection_date]
        demand_g = demand_by_date[projection_date]
        balance = opening_balance + open_po_receipts_g + candidate_receipts_g - demand_g
        minimum_balance = min(minimum_balance, balance)
        stockout_g = max(Decimal("0"), -balance)
        if stockout_g > 0 and first_stockout_date is None:
            first_stockout_date = projection_date
        if earliest_candidate_date is not None and projection_date < earliest_candidate_date:
            unavoidable_pre_candidate_stockout_g = max(
                unavoidable_pre_candidate_stockout_g, stockout_g
            )
        days.append(
            InventoryProjectionDay(
                projection_date=projection_date,
                opening_balance_g=opening_balance,
                demand_g=demand_g,
                open_po_receipts_g=open_po_receipts_g,
                candidate_receipts_g=candidate_receipts_g,
                closing_balance_g=balance,
                stockout_g=stockout_g,
            )
        )

    gross_requirement_g = sum(demand_by_date.values(), start=Decimal("0"))
    open_po_due_g = sum(open_po_by_date.values(), start=Decimal("0"))
    candidate_receipt_g = sum(candidate_by_date.values(), start=Decimal("0"))
    net_requirement_g = max(
        Decimal("0"), gross_requirement_g - opening_on_hand_g - open_po_due_g
    )
    return NettingResult(
        location_id=location_id,
        item_id=item_id,
        projection_start_date=projection_start_date,
        projection_end_date=projection_end_date,
        opening_on_hand_g=opening_on_hand_g,
        gross_requirement_g=gross_requirement_g,
        open_po_due_g=open_po_due_g,
        net_requirement_g=net_requirement_g,
        candidate_receipt_g=candidate_receipt_g,
        overdue_open_po_g=overdue_open_po_g,
        open_po_after_horizon_g=open_po_after_horizon_g,
        open_po_after_final_demand_g=open_po_after_final_demand_g,
        ending_projected_balance_g=balance,
        minimum_projected_balance_g=minimum_balance,
        first_stockout_date=first_stockout_date,
        unavoidable_pre_candidate_stockout_g=unavoidable_pre_candidate_stockout_g,
        events=tuple(events),
        days=tuple(days),
    )
