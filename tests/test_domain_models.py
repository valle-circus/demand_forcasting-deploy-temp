from __future__ import annotations

import unittest
from datetime import UTC, date, datetime
from decimal import Decimal

from supply_planning.domain.models import (
    Item,
    PlanningLine,
    PlanningRecommendation,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    Provenance,
    StorageClass,
)


class DomainModelTests(unittest.TestCase):
    def test_item_carries_editable_phase2_policy_fields(self) -> None:
        item = Item(
            item_id="ITEM_A",
            item_name="Synthetic item",
            storage_class=StorageClass.RT,
            pack_size_g=Decimal("1000"),
            shelf_life_days=14,
            min_safety_days=Decimal("1.5"),
            max_cover_days=Decimal("7"),
        )

        self.assertEqual(item.shelf_life_days, 14)
        self.assertEqual(item.min_safety_days, Decimal("1.5"))
        self.assertEqual(item.max_cover_days, Decimal("7"))

    def test_planning_line_preserves_derivation_and_schedule(self) -> None:
        line = PlanningLine(
            planning_line_id="LINE_A",
            run_id="RUN_A",
            location_id="LOC_A",
            item_id="ITEM_A",
            supplier_id="SUPPLIER_A",
            gross_requirement_g=Decimal("10000"),
            yield_factor=Decimal("1.10"),
            yield_factor_provenance=Provenance.POLICY_DEFAULT,
            safety_stock_g=Decimal("1000"),
            safety_stock_provenance=Provenance.POLICY_DEFAULT,
            usable_on_hand_g=Decimal("3000"),
            open_po_due_g=Decimal("2000"),
            raw_order_g=Decimal("6000"),
            shelf_life_cap_g=Decimal("9000"),
            max_cover_cap_g=Decimal("8000"),
            capped_order_g=Decimal("6000"),
            proposed_order_units=Decimal("6"),
            rounding_delta_g=Decimal("0"),
            order_date=date(2026, 8, 24),
            expected_delivery_date=date(2026, 8, 31),
        )

        self.assertEqual(line.proposed_order_units, Decimal("6"))
        self.assertEqual(line.open_po_due_g, Decimal("2000"))

    def test_recommendation_rejects_receipt_before_order(self) -> None:
        with self.assertRaisesRegex(ValueError, "expected_delivery_date"):
            PlanningRecommendation(
                recommendation_id="RECOMMENDATION_A",
                planning_line_id="LINE_A",
                run_id="RUN_A",
                location_id="LOC_A",
                supplier_id="SUPPLIER_A",
                item_id="ITEM_A",
                order_date=date(2026, 8, 31),
                expected_delivery_date=date(2026, 8, 24),
                proposed_qty_units=Decimal("1"),
            )

    def test_purchase_order_requires_typed_status(self) -> None:
        with self.assertRaisesRegex(ValueError, "PurchaseOrderStatus"):
            PurchaseOrderLine(
                po_id="PO_A",
                po_line_id="PO_LINE_A",
                location_id="LOC_A",
                supplier_id="SUPPLIER_A",
                item_id="ITEM_A",
                ordered_at=datetime(2026, 8, 24, 9, 0, tzinfo=UTC),
                expected_receipt_at=datetime(2026, 8, 25, 9, 0, tzinfo=UTC),
                open_qty_units=Decimal("1"),
                status="open",  # type: ignore[arg-type]
            )

        valid = PurchaseOrderLine(
            po_id="PO_B",
            po_line_id="PO_LINE_B",
            location_id="LOC_A",
            supplier_id="SUPPLIER_A",
            item_id="ITEM_A",
            ordered_at=datetime(2026, 8, 24, 9, 0, tzinfo=UTC),
            expected_receipt_at=datetime(2026, 8, 25, 9, 0, tzinfo=UTC),
            open_qty_units=Decimal("1"),
            status=PurchaseOrderStatus.OPEN,
        )
        self.assertTrue(valid.status.is_open)


if __name__ == "__main__":
    unittest.main()
