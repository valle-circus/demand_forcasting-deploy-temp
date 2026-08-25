from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, TypeVar

from supply_planning.adapters.errors import InputFileError
from supply_planning.domain.models import (
    BomLine,
    ForecastDaily,
    InputSourceStatus,
    InventorySnapshot,
    Item,
    MenuCalendarEntry,
    Provenance,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    StorageClass,
)

DATASET_FILES = {
    "forecast_daily": "forecast_daily.csv",
    "menu_calendar": "menu_calendar.csv",
    "bom_lines": "bom_lines.csv",
    "items": "items.csv",
    "inventory_snapshots": "inventory_snapshots.csv",
    "purchase_orders": "open_pos.csv",
}

MANIFEST_FIELDS = ("dataset", "provenance", "source_version")
FORECAST_FIELDS = (
    "location_id",
    "dish_id",
    "service_date",
    "forecast_portions",
    "forecast_sigma",
    "forecast_version",
)
MENU_FIELDS = ("location_id", "dish_id", "service_date", "menu_version", "active")
BOM_FIELDS = (
    "bom_line_id",
    "dish_id",
    "silo_id",
    "item_id",
    "grams_per_portion",
    "effective_from",
    "effective_to",
)
ITEM_FIELDS = (
    "item_id",
    "item_name",
    "storage_class",
    "pack_size_g",
    "shelf_life_days",
    "min_safety_days",
    "max_cover_days",
    "last_order_date_offset_days",
    "pipeline_cancellable",
    "active",
)
INVENTORY_FIELDS = (
    "location_id",
    "item_id",
    "counted_at",
    "usable_on_hand_units",
    "partial_pack_g",
)
PURCHASE_ORDER_FIELDS = (
    "po_id",
    "po_line_id",
    "location_id",
    "supplier_id",
    "item_id",
    "ordered_at",
    "expected_receipt_at",
    "open_qty_units",
    "status",
)

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class CanonicalInputBundle:
    forecasts: tuple[ForecastDaily, ...]
    menu_entries: tuple[MenuCalendarEntry, ...]
    bom_lines: tuple[BomLine, ...]
    items: tuple[Item, ...]
    inventory_snapshots: tuple[InventorySnapshot, ...]
    purchase_orders: tuple[PurchaseOrderLine, ...]
    source_statuses: tuple[InputSourceStatus, ...]

    def source_status(self, dataset: str) -> InputSourceStatus:
        for status in self.source_statuses:
            if status.dataset == dataset:
                return status
        raise KeyError(dataset)


def _read_rows(path: Path, required_fields: tuple[str, ...]) -> list[tuple[int, dict[str, str]]]:
    try:
        handle = path.open("r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise InputFileError(f"cannot read {path}: {exc}") from exc

    with handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        missing = [field for field in required_fields if field not in fieldnames]
        if missing:
            raise InputFileError(
                f"{path}: missing required columns {', '.join(missing)}; "
                f"expected {', '.join(required_fields)}"
            )
        return [
            (row_number, {key: value or "" for key, value in row.items() if key is not None})
            for row_number, row in enumerate(reader, start=2)
            if any((value or "").strip() for value in row.values())
        ]


def _text(path: Path, row_number: int, field: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise InputFileError(
            f"{path} row {row_number}, field {field}: value is blank; provide a stable ID/value"
        )
    return normalized


def _decimal(
    path: Path,
    row_number: int,
    field: str,
    value: str,
    *,
    optional: bool = False,
) -> Decimal | None:
    normalized = value.strip()
    if optional and not normalized:
        return None
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise InputFileError(
            f"{path} row {row_number}, field {field}: {value!r} is not a decimal; "
            "use a plain numeric value with '.' as the decimal separator"
        ) from exc


def _integer(
    path: Path,
    row_number: int,
    field: str,
    value: str,
    *,
    optional: bool = False,
    default: int | None = None,
) -> int | None:
    normalized = value.strip()
    if not normalized:
        if optional:
            return default
        raise InputFileError(
            f"{path} row {row_number}, field {field}: value is blank; provide a whole number"
        )
    try:
        return int(normalized)
    except ValueError as exc:
        raise InputFileError(
            f"{path} row {row_number}, field {field}: {value!r} is not a whole number"
        ) from exc


def _date(path: Path, row_number: int, field: str, value: str) -> date:
    normalized = _text(path, row_number, field, value)
    try:
        return date.fromisoformat(normalized)
    except ValueError as exc:
        raise InputFileError(
            f"{path} row {row_number}, field {field}: {value!r} is not YYYY-MM-DD"
        ) from exc


def _optional_date(path: Path, row_number: int, field: str, value: str) -> date | None:
    return None if not value.strip() else _date(path, row_number, field, value)


def _datetime(path: Path, row_number: int, field: str, value: str) -> datetime:
    normalized = _text(path, row_number, field, value)
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise InputFileError(
            f"{path} row {row_number}, field {field}: {value!r} is not an ISO timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InputFileError(
            f"{path} row {row_number}, field {field}: {value!r} has no timezone offset; "
            "use an ISO timestamp such as 2026-08-25T08:00:00+02:00"
        )
    return parsed


def _boolean(path: Path, row_number: int, field: str, value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise InputFileError(
        f"{path} row {row_number}, field {field}: {value!r} is not a boolean; "
        "use true or false"
    )


def _enum(
    path: Path,
    row_number: int,
    field: str,
    value: str,
    enum_type: type[T],
) -> T:
    normalized = _text(path, row_number, field, value)
    try:
        return enum_type(normalized)  # type: ignore[call-arg]
    except ValueError as exc:
        allowed = ", ".join(member.value for member in enum_type)  # type: ignore[attr-defined]
        raise InputFileError(
            f"{path} row {row_number}, field {field}: {value!r} is not allowed; "
            f"use one of {allowed}"
        ) from exc


def _construct(path: Path, row_number: int, constructor: Callable[[], T]) -> T:
    try:
        return constructor()
    except InputFileError:
        raise
    except ValueError as exc:
        raise InputFileError(f"{path} row {row_number}: {exc}; correct the row") from exc


def _ensure_unique(
    path: Path,
    rows: list[tuple[int, T]],
    *,
    dataset: str,
    fields: str,
    key: Callable[[T], tuple[object, ...]],
) -> None:
    seen: dict[tuple[object, ...], int] = {}
    for row_number, record in rows:
        record_key = key(record)
        first_row = seen.get(record_key)
        if first_row is not None:
            raise InputFileError(
                f"{path} row {row_number}, key {fields}={record_key!r}: duplicate {dataset} "
                f"record; first seen at row {first_row}; keep exactly one record per key"
            )
        seen[record_key] = row_number


def _load_manifest(path: Path) -> dict[str, tuple[Provenance, str]]:
    rows = _read_rows(path, MANIFEST_FIELDS)
    manifest: dict[str, tuple[Provenance, str]] = {}
    for row_number, row in rows:
        dataset = _text(path, row_number, "dataset", row["dataset"])
        if dataset not in DATASET_FILES:
            raise InputFileError(
                f"{path} row {row_number}, field dataset: {dataset!r} is unknown; "
                f"use one of {', '.join(DATASET_FILES)}"
            )
        if dataset in manifest:
            raise InputFileError(
                f"{path} row {row_number}, field dataset: {dataset!r} is duplicated; "
                "keep one manifest row per dataset"
            )
        provenance = _enum(
            path, row_number, "provenance", row["provenance"], Provenance
        )
        source_version = _text(path, row_number, "source_version", row["source_version"])
        manifest[dataset] = (provenance, source_version)

    missing = [dataset for dataset in DATASET_FILES if dataset not in manifest]
    if missing:
        raise InputFileError(
            f"{path}: missing dataset rows {', '.join(missing)}; "
            "declare provenance and source_version for every canonical input"
        )
    return manifest


def load_forecast_daily_csv(path: Path, provenance: Provenance) -> tuple[ForecastDaily, ...]:
    parsed: list[tuple[int, ForecastDaily]] = []
    for row_number, row in _read_rows(path, FORECAST_FIELDS):
        record = _construct(
            path,
            row_number,
            lambda row=row, row_number=row_number: ForecastDaily(
                location_id=_text(path, row_number, "location_id", row["location_id"]),
                dish_id=_text(path, row_number, "dish_id", row["dish_id"]),
                service_date=_date(path, row_number, "service_date", row["service_date"]),
                forecast_portions=_decimal(
                    path, row_number, "forecast_portions", row["forecast_portions"]
                ),  # type: ignore[arg-type]
                forecast_sigma=_decimal(
                    path,
                    row_number,
                    "forecast_sigma",
                    row["forecast_sigma"],
                    optional=True,
                ),
                forecast_version=_text(
                    path, row_number, "forecast_version", row["forecast_version"]
                ),
                provenance=provenance,
            ),
        )
        parsed.append((row_number, record))
    _ensure_unique(
        path,
        parsed,
        dataset="forecast_daily",
        fields="location_id+dish_id+service_date+forecast_version",
        key=lambda row: (
            row.location_id,
            row.dish_id,
            row.service_date,
            row.forecast_version,
        ),
    )
    return tuple(record for _, record in parsed)


def load_menu_calendar_csv(
    path: Path, provenance: Provenance
) -> tuple[MenuCalendarEntry, ...]:
    parsed: list[tuple[int, MenuCalendarEntry]] = []
    for row_number, row in _read_rows(path, MENU_FIELDS):
        record = _construct(
            path,
            row_number,
            lambda row=row, row_number=row_number: MenuCalendarEntry(
                location_id=_text(path, row_number, "location_id", row["location_id"]),
                dish_id=_text(path, row_number, "dish_id", row["dish_id"]),
                service_date=_date(path, row_number, "service_date", row["service_date"]),
                menu_version=_text(path, row_number, "menu_version", row["menu_version"]),
                active=_boolean(path, row_number, "active", row["active"]),
                provenance=provenance,
            ),
        )
        parsed.append((row_number, record))
    _ensure_unique(
        path,
        parsed,
        dataset="menu_calendar",
        fields="location_id+dish_id+service_date+menu_version",
        key=lambda row: (row.location_id, row.dish_id, row.service_date, row.menu_version),
    )
    return tuple(record for _, record in parsed)


def load_bom_lines_csv(path: Path, provenance: Provenance) -> tuple[BomLine, ...]:
    parsed: list[tuple[int, BomLine]] = []
    for row_number, row in _read_rows(path, BOM_FIELDS):
        record = _construct(
            path,
            row_number,
            lambda row=row, row_number=row_number: BomLine(
                bom_line_id=_text(path, row_number, "bom_line_id", row["bom_line_id"]),
                dish_id=_text(path, row_number, "dish_id", row["dish_id"]),
                silo_id=_text(path, row_number, "silo_id", row["silo_id"]),
                item_id=_text(path, row_number, "item_id", row["item_id"]),
                grams_per_portion=_decimal(
                    path, row_number, "grams_per_portion", row["grams_per_portion"]
                ),  # type: ignore[arg-type]
                effective_from=_date(
                    path, row_number, "effective_from", row["effective_from"]
                ),
                effective_to=_optional_date(
                    path, row_number, "effective_to", row["effective_to"]
                ),
                provenance=provenance,
            ),
        )
        parsed.append((row_number, record))
    _ensure_unique(
        path,
        parsed,
        dataset="bom_lines",
        fields="bom_line_id",
        key=lambda row: (row.bom_line_id,),
    )
    return tuple(record for _, record in parsed)


def load_items_csv(path: Path, provenance: Provenance) -> tuple[Item, ...]:
    parsed: list[tuple[int, Item]] = []
    for row_number, row in _read_rows(path, ITEM_FIELDS):
        record = _construct(
            path,
            row_number,
            lambda row=row, row_number=row_number: Item(
                item_id=_text(path, row_number, "item_id", row["item_id"]),
                item_name=_text(path, row_number, "item_name", row["item_name"]),
                storage_class=_enum(
                    path, row_number, "storage_class", row["storage_class"], StorageClass
                ),
                pack_size_g=_decimal(
                    path, row_number, "pack_size_g", row["pack_size_g"]
                ),  # type: ignore[arg-type]
                shelf_life_days=_integer(
                    path,
                    row_number,
                    "shelf_life_days",
                    row["shelf_life_days"],
                    optional=True,
                ),
                min_safety_days=_decimal(
                    path,
                    row_number,
                    "min_safety_days",
                    row["min_safety_days"],
                    optional=True,
                ),
                max_cover_days=_decimal(
                    path,
                    row_number,
                    "max_cover_days",
                    row["max_cover_days"],
                    optional=True,
                ),
                last_order_date_offset_days=_integer(
                    path,
                    row_number,
                    "last_order_date_offset_days",
                    row["last_order_date_offset_days"],
                    optional=True,
                    default=0,
                ),  # type: ignore[arg-type]
                pipeline_cancellable=_boolean(
                    path, row_number, "pipeline_cancellable", row["pipeline_cancellable"]
                ),
                active=_boolean(path, row_number, "active", row["active"]),
                provenance=provenance,
            ),
        )
        parsed.append((row_number, record))
    _ensure_unique(
        path,
        parsed,
        dataset="items",
        fields="item_id",
        key=lambda row: (row.item_id,),
    )
    return tuple(record for _, record in parsed)


def load_inventory_snapshots_csv(
    path: Path, provenance: Provenance
) -> tuple[InventorySnapshot, ...]:
    parsed: list[tuple[int, InventorySnapshot]] = []
    for row_number, row in _read_rows(path, INVENTORY_FIELDS):
        record = _construct(
            path,
            row_number,
            lambda row=row, row_number=row_number: InventorySnapshot(
                location_id=_text(path, row_number, "location_id", row["location_id"]),
                item_id=_text(path, row_number, "item_id", row["item_id"]),
                counted_at=_datetime(path, row_number, "counted_at", row["counted_at"]),
                usable_on_hand_units=_decimal(
                    path,
                    row_number,
                    "usable_on_hand_units",
                    row["usable_on_hand_units"],
                ),  # type: ignore[arg-type]
                partial_pack_g=_decimal(
                    path, row_number, "partial_pack_g", row["partial_pack_g"]
                ),  # type: ignore[arg-type]
                provenance=provenance,
            ),
        )
        parsed.append((row_number, record))
    _ensure_unique(
        path,
        parsed,
        dataset="inventory_snapshots",
        fields="location_id+item_id+counted_at",
        key=lambda row: (row.location_id, row.item_id, row.counted_at),
    )
    return tuple(record for _, record in parsed)


def load_purchase_orders_csv(
    path: Path, provenance: Provenance
) -> tuple[PurchaseOrderLine, ...]:
    parsed: list[tuple[int, PurchaseOrderLine]] = []
    for row_number, row in _read_rows(path, PURCHASE_ORDER_FIELDS):
        record = _construct(
            path,
            row_number,
            lambda row=row, row_number=row_number: PurchaseOrderLine(
                po_id=_text(path, row_number, "po_id", row["po_id"]),
                po_line_id=_text(path, row_number, "po_line_id", row["po_line_id"]),
                location_id=_text(path, row_number, "location_id", row["location_id"]),
                supplier_id=_text(path, row_number, "supplier_id", row["supplier_id"]),
                item_id=_text(path, row_number, "item_id", row["item_id"]),
                ordered_at=_datetime(path, row_number, "ordered_at", row["ordered_at"]),
                expected_receipt_at=_datetime(
                    path, row_number, "expected_receipt_at", row["expected_receipt_at"]
                ),
                open_qty_units=_decimal(
                    path, row_number, "open_qty_units", row["open_qty_units"]
                ),  # type: ignore[arg-type]
                status=_enum(
                    path,
                    row_number,
                    "status",
                    row["status"],
                    PurchaseOrderStatus,
                ),
                provenance=provenance,
            ),
        )
        parsed.append((row_number, record))
    _ensure_unique(
        path,
        parsed,
        dataset="purchase_orders",
        fields="po_line_id",
        key=lambda row: (row.po_line_id,),
    )
    return tuple(record for _, record in parsed)


def _validate_bundle(bundle: CanonicalInputBundle, input_dir: Path) -> None:
    errors: list[str] = []
    items = {item.item_id: item for item in bundle.items}
    menu_locations = {entry.location_id for entry in bundle.menu_entries}

    active_menu: dict[tuple[str, str, date], int] = {}
    for entry in bundle.menu_entries:
        if entry.active:
            key = (entry.location_id, entry.dish_id, entry.service_date)
            active_menu[key] = active_menu.get(key, 0) + 1
    for key, count in sorted(active_menu.items()):
        if count > 1:
            errors.append(
                f"menu_calendar key {key!r} has {count} active versions; keep one active "
                "menu snapshot per location/dish/day"
            )

    forecast_grain: set[tuple[str, str, date]] = set()
    for forecast in bundle.forecasts:
        key = (forecast.location_id, forecast.dish_id, forecast.service_date)
        if key in forecast_grain:
            errors.append(
                f"forecast_daily key {key!r} has multiple forecast versions in one input "
                "snapshot; select one version before planning"
            )
        forecast_grain.add(key)
        if active_menu.get(key, 0) != 1:
            errors.append(
                f"forecast_daily {key!r} has no single active menu_calendar row; add or "
                "correct the committed menu assignment"
            )
        effective_bom = any(
            line.dish_id == forecast.dish_id and line.is_active_on(forecast.service_date)
            for line in bundle.bom_lines
        )
        if not effective_bom:
            errors.append(
                f"forecast_daily {key!r} has no effective bom_lines row; add a versioned "
                "Dish -> Silo -> Item mapping covering the service date"
            )

    for line in bundle.bom_lines:
        if line.item_id not in items:
            errors.append(
                f"bom_lines bom_line_id={line.bom_line_id!r} references unknown "
                f"item_id={line.item_id!r}; add the item or correct the stable ID"
            )

    for snapshot in bundle.inventory_snapshots:
        item = items.get(snapshot.item_id)
        if item is None:
            errors.append(
                f"inventory_snapshots {snapshot.location_id!r}/{snapshot.item_id!r} "
                "references an unknown item_id"
            )
        elif snapshot.partial_pack_g >= item.pack_size_g:
            errors.append(
                f"inventory_snapshots {snapshot.location_id!r}/{snapshot.item_id!r} has "
                f"partial_pack_g={snapshot.partial_pack_g} not below pack_size_g="
                f"{item.pack_size_g}; convert full packs into usable_on_hand_units"
            )
        if menu_locations and snapshot.location_id not in menu_locations:
            errors.append(
                f"inventory_snapshots location_id={snapshot.location_id!r} is absent from "
                "menu_calendar; correct the stable location ID or add its menu rows"
            )

    for po in bundle.purchase_orders:
        if po.item_id not in items:
            errors.append(
                f"purchase_orders po_line_id={po.po_line_id!r} references unknown "
                f"item_id={po.item_id!r}"
            )
        if menu_locations and po.location_id not in menu_locations:
            errors.append(
                f"purchase_orders po_line_id={po.po_line_id!r} uses location_id="
                f"{po.location_id!r}, absent from menu_calendar"
            )

    for status in bundle.source_statuses:
        if status.record_count > 0 and status.provenance in {
            Provenance.EMPTY_PLACEHOLDER,
            Provenance.UNAVAILABLE,
        }:
            errors.append(
                f"source_manifest dataset={status.dataset!r} is {status.provenance.value} "
                f"but {status.record_count} rows were supplied; correct the provenance or "
                "empty the placeholder file"
            )

    if errors:
        formatted = "\n".join(f"- {error}" for error in errors)
        raise InputFileError(
            f"{input_dir}: canonical input validation failed:\n{formatted}"
        )


def load_canonical_bundle(input_dir: Path) -> CanonicalInputBundle:
    manifest = _load_manifest(input_dir / "source_manifest.csv")

    def provenance(dataset: str) -> Provenance:
        return manifest[dataset][0]

    forecasts = load_forecast_daily_csv(
        input_dir / DATASET_FILES["forecast_daily"], provenance("forecast_daily")
    )
    menu_entries = load_menu_calendar_csv(
        input_dir / DATASET_FILES["menu_calendar"], provenance("menu_calendar")
    )
    bom_lines = load_bom_lines_csv(
        input_dir / DATASET_FILES["bom_lines"], provenance("bom_lines")
    )
    items = load_items_csv(input_dir / DATASET_FILES["items"], provenance("items"))
    inventory_snapshots = load_inventory_snapshots_csv(
        input_dir / DATASET_FILES["inventory_snapshots"],
        provenance("inventory_snapshots"),
    )
    purchase_orders = load_purchase_orders_csv(
        input_dir / DATASET_FILES["purchase_orders"], provenance("purchase_orders")
    )

    counts = {
        "forecast_daily": len(forecasts),
        "menu_calendar": len(menu_entries),
        "bom_lines": len(bom_lines),
        "items": len(items),
        "inventory_snapshots": len(inventory_snapshots),
        "purchase_orders": len(purchase_orders),
    }
    statuses = tuple(
        InputSourceStatus(
            dataset=dataset,
            provenance=manifest[dataset][0],
            record_count=counts[dataset],
            source_version=manifest[dataset][1],
        )
        for dataset in DATASET_FILES
    )
    bundle = CanonicalInputBundle(
        forecasts=forecasts,
        menu_entries=menu_entries,
        bom_lines=bom_lines,
        items=items,
        inventory_snapshots=inventory_snapshots,
        purchase_orders=purchase_orders,
        source_statuses=statuses,
    )
    _validate_bundle(bundle, input_dir)
    return bundle
