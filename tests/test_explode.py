from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from supply_planning.domain.models import BomLine, ForecastDaily
from supply_planning.engine.explode import MissingBomError, aggregate_item_demand, explode_bom


class ExplodeBomTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service_date = date(2026, 8, 17)
        self.forecasts = (
            ForecastDaily(
                location_id="LOC_TEST",
                dish_id="DISH_A",
                service_date=self.service_date,
                forecast_portions=Decimal("10"),
            ),
            ForecastDaily(
                location_id="LOC_TEST",
                dish_id="DISH_B",
                service_date=self.service_date,
                forecast_portions=Decimal("5"),
            ),
        )
        self.bom_lines = (
            BomLine(
                bom_line_id="BOM_A_MAIN",
                dish_id="DISH_A",
                silo_id="SILO_MAIN",
                item_id="ITEM_SHARED",
                grams_per_portion=Decimal("100"),
                effective_from=date(2026, 1, 1),
            ),
            BomLine(
                bom_line_id="BOM_A_PREMIX",
                dish_id="DISH_A",
                silo_id="SILO_PREMIX",
                item_id="ITEM_PREMIX_COMPONENT",
                grams_per_portion=Decimal("25"),
                effective_from=date(2026, 1, 1),
            ),
            BomLine(
                bom_line_id="BOM_B_SHARED",
                dish_id="DISH_B",
                silo_id="SILO_SECONDARY",
                item_id="ITEM_SHARED",
                grams_per_portion=Decimal("200"),
                effective_from=date(2026, 1, 1),
            ),
        )

    def test_preserves_silo_path_and_aggregates_shared_item(self) -> None:
        exploded = explode_bom(self.forecasts, self.bom_lines)

        self.assertEqual(len(exploded), 3)
        self.assertEqual(
            {line.silo_id for line in exploded},
            {"SILO_MAIN", "SILO_PREMIX", "SILO_SECONDARY"},
        )
        totals = {row.item_id: row for row in aggregate_item_demand(exploded)}
        self.assertEqual(totals["ITEM_SHARED"].required_g, Decimal("2000"))
        self.assertEqual(totals["ITEM_SHARED"].source_line_count, 2)
        self.assertEqual(totals["ITEM_PREMIX_COMPONENT"].required_g, Decimal("250"))

    def test_zero_forecast_remains_zero_without_early_rounding(self) -> None:
        zero_forecast = (
            ForecastDaily(
                location_id="LOC_TEST",
                dish_id="DISH_A",
                service_date=self.service_date,
                forecast_portions=Decimal("0"),
            ),
        )
        exploded = explode_bom(zero_forecast, self.bom_lines)
        self.assertTrue(all(line.required_g == Decimal("0") for line in exploded))

    def test_missing_effective_bom_has_human_readable_context(self) -> None:
        forecast = (
            ForecastDaily(
                location_id="LOC_TEST",
                dish_id="DISH_UNKNOWN",
                service_date=self.service_date,
                forecast_portions=Decimal("1"),
            ),
        )
        with self.assertRaisesRegex(MissingBomError, "LOC_TEST/DISH_UNKNOWN/2026-08-17"):
            explode_bom(forecast, self.bom_lines)


if __name__ == "__main__":
    unittest.main()
