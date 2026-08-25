from __future__ import annotations

import unittest
from datetime import UTC, date, datetime
from decimal import Decimal

from supply_planning.domain.models import (
    ApprovalDecision,
    ApprovalRecord,
    Item,
    OrderProposal,
    PlanningLine,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    ProposalStatus,
    Provenance,
    StorageClass,
)


class DomainModelTests(unittest.TestCase):
    def test_item_carries_menu_transition_controls(self) -> None:
        item = Item(
            item_id="ITEM_A",
            item_name="Synthetic item",
            storage_class=StorageClass.RT,
            pack_size_g=Decimal("1000"),
            last_order_date_offset_days=28,
            pipeline_cancellable=True,
        )

        self.assertEqual(item.last_order_date_offset_days, 28)
        self.assertTrue(item.pipeline_cancellable)

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

    def test_proposal_rejects_receipt_before_order(self) -> None:
        with self.assertRaisesRegex(ValueError, "expected_delivery_date"):
            OrderProposal(
                proposal_id="PROPOSAL_A",
                planning_line_id="LINE_A",
                run_id="RUN_A",
                location_id="LOC_A",
                supplier_id="SUPPLIER_A",
                item_id="ITEM_A",
                order_date=date(2026, 8, 31),
                expected_delivery_date=date(2026, 8, 24),
                proposed_qty_units=Decimal("1"),
                status=ProposalStatus.PROPOSED,
            )

    def test_approval_requires_timezone_aware_timestamp(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone offset"):
            ApprovalRecord(
                approval_id="APPROVAL_A",
                proposal_id="PROPOSAL_A",
                run_id="RUN_A",
                decision=ApprovalDecision.APPROVED,
                decided_by="planner@example.invalid",
                decided_at=datetime(2026, 8, 24, 9, 0),
                reason="Reviewed against the source plan.",
            )

        approval = ApprovalRecord(
            approval_id="APPROVAL_B",
            proposal_id="PROPOSAL_A",
            run_id="RUN_A",
            decision=ApprovalDecision.REJECTED,
            decided_by="planner@example.invalid",
            decided_at=datetime(2026, 8, 24, 9, 0, tzinfo=UTC),
            reason="Supplier constraint needs review.",
        )
        self.assertEqual(approval.decision, ApprovalDecision.REJECTED)

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
