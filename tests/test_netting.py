from __future__ import annotations

import unittest
from datetime import UTC, date, datetime
from decimal import Decimal

from supply_planning.domain.models import (
    InventorySnapshot,
    Item,
    ItemDemandDaily,
    Provenance,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    StorageClass,
)
from supply_planning.engine.netting import (
    CandidateReceipt,
    InventoryEventKind,
    project_inventory,
)


class NettingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.item = Item(
            item_id="ITEM_A",
            item_name="Synthetic item",
            storage_class=StorageClass.RT,
            pack_size_g=Decimal("500"),
        )
        self.snapshot = InventorySnapshot(
            location_id="LOC_A",
            item_id="ITEM_A",
            counted_at=datetime(2026, 8, 25, tzinfo=UTC),
            usable_on_hand_units=Decimal("2"),
            provenance=Provenance.MANUAL,
        )

    def _po(self, line_id: str, receipt_day: int) -> PurchaseOrderLine:
        return PurchaseOrderLine(
            po_id=f"PO_{line_id}",
            po_line_id=line_id,
            location_id="LOC_A",
            supplier_id="SUP_A",
            item_id="ITEM_A",
            ordered_at=datetime(2026, 8, 20, tzinfo=UTC),
            expected_receipt_at=datetime(2026, 8, receipt_day, tzinfo=UTC),
            open_qty_units=Decimal("1"),
            status=PurchaseOrderStatus.OPEN,
            provenance=Provenance.MANUAL,
        )

    def test_dated_netting_counts_horizon_demand_once(self) -> None:
        demands = (
            ItemDemandDaily("LOC_A", date(2026, 8, 25), "ITEM_A", Decimal("600"), 1),
            ItemDemandDaily("LOC_A", date(2026, 8, 26), "ITEM_A", Decimal("600"), 1),
        )

        result = project_inventory(
            location_id="LOC_A",
            item_id="ITEM_A",
            projection_start_date=date(2026, 8, 25),
            projection_end_date=date(2026, 8, 26),
            demands=demands,
            snapshot=self.snapshot,
            item=self.item,
            purchase_orders=(self._po("OVERDUE", 24), self._po("DUE", 26), self._po("LATE", 27)),
            demand_provenance=Provenance.MANUAL,
        )

        self.assertEqual(result.opening_on_hand_g, Decimal("1000"))
        self.assertEqual(result.gross_requirement_g, Decimal("1200"))
        self.assertEqual(result.open_po_due_g, Decimal("500"))
        self.assertEqual(result.net_requirement_g, Decimal("0"))
        self.assertEqual(result.overdue_open_po_g, Decimal("500"))
        self.assertEqual(result.open_po_after_horizon_g, Decimal("500"))
        self.assertEqual(result.ending_projected_balance_g, Decimal("300"))
        self.assertIsNone(result.first_stockout_date)
        self.assertEqual(
            [event.kind for event in result.events],
            [
                InventoryEventKind.OPENING_BALANCE,
                InventoryEventKind.DEMAND,
                InventoryEventKind.OPEN_PO_RECEIPT,
                InventoryEventKind.DEMAND,
            ],
        )

    def test_candidate_receipt_exposes_unavoidable_pre_arrival_shortage(self) -> None:
        empty_snapshot = InventorySnapshot(
            location_id="LOC_A",
            item_id="ITEM_A",
            counted_at=datetime(2026, 8, 25, tzinfo=UTC),
            usable_on_hand_units=Decimal("0"),
        )
        demands = tuple(
            ItemDemandDaily("LOC_A", date(2026, 8, day), "ITEM_A", Decimal("100"), 1)
            for day in (25, 26, 27)
        )
        candidate = CandidateReceipt(
            candidate_receipt_id="CANDIDATE_A",
            location_id="LOC_A",
            item_id="ITEM_A",
            receipt_date=date(2026, 8, 27),
            quantity_g=Decimal("300"),
            provenance=Provenance.POLICY_DEFAULT,
        )

        result = project_inventory(
            location_id="LOC_A",
            item_id="ITEM_A",
            projection_start_date=date(2026, 8, 25),
            projection_end_date=date(2026, 8, 27),
            demands=demands,
            snapshot=empty_snapshot,
            item=self.item,
            purchase_orders=(),
            demand_provenance=Provenance.MANUAL,
            candidate_receipts=(candidate,),
        )

        self.assertEqual(result.net_requirement_g, Decimal("300"))
        self.assertEqual(result.candidate_receipt_g, Decimal("300"))
        self.assertEqual(result.unavoidable_pre_candidate_stockout_g, Decimal("200"))
        self.assertEqual(result.first_stockout_date, date(2026, 8, 25))
        self.assertEqual(result.ending_projected_balance_g, Decimal("0"))
        day_three = result.days[2]
        self.assertEqual(day_three.candidate_receipts_g, Decimal("300"))
        self.assertEqual(day_three.demand_g, Decimal("100"))

    def test_receipt_on_service_day_is_available_before_daily_demand(self) -> None:
        result = project_inventory(
            location_id="LOC_A",
            item_id="ITEM_A",
            projection_start_date=date(2026, 8, 25),
            projection_end_date=date(2026, 8, 25),
            demands=(
                ItemDemandDaily(
                    "LOC_A", date(2026, 8, 25), "ITEM_A", Decimal("1400"), 1
                ),
            ),
            snapshot=self.snapshot,
            item=self.item,
            purchase_orders=(self._po("SAME_DAY", 25),),
            demand_provenance=Provenance.MANUAL,
        )

        self.assertEqual(result.days[0].open_po_receipts_g, Decimal("500"))
        self.assertEqual(result.days[0].closing_balance_g, Decimal("100"))
        self.assertIsNone(result.first_stockout_date)


if __name__ == "__main__":
    unittest.main()
