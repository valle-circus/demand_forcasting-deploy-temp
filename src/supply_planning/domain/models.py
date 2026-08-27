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


class ItemType(StrEnum):
    POD = "POD"
    INGREDIENT = "INGREDIENT"


class StockQuantityUnit(StrEnum):
    PACK = "PACK"
    ORDER_UNIT = "ORDER_UNIT"


class ShelfLifeAnchor(StrEnum):
    ORDER_DATE = "ORDER_DATE"
    RECEIPT_DATE = "RECEIPT_DATE"
    LOT_EXPIRY = "LOT_EXPIRY"


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
    PRODUCTION = "production"


class RunStatus(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


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
    forecast_version: str = "manual"
    provenance: Provenance = Provenance.MANUAL

    def __post_init__(self) -> None:
        _require_text(self.location_id, "location_id")
        _require_text(self.dish_id, "dish_id")
        _require_text(self.forecast_version, "forecast_version")
        _require_non_negative(self.forecast_portions, "forecast_portions")


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


@dataclass(frozen=True, slots=True)
class Supplier:
    supplier_id: str
    supplier_name: str
    timezone: str
    default_planning_lead_time_days: int | None = None
    active: bool = True

    def __post_init__(self) -> None:
        _require_text(self.supplier_id, "supplier_id")
        _require_text(self.supplier_name, "supplier_name")
        _require_text(self.timezone, "timezone")
        if (
            self.default_planning_lead_time_days is not None
            and self.default_planning_lead_time_days < 0
        ):
            raise ValueError(
                "default_planning_lead_time_days must be greater than or equal to zero"
            )


@dataclass(frozen=True, slots=True)
class SupplierItem:
    supplier_id: str
    item_id: str
    supplier_item_id: str | None = None
    planning_lead_time_days: int | None = None
    moq_units: Decimal = Decimal("0")
    case_size_units: Decimal = Decimal("1")
    order_cutoff_local: time | None = None
    active: bool = True
    provenance: Provenance = Provenance.MANUAL

    def __post_init__(self) -> None:
        _require_non_negative(self.moq_units, "moq_units")
        _require_positive(self.case_size_units, "case_size_units")
        if (
            self.planning_lead_time_days is not None
            and self.planning_lead_time_days < 0
        ):
            raise ValueError(
                "planning_lead_time_days must be greater than or equal to zero"
            )


@dataclass(frozen=True, slots=True)
class ItemPlanningPolicy:
    item_id: str
    item_type: ItemType
    official_supplier: str
    ordering_channel: str
    supplier_id: str
    supplier_article_number: str | None
    supplier_description_match: str | None
    packs_per_order_unit: Decimal
    order_unit: str
    stock_qty_unit: StockQuantityUnit
    apicbase_uid: str | None
    apicbase_stock_item_name: str | None
    lead_time_calendar_days: int
    shelf_life_anchor: ShelfLifeAnchor | None
    yield_factor: Decimal
    moq_order_units: Decimal
    case_multiple_order_units: Decimal
    data_status: str
    provenance: Provenance = Provenance.MANUAL

    def __post_init__(self) -> None:
        for field_name in (
            "item_id",
            "official_supplier",
            "ordering_channel",
            "supplier_id",
            "order_unit",
            "data_status",
        ):
            _require_text(getattr(self, field_name), field_name)
        _require_positive(self.packs_per_order_unit, "packs_per_order_unit")
        _require_positive(self.yield_factor, "yield_factor")
        _require_non_negative(self.moq_order_units, "moq_order_units")
        _require_positive(self.case_multiple_order_units, "case_multiple_order_units")
        if self.lead_time_calendar_days < 0:
            raise ValueError("lead_time_calendar_days must be greater than or equal to zero")


@dataclass(frozen=True, slots=True)
class DeliveryCoverageRule:
    delivery_rule_id: str
    location_id: str
    ordering_channel: str
    storage_class: StorageClass
    delivery_weekday: int | None
    covered_service_weekdays: tuple[int, ...]
    order_weekday: int | None
    review_period_days: int
    effective_from: date
    effective_to: date | None
    active: bool
    data_status: str
    provenance: Provenance = Provenance.MANUAL

    def __post_init__(self) -> None:
        for field_name in (
            "delivery_rule_id",
            "location_id",
            "ordering_channel",
            "data_status",
        ):
            _require_text(getattr(self, field_name), field_name)
        for field_name in ("delivery_weekday", "order_weekday"):
            value = getattr(self, field_name)
            if value is not None and not 0 <= value <= 6:
                raise ValueError(f"{field_name} must use Python weekday values 0 through 6")
        if any(not 0 <= weekday <= 6 for weekday in self.covered_service_weekdays):
            raise ValueError("covered_service_weekdays must use Python weekday values 0 through 6")
        if self.storage_class is StorageClass.FRISCH:
            if self.delivery_weekday is None or not self.covered_service_weekdays:
                raise ValueError(
                    "fresh delivery rules require delivery_weekday and covered service days"
                )
        if self.review_period_days <= 0:
            raise ValueError("review_period_days must be greater than zero")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not be before effective_from")

    def is_active_on(self, value: date) -> bool:
        return self.active and self.effective_from <= value and (
            self.effective_to is None or value <= self.effective_to
        )


@dataclass(frozen=True, slots=True)
class DeliveryScheduleRule:
    delivery_schedule_id: str
    supplier_id: str
    location_id: str
    order_weekday: int
    order_cutoff_local: time
    delivery_weekday: int
    active: bool = True

    def __post_init__(self) -> None:
        for field_name in ("delivery_schedule_id", "supplier_id", "location_id"):
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
    schedule_rule_id: str | None = None
    coverage_start_date: date | None = None
    coverage_end_date: date | None = None
    protection_days: int | None = None
    adjusted_requirement_g: Decimal = Decimal("0")
    order_unit_size_g: Decimal = Decimal("1")
    moq_order_units: Decimal = Decimal("0")
    case_multiple_order_units: Decimal = Decimal("1")
    data_status: str = "UNSPECIFIED"

    def __post_init__(self) -> None:
        for field_name in ("planning_line_id", "run_id", "location_id", "item_id"):
            _require_text(getattr(self, field_name), field_name)
        if self.supplier_id is not None:
            _require_text(self.supplier_id, "supplier_id")
        _require_positive(self.yield_factor, "yield_factor")
        for field_name in (
            "gross_requirement_g",
            "adjusted_requirement_g",
            "safety_stock_g",
            "usable_on_hand_g",
            "open_po_due_g",
            "raw_order_g",
            "capped_order_g",
            "proposed_order_units",
            "rounding_delta_g",
        ):
            _require_non_negative(getattr(self, field_name), field_name)
        _require_positive(self.order_unit_size_g, "order_unit_size_g")
        _require_non_negative(self.moq_order_units, "moq_order_units")
        _require_positive(self.case_multiple_order_units, "case_multiple_order_units")
        if self.protection_days is not None and self.protection_days <= 0:
            raise ValueError("protection_days must be greater than zero when supplied")
        if (
            self.coverage_start_date is not None
            and self.coverage_end_date is not None
            and self.coverage_end_date < self.coverage_start_date
        ):
            raise ValueError("coverage_end_date must not be before coverage_start_date")
        if self.schedule_rule_id is not None:
            _require_text(self.schedule_rule_id, "schedule_rule_id")
        _require_text(self.data_status, "data_status")
        for field_name in ("shelf_life_cap_g", "max_cover_cap_g"):
            value = getattr(self, field_name)
            if value is not None:
                _require_non_negative(value, field_name)
        if self.expected_delivery_date < self.order_date:
            raise ValueError("expected_delivery_date must not be before order_date")


@dataclass(frozen=True, slots=True)
class PlanningRecommendation:
    recommendation_id: str
    planning_line_id: str
    run_id: str
    location_id: str
    supplier_id: str
    item_id: str
    order_date: date
    expected_delivery_date: date
    proposed_qty_units: Decimal

    def __post_init__(self) -> None:
        for field_name in (
            "recommendation_id",
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
