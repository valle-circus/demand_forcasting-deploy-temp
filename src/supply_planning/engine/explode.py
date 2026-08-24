from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from supply_planning.domain.models import (
    BomLine,
    ForecastDaily,
    IngredientDemandDaily,
    ItemDemandDaily,
)


class MissingBomError(ValueError):
    """Raised when a forecasted dish has no active BOM on its service date."""


def explode_bom(
    forecasts: Iterable[ForecastDaily],
    bom_lines: Iterable[BomLine],
) -> tuple[IngredientDemandDaily, ...]:
    """Explode daily dish demand while preserving the Dish -> Silo -> Item path."""

    lines_by_dish: dict[str, list[BomLine]] = defaultdict(list)
    for line in bom_lines:
        lines_by_dish[line.dish_id].append(line)

    exploded: list[IngredientDemandDaily] = []
    for forecast in forecasts:
        active_lines = [
            line
            for line in lines_by_dish.get(forecast.dish_id, ())
            if line.is_active_on(forecast.service_date)
        ]
        if not active_lines:
            raise MissingBomError(
                "forecast_daily "
                f"{forecast.location_id}/{forecast.dish_id}/{forecast.service_date.isoformat()}: "
                "no active bom_lines record; add an effective BOM or remove the forecast"
            )

        for line in active_lines:
            required_g = forecast.forecast_portions * line.grams_per_portion
            exploded.append(
                IngredientDemandDaily(
                    location_id=forecast.location_id,
                    service_date=forecast.service_date,
                    dish_id=forecast.dish_id,
                    silo_id=line.silo_id,
                    item_id=line.item_id,
                    forecast_portions=forecast.forecast_portions,
                    grams_per_portion=line.grams_per_portion,
                    required_g=required_g,
                    bom_line_id=line.bom_line_id,
                )
            )

    return tuple(exploded)


def aggregate_item_demand(
    exploded_lines: Iterable[IngredientDemandDaily],
) -> tuple[ItemDemandDaily, ...]:
    """Aggregate exploded grams by location, service date, and purchasable item."""

    totals: dict[tuple[str, date, str], Decimal] = defaultdict(lambda: Decimal("0"))
    counts: dict[tuple[str, date, str], int] = defaultdict(int)
    for line in exploded_lines:
        key = (line.location_id, line.service_date, line.item_id)
        totals[key] += line.required_g
        counts[key] += 1

    return tuple(
        ItemDemandDaily(
            location_id=location_id,
            service_date=service_date,
            item_id=item_id,
            required_g=totals[(location_id, service_date, item_id)],
            source_line_count=counts[(location_id, service_date, item_id)],
        )
        for location_id, service_date, item_id in sorted(totals)
    )
