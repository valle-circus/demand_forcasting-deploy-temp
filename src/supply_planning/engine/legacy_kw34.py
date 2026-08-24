from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

TWO_DECIMALS = Decimal("0.01")
ONE_DECIMAL = Decimal("0.1")
ZERO = Decimal("0")
LEGACY_BUFFER = Decimal("1.20")
LEGACY_COVER_DAYS = Decimal("6")
LEGACY_BRIDGE_DAYS = Decimal("2.5")


def _round(value: Decimal, quantum: Decimal) -> Decimal:
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def _ceil_units(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_CEILING))


@dataclass(frozen=True, slots=True)
class LegacyKw34Input:
    item_id: str
    grams_per_day: Decimal
    pack_size_g: Decimal
    previous_daily_units: Decimal
    stock_units: Decimal
    observed_order_units: int | None = None
    source_row: int | None = None

    def __post_init__(self) -> None:
        if not self.item_id.strip():
            raise ValueError("item_id must not be blank")
        if self.grams_per_day < 0:
            raise ValueError("grams_per_day must be greater than or equal to zero")
        if self.pack_size_g <= 0:
            raise ValueError("pack_size_g must be greater than zero")
        if self.previous_daily_units < 0:
            raise ValueError("previous_daily_units must be greater than or equal to zero")
        if self.stock_units < 0:
            raise ValueError("stock_units must be greater than or equal to zero")
        if self.observed_order_units is not None and self.observed_order_units < 0:
            raise ValueError("observed_order_units must be greater than or equal to zero")


@dataclass(frozen=True, slots=True)
class LegacyKw34Result:
    item_id: str
    grams_per_day: Decimal
    pack_size_g: Decimal
    daily_units: Decimal
    need_units: int
    previous_daily_units: Decimal
    bridge_units: Decimal
    stock_units: Decimal
    after_units: Decimal
    calculated_order_units: int
    observed_order_units: int | None
    source_row: int | None

    def as_dict(self) -> dict[str, str | int | None]:
        return {
            "item_id": self.item_id,
            "grams_per_day": str(self.grams_per_day),
            "pack_size_g": str(self.pack_size_g),
            "daily_units": str(self.daily_units),
            "need_units": self.need_units,
            "previous_daily_units": str(self.previous_daily_units),
            "bridge_units": str(self.bridge_units),
            "stock_units": str(self.stock_units),
            "after_units": str(self.after_units),
            "calculated_order_units": self.calculated_order_units,
            "observed_order_units": self.observed_order_units,
            "source_row": self.source_row,
        }


def calculate_legacy_kw34(value: LegacyKw34Input) -> LegacyKw34Result:
    """Reproduce the documented KW34 displayed-value calculation profile."""

    daily_units = _round(
        value.grams_per_day / value.pack_size_g * LEGACY_BUFFER,
        TWO_DECIMALS,
    )
    need_units = _ceil_units(daily_units * LEGACY_COVER_DAYS)
    bridge_units = _round(value.previous_daily_units * LEGACY_BRIDGE_DAYS, TWO_DECIMALS)
    after_units = _round(max(ZERO, value.stock_units - bridge_units), ONE_DECIMAL)
    calculated_order_units = _ceil_units(max(ZERO, Decimal(need_units) - after_units))

    return LegacyKw34Result(
        item_id=value.item_id,
        grams_per_day=value.grams_per_day,
        pack_size_g=value.pack_size_g,
        daily_units=daily_units,
        need_units=need_units,
        previous_daily_units=value.previous_daily_units,
        bridge_units=bridge_units,
        stock_units=value.stock_units,
        after_units=after_units,
        calculated_order_units=calculated_order_units,
        observed_order_units=value.observed_order_units,
        source_row=value.source_row,
    )
