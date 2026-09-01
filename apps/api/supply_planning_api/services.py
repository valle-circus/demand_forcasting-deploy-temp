from __future__ import annotations

import asyncio
import csv
import io
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import uuid4

from supply_planning.adapters.apicbase_stock_xlsx import normalize_apicbase_stock
from supply_planning.adapters.canonical_csv import CanonicalInputBundle
from supply_planning.adapters.errors import InputFileError
from supply_planning.adapters.template_xlsx import (
    BOM_HEADERS,
    DELIVERY_HEADERS,
    DEMAND_HEADERS,
    ITEM_HEADERS,
    LOCATION_HEADERS,
    MENU_HEADERS,
    PlanningWorkbookData,
    load_master_template,
    load_planning_template,
)
from supply_planning.adapters.transgourmet_v1 import normalize_transgourmet_pos
from supply_planning.application.run_improved import (
    POLICY_VERSION,
    PROFILE,
    SCHEMA_VERSION,
    ImprovedRunResult,
    run_improved_plan,
)
from supply_planning.application.run_template_v1 import selected_required_items
from supply_planning.domain.issues import ExceptionCode, PlanningIssue, Severity
from supply_planning.domain.models import (
    BomLine,
    DeliveryCoverageRule,
    ForecastDaily,
    InputSourceStatus,
    InventorySnapshot,
    Item,
    ItemPlanningPolicy,
    ItemType,
    Location,
    MenuCalendarEntry,
    Provenance,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    RunMode,
    ShelfLifeAnchor,
    ShelfLifeCapBasis,
    StockQuantityUnit,
    StorageClass,
)

from . import __version__
from .auth import AuthenticatedUser
from .config import Settings
from .errors import ConflictError, NotFoundError, ValidationError
from .repository import CanonicalStore, JsonObject
from .schemas import CreatePlanningRunRequest
from .source_rows import (
    optional_text,
    read_validated_sheet_rows,
    temporal_text,
    text_value,
)
from .uploads import SavedUpload, combined_content_hash

ACCEPTED_STATUSES = "in.(accepted,accepted_with_warnings)"
PARSER_VERSION = f"supply-planning-api/{__version__}"


class Backend(Protocol):
    async def list_imports(
        self,
        *,
        dataset_type: str | None,
        location_id: str | None,
    ) -> list[JsonObject]: ...

    async def get_import(self, import_id: str) -> JsonObject: ...

    async def import_master_data(
        self, file: SavedUpload, user: AuthenticatedUser
    ) -> JsonObject: ...

    async def import_planning_input(
        self, file: SavedUpload, user: AuthenticatedUser
    ) -> JsonObject: ...

    async def import_stock(
        self,
        file: SavedUpload,
        *,
        location_id: str,
        user: AuthenticatedUser,
    ) -> JsonObject: ...

    async def import_purchase_orders(
        self,
        files: tuple[SavedUpload, ...],
        *,
        location_id: str,
        as_of_at: datetime,
        user: AuthenticatedUser,
    ) -> JsonObject: ...

    async def list_master_versions(self) -> list[JsonObject]: ...

    async def activate_master_version(
        self, version_id: str, user: AuthenticatedUser
    ) -> JsonObject: ...

    async def list_locations(self) -> JsonObject: ...

    async def planning_status(self, location_id: str) -> JsonObject: ...

    async def inventory(self, location_id: str) -> JsonObject: ...

    async def purchase_orders(self, location_id: str) -> JsonObject: ...

    async def create_planning_run(
        self,
        request: CreatePlanningRunRequest,
        user: AuthenticatedUser,
    ) -> JsonObject: ...

    async def get_planning_run(self, run_id: str) -> JsonObject: ...

    async def overview(self) -> JsonObject: ...

    async def recommendation_json(self, run_id: str) -> JsonObject: ...

    async def recommendation_csv(self, run_id: str) -> str: ...


@dataclass(frozen=True, slots=True)
class LoadedMaster:
    version: JsonObject
    locations: tuple[Location, ...]
    items: tuple[Item, ...]
    policies: tuple[ItemPlanningPolicy, ...]
    rules: tuple[DeliveryCoverageRule, ...]


@dataclass(frozen=True, slots=True)
class SelectedSources:
    master: LoadedMaster
    planning_import: JsonObject
    stock_import: JsonObject
    purchase_orders_import: JsonObject
    bundle: CanonicalInputBundle


def _now() -> datetime:
    return datetime.now(UTC)


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _date_value(value: Any) -> date:
    # Excel date cells are commonly returned as midnight ``datetime`` values.
    # Service dates are deliberately date-only, so normalize that representation
    # before parsing strings from persisted API rows.
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _datetime_value(value: Any) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("persisted datetime is missing a timezone offset")
    return result


def _optional_date(value: Any) -> date | None:
    return None if value in (None, "") else _date_value(value)


def _optional_decimal(value: Any) -> Decimal | None:
    return None if value in (None, "") else _decimal(value)


def _value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "value"):
        return str(value.value)
    return value


def _issue_payload(issue: PlanningIssue) -> JsonObject:
    return {
        "code": issue.code.value,
        "severity": issue.severity.value,
        "dataset": issue.dataset,
        "record_ref": issue.record_ref,
        "message": issue.message,
        "remedy": issue.remedy,
    }


def _accepted_status(warning_count: int) -> str:
    return "accepted_with_warnings" if warning_count else "accepted"


class PlanningBackend:
    def __init__(self, store: CanonicalStore, settings: Settings) -> None:
        self._store = store
        self._settings = settings

    async def _find_duplicate(
        self,
        *,
        dataset_type: str,
        content_hash: str,
        location_id: str | None,
    ) -> JsonObject | None:
        filters = {
            "dataset_type": f"eq.{dataset_type}",
            "content_hash": f"eq.{content_hash}",
            "status": ACCEPTED_STATUSES,
            "location_id": "is.null" if location_id is None else f"eq.{location_id}",
        }
        rows = await self._store.select_rows(
            "source_imports",
            filters=filters,
            order="created_at.desc",
            limit=1,
        )
        return rows[0] if rows else None

    async def _latest_import(
        self,
        dataset_type: str,
        *,
        location_id: str | None,
    ) -> JsonObject | None:
        filters = {
            "dataset_type": f"eq.{dataset_type}",
            "status": ACCEPTED_STATUSES,
            "location_id": "is.null" if location_id is None else f"eq.{location_id}",
        }
        rows = await self._store.select_rows(
            "source_imports",
            filters=filters,
            order="created_at.desc",
            limit=1,
        )
        return rows[0] if rows else None

    async def _latest_planning_import_for_location(
        self, location_id: str
    ) -> JsonObject | None:
        candidates = await self._store.select_rows(
            "source_imports",
            filters={
                "dataset_type": "eq.planning_input",
                "status": ACCEPTED_STATUSES,
            },
            order="created_at.desc",
            limit=25,
        )
        for candidate in candidates:
            rows = await self._store.select_rows(
                "forecast_daily",
                columns="import_id",
                filters={
                    "import_id": f"eq.{candidate['id']}",
                    "location_id": f"eq.{location_id}",
                },
                limit=1,
            )
            if rows:
                return candidate
        return None

    async def _superseded_import_id(
        self,
        *,
        dataset_type: str,
        location_id: str | None,
    ) -> str | None:
        latest = await self._latest_import(dataset_type, location_id=location_id)
        return str(latest["id"]) if latest is not None else None

    def _import_row(
        self,
        *,
        import_id: str,
        dataset_type: str,
        location_id: str | None,
        status: str,
        source_version: str,
        source_as_of_at: datetime | None,
        coverage_start_date: date | None,
        coverage_end_date: date | None,
        files: tuple[SavedUpload, ...],
        content_hash: str,
        record_count: int,
        issues: list[JsonObject],
        metadata: JsonObject,
        supersedes_import_id: str | None,
        user: AuthenticatedUser,
    ) -> JsonObject:
        warning_count = sum(issue.get("severity") == "warning" for issue in issues)
        error_count = sum(issue.get("severity") == "blocker" for issue in issues)
        return {
            "id": import_id,
            "dataset_type": dataset_type,
            "location_id": location_id,
            "status": status,
            "source_version": source_version,
            "source_as_of_at": _value(source_as_of_at),
            "coverage_start_date": _value(coverage_start_date),
            "coverage_end_date": _value(coverage_end_date),
            "file_names": [file.file_name for file in files],
            "file_count": len(files),
            "total_bytes": sum(file.size_bytes for file in files),
            "content_hash": content_hash,
            "parser_version": PARSER_VERSION,
            "record_count": record_count,
            "warning_count": warning_count,
            "error_count": error_count,
            "validation_issues": issues,
            "metadata": metadata,
            "supersedes_import_id": supersedes_import_id,
            "created_at": _now().isoformat(),
            "created_by": user.user_id,
        }

    async def _persist_rejected(
        self,
        *,
        dataset_type: str,
        location_id: str | None,
        files: tuple[SavedUpload, ...],
        content_hash: str,
        message: str,
        user: AuthenticatedUser,
    ) -> str:
        import_id = str(uuid4())
        row = self._import_row(
            import_id=import_id,
            dataset_type=dataset_type,
            location_id=location_id,
            status="rejected",
            source_version=f"rejected-{content_hash[:12]}",
            source_as_of_at=None,
            coverage_start_date=None,
            coverage_end_date=None,
            files=files,
            content_hash=content_hash,
            record_count=0,
            issues=[
                {
                    "code": "INPUT_VALIDATION_FAILED",
                    "severity": "blocker",
                    "dataset": dataset_type,
                    "record_ref": None,
                    "message": message,
                    "remedy": "Correct the referenced file field and upload a new version.",
                }
            ],
            metadata={},
            supersedes_import_id=None,
            user=user,
        )
        await self._store.insert_rows("source_imports", [row])
        return import_id

    async def _persist_dataset_import(
        self,
        *,
        import_row: JsonObject,
        rows_by_table: tuple[tuple[str, list[JsonObject]], ...],
        final_status: str,
    ) -> JsonObject:
        payload: JsonObject = {
            "source_import": {**import_row, "status": "validating"},
            "final_status": final_status,
        }
        for table, rows in rows_by_table:
            payload[table] = rows
        return await self._store.persist_source_import(payload)

    async def list_imports(
        self,
        *,
        dataset_type: str | None,
        location_id: str | None,
    ) -> list[JsonObject]:
        filters: dict[str, str] = {}
        if dataset_type is not None:
            filters["dataset_type"] = f"eq.{dataset_type}"
        if location_id is not None:
            filters["location_id"] = f"eq.{location_id}"
        return await self._store.select_rows(
            "source_imports",
            filters=filters,
            order="created_at.desc",
            limit=100,
        )

    async def get_import(self, import_id: str) -> JsonObject:
        rows = await self._store.select_rows(
            "source_imports", filters={"id": f"eq.{import_id}"}, limit=1
        )
        if not rows:
            raise NotFoundError("Source import", import_id)
        return rows[0]

    async def import_master_data(
        self, file: SavedUpload, user: AuthenticatedUser
    ) -> JsonObject:
        duplicate = await self._find_duplicate(
            dataset_type="master_data", content_hash=file.sha256, location_id=None
        )
        if duplicate is not None:
            return duplicate
        try:
            parsed = await asyncio.to_thread(load_master_template, file.path)
        except InputFileError as exc:
            rejected_id = await self._persist_rejected(
                dataset_type="master_data",
                location_id=None,
                files=(file,),
                content_hash=file.sha256,
                message=str(exc),
                user=user,
            )
            raise ValidationError(str(exc), details={"import_id": rejected_id}) from exc

        import_id = str(uuid4())
        version_id = str(uuid4())
        supersedes = await self._superseded_import_id(
            dataset_type="master_data", location_id=None
        )
        source_items = {
            text_value(row["item_id"]): row
            for row in read_validated_sheet_rows(file.path, "Items", ITEM_HEADERS)
        }
        source_locations = {
            text_value(row["location_id"]): row
            for row in read_validated_sheet_rows(file.path, "Locations", LOCATION_HEADERS)
        }
        source_rules = {
            text_value(row["delivery_rule_id"]): row
            for row in read_validated_sheet_rows(
                file.path, "Delivery_Rules", DELIVERY_HEADERS
            )
        }
        policy_by_id = {policy.item_id: policy for policy in parsed.item_policies}
        location_rows = [
            {
                "version_id": version_id,
                "location_id": location.location_id,
                "location_name": location.location_name,
                "timezone": location.timezone,
                "active": location.active,
                "data_status": text_value(source_locations[location.location_id]["data_status"]),
                "source_note": optional_text(
                    source_locations[location.location_id]["source_note"]
                ),
            }
            for location in parsed.locations
        ]
        item_rows: list[JsonObject] = []
        policy_rows: list[JsonObject] = []
        for item in parsed.items:
            source = source_items[item.item_id]
            policy = policy_by_id[item.item_id]
            item_rows.append(
                {
                    "version_id": version_id,
                    "item_id": item.item_id,
                    "item_name": item.item_name,
                    "storage_class": item.storage_class.value,
                    "pack_size_g": _value(item.pack_size_g),
                    "shelf_life_days": item.shelf_life_days,
                    "min_safety_days": _value(item.min_safety_days),
                    "max_cover_days": _value(item.max_cover_days),
                    "active": item.active,
                    "data_status": text_value(source["data_status"]),
                    "source_note": optional_text(source["source_note"]),
                }
            )
            policy_rows.append(
                {
                    "version_id": version_id,
                    "item_id": policy.item_id,
                    "item_type": policy.item_type.value,
                    "official_supplier": policy.official_supplier,
                    "ordering_channel": policy.ordering_channel,
                    "supplier_id": policy.supplier_id,
                    "supplier_article_number": policy.supplier_article_number,
                    "supplier_description_match": policy.supplier_description_match,
                    "packs_per_order_unit": _value(policy.packs_per_order_unit),
                    "order_unit": policy.order_unit,
                    "stock_qty_unit": policy.stock_qty_unit.value,
                    "apicbase_uid": policy.apicbase_uid,
                    "apicbase_stock_item_name": policy.apicbase_stock_item_name,
                    "lead_time_calendar_days": policy.lead_time_calendar_days,
                    "shelf_life_anchor": _value(policy.shelf_life_anchor),
                    "yield_factor": _value(policy.yield_factor),
                    "moq_order_units": _value(policy.moq_order_units),
                    "case_multiple_order_units": _value(
                        policy.case_multiple_order_units
                    ),
                    "data_status": policy.data_status,
                    "source_note": optional_text(source["source_note"]),
                }
            )
        rule_rows = []
        for rule in parsed.delivery_rules:
            source = source_rules[rule.delivery_rule_id]
            rule_rows.append(
                {
                    "version_id": version_id,
                    "delivery_rule_id": rule.delivery_rule_id,
                    "location_id": rule.location_id,
                    "ordering_channel": rule.ordering_channel,
                    "storage_class": rule.storage_class.value,
                    "delivery_weekday": rule.delivery_weekday,
                    "covered_service_weekdays": list(rule.covered_service_weekdays),
                    "order_weekday": rule.order_weekday,
                    "order_cutoff_local": temporal_text(source["order_cutoff_local"]),
                    "receipt_available_local": temporal_text(
                        source["receipt_available_local"]
                    ),
                    "review_period_days": rule.review_period_days,
                    "effective_from": rule.effective_from.isoformat(),
                    "effective_to": _value(rule.effective_to),
                    "active": rule.active,
                    "data_status": rule.data_status,
                    "source_note": optional_text(source["source_note"]),
                }
            )
        record_count = len(location_rows) + len(item_rows) + len(rule_rows)
        import_row = self._import_row(
            import_id=import_id,
            dataset_type="master_data",
            location_id=None,
            status="accepted",
            source_version=parsed.source_version,
            source_as_of_at=None,
            coverage_start_date=None,
            coverage_end_date=None,
            files=(file,),
            content_hash=parsed.content_hash,
            record_count=record_count,
            issues=[],
            metadata={
                "master_data_version_id": version_id,
                "location_count": len(location_rows),
                "item_count": len(item_rows),
                "delivery_rule_count": len(rule_rows),
            },
            supersedes_import_id=supersedes,
            user=user,
        )
        return await self._store.persist_master_import(
            {
                "source_import": {**import_row, "status": "validating"},
                "master_data_version": {
                    "id": version_id,
                    "environment": self._settings.app_environment,
                    "version_label": parsed.source_version,
                    "status": "draft",
                    "config_hash": parsed.content_hash,
                    "source_note": f"Imported from {file.file_name}",
                    "created_at": _now().isoformat(),
                    "created_by": user.user_id,
                    "activated_at": None,
                    "activated_by": None,
                    "source_import_id": import_id,
                },
                "locations": location_rows,
                "items": item_rows,
                "item_policy_overrides": policy_rows,
                "delivery_rules": rule_rows,
                "final_status": "accepted",
            }
        )

    async def import_planning_input(
        self, file: SavedUpload, user: AuthenticatedUser
    ) -> JsonObject:
        duplicate = await self._find_duplicate(
            dataset_type="planning_input", content_hash=file.sha256, location_id=None
        )
        if duplicate is not None:
            return duplicate
        try:
            parsed = await asyncio.to_thread(load_planning_template, file.path)
            master = await self._load_master()
            self._validate_planning_references(parsed, master)
        except (InputFileError, ValidationError) as exc:
            message = exc.message if isinstance(exc, ValidationError) else str(exc)
            rejected_id = await self._persist_rejected(
                dataset_type="planning_input",
                location_id=None,
                files=(file,),
                content_hash=file.sha256,
                message=message,
                user=user,
            )
            raise ValidationError(message, details={"import_id": rejected_id}) from exc

        import_id = str(uuid4())
        source_forecasts = {
            (
                text_value(row["location_id"]),
                _date_value(row["service_date"]),
                text_value(row["dish_id"]),
                text_value(row["forecast_version"]),
            ): row
            for row in read_validated_sheet_rows(file.path, "Demand_Plan", DEMAND_HEADERS)
        }
        source_menu = {
            (
                text_value(row["location_id"]),
                _date_value(row["service_date"]),
                text_value(row["dish_id"]),
                text_value(row["menu_version"]),
            ): row
            for row in read_validated_sheet_rows(file.path, "Menu_Calendar", MENU_HEADERS)
        }
        source_bom = {
            text_value(row["bom_line_id"]): row
            for row in read_validated_sheet_rows(file.path, "BOM_Lines", BOM_HEADERS)
        }
        forecast_rows = []
        for forecast in parsed.forecasts:
            source = source_forecasts[
                (
                    forecast.location_id,
                    forecast.service_date,
                    forecast.dish_id,
                    forecast.forecast_version,
                )
            ]
            forecast_rows.append(
                {
                    "import_id": import_id,
                    "location_id": forecast.location_id,
                    "service_date": forecast.service_date.isoformat(),
                    "dish_id": forecast.dish_id,
                    "dish_name": text_value(source["dish_name"]),
                    "forecast_portions": _value(forecast.forecast_portions),
                    "forecast_version": forecast.forecast_version,
                    "provenance": forecast.provenance.value,
                    "source_note": optional_text(source["source_note"]),
                }
            )
        menu_rows = []
        for menu in parsed.menu_entries:
            source = source_menu[
                (menu.location_id, menu.service_date, menu.dish_id, menu.menu_version)
            ]
            menu_rows.append(
                {
                    "import_id": import_id,
                    "location_id": menu.location_id,
                    "service_date": menu.service_date.isoformat(),
                    "dish_id": menu.dish_id,
                    "dish_name": text_value(source["dish_name"]),
                    "menu_version": menu.menu_version,
                    "active": menu.active,
                    "provenance": menu.provenance.value,
                    "source_note": optional_text(source["source_note"]),
                }
            )
        bom_rows = []
        for line in parsed.bom_lines:
            source = source_bom[line.bom_line_id]
            bom_rows.append(
                {
                    "import_id": import_id,
                    "bom_line_id": line.bom_line_id,
                    "dish_id": line.dish_id,
                    "dish_name": text_value(source["dish_name"]),
                    "silo_id": line.silo_id,
                    "silo_name": text_value(source["silo_name"]),
                    "item_id": line.item_id,
                    "grams_per_portion": _value(line.grams_per_portion),
                    "effective_from": line.effective_from.isoformat(),
                    "effective_to": _value(line.effective_to),
                    "bom_version": text_value(source["bom_version"]),
                    "active": True,
                    "data_status": text_value(source["data_status"]),
                    "provenance": line.provenance.value,
                    "source_note": optional_text(source["source_note"]),
                }
            )
        service_dates = [row.service_date for row in parsed.forecasts]
        supersedes = await self._superseded_import_id(
            dataset_type="planning_input", location_id=None
        )
        import_row = self._import_row(
            import_id=import_id,
            dataset_type="planning_input",
            location_id=None,
            status="accepted",
            source_version=parsed.source_version,
            source_as_of_at=None,
            coverage_start_date=min(service_dates) if service_dates else None,
            coverage_end_date=max(service_dates) if service_dates else None,
            files=(file,),
            content_hash=parsed.content_hash,
            record_count=len(forecast_rows) + len(menu_rows) + len(bom_rows),
            issues=[],
            metadata={
                "forecast_count": len(forecast_rows),
                "menu_count": len(menu_rows),
                "bom_line_count": len(bom_rows),
                "location_ids": sorted({row.location_id for row in parsed.forecasts}),
            },
            supersedes_import_id=supersedes,
            user=user,
        )
        return await self._persist_dataset_import(
            import_row=import_row,
            rows_by_table=(
                ("forecast_daily", forecast_rows),
                ("menu_calendar", menu_rows),
                ("bom_lines", bom_rows),
            ),
            final_status="accepted",
        )

    @staticmethod
    def _validate_planning_references(
        planning: PlanningWorkbookData, master: LoadedMaster
    ) -> None:
        location_ids = {row.location_id for row in master.locations if row.active}
        referenced_locations = {
            row.location_id for row in planning.forecasts
        } | {row.location_id for row in planning.menu_entries}
        unknown_locations = sorted(referenced_locations - location_ids)
        if unknown_locations:
            raise ValidationError(
                "The planning workbook references locations absent from the active master version.",
                details={"location_ids": unknown_locations},
            )
        item_ids = {row.item_id for row in master.items if row.active}
        unknown_items = sorted(
            {row.item_id for row in planning.bom_lines if row.item_id not in item_ids}
        )
        if unknown_items:
            raise ValidationError(
                "The planning workbook references items absent from the active master version.",
                details={"item_ids": unknown_items},
            )

    async def import_stock(
        self,
        file: SavedUpload,
        *,
        location_id: str,
        user: AuthenticatedUser,
    ) -> JsonObject:
        duplicate = await self._find_duplicate(
            dataset_type="stock", content_hash=file.sha256, location_id=location_id
        )
        if duplicate is not None:
            return duplicate
        master = await self._load_master()
        location = self._location(master, location_id)
        planning_import = await self._latest_planning_import_for_location(location_id)
        if planning_import is None:
            raise ConflictError(
                "planning_input_missing",
                "Upload an accepted planning workbook for this location before stock, so "
                "the required item set can be validated.",
            )
        planning = await self._load_planning(str(planning_import["id"]), location_id)
        required_item_ids = selected_required_items(
            planning.forecasts, planning.bom_lines
        )
        try:
            result = await asyncio.to_thread(
                normalize_apicbase_stock,
                file.path,
                location_id=location_id,
                timezone_name=location.timezone,
                items=master.items,
                item_policies=master.policies,
                required_item_ids=required_item_ids,
                assume_zero_for_unmapped=False,
            )
        except InputFileError as exc:
            rejected_id = await self._persist_rejected(
                dataset_type="stock",
                location_id=location_id,
                files=(file,),
                content_hash=file.sha256,
                message=str(exc),
                user=user,
            )
            raise ValidationError(str(exc), details={"import_id": rejected_id}) from exc

        import_id = str(uuid4())
        issues = [
            _issue_payload(
                PlanningIssue(
                    code=ExceptionCode.STOCK_MAPPING_UNRESOLVED,
                    severity=Severity.WARNING,
                    dataset="inventory_snapshots",
                    record_ref=(
                        f"location_id={location_id},item_id={review.item_id}"
                    ),
                    message=review.reason,
                    remedy=review.remedy,
                )
            )
            for review in result.reviews
        ]
        snapshot_rows = [
            {
                "import_id": import_id,
                "location_id": row.location_id,
                "item_id": row.item_id,
                "counted_at": row.counted_at.isoformat(),
                "usable_on_hand_units": _value(row.usable_on_hand_units),
                "partial_pack_g": _value(row.partial_pack_g),
                "provenance": row.provenance.value,
            }
            for row in result.snapshots
        ]
        supersedes = await self._superseded_import_id(
            dataset_type="stock", location_id=location_id
        )
        final_status = _accepted_status(len(issues))
        import_row = self._import_row(
            import_id=import_id,
            dataset_type="stock",
            location_id=location_id,
            status=final_status,
            source_version=result.source_version,
            source_as_of_at=result.counted_at,
            coverage_start_date=None,
            coverage_end_date=None,
            files=(file,),
            content_hash=result.content_hash,
            record_count=len(snapshot_rows),
            issues=issues,
            metadata={
                "source_report_location": result.source_report_location,
                "required_item_count": len(required_item_ids),
                "mapped_item_count": len(snapshot_rows),
            },
            supersedes_import_id=supersedes,
            user=user,
        )
        return await self._persist_dataset_import(
            import_row=import_row,
            rows_by_table=(("inventory_snapshots", snapshot_rows),),
            final_status=final_status,
        )

    async def import_purchase_orders(
        self,
        files: tuple[SavedUpload, ...],
        *,
        location_id: str,
        as_of_at: datetime,
        user: AuthenticatedUser,
    ) -> JsonObject:
        if as_of_at.tzinfo is None or as_of_at.utcoffset() is None:
            raise ValidationError("as_of_at must include a timezone offset")
        raw_hash = combined_content_hash(files)
        duplicate = await self._find_duplicate(
            dataset_type="purchase_orders",
            content_hash=raw_hash,
            location_id=location_id,
        )
        if duplicate is not None:
            return duplicate
        master = await self._load_master()
        location = self._location(master, location_id)
        input_dir = files[0].path.parent
        try:
            result = await asyncio.to_thread(
                normalize_transgourmet_pos,
                input_dir,
                as_of_date=as_of_at.date(),
                location_id=location_id,
                item_policies=master.policies,
                timezone_name=location.timezone,
            )
        except InputFileError as exc:
            rejected_id = await self._persist_rejected(
                dataset_type="purchase_orders",
                location_id=location_id,
                files=files,
                content_hash=raw_hash,
                message=str(exc),
                user=user,
            )
            raise ValidationError(str(exc), details={"import_id": rejected_id}) from exc

        import_id = str(uuid4())
        issues = [
            _issue_payload(
                PlanningIssue(
                    code=ExceptionCode.PO_MAPPING_UNRESOLVED,
                    severity=Severity.WARNING,
                    dataset="purchase_orders",
                    record_ref=f"po_line_id={review.po_line_id}",
                    message=(
                        f"Transgourmet article {review.supplier_article_number} "
                        f"({review.supplier_description}) was excluded: {review.reason}."
                    ),
                    remedy=review.remedy,
                )
            )
            for review in result.reviews
        ]
        po_rows = [
            {
                "import_id": import_id,
                "po_line_id": row.po_line_id,
                "po_id": row.po_id,
                "location_id": row.location_id,
                "supplier_id": row.supplier_id,
                "supplier_article_number": row.supplier_article_number,
                "supplier_description": row.supplier_description,
                "item_id": row.item_id,
                "ordered_at": row.ordered_at.isoformat(),
                "expected_receipt_at": _value(row.expected_receipt_at),
                "ordered_qty_order_units": _value(row.ordered_qty_order_units),
                "open_qty_units": _value(row.open_qty_units),
                "package_content_units": _value(row.package_content_units),
                "source_base_unit_code": row.source_base_unit_code,
                "line_total_eur": _value(row.line_total_eur),
                "derived_status": row.derived_status,
                "mapping_status": row.mapping_status,
                "mapping_message": row.mapping_message,
                "provenance": row.provenance.value,
            }
            for row in result.observed_lines
        ]
        expected_dates = [
            row.expected_receipt_at.date()
            for row in result.observed_lines
            if row.expected_receipt_at is not None
        ]
        supersedes = await self._superseded_import_id(
            dataset_type="purchase_orders", location_id=location_id
        )
        final_status = _accepted_status(len(issues))
        import_row = self._import_row(
            import_id=import_id,
            dataset_type="purchase_orders",
            location_id=location_id,
            status=final_status,
            source_version=result.source_version,
            source_as_of_at=as_of_at,
            coverage_start_date=min(expected_dates) if expected_dates else None,
            coverage_end_date=max(expected_dates) if expected_dates else None,
            files=files,
            content_hash=raw_hash,
            record_count=len(po_rows),
            issues=issues,
            metadata={
                "normalized_content_hash": result.content_hash,
                "scanned_pdf_count": result.scanned_pdf_count,
                "ignored_pdf_count": result.ignored_pdf_count,
                "unique_document_count": result.unique_document_count,
                "open_source_line_count": result.open_source_line_count,
                "mapped_open_line_count": result.mapped_open_line_count,
            },
            supersedes_import_id=supersedes,
            user=user,
        )
        return await self._persist_dataset_import(
            import_row=import_row,
            rows_by_table=(("purchase_order_lines", po_rows),),
            final_status=final_status,
        )

    async def list_master_versions(self) -> list[JsonObject]:
        return await self._store.select_rows(
            "master_data_versions",
            filters={"environment": f"eq.{self._settings.app_environment}"},
            order="created_at.desc",
            limit=100,
        )

    async def activate_master_version(
        self, version_id: str, user: AuthenticatedUser
    ) -> JsonObject:
        rows = await self._store.select_rows(
            "master_data_versions",
            filters={"id": f"eq.{version_id}"},
            limit=1,
        )
        if not rows:
            raise NotFoundError("Master-data version", version_id)
        source_import_id = rows[0].get("source_import_id")
        if source_import_id is None:
            raise ConflictError(
                "master_source_missing",
                "The master-data version has no accepted source import and cannot be activated.",
            )
        source = await self.get_import(str(source_import_id))
        if source.get("status") not in {"accepted", "accepted_with_warnings"}:
            raise ConflictError(
                "master_source_not_accepted",
                "Only a version backed by an accepted import can be activated.",
            )
        return await self._store.activate_master_version(
            version_id=version_id,
            actor_id=user.user_id,
            environment=self._settings.app_environment,
        )

    async def _load_master(self, version_id: str | None = None) -> LoadedMaster:
        filters = {"environment": f"eq.{self._settings.app_environment}"}
        if version_id is None:
            filters["status"] = "eq.active"
        else:
            filters["id"] = f"eq.{version_id}"
        versions = await self._store.select_rows(
            "master_data_versions", filters=filters, limit=1
        )
        if not versions:
            identifier = version_id or self._settings.app_environment
            raise NotFoundError("Active master-data version", identifier)
        version = versions[0]
        selected_id = str(version["id"])
        locations_raw, items_raw, policies_raw, rules_raw = await asyncio.gather(
            self._store.select_rows(
                "locations", filters={"version_id": f"eq.{selected_id}"}
            ),
            self._store.select_rows(
                "items", filters={"version_id": f"eq.{selected_id}"}
            ),
            self._store.select_rows(
                "item_policy_overrides", filters={"version_id": f"eq.{selected_id}"}
            ),
            self._store.select_rows(
                "delivery_rules", filters={"version_id": f"eq.{selected_id}"}
            ),
        )
        return LoadedMaster(
            version=version,
            locations=tuple(
                Location(
                    location_id=str(row["location_id"]),
                    location_name=str(row["location_name"]),
                    timezone=str(row["timezone"]),
                    active=bool(row["active"]),
                )
                for row in locations_raw
            ),
            items=tuple(
                Item(
                    item_id=str(row["item_id"]),
                    item_name=str(row["item_name"]),
                    storage_class=StorageClass(str(row["storage_class"])),
                    pack_size_g=_decimal(row["pack_size_g"]),
                    shelf_life_days=(
                        int(row["shelf_life_days"])
                        if row.get("shelf_life_days") is not None
                        else None
                    ),
                    min_safety_days=_optional_decimal(row.get("min_safety_days")),
                    max_cover_days=_optional_decimal(row.get("max_cover_days")),
                    active=bool(row["active"]),
                    provenance=Provenance.MANUAL,
                )
                for row in items_raw
            ),
            policies=tuple(
                ItemPlanningPolicy(
                    item_id=str(row["item_id"]),
                    item_type=ItemType(str(row["item_type"])),
                    official_supplier=str(row["official_supplier"]),
                    ordering_channel=str(row["ordering_channel"]),
                    supplier_id=str(row["supplier_id"]),
                    supplier_article_number=(
                        str(row["supplier_article_number"])
                        if row.get("supplier_article_number") is not None
                        else None
                    ),
                    supplier_description_match=(
                        str(row["supplier_description_match"])
                        if row.get("supplier_description_match") is not None
                        else None
                    ),
                    packs_per_order_unit=_decimal(row["packs_per_order_unit"]),
                    order_unit=str(row["order_unit"]),
                    stock_qty_unit=StockQuantityUnit(str(row["stock_qty_unit"])),
                    apicbase_uid=(
                        str(row["apicbase_uid"])
                        if row.get("apicbase_uid") is not None
                        else None
                    ),
                    apicbase_stock_item_name=(
                        str(row["apicbase_stock_item_name"])
                        if row.get("apicbase_stock_item_name") is not None
                        else None
                    ),
                    lead_time_calendar_days=int(row["lead_time_calendar_days"]),
                    shelf_life_anchor=(
                        ShelfLifeAnchor(str(row["shelf_life_anchor"]))
                        if row.get("shelf_life_anchor") is not None
                        else None
                    ),
                    yield_factor=_decimal(row["yield_factor"]),
                    moq_order_units=_decimal(row["moq_order_units"]),
                    case_multiple_order_units=_decimal(
                        row["case_multiple_order_units"]
                    ),
                    data_status=str(row["data_status"]),
                    provenance=Provenance.MANUAL,
                )
                for row in policies_raw
            ),
            rules=tuple(
                DeliveryCoverageRule(
                    delivery_rule_id=str(row["delivery_rule_id"]),
                    location_id=str(row["location_id"]),
                    ordering_channel=str(row["ordering_channel"]),
                    storage_class=StorageClass(str(row["storage_class"])),
                    delivery_weekday=(
                        int(row["delivery_weekday"])
                        if row.get("delivery_weekday") is not None
                        else None
                    ),
                    covered_service_weekdays=tuple(
                        int(value) for value in row["covered_service_weekdays"]
                    ),
                    order_weekday=(
                        int(row["order_weekday"])
                        if row.get("order_weekday") is not None
                        else None
                    ),
                    review_period_days=int(row["review_period_days"]),
                    effective_from=_date_value(row["effective_from"]),
                    effective_to=_optional_date(row.get("effective_to")),
                    active=bool(row["active"]),
                    data_status=str(row["data_status"]),
                    provenance=Provenance.MANUAL,
                )
                for row in rules_raw
            ),
        )

    @staticmethod
    def _location(master: LoadedMaster, location_id: str) -> Location:
        location = next(
            (row for row in master.locations if row.location_id == location_id), None
        )
        if location is None or not location.active:
            raise NotFoundError("Active location", location_id)
        return location

    async def _load_planning(
        self, import_id: str, location_id: str
    ) -> PlanningWorkbookData:
        forecast_rows, menu_rows, bom_rows = await asyncio.gather(
            self._store.select_rows(
                "forecast_daily",
                filters={
                    "import_id": f"eq.{import_id}",
                    "location_id": f"eq.{location_id}",
                },
            ),
            self._store.select_rows(
                "menu_calendar",
                filters={
                    "import_id": f"eq.{import_id}",
                    "location_id": f"eq.{location_id}",
                },
            ),
            self._store.select_rows(
                "bom_lines", filters={"import_id": f"eq.{import_id}"}
            ),
        )
        if not forecast_rows:
            raise ConflictError(
                "planning_location_missing",
                f"The selected planning import has no forecast rows for {location_id!r}.",
            )
        import_row = await self.get_import(import_id)
        return PlanningWorkbookData(
            forecasts=tuple(
                ForecastDaily(
                    location_id=str(row["location_id"]),
                    dish_id=str(row["dish_id"]),
                    service_date=_date_value(row["service_date"]),
                    forecast_portions=_decimal(row["forecast_portions"]),
                    forecast_version=str(row["forecast_version"]),
                    provenance=Provenance(str(row["provenance"])),
                )
                for row in forecast_rows
            ),
            menu_entries=tuple(
                MenuCalendarEntry(
                    location_id=str(row["location_id"]),
                    dish_id=str(row["dish_id"]),
                    service_date=_date_value(row["service_date"]),
                    menu_version=str(row["menu_version"]),
                    active=bool(row["active"]),
                    provenance=Provenance(str(row["provenance"])),
                )
                for row in menu_rows
            ),
            bom_lines=tuple(
                BomLine(
                    bom_line_id=str(row["bom_line_id"]),
                    dish_id=str(row["dish_id"]),
                    silo_id=str(row["silo_id"]),
                    item_id=str(row["item_id"]),
                    grams_per_portion=_decimal(row["grams_per_portion"]),
                    effective_from=_date_value(row["effective_from"]),
                    effective_to=_optional_date(row.get("effective_to")),
                    provenance=Provenance(str(row["provenance"])),
                )
                for row in bom_rows
                if bool(row["active"])
            ),
            source_version=str(import_row["source_version"]),
            content_hash=str(import_row["content_hash"]),
        )

    async def _selected_import(
        self,
        import_id: str | None,
        *,
        dataset_type: str,
        location_id: str | None,
    ) -> JsonObject:
        if import_id is None:
            if dataset_type == "planning_input" and location_id is not None:
                row = await self._latest_planning_import_for_location(location_id)
            else:
                row = await self._latest_import(dataset_type, location_id=location_id)
            if row is None:
                raise ConflictError(
                    f"{dataset_type}_missing",
                    f"No accepted {dataset_type.replace('_', ' ')} import is available.",
                )
        else:
            row = await self.get_import(import_id)
        if row.get("dataset_type") != dataset_type:
            raise ConflictError(
                "source_type_mismatch",
                f"Import {row.get('id')!r} is not a {dataset_type} source.",
            )
        if row.get("status") not in {"accepted", "accepted_with_warnings"}:
            raise ConflictError(
                "source_not_accepted",
                f"Import {row.get('id')!r} is not accepted and cannot be used in a run.",
            )
        if (
            location_id is not None
            and dataset_type in {"stock", "purchase_orders"}
            and row.get("location_id") != location_id
        ):
            raise ConflictError(
                "source_location_mismatch",
                f"Import {row.get('id')!r} belongs to another location.",
            )
        return row

    async def _assemble_sources(
        self, request: CreatePlanningRunRequest
    ) -> SelectedSources:
        master = await self._load_master(
            str(request.master_data_version_id)
            if request.master_data_version_id is not None
            else None
        )
        if master.version.get("status") != "active":
            raise ConflictError(
                "master_not_active",
                "Planning runs must use the active master-data version.",
            )
        self._location(master, request.location_id)
        planning_import, stock_import, po_import = await asyncio.gather(
            self._selected_import(
                str(request.planning_input_import_id)
                if request.planning_input_import_id is not None
                else None,
                dataset_type="planning_input",
                location_id=request.location_id,
            ),
            self._selected_import(
                str(request.stock_import_id)
                if request.stock_import_id is not None
                else None,
                dataset_type="stock",
                location_id=request.location_id,
            ),
            self._selected_import(
                str(request.purchase_orders_import_id)
                if request.purchase_orders_import_id is not None
                else None,
                dataset_type="purchase_orders",
                location_id=request.location_id,
            ),
        )
        planning = await self._load_planning(str(planning_import["id"]), request.location_id)
        inventory_rows, po_rows = await asyncio.gather(
            self._store.select_rows(
                "inventory_snapshots",
                filters={
                    "import_id": f"eq.{stock_import['id']}",
                    "location_id": f"eq.{request.location_id}",
                },
            ),
            self._store.select_rows(
                "purchase_order_lines",
                filters={
                    "import_id": f"eq.{po_import['id']}",
                    "location_id": f"eq.{request.location_id}",
                    "derived_status": "eq.open",
                    "mapping_status": "eq.mapped",
                },
            ),
        )
        snapshots = tuple(
            InventorySnapshot(
                location_id=str(row["location_id"]),
                item_id=str(row["item_id"]),
                counted_at=_datetime_value(row["counted_at"]),
                usable_on_hand_units=_decimal(row["usable_on_hand_units"]),
                partial_pack_g=_decimal(row["partial_pack_g"]),
                provenance=Provenance(str(row["provenance"])),
            )
            for row in inventory_rows
        )
        purchase_orders = tuple(
            PurchaseOrderLine(
                po_id=str(row["po_id"]),
                po_line_id=str(row["po_line_id"]),
                location_id=str(row["location_id"]),
                supplier_id=str(row["supplier_id"]),
                item_id=str(row["item_id"]),
                ordered_at=_datetime_value(row["ordered_at"]),
                expected_receipt_at=_datetime_value(row["expected_receipt_at"]),
                open_qty_units=_decimal(row["open_qty_units"]),
                status=PurchaseOrderStatus.OPEN,
                provenance=Provenance(str(row["provenance"])),
            )
            for row in po_rows
            if row.get("item_id") is not None
            and row.get("expected_receipt_at") is not None
            and row.get("open_qty_units") is not None
        )
        statuses = (
            InputSourceStatus(
                "forecast_daily",
                Provenance.MANUAL,
                len(planning.forecasts),
                str(planning_import["source_version"]),
            ),
            InputSourceStatus(
                "menu_calendar",
                Provenance.MANUAL,
                len(planning.menu_entries),
                str(planning_import["source_version"]),
            ),
            InputSourceStatus(
                "bom_lines",
                Provenance.MANUAL,
                len(planning.bom_lines),
                str(planning_import["source_version"]),
            ),
            InputSourceStatus(
                "items",
                Provenance.MANUAL,
                len(master.items),
                str(master.version["version_label"]),
            ),
            InputSourceStatus(
                "inventory_snapshots",
                Provenance.OBSERVED,
                len(snapshots),
                str(stock_import["source_version"]),
            ),
            InputSourceStatus(
                "purchase_orders",
                Provenance.OBSERVED,
                len(purchase_orders),
                str(po_import["source_version"]),
            ),
            InputSourceStatus(
                "locations",
                Provenance.MANUAL,
                len(master.locations),
                str(master.version["version_label"]),
            ),
            InputSourceStatus(
                "item_policies",
                Provenance.MANUAL,
                len(master.policies),
                str(master.version["version_label"]),
            ),
            InputSourceStatus(
                "delivery_rules",
                Provenance.MANUAL,
                len(master.rules),
                str(master.version["version_label"]),
            ),
        )
        bundle = CanonicalInputBundle(
            forecasts=planning.forecasts,
            menu_entries=planning.menu_entries,
            bom_lines=planning.bom_lines,
            items=master.items,
            inventory_snapshots=snapshots,
            purchase_orders=purchase_orders,
            source_statuses=statuses,
            locations=master.locations,
            item_policies=master.policies,
            delivery_rules=master.rules,
        )
        return SelectedSources(master, planning_import, stock_import, po_import, bundle)

    async def create_planning_run(
        self,
        request: CreatePlanningRunRequest,
        user: AuthenticatedUser,
    ) -> JsonObject:
        if request.run_mode is RunMode.PRODUCTION:
            raise ConflictError(
                "production_mode_disabled",
                "Production mode is disabled until maintainer approval and shadow validation pass.",
            )
        sources = await self._assemble_sources(request)
        result = await asyncio.to_thread(
            run_improved_plan,
            sources.bundle,
            planning_as_of_at=request.planning_as_of_at,
            run_mode=request.run_mode,
        )
        result = self._merge_import_issues(
            result, (sources.stock_import, sources.purchase_orders_import)
        )
        payload = self._run_payload(result, sources, request.location_id, user)
        persisted_id = await self._store.persist_planning_run(payload)
        return await self.get_planning_run(persisted_id)

    @staticmethod
    def _merge_import_issues(
        result: ImprovedRunResult, imports: tuple[JsonObject, ...]
    ) -> ImprovedRunResult:
        issues = list(result.issues)
        for source in imports:
            raw_issues = source.get("validation_issues")
            if not isinstance(raw_issues, list):
                continue
            for raw in raw_issues:
                if not isinstance(raw, dict):
                    continue
                try:
                    issues.append(
                        PlanningIssue(
                            code=ExceptionCode(str(raw["code"])),
                            severity=Severity(str(raw["severity"])),
                            dataset=(
                                str(raw["dataset"])
                                if raw.get("dataset") is not None
                                else None
                            ),
                            record_ref=(
                                str(raw["record_ref"])
                                if raw.get("record_ref") is not None
                                else None
                            ),
                            message=str(raw["message"]),
                            remedy=str(raw["remedy"]),
                        )
                    )
                except (KeyError, ValueError):
                    continue
        return replace(
            result,
            issues=tuple(
                sorted(
                    issues,
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

    def _run_payload(
        self,
        result: ImprovedRunResult,
        sources: SelectedSources,
        location_id: str,
        user: AuthenticatedUser,
    ) -> JsonObject:
        completed_at = _now()
        master_import_id = sources.master.version.get("source_import_id")
        if master_import_id is None:
            raise ConflictError(
                "master_source_missing",
                "The active master version has no source import reference.",
            )
        imports_by_dataset = {
            "forecast_daily": sources.planning_import,
            "menu_calendar": sources.planning_import,
            "bom_lines": sources.planning_import,
            "items": {**sources.master.version, "id": master_import_id},
            "locations": {**sources.master.version, "id": master_import_id},
            "item_policies": {**sources.master.version, "id": master_import_id},
            "delivery_rules": {**sources.master.version, "id": master_import_id},
            "inventory_snapshots": sources.stock_import,
            "purchase_orders": sources.purchase_orders_import,
        }
        run_inputs = []
        for status in result.source_statuses:
            source = imports_by_dataset[status.dataset]
            run_inputs.append(
                {
                    "run_id": result.run_id,
                    "dataset": status.dataset,
                    "source_version": status.source_version or "unknown",
                    "content_hash": str(
                        source.get("content_hash")
                        or source.get("config_hash")
                        or "unknown"
                    ),
                    "provenance": status.provenance.value,
                    "record_count": status.record_count,
                    "source_import_id": str(source["id"]),
                }
            )
        line_ids = {line.planning_line_id for line in result.planning_lines}
        return {
            "run": {
                "run_id": result.run_id,
                "schema_version": SCHEMA_VERSION,
                "policy_profile": PROFILE,
                "policy_version": POLICY_VERSION,
                "run_mode": result.run_mode.value,
                "planning_as_of_at": result.planning_as_of_at.isoformat(),
                "created_at": completed_at.isoformat(),
                "input_hash": result.input_hash,
                "config_hash": str(sources.master.version["config_hash"]),
                "code_version": __version__,
                "status": result.status.value,
                "master_data_version_id": str(sources.master.version["id"]),
                "created_by": user.user_id,
                "location_id": location_id,
                "completed_at": completed_at.isoformat(),
                "failure_summary": None,
            },
            "run_inputs": run_inputs,
            "planning_lines": [
                {
                    "planning_line_id": line.planning_line_id,
                    "run_id": line.run_id,
                    "location_id": line.location_id,
                    "item_id": line.item_id,
                    "supplier_id": line.supplier_id,
                    "schedule_rule_id": line.schedule_rule_id,
                    "order_date": line.order_date.isoformat(),
                    "expected_delivery_date": line.expected_delivery_date.isoformat(),
                    "coverage_start_date": _value(line.coverage_start_date),
                    "coverage_end_date": _value(line.coverage_end_date),
                    "protection_days": line.protection_days,
                    "gross_requirement_g": _value(line.gross_requirement_g),
                    "yield_factor": _value(line.yield_factor),
                    "yield_factor_provenance": line.yield_factor_provenance.value,
                    "adjusted_requirement_g": _value(line.adjusted_requirement_g),
                    "safety_stock_g": _value(line.safety_stock_g),
                    "safety_stock_provenance": line.safety_stock_provenance.value,
                    "usable_on_hand_g": _value(line.usable_on_hand_g),
                    "open_po_due_g": _value(line.open_po_due_g),
                    "raw_order_g": _value(line.raw_order_g),
                    "shelf_life_cap_g": _value(line.shelf_life_cap_g),
                    "max_cover_cap_g": _value(line.max_cover_cap_g),
                    "capped_order_g": _value(line.capped_order_g),
                    "order_unit_size_g": _value(line.order_unit_size_g),
                    "moq_order_units": _value(line.moq_order_units),
                    "case_multiple_order_units": _value(
                        line.case_multiple_order_units
                    ),
                    "proposed_order_units": _value(line.proposed_order_units),
                    "rounding_delta_g": _value(line.rounding_delta_g),
                    "rounding_direction": line.rounding_direction.value,
                    "candidate_expiry_date": _value(line.candidate_expiry_date),
                    "shelf_life_cap_basis": line.shelf_life_cap_basis.value,
                    "forecast_through_expiry": line.forecast_through_expiry,
                    "projected_candidate_residual_at_expiry_g": _value(
                        line.projected_candidate_residual_at_expiry_g
                    ),
                    "max_cover_end_date": _value(line.max_cover_end_date),
                    "forecast_through_max_cover": line.forecast_through_max_cover,
                    "binding_constraint": line.binding_constraint.value,
                    "constraint_status": line.constraint_status.value,
                    "data_status": line.data_status,
                }
                for line in result.planning_lines
            ],
            "recommendations": [
                {
                    "recommendation_id": row.recommendation_id,
                    "planning_line_id": row.planning_line_id,
                    "run_id": row.run_id,
                    "location_id": row.location_id,
                    "supplier_id": row.supplier_id,
                    "item_id": row.item_id,
                    "order_date": row.order_date.isoformat(),
                    "expected_delivery_date": row.expected_delivery_date.isoformat(),
                    "proposed_qty_units": _value(row.proposed_qty_units),
                }
                for row in result.recommendations
            ],
            "exceptions": [
                {
                    "exception_id": f"EXC-{result.run_id}-{index:04d}",
                    "run_id": result.run_id,
                    "planning_line_id": (
                        issue.record_ref if issue.record_ref in line_ids else None
                    ),
                    "code": issue.code.value,
                    "severity": issue.severity.value,
                    "dataset": issue.dataset,
                    "record_ref": issue.record_ref,
                    "message": issue.message,
                    "remedy": issue.remedy,
                }
                for index, issue in enumerate(result.issues, start=1)
            ],
            "netting_results": [
                {
                    "run_id": result.run_id,
                    "location_id": row.location_id,
                    "item_id": row.item_id,
                    "projection_start_date": row.projection_start_date.isoformat(),
                    "projection_end_date": row.projection_end_date.isoformat(),
                    "opening_on_hand_g": _value(row.opening_on_hand_g),
                    "gross_requirement_g": _value(row.gross_requirement_g),
                    "open_po_due_g": _value(row.open_po_due_g),
                    "net_requirement_g": _value(row.net_requirement_g),
                    "candidate_receipt_g": _value(row.candidate_receipt_g),
                    "overdue_open_po_g": _value(row.overdue_open_po_g),
                    "open_po_after_horizon_g": _value(row.open_po_after_horizon_g),
                    "open_po_after_final_demand_g": _value(
                        row.open_po_after_final_demand_g
                    ),
                    "ending_projected_balance_g": _value(
                        row.ending_projected_balance_g
                    ),
                    "minimum_projected_balance_g": _value(
                        row.minimum_projected_balance_g
                    ),
                    "first_stockout_date": _value(row.first_stockout_date),
                    "unavoidable_pre_candidate_stockout_g": _value(
                        row.unavoidable_pre_candidate_stockout_g
                    ),
                    "risk_horizon_end_date": _value(row.risk_horizon_end_date),
                    "risk_evaluated_through_date": _value(
                        row.risk_evaluated_through_date
                    ),
                    "risk_horizon_fully_observed": row.risk_horizon_fully_observed,
                    "actionable_risk_status": row.actionable_risk_status.value,
                    "first_stockout_within_horizon_date": _value(
                        row.first_stockout_within_horizon_date
                    ),
                    "projected_balance_at_risk_horizon_end_g": _value(
                        row.projected_balance_at_risk_horizon_end_g
                    ),
                    "max_stockout_within_horizon_g": _value(
                        row.max_stockout_within_horizon_g
                    ),
                    "coverage_contract_version": row.coverage_contract_version,
                    "on_hand_coverage_days": row.on_hand_coverage_days,
                    "on_hand_coverage_through_date": _value(
                        row.on_hand_coverage_through_date
                    ),
                    "on_hand_first_uncovered_date": _value(
                        row.on_hand_first_uncovered_date
                    ),
                    "on_hand_coverage_forecast_limited": (
                        row.on_hand_coverage_forecast_limited
                    ),
                    "with_open_po_coverage_days": row.with_open_po_coverage_days,
                    "with_open_po_coverage_through_date": _value(
                        row.with_open_po_coverage_through_date
                    ),
                    "with_open_po_first_uncovered_date": _value(
                        row.with_open_po_first_uncovered_date
                    ),
                    "with_open_po_coverage_forecast_limited": (
                        row.with_open_po_coverage_forecast_limited
                    ),
                    "with_proposal_coverage_days": (
                        row.with_proposal_coverage_days
                    ),
                    "with_proposal_coverage_through_date": _value(
                        row.with_proposal_coverage_through_date
                    ),
                    "with_proposal_first_uncovered_date": _value(
                        row.with_proposal_first_uncovered_date
                    ),
                    "with_proposal_coverage_forecast_limited": (
                        row.with_proposal_coverage_forecast_limited
                    ),
                    "open_po_coverage_extension_days": (
                        row.open_po_coverage_extension_days
                    ),
                    "open_po_coverage_extension_status": _value(
                        row.open_po_coverage_extension_status
                    ),
                    "proposal_coverage_extension_days": (
                        row.proposal_coverage_extension_days
                    ),
                    "proposal_coverage_extension_status": _value(
                        row.proposal_coverage_extension_status
                    ),
                    "open_po_receipts_at_or_after_gap": (
                        row.open_po_receipts_at_or_after_gap
                    ),
                    "proposal_receipts_at_or_after_gap": (
                        row.proposal_receipts_at_or_after_gap
                    ),
                    "protection_horizon_days": row.protection_horizon_days,
                }
                for row in result.netting_results
            ],
            "projection_days": [
                {
                    "run_id": result.run_id,
                    "location_id": row.location_id,
                    "item_id": row.item_id,
                    "projection_date": day.projection_date.isoformat(),
                    "opening_balance_g": _value(day.opening_balance_g),
                    "demand_g": _value(day.demand_g),
                    "open_po_receipts_g": _value(day.open_po_receipts_g),
                    "candidate_receipts_g": _value(day.candidate_receipts_g),
                    "closing_balance_g": _value(day.closing_balance_g),
                    "stockout_g": _value(day.stockout_g),
                }
                for row in result.netting_results
                for day in row.days
            ],
        }

    async def get_planning_run(self, run_id: str) -> JsonObject:
        runs = await self._store.select_rows(
            "planning_runs", filters={"run_id": f"eq.{run_id}"}, limit=1
        )
        if not runs:
            raise NotFoundError("Planning run", run_id)
        run = runs[0]
        inputs, lines, recommendations, exceptions, netting, projections = (
            await asyncio.gather(
                self._store.select_rows(
                    "planning_run_inputs",
                    filters={"run_id": f"eq.{run_id}"},
                    order="dataset.asc",
                ),
                self._store.select_rows(
                    "planning_lines",
                    filters={"run_id": f"eq.{run_id}"},
                    order="order_date.asc,item_id.asc",
                ),
                self._store.select_rows(
                    "planning_recommendations",
                    filters={"run_id": f"eq.{run_id}"},
                    order="order_date.asc,item_id.asc",
                ),
                self._store.select_rows(
                    "planning_exceptions",
                    filters={"run_id": f"eq.{run_id}"},
                    order="severity.desc,code.asc",
                ),
                self._store.select_rows(
                    "planning_netting_results",
                    filters={"run_id": f"eq.{run_id}"},
                    order="item_id.asc",
                ),
                self._store.select_rows(
                    "planning_projection_days",
                    filters={"run_id": f"eq.{run_id}"},
                    order="item_id.asc,projection_date.asc",
                ),
            )
        )
        planning_line_explanations = await self._planning_line_explanations(
            run=run,
            lines=lines,
        )
        return {
            "run": run,
            "summary": {
                "recommendation_count": len(recommendations),
                "issue_count": len(exceptions),
                "blocker_count": sum(
                    row.get("severity") == "blocker" for row in exceptions
                ),
                "items_at_risk": sum(
                    row.get("actionable_risk_status") == "at_risk"
                    for row in netting
                ),
                "items_risk_not_evaluated": sum(
                    row.get("actionable_risk_status") == "not_evaluated"
                    for row in netting
                ),
                "future_stockout_items": sum(
                    row.get("actionable_risk_status") == "covered"
                    and row.get("first_stockout_date") is not None
                    and row.get("first_stockout_within_horizon_date") is None
                    for row in netting
                ),
            },
            "inputs": inputs,
            "planning_lines": lines,
            "planning_line_explanations": planning_line_explanations,
            "explanation_context": {
                "calculation_owner": "python_backend",
                "master_data_version_id": run.get("master_data_version_id"),
                "policy_version": run.get("policy_version"),
                "code_version": run.get("code_version"),
                "field_lineage": {
                    "gross_requirement_g": [
                        "forecast_daily",
                        "menu_calendar",
                        "bom_lines",
                    ],
                    "adjusted_requirement_g": [
                        "gross_requirement_g",
                        "yield_factor",
                    ],
                    "safety_stock_g": [
                        "gross_requirement_g",
                        "protection_days",
                        "min_safety_days",
                    ],
                    "usable_on_hand_g": ["inventory_snapshots"],
                    "open_po_due_g": ["purchase_orders"],
                    "raw_order_g": [
                        "adjusted_daily_demand",
                        "safety_stock_g",
                        "dated_projected_supply_position",
                        "candidate_receipt_date",
                    ],
                    "candidate_expiry_date": [
                        "order_date_or_expected_delivery_date",
                        "shelf_life_days",
                        "shelf_life_anchor",
                    ],
                    "shelf_life_cap_g": [
                        "projected_supply_position",
                        "shelf_life_days",
                        "shelf_life_anchor",
                        "forecast_daily",
                    ],
                    "max_cover_cap_g": [
                        "projected_supply_position",
                        "max_cover_days",
                        "forecast_daily",
                    ],
                    "projected_candidate_residual_at_expiry_g": [
                        "proposed_order_units",
                        "candidate_expiry_date",
                        "projected_competing_supply",
                        "forecast_daily",
                    ],
                    "capped_order_g": [
                        "raw_order_g",
                        "shelf_life_cap_g",
                        "max_cover_cap_g",
                    ],
                    "proposed_order_units": [
                        "capped_order_g",
                        "order_unit_size_g",
                        "moq_order_units",
                        "case_multiple_order_units",
                    ],
                    "on_hand_coverage_days": [
                        "inventory_snapshots",
                        "forecast_daily",
                        "menu_calendar",
                        "bom_lines",
                    ],
                    "with_open_po_coverage_days": [
                        "on_hand_coverage_days",
                        "purchase_orders",
                        "expected_receipt_at",
                    ],
                    "with_proposal_coverage_days": [
                        "with_open_po_coverage_days",
                        "planning_recommendations",
                        "expected_delivery_date",
                    ],
                    "protection_horizon_days": [
                        "planning_as_of_at",
                        "planning_lines.coverage_end_date",
                    ],
                },
                "daily_projection_fields": [
                    "demand_g",
                    "open_po_receipts_g",
                    "candidate_receipts_g",
                    "closing_balance_g",
                    "stockout_g",
                ],
            },
            "coverage_context": {
                "contract_version": 1,
                "available_for_all_items": bool(netting)
                and all(row.get("coverage_contract_version") == 1 for row in netting),
                "requires_fresh_schema_v3_run": not bool(netting)
                or any(row.get("coverage_contract_version") != 1 for row in netting),
                "calculation_owner": "python_backend",
                "unit": "continuous_calendar_days",
                "starts_on": "projection_start_date",
                "first_uncovered_day_is_excluded": True,
                "zero_closing_balance_is_covered": True,
                "same_day_receipts_arrive_before_demand": True,
                "forecast_limited_values_are_lower_bounds": True,
                "scenario_order": [
                    "usable_stock_only",
                    "usable_stock_plus_accepted_open_pos",
                    "usable_stock_plus_open_pos_plus_proposed_receipts",
                ],
                "proposal_is_not_an_order": True,
                "existing_inventory_lot_expiry_available": False,
                "open_po_lot_expiry_available": False,
            },
            "recommendations": recommendations,
            "exceptions": exceptions,
            "netting_results": netting,
            "projection_days": projections,
            "proposal_only": True,
        }

    async def _planning_line_explanations(
        self,
        *,
        run: JsonObject,
        lines: list[JsonObject],
    ) -> list[JsonObject]:
        version_id = run.get("master_data_version_id")
        if version_id is None:
            return []
        master = await self._load_master(str(version_id))
        items = {item.item_id: item for item in master.items}
        policies = {policy.item_id: policy for policy in master.policies}
        rules = {rule.delivery_rule_id: rule for rule in master.rules}
        explanations: list[JsonObject] = []
        for line in lines:
            item_id = str(line["item_id"])
            item = items.get(item_id)
            policy = policies.get(item_id)
            schedule_rule_id = line.get("schedule_rule_id")
            rule = (
                rules.get(str(schedule_rule_id))
                if schedule_rule_id is not None
                else None
            )
            explanations.append(
                {
                    "planning_line_id": str(line["planning_line_id"]),
                    "item": (
                        {
                            "item_id": item.item_id,
                            "item_name": item.item_name,
                            "storage_class": item.storage_class.value,
                            "pack_size_g": _value(item.pack_size_g),
                            "shelf_life_days": item.shelf_life_days,
                            "min_safety_days": _value(item.min_safety_days),
                            "max_cover_days": _value(item.max_cover_days),
                        }
                        if item is not None
                        else None
                    ),
                    "planning_policy": (
                        {
                            "item_type": policy.item_type.value,
                            "official_supplier": policy.official_supplier,
                            "ordering_channel": policy.ordering_channel,
                            "supplier_id": policy.supplier_id,
                            "supplier_article_number": (
                                policy.supplier_article_number
                            ),
                            "packs_per_order_unit": _value(
                                policy.packs_per_order_unit
                            ),
                            "order_unit": policy.order_unit,
                            "lead_time_calendar_days": (
                                policy.lead_time_calendar_days
                            ),
                            "shelf_life_anchor": (
                                policy.shelf_life_anchor.value
                                if policy.shelf_life_anchor is not None
                                else None
                            ),
                            "yield_factor": _value(policy.yield_factor),
                            "moq_order_units": _value(
                                policy.moq_order_units
                            ),
                            "case_multiple_order_units": _value(
                                policy.case_multiple_order_units
                            ),
                            "data_status": policy.data_status,
                            "provenance": policy.provenance.value,
                        }
                        if policy is not None
                        else None
                    ),
                    "delivery_rule": (
                        {
                            "delivery_rule_id": rule.delivery_rule_id,
                            "ordering_channel": rule.ordering_channel,
                            "storage_class": rule.storage_class.value,
                            "delivery_weekday": rule.delivery_weekday,
                            "covered_service_weekdays": list(
                                rule.covered_service_weekdays
                            ),
                            "order_weekday": rule.order_weekday,
                            "review_period_days": rule.review_period_days,
                            "effective_from": rule.effective_from.isoformat(),
                            "effective_to": _value(rule.effective_to),
                            "data_status": rule.data_status,
                            "provenance": rule.provenance.value,
                        }
                        if rule is not None
                        else None
                    ),
                    "protection_mode": (
                        "fresh_delivery_service_window"
                        if item is not None
                        and item.storage_class is StorageClass.FRISCH
                        else "lead_time_plus_review_period"
                    ),
                    "evidence_scope": {
                        "candidate_expiry_basis": line.get(
                            "shelf_life_cap_basis"
                        ),
                        "exact_candidate_lot_expiry": (
                            line.get("shelf_life_cap_basis")
                            == ShelfLifeCapBasis.EXACT_LOT_EXPIRY.value
                        ),
                        "existing_inventory_lot_expiry_available": False,
                        "forecast_through_candidate_expiry": line.get(
                            "forecast_through_expiry"
                        ),
                        "forecast_through_max_cover": line.get(
                            "forecast_through_max_cover"
                        ),
                    },
                }
            )
        return explanations

    async def list_locations(self) -> JsonObject:
        master = await self._load_master()
        return {
            "master_data_version_id": master.version["id"],
            "locations": [
                {
                    "location_id": row.location_id,
                    "location_name": row.location_name,
                    "timezone": row.timezone,
                    "active": row.active,
                }
                for row in master.locations
                if row.active
            ],
        }

    async def _latest_run(self, location_id: str) -> JsonObject | None:
        rows = await self._store.select_rows(
            "planning_runs",
            filters={"location_id": f"eq.{location_id}"},
            order="created_at.desc",
            limit=1,
        )
        return rows[0] if rows else None

    async def planning_status(self, location_id: str) -> JsonObject:
        blockers: list[JsonObject] = []
        try:
            master = await self._load_master()
            self._location(master, location_id)
        except (NotFoundError, ConflictError) as exc:
            master = None
            blockers.append({"code": "master_missing", "message": exc.message})
        planning, stock, po = await asyncio.gather(
            self._latest_planning_import_for_location(location_id),
            self._latest_import("stock", location_id=location_id),
            self._latest_import("purchase_orders", location_id=location_id),
        )
        for code, label, source in (
            ("planning_input_missing", "planning workbook", planning),
            ("stock_missing", "current stock", stock),
            ("purchase_orders_missing", "purchase-order PDFs", po),
        ):
            if source is None:
                blockers.append(
                    {"code": code, "message": f"No accepted {label} import is available."}
                )
        latest_run = await self._latest_run(location_id)
        current_ids = {
            str(source["id"])
            for source in (planning, stock, po)
            if source is not None
        }
        is_current = False
        if latest_run is not None and master is not None:
            run_inputs = await self._store.select_rows(
                "planning_run_inputs",
                columns="source_import_id",
                filters={"run_id": f"eq.{latest_run['run_id']}"},
            )
            used_ids = {
                str(row["source_import_id"])
                for row in run_inputs
                if row.get("source_import_id") is not None
            }
            is_current = (
                current_ids.issubset(used_ids)
                and str(latest_run.get("master_data_version_id"))
                == str(master.version["id"])
            )
        return {
            "location_id": location_id,
            "ready": not blockers,
            "blockers": blockers,
            "sources": {
                "master_data_version": master.version if master is not None else None,
                "planning_input": planning,
                "stock": stock,
                "purchase_orders": po,
            },
            "latest_run": latest_run,
            "latest_run_is_current": is_current,
            "proposal_only": True,
        }

    async def inventory(self, location_id: str) -> JsonObject:
        source = await self._latest_import("stock", location_id=location_id)
        if source is None:
            raise NotFoundError("Accepted stock import for location", location_id)
        master = await self._load_master()
        items = {item.item_id: item for item in master.items}
        rows = await self._store.select_rows(
            "inventory_snapshots",
            filters={
                "import_id": f"eq.{source['id']}",
                "location_id": f"eq.{location_id}",
            },
            order="item_id.asc",
        )
        return {
            "source_import": source,
            "items": [
                {
                    **row,
                    "item_name": items[str(row["item_id"])].item_name,
                    "pack_size_g": _value(items[str(row["item_id"])].pack_size_g),
                }
                for row in rows
                if str(row["item_id"]) in items
            ],
        }

    async def purchase_orders(self, location_id: str) -> JsonObject:
        source = await self._latest_import("purchase_orders", location_id=location_id)
        if source is None:
            raise NotFoundError("Accepted purchase-order import for location", location_id)
        rows = await self._store.select_rows(
            "purchase_order_lines",
            filters={
                "import_id": f"eq.{source['id']}",
                "location_id": f"eq.{location_id}",
            },
            order="ordered_at.desc,po_id.asc,po_line_id.asc",
        )
        return {
            "source_import": source,
            "summary": {
                "document_count": len({row["po_id"] for row in rows}),
                "open_line_count": sum(row["derived_status"] == "open" for row in rows),
                "unmapped_line_count": sum(
                    row["mapping_status"] != "mapped" for row in rows
                ),
            },
            "lines": rows,
            "observed_not_supplier_confirmation": True,
        }

    async def overview(self) -> JsonObject:
        locations_payload = await self.list_locations()
        location_metadata = {
            str(row["location_id"]): row for row in locations_payload["locations"]
        }
        statuses = [
            await self.planning_status(str(row["location_id"]))
            for row in locations_payload["locations"]
        ]
        items_at_risk = 0
        items_risk_not_evaluated = 0
        recommendations_due = 0
        blocking_issues = 0
        open_pos = 0
        today = date.today()
        location_rows: list[JsonObject] = []
        for status_payload in statuses:
            location_id = str(status_payload["location_id"])
            run = status_payload.get("latest_run")
            risk_count = 0
            risk_not_evaluated_count = 0
            earliest_risk_date: str | None = None
            if isinstance(run, dict) and status_payload["latest_run_is_current"]:
                run_id = str(run["run_id"])
                netting, risk_not_evaluated, recommendations, exceptions = await asyncio.gather(
                    self._store.select_rows(
                        "planning_netting_results",
                        filters={
                            "run_id": f"eq.{run_id}",
                            "actionable_risk_status": "eq.at_risk",
                        },
                    ),
                    self._store.select_rows(
                        "planning_netting_results",
                        filters={
                            "run_id": f"eq.{run_id}",
                            "actionable_risk_status": "eq.not_evaluated",
                        },
                    ),
                    self._store.select_rows(
                        "planning_recommendations",
                        filters={"run_id": f"eq.{run_id}"},
                    ),
                    self._store.select_rows(
                        "planning_exceptions",
                        filters={"run_id": f"eq.{run_id}", "severity": "eq.blocker"},
                    ),
                )
                risk_count = len(netting)
                earliest_risk_date = min(
                    (
                        str(row["first_stockout_within_horizon_date"])
                        for row in netting
                        if row.get("first_stockout_within_horizon_date") is not None
                    ),
                    default=None,
                )
                items_at_risk += risk_count
                risk_not_evaluated_count = len(risk_not_evaluated)
                items_risk_not_evaluated += risk_not_evaluated_count
                recommendations_due += sum(
                    _date_value(row["order_date"]) <= today
                    and _decimal(row["proposed_qty_units"]) > 0
                    for row in recommendations
                )
                blocking_issues += len(exceptions)
            po_source = status_payload["sources"].get("purchase_orders")
            if isinstance(po_source, dict):
                po_rows = await self._store.select_rows(
                    "purchase_order_lines",
                    columns="po_line_id",
                    filters={
                        "import_id": f"eq.{po_source['id']}",
                        "derived_status": "eq.open",
                    },
                )
                open_pos += len(po_rows)
            location_rows.append(
                {
                    "location_id": location_id,
                    "location_name": location_metadata[location_id]["location_name"],
                    "timezone": location_metadata[location_id]["timezone"],
                    "ready": status_payload["ready"],
                    "items_at_risk": risk_count,
                    "items_risk_not_evaluated": risk_not_evaluated_count,
                    "earliest_risk_date": earliest_risk_date,
                    "sources": status_payload["sources"],
                    "latest_run": run,
                    "latest_run_is_current": status_payload["latest_run_is_current"],
                    "blockers": status_payload["blockers"],
                }
            )
        latest_run_at = max(
            (
                str(row["latest_run"]["created_at"])
                for row in location_rows
                if isinstance(row.get("latest_run"), dict)
            ),
            default=None,
        )
        return {
            "as_of_date": today.isoformat(),
            "kpis": {
                "locations_ready": sum(row["ready"] for row in location_rows),
                "locations_total": len(location_rows),
                "locations_at_risk": sum(
                    row["items_at_risk"] > 0 for row in location_rows
                ),
                "items_at_risk": items_at_risk,
                "items_risk_not_evaluated": items_risk_not_evaluated,
                "recommendations_due": recommendations_due,
                "blocking_issues": blocking_issues,
                "open_purchase_order_lines": open_pos,
            },
            "latest_run_at": latest_run_at,
            "locations": location_rows,
            "proposal_only": True,
        }

    async def recommendation_json(self, run_id: str) -> JsonObject:
        result = await self.get_planning_run(run_id)
        return {
            "run": result["run"],
            "recommendations": result["recommendations"],
            "exceptions": result["exceptions"],
            "proposal_only": True,
        }

    async def recommendation_csv(self, run_id: str) -> str:
        result = await self.get_planning_run(run_id)
        run = result["run"]
        master = await self._load_master(str(run["master_data_version_id"]))
        policies = {row.item_id: row for row in master.policies}
        items = {row.item_id: row for row in master.items}
        buffer = io.StringIO(newline="")
        fields = (
            "recommendation_id",
            "planning_line_id",
            "run_id",
            "location_id",
            "supplier_id",
            "item_id",
            "item_name",
            "order_date",
            "expected_delivery_date",
            "proposed_qty_order_units",
            "order_unit",
            "packs_per_order_unit",
            "proposed_qty_packs",
            "proposed_qty_g",
            "proposal_only",
        )
        writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in result["recommendations"]:
            item_id = str(row["item_id"])
            policy = policies[item_id]
            item = items[item_id]
            proposed_units = _decimal(row["proposed_qty_units"])
            proposed_packs = proposed_units * policy.packs_per_order_unit
            writer.writerow(
                {
                    **{field: row.get(field) for field in fields if field in row},
                    "item_name": item.item_name,
                    "proposed_qty_order_units": _value(proposed_units),
                    "order_unit": policy.order_unit,
                    "packs_per_order_unit": _value(policy.packs_per_order_unit),
                    "proposed_qty_packs": _value(proposed_packs),
                    "proposed_qty_g": _value(proposed_packs * item.pack_size_g),
                    "proposal_only": "true",
                }
            )
        return buffer.getvalue()
