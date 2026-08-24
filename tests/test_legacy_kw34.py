from __future__ import annotations

import unittest
from decimal import Decimal

from supply_planning.application.run_legacy import run_legacy_kw34
from supply_planning.domain.issues import ExceptionCode
from supply_planning.engine.legacy_kw34 import LegacyKw34Input, calculate_legacy_kw34


class LegacyKw34Tests(unittest.TestCase):
    def test_documented_rounding_sequence(self) -> None:
        result = calculate_legacy_kw34(
            LegacyKw34Input(
                item_id="ITEM_A",
                grams_per_day=Decimal("1000"),
                pack_size_g=Decimal("1000"),
                previous_daily_units=Decimal("1.20"),
                stock_units=Decimal("4"),
                observed_order_units=7,
            )
        )

        self.assertEqual(result.daily_units, Decimal("1.20"))
        self.assertEqual(result.need_units, 8)
        self.assertEqual(result.bridge_units, Decimal("3.00"))
        self.assertEqual(result.after_units, Decimal("1.0"))
        self.assertEqual(result.calculated_order_units, 7)

    def test_bridge_uses_previous_daily_and_half_up_rounding(self) -> None:
        result = calculate_legacy_kw34(
            LegacyKw34Input(
                item_id="ITEM_BRIDGE",
                grams_per_day=Decimal("0"),
                pack_size_g=Decimal("500"),
                previous_daily_units=Decimal("10.01"),
                stock_units=Decimal("30"),
            )
        )

        self.assertEqual(result.bridge_units, Decimal("25.03"))
        self.assertEqual(result.after_units, Decimal("5.0"))

    def test_stock_after_bridge_is_floored_at_zero(self) -> None:
        result = calculate_legacy_kw34(
            LegacyKw34Input(
                item_id="ITEM_FLOOR",
                grams_per_day=Decimal("333"),
                pack_size_g=Decimal("1000"),
                previous_daily_units=Decimal("0.40"),
                stock_units=Decimal("0"),
            )
        )

        self.assertEqual(result.daily_units, Decimal("0.40"))
        self.assertEqual(result.need_units, 3)
        self.assertEqual(result.after_units, Decimal("0.0"))
        self.assertEqual(result.calculated_order_units, 3)

    def test_blank_positive_order_is_reported_as_unexplained(self) -> None:
        run = run_legacy_kw34(
            (
                LegacyKw34Input(
                    item_id="ITEM_BLANK",
                    grams_per_day=Decimal("333"),
                    pack_size_g=Decimal("1000"),
                    previous_daily_units=Decimal("0.40"),
                    stock_units=Decimal("0"),
                    observed_order_units=None,
                ),
            )
        )

        self.assertEqual(
            run.lines[0].issues[0].code,
            ExceptionCode.UNEXPLAINED_BLANK_ORDER,
        )

    def test_run_id_and_output_are_deterministic(self) -> None:
        rows = (
            LegacyKw34Input(
                item_id="ITEM_DETERMINISTIC",
                grams_per_day=Decimal("100"),
                pack_size_g=Decimal("1000"),
                previous_daily_units=Decimal("0.12"),
                stock_units=Decimal("1"),
                observed_order_units=0,
            ),
        )
        first = run_legacy_kw34(rows)
        second = run_legacy_kw34(rows)

        self.assertEqual(first.run_id, second.run_id)
        self.assertEqual(first.as_dict(), second.as_dict())


if __name__ == "__main__":
    unittest.main()
