from __future__ import annotations

import unittest
from datetime import UTC, date, datetime, timedelta
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
    ActionableRiskStatus,
    CandidateReceipt,
    CoverageExtensionStatus,
    InventoryEventKind,
    OrderRequirementStatus,
    attach_supply_coverage,
    classify_actionable_risk,
    classify_order_requirement,
    continuous_coverage_runway,
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

    def test_shortage_after_action_horizon_is_future_context_not_current_risk(self) -> None:
        demands = tuple(
            ItemDemandDaily(
                "LOC_A",
                date(2026, 8, 25) + timedelta(days=offset),
                "ITEM_A",
                Decimal("500"),
                1,
            )
            for offset in range(5)
        )
        projected = project_inventory(
            location_id="LOC_A",
            item_id="ITEM_A",
            projection_start_date=date(2026, 8, 25),
            projection_end_date=date(2026, 8, 29),
            demands=demands,
            snapshot=self.snapshot,
            item=self.item,
            purchase_orders=(),
            demand_provenance=Provenance.MANUAL,
        )

        result = classify_actionable_risk(
            projected,
            risk_horizon_end_date=date(2026, 8, 26),
        )

        self.assertEqual(result.first_stockout_date, date(2026, 8, 27))
        self.assertIsNone(result.first_stockout_within_horizon_date)
        self.assertEqual(result.actionable_risk_status, ActionableRiskStatus.COVERED)
        self.assertEqual(
            result.projected_balance_at_risk_horizon_end_g,
            Decimal("0"),
        )

    def test_incomplete_action_horizon_is_not_reported_as_covered(self) -> None:
        projected = project_inventory(
            location_id="LOC_A",
            item_id="ITEM_A",
            projection_start_date=date(2026, 8, 25),
            projection_end_date=date(2026, 8, 25),
            demands=(),
            snapshot=self.snapshot,
            item=self.item,
            purchase_orders=(),
            demand_provenance=Provenance.MANUAL,
        )

        result = classify_actionable_risk(
            projected,
            risk_horizon_end_date=date(2026, 8, 27),
        )

        self.assertEqual(
            result.actionable_risk_status,
            ActionableRiskStatus.NOT_EVALUATED,
        )
        self.assertFalse(result.risk_horizon_fully_observed)
        self.assertEqual(result.risk_evaluated_through_date, date(2026, 8, 25))

    def test_order_requirement_is_separate_from_post_proposal_outcome(self) -> None:
        status = classify_order_requirement(
            accepted_supply_first_uncovered_date=date(2026, 8, 27),
            risk_horizon_end_date=date(2026, 8, 30),
            risk_horizon_fully_observed=True,
        )

        self.assertEqual(status, OrderRequirementStatus.NEEDS_ORDER)

    def test_order_requirement_needs_complete_evidence_before_saying_covered(
        self,
    ) -> None:
        unknown = classify_order_requirement(
            accepted_supply_first_uncovered_date=None,
            risk_horizon_end_date=date(2026, 8, 30),
            risk_horizon_fully_observed=False,
        )
        covered = classify_order_requirement(
            accepted_supply_first_uncovered_date=date(2026, 9, 2),
            risk_horizon_end_date=date(2026, 8, 30),
            risk_horizon_fully_observed=True,
        )

        self.assertEqual(unknown, OrderRequirementStatus.NOT_EVALUATED)
        self.assertEqual(covered, OrderRequirementStatus.COVERED_WITHOUT_ORDER)

    def test_supply_coverage_uses_lumpy_dated_demand_and_nested_scenarios(
        self,
    ) -> None:
        start = date(2026, 8, 25)
        end = date(2026, 8, 30)
        demands = tuple(
            ItemDemandDaily(
                "LOC_A",
                start + timedelta(days=offset),
                "ITEM_A",
                quantity,
                1,
            )
            for offset, quantity in enumerate(
                (
                    Decimal("100"),
                    Decimal("0"),
                    Decimal("900"),
                    Decimal("100"),
                    Decimal("300"),
                    Decimal("200"),
                )
            )
        )
        on_hand_only = project_inventory(
            location_id="LOC_A",
            item_id="ITEM_A",
            projection_start_date=start,
            projection_end_date=end,
            demands=demands,
            snapshot=self.snapshot,
            item=self.item,
            purchase_orders=(),
            demand_provenance=Provenance.MANUAL,
        )
        with_open_pos = project_inventory(
            location_id="LOC_A",
            item_id="ITEM_A",
            projection_start_date=start,
            projection_end_date=end,
            demands=demands,
            snapshot=self.snapshot,
            item=self.item,
            purchase_orders=(self._po("DUE", 28),),
            demand_provenance=Provenance.MANUAL,
        )
        projected = classify_actionable_risk(
            project_inventory(
                location_id="LOC_A",
                item_id="ITEM_A",
                projection_start_date=start,
                projection_end_date=end,
                demands=demands,
                snapshot=self.snapshot,
                item=self.item,
                purchase_orders=(self._po("DUE", 28),),
                demand_provenance=Provenance.MANUAL,
                candidate_receipts=(
                    CandidateReceipt(
                        candidate_receipt_id="PROPOSAL",
                        location_id="LOC_A",
                        item_id="ITEM_A",
                        receipt_date=end,
                        quantity_g=Decimal("500"),
                    ),
                ),
            ),
            risk_horizon_end_date=date(2026, 8, 29),
        )

        result = attach_supply_coverage(
            projected,
            on_hand_only=on_hand_only,
            with_open_pos=with_open_pos,
        )

        self.assertEqual(result.coverage_contract_version, 1)
        self.assertEqual(result.on_hand_coverage_days, 3)
        self.assertEqual(result.on_hand_coverage_through_date, date(2026, 8, 27))
        self.assertEqual(result.on_hand_first_uncovered_date, date(2026, 8, 28))
        self.assertFalse(result.on_hand_coverage_forecast_limited)
        self.assertEqual(result.with_open_po_coverage_days, 5)
        self.assertEqual(result.open_po_coverage_extension_days, 2)
        self.assertEqual(
            result.open_po_coverage_extension_status,
            CoverageExtensionStatus.EXACT,
        )
        self.assertEqual(result.with_proposal_coverage_days, 6)
        self.assertEqual(result.proposal_coverage_extension_days, 1)
        self.assertEqual(
            result.proposal_coverage_extension_status,
            CoverageExtensionStatus.LOWER_BOUND,
        )
        self.assertTrue(result.with_proposal_coverage_forecast_limited)
        self.assertEqual(result.protection_horizon_days, 5)

    def test_late_receipt_does_not_bridge_an_earlier_supply_gap(self) -> None:
        start = date(2026, 8, 25)
        end = date(2026, 8, 27)
        demands = tuple(
            ItemDemandDaily(
                "LOC_A",
                start + timedelta(days=offset),
                "ITEM_A",
                Decimal("600"),
                1,
            )
            for offset in range(3)
        )
        on_hand_only = project_inventory(
            location_id="LOC_A",
            item_id="ITEM_A",
            projection_start_date=start,
            projection_end_date=end,
            demands=demands,
            snapshot=self.snapshot,
            item=self.item,
            purchase_orders=(),
            demand_provenance=Provenance.MANUAL,
        )
        with_open_pos = project_inventory(
            location_id="LOC_A",
            item_id="ITEM_A",
            projection_start_date=start,
            projection_end_date=end,
            demands=demands,
            snapshot=self.snapshot,
            item=self.item,
            purchase_orders=(self._po("TOO_LATE", 27),),
            demand_provenance=Provenance.MANUAL,
        )

        result = attach_supply_coverage(
            with_open_pos,
            on_hand_only=on_hand_only,
            with_open_pos=with_open_pos,
        )

        self.assertEqual(result.on_hand_coverage_days, 1)
        self.assertEqual(result.with_open_po_coverage_days, 1)
        self.assertEqual(result.open_po_coverage_extension_days, 0)
        self.assertEqual(
            result.open_po_coverage_extension_status,
            CoverageExtensionStatus.EXACT,
        )
        self.assertEqual(result.with_open_po_first_uncovered_date, date(2026, 8, 26))
        self.assertTrue(result.open_po_receipts_at_or_after_gap)

    def test_no_shortage_is_an_explicit_forecast_limited_lower_bound(self) -> None:
        projected = project_inventory(
            location_id="LOC_A",
            item_id="ITEM_A",
            projection_start_date=date(2026, 8, 25),
            projection_end_date=date(2026, 8, 27),
            demands=(),
            snapshot=self.snapshot,
            item=self.item,
            purchase_orders=(),
            demand_provenance=Provenance.MANUAL,
        )

        runway = continuous_coverage_runway(projected.days)
        result = attach_supply_coverage(
            projected,
            on_hand_only=projected,
            with_open_pos=projected,
        )

        self.assertEqual(runway.coverage_days, 3)
        self.assertEqual(runway.coverage_through_date, date(2026, 8, 27))
        self.assertIsNone(runway.first_uncovered_date)
        self.assertTrue(runway.forecast_limited)
        self.assertEqual(result.open_po_coverage_extension_days, 0)
        self.assertEqual(
            result.open_po_coverage_extension_status,
            CoverageExtensionStatus.NOT_OBSERVABLE,
        )
        self.assertEqual(
            result.proposal_coverage_extension_status,
            CoverageExtensionStatus.NOT_OBSERVABLE,
        )


if __name__ == "__main__":
    unittest.main()
