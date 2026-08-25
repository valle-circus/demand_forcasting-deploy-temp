from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum

from supply_planning.domain.issues import ExceptionCode, Severity


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")


def _require_non_negative(value: Decimal, field_name: str) -> None:
    if value < 0:
        raise ValueError(f"{field_name} must be greater than or equal to zero")


def _require_positive(value: Decimal, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero")


def _require_aware_datetime(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone offset")


class StorageClass(StrEnum):
    TK = "TK"
    KUEHL = "Kuehl"
    RT = "RT"
    FRISCH = "Frisch"


class Provenance(StrEnum):
    OBSERVED = "observed"
    MANUAL = "manual"
    POLICY_DEFAULT = "policy_default"
    EMPTY_PLACEHOLDER = "empty_placeholder"
    UNAVAILABLE = "unavailable"


class RunMode(StrEnum):
    FIXTURE = "fixture"
    SCENARIO = "scenario"
    SHADOW = "shadow"
    OPERATIONAL = "operational"


class RunStatus(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class ProposalStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class PurchaseOrderStatus(StrEnum):
    OPEN = "open"
    CONFIRMED = "confirmed"
    PARTIALLY_RECEIVED = "partially_received"
    CLOSED = "closed"
    CANCELLED = "cancelled"

    @property
    def is_open(self) -> bool:
        return self in {
            PurchaseOrderStatus.OPEN,
            PurchaseOrderStatus.CONFIRMED,
            PurchaseOrderStatus.PARTIALLY_RECEIVED,
        }


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class Location:
    location_id: str
    location_name: str
    timezone: str
    active: bool = True

    def __post_init__(self) -> None:
        _require_text(self.location_id, "location_id")
        _require_text(self.location_name, "location_name")
        _require_text(self.timezone, "timezone")


@dataclass(frozen=True, slots=True)
class ForecastDaily:
    location_id: str
    dish_id: str
    service_date: date
    forecast_portions: Decimal
    forecast_sigma: Decimal | None = None
    forecast_version: str = "manual"
    provenance: Provenance = Provenance.MANUAL

    def __post_init__(self) -> None:
        _require_text(self.location_id, "location_id")
        _require_text(self.dish_id, "dish_id")
        _require_text(self.forecast_version, "forecast_version")
        _require_non_negative(self.forecast_portions, "forecast_portions")
        if self.forecast_sigma is not None:
            _require_non_negative(self.forecast_sigma, "forecast_sigma")


@dataclass(frozen=True, slots=True)
class MenuCalendarEntry:
    location_id: str
    dish_id: str
    service_date: date
    menu_version: str
    active: bool = True
    provenance: Provenance = Provenance.MANUAL

    def __post_init__(self) -> None:
        _require_text(self.location_id, "location_id")
        _require_text(self.dish_id, "dish_id")
        _require_text(self.menu_version, "menu_version")


@dataclass(frozen=True, slots=True)
class BomLine:
    bom_line_id: str
    dish_id: str
    silo_id: str
    item_id: str
    grams_per_portion: Decimal
    effective_from: date
    effective_to: date | None = None
    provenance: Provenance = Provenance.MANUAL

    def __post_init__(self) -> None:
        for field_name in ("bom_line_id", "dish_id", "silo_id", "item_id"):
            _require_text(getattr(self, field_name), field_name)
        _require_positive(self.grams_per_portion, "grams_per_portion")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not be before effective_from")

    def is_active_on(self, service_date: date) -> bool:
        return self.effective_from <= service_date and (
            self.effective_to is None or service_date <= self.effective_to
        )


@dataclass(frozen=True, slots=True)
class Item:
    item_id: str
    item_name: str
    storage_class: StorageClass
    pack_size_g: Decimal
    shelf_life_days: int | None = None
    min_safety_days: Decimal | None = None
    max_cover_days: Decimal | None = None
    last_order_date_offset_days: int = 0
    pipeline_cancellable: bool = False
    active: bool = True
    provenance: Provenance = Provenance.MANUAL

    def __post_init__(self) -> None:
        _require_text(self.item_id, "item_id")
        _require_text(self.item_name, "item_name")
        _require_positive(self.pack_size_g, "pack_size_g")
        if self.shelf_life_days is not None and self.shelf_life_days <= 0:
            raise ValueError("shelf_life_days must be greater than zero when supplied")
        if self.min_safety_days is not None:
            _require_non_negative(self.min_safety_days, "min_safety_days")
        if self.max_cover_days is not None:
            _require_positive(self.max_cover_days, "max_cover_days")
        if self.last_order_date_offset_days < 0:
            raise ValueError(
                "last_order_date_offset_days must be greater than or equal to zero"
            )


@dataclass(frozen=True, slots=True)
class Supplier:
    supplier_id: str
    supplier_name: str
    timezone: str
    default_production_lead_days: int | None = None
    default_transport_lead_days: int | None = None
    active: bool = True

    def __post_init__(self) -> None:
        _require_text(self.supplier_id, "supplier_id")
        _require_text(self.supplier_name, "supplier_name")
        _require_text(self.timezone, "timezone")
        for name in ("default_production_lead_days", "default_transport_lead_days"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must be greater than or equal to zero")


@dataclass(frozen=True, slots=True)
class SupplierItem:
    supplier_id: str
    item_id: str
    supplier_item_id: str | None = None
    production_lead_days: int | None = None
    transport_lead_days: int | None = None
    moq_units: Decimal = Decimal("0")
    case_size_units: Decimal = Decimal("1")
    order_cutoff_local: time | None = None
    active: bool = True
    provenance: Provenance = Provenance.MANUAL

    def __post_init__(self) -> None:
        _require_non_negative(self.moq_units, "moq_units")
        _require_positive(self.case_size_units, "case_size_units")
        for name in ("production_lead_days", "transport_lead_days"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must be greater than or equal to zero")


@dataclass(frozen=True, slots=True)
class SupplierCalendarRule:
    supplier_calendar_id: str
    supplier_id: str
    location_id: str
    order_weekday: int
    order_cutoff_local: time
    delivery_weekday: int
    active: bool = True

    def __post_init__(self) -> None:
        for field_name in ("supplier_calendar_id", "supplier_id", "location_id"):
            _require_text(getattr(self, field_name), field_name)
        for field_name in ("order_weekday", "delivery_weekday"):
            value = getattr(self, field_name)
            if value < 0 or value > 6:
                raise ValueError(f"{field_name} must use Python weekday values 0 through 6")


@dataclass(frozen=True, slots=True)
class InventorySnapshot:
    location_id: str
    item_id: str
    counted_at: datetime
    usable_on_hand_units: Decimal
    partial_pack_g: Decimal = Decimal("0")
    provenance: Provenance = Provenance.MANUAL

    def __post_init__(self) -> None:
        _require_text(self.location_id, "location_id")
        _require_text(self.item_id, "item_id")
        _require_aware_datetime(self.counted_at, "counted_at")
        _require_non_negative(self.usable_on_hand_units, "usable_on_hand_units")
        _require_non_negative(self.partial_pack_g, "partial_pack_g")


@dataclass(frozen=True, slots=True)
class PurchaseOrderLine:
    po_id: str
    po_line_id: str
    location_id: str
    supplier_id: str
    item_id: str
    ordered_at: datetime
    expected_receipt_at: datetime
    open_qty_units: Decimal
    status: PurchaseOrderStatus
    provenance: Provenance = Provenance.OBSERVED

    def __post_init__(self) -> None:
        for field_name in ("po_id", "po_line_id", "location_id", "supplier_id", "item_id"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.status, PurchaseOrderStatus):
            raise ValueError("status must be a PurchaseOrderStatus")
        _require_aware_datetime(self.ordered_at, "ordered_at")
        _require_aware_datetime(self.expected_receipt_at, "expected_receipt_at")
        _require_non_negative(self.open_qty_units, "open_qty_units")
        if self.expected_receipt_at < self.ordered_at:
            raise ValueError("expected_receipt_at must not be before ordered_at")
        if not self.status.is_open and self.open_qty_units != 0:
            raise ValueError("closed or cancelled purchase orders must have zero open_qty_units")


@dataclass(frozen=True, slots=True)
class InputSourceStatus:
    dataset: str
    provenance: Provenance
    record_count: int
    source_version: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.dataset, "dataset")
        if self.record_count < 0:
            raise ValueError("record_count must be greater than or equal to zero")


@dataclass(frozen=True, slots=True)
class IngredientDemandDaily:
    location_id: str
    service_date: date
    dish_id: str
    silo_id: str
    item_id: str
    forecast_portions: Decimal
    grams_per_portion: Decimal
    required_g: Decimal
    bom_line_id: str


@dataclass(frozen=True, slots=True)
class ItemDemandDaily:
    location_id: str
    service_date: date
    item_id: str
    required_g: Decimal
    source_line_count: int


@dataclass(frozen=True, slots=True)
class PlanningRun:
    run_id: str
    schema_version: int
    policy_profile: str
    policy_version: str
    run_mode: RunMode
    planning_as_of_at: datetime
    created_at: datetime
    input_hash: str
    config_hash: str
    code_version: str
    status: RunStatus

    def __post_init__(self) -> None:
        for field_name in (
            "run_id",
            "policy_profile",
            "policy_version",
            "input_hash",
            "config_hash",
            "code_version",
        ):
            _require_text(getattr(self, field_name), field_name)
        if self.schema_version <= 0:
            raise ValueError("schema_version must be greater than zero")
        _require_aware_datetime(self.planning_as_of_at, "planning_as_of_at")
        _require_aware_datetime(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class PlanningRunInput:
    run_id: str
    dataset: str
    source_version: str
    content_hash: str
    provenance: Provenance
    record_count: int

    def __post_init__(self) -> None:
        for field_name in ("run_id", "dataset", "source_version", "content_hash"):
            _require_text(getattr(self, field_name), field_name)
        if self.record_count < 0:
            raise ValueError("record_count must be greater than or equal to zero")


@dataclass(frozen=True, slots=True)
class PlanningLine:
    planning_line_id: str
    run_id: str
    location_id: str
    item_id: str
    supplier_id: str | None
    gross_requirement_g: Decimal
    yield_factor: Decimal
    yield_factor_provenance: Provenance
    safety_stock_g: Decimal
    safety_stock_provenance: Provenance
    usable_on_hand_g: Decimal
    open_po_due_g: Decimal
    raw_order_g: Decimal
    shelf_life_cap_g: Decimal | None
    max_cover_cap_g: Decimal | None
    capped_order_g: Decimal
    proposed_order_units: Decimal
    rounding_delta_g: Decimal
    order_date: date
    expected_delivery_date: date

    def __post_init__(self) -> None:
        for field_name in ("planning_line_id", "run_id", "location_id", "item_id"):
            _require_text(getattr(self, field_name), field_name)
        if self.supplier_id is not None:
            _require_text(self.supplier_id, "supplier_id")
        _require_positive(self.yield_factor, "yield_factor")
        for field_name in (
            "gross_requirement_g",
            "safety_stock_g",
            "usable_on_hand_g",
            "open_po_due_g",
            "raw_order_g",
            "capped_order_g",
            "proposed_order_units",
            "rounding_delta_g",
        ):
            _require_non_negative(getattr(self, field_name), field_name)
        for field_name in ("shelf_life_cap_g", "max_cover_cap_g"):
            value = getattr(self, field_name)
            if value is not None:
                _require_non_negative(value, field_name)
        if self.expected_delivery_date < self.order_date:
            raise ValueError("expected_delivery_date must not be before order_date")


@dataclass(frozen=True, slots=True)
class OrderProposal:
    proposal_id: str
    planning_line_id: str
    run_id: str
    location_id: str
    supplier_id: str
    item_id: str
    order_date: date
    expected_delivery_date: date
    proposed_qty_units: Decimal
    status: ProposalStatus = ProposalStatus.PROPOSED

    def __post_init__(self) -> None:
        for field_name in (
            "proposal_id",
            "planning_line_id",
            "run_id",
            "location_id",
            "supplier_id",
            "item_id",
        ):
            _require_text(getattr(self, field_name), field_name)
        _require_non_negative(self.proposed_qty_units, "proposed_qty_units")
        if self.expected_delivery_date < self.order_date:
            raise ValueError("expected_delivery_date must not be before order_date")


@dataclass(frozen=True, slots=True)
class PlanningExceptionRecord:
    exception_id: str
    run_id: str
    planning_line_id: str | None
    code: ExceptionCode
    severity: Severity
    message: str
    remedy: str

    def __post_init__(self) -> None:
        for field_name in ("exception_id", "run_id", "message", "remedy"):
            _require_text(getattr(self, field_name), field_name)
        if self.planning_line_id is not None:
            _require_text(self.planning_line_id, "planning_line_id")


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    approval_id: str
    proposal_id: str
    run_id: str
    decision: ApprovalDecision
    decided_by: str
    decided_at: datetime
    reason: str

    def __post_init__(self) -> None:
        for field_name in (
            "approval_id",
            "proposal_id",
            "run_id",
            "decided_by",
            "reason",
        ):
            _require_text(getattr(self, field_name), field_name)
        _require_aware_datetime(self.decided_at, "decided_at")
