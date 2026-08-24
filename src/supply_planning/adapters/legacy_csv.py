from __future__ import annotations

import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from supply_planning.application.run_legacy import LegacyRunResult
from supply_planning.engine.legacy_kw34 import LegacyKw34Input

REQUIRED_FIELDS = (
    "item_id",
    "grams_per_day",
    "pack_size_g",
    "previous_daily_units",
    "stock_units",
    "observed_order_units",
)


class InputFileError(ValueError):
    """Planner-facing file validation error with location and remedy."""


def _decimal(path: Path, row_number: int, field: str, value: str) -> Decimal:
    try:
        return Decimal(value.strip())
    except (InvalidOperation, AttributeError) as exc:
        raise InputFileError(
            f"{path} row {row_number}, field {field}: {value!r} is not a decimal; "
            "provide a plain numeric value using '.' as the decimal separator"
        ) from exc


def _optional_int(path: Path, row_number: int, field: str, value: str) -> int | None:
    if not value.strip():
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise InputFileError(
            f"{path} row {row_number}, field {field}: {value!r} is not a whole number; "
            "provide an integer number of units or leave the cell blank"
        ) from exc


def load_legacy_csv(path: Path) -> tuple[LegacyKw34Input, ...]:
    try:
        handle = path.open("r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise InputFileError(f"cannot read {path}: {exc}") from exc

    with handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        missing = [field for field in REQUIRED_FIELDS if field not in fieldnames]
        if missing:
            raise InputFileError(
                f"{path}: missing required columns {', '.join(missing)}; "
                f"expected {', '.join(REQUIRED_FIELDS)}"
            )

        rows: list[LegacyKw34Input] = []
        for row_number, row in enumerate(reader, start=2):
            try:
                rows.append(
                    LegacyKw34Input(
                        item_id=(row["item_id"] or "").strip(),
                        grams_per_day=_decimal(
                            path, row_number, "grams_per_day", row["grams_per_day"] or ""
                        ),
                        pack_size_g=_decimal(
                            path, row_number, "pack_size_g", row["pack_size_g"] or ""
                        ),
                        previous_daily_units=_decimal(
                            path,
                            row_number,
                            "previous_daily_units",
                            row["previous_daily_units"] or "",
                        ),
                        stock_units=_decimal(
                            path, row_number, "stock_units", row["stock_units"] or ""
                        ),
                        observed_order_units=_optional_int(
                            path,
                            row_number,
                            "observed_order_units",
                            row["observed_order_units"] or "",
                        ),
                        source_row=row_number,
                    )
                )
            except ValueError as exc:
                if isinstance(exc, InputFileError):
                    raise
                raise InputFileError(f"{path} row {row_number}: {exc}") from exc

    if not rows:
        raise InputFileError(f"{path}: no data rows found")
    return tuple(rows)


def write_legacy_audit_json(path: Path, result: LegacyRunResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = result.as_dict()
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
