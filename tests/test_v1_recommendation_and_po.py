from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from supply_planning.adapters.transgourmet_pdf import parse_transgourmet_order_text
from supply_planning.adapters.transgourmet_v1 import normalize_transgourmet_pos
from supply_planning.domain.issues import ExceptionCode
from supply_planning.domain.models import (
    BindingConstraint,
    ConstraintStatus,
    DeliveryCoverageRule,
    InventorySnapshot,
    Item,
    ItemDemandDaily,
    ItemPlanningPolicy,
    ItemType,
    Provenance,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    ShelfLifeAnchor,
    StockQuantityUnit,
    StorageClass,
)
from supply_planning.engine.recommend import schedule_recommendations


def _policy(
    item_id: str,
    *,
    item_type: ItemType,
    lead_days: int,
    packs_per_order_unit: str = "1",
    article: str = "123",
) -> ItemPlanningPolicy:
    return ItemPlanningPolicy(
        item_id=item_id,
        item_type=item_type,
        official_supplier="Circus" if item_type is ItemType.POD else "Transgourmet",
        ordering_channel="TRANSGOURMET",
        supplier_id="TRANSGOURMET",
        supplier_article_number=article,
        supplier_description_match="Test Pod" if item_type is ItemType.POD else "Fresh Item",
        packs_per_order_unit=Decimal(packs_per_order_unit),
        order_unit="CARTON" if item_type is ItemType.POD else "PACK",
        stock_qty_unit=StockQuantityUnit.PACK,
        apicbase_uid=None,
        apicbase_stock_item_name=None,
        lead_time_calendar_days=lead_days,
        shelf_life_anchor=(
            ShelfLifeAnchor.ORDER_DATE
            if item_type is ItemType.POD
            else ShelfLifeAnchor.RECEIPT_DATE
        ),
        yield_factor=Decimal("1"),
        moq_order_units=Decimal("1"),
        case_multiple_order_units=Decimal("1"),
        data_status="PROPOSED_REVIEW",
        provenance=Provenance.POLICY_DEFAULT,
    )


class RecommendationEngineTests(unittest.TestCase):
    def test_pod_does_not_let_arrival_repair_pre_arrival_demand(self) -> None:
        start = date(2026, 8, 26)
        item = Item(
            "POD_1", "Test Pod", StorageClass.RT, Decimal("1000"),
            min_safety_days=Decimal("7"),
            provenance=Provenance.POLICY_DEFAULT,
        )
        demands = tuple(
            ItemDemandDaily("LOC_1", start + timedelta(days=offset), "POD_1", Decimal("100"), 1)
            for offset in range(35)
        )
        result = schedule_recommendations(
            run_id="run",
            planning_as_of_date=start,
            daily_item_demand=demands,
            items=(item,),
            item_policies=(
                _policy(
                    "POD_1",
                    item_type=ItemType.POD,
                    lead_days=28,
                    packs_per_order_unit="5",
                ),
            ),
            delivery_rules=(
                DeliveryCoverageRule(
                    "RULE", "LOC_1", "TRANSGOURMET", StorageClass.RT, None, (), None,
                    7, start, None, True, "PROPOSED_REVIEW", Provenance.POLICY_DEFAULT,
                ),
            ),
            snapshots=(
                InventorySnapshot(
                    "LOC_1", "POD_1", datetime.fromisoformat("2026-08-26T00:00:00+02:00"),
                    Decimal("0"), provenance=Provenance.POLICY_DEFAULT,
                ),
            ),
            purchase_orders=(),
        )

        line = result.planning_lines[0]
        self.assertEqual(line.protection_days, 35)
        self.assertEqual(line.gross_requirement_g, Decimal("3500"))
        self.assertEqual(line.safety_stock_g, Decimal("700"))
        self.assertEqual(line.raw_order_g, Decimal("1400"))
        self.assertEqual(line.order_unit_size_g, Decimal("5000"))
        self.assertEqual(line.proposed_order_units, Decimal("1"))
        self.assertEqual(result.recommendations[0].expected_delivery_date, date(2026, 9, 23))

    def test_fresh_sums_actual_covered_days_and_exposes_pack_cap_conflict(self) -> None:
        start = date(2026, 8, 31)  # Monday delivery
        item = Item(
            "FRESH_1", "Fresh Item", StorageClass.FRISCH, Decimal("500"),
            shelf_life_days=5, min_safety_days=Decimal("0.5"), max_cover_days=Decimal("3"),
            provenance=Provenance.POLICY_DEFAULT,
        )
        result = schedule_recommendations(
            run_id="run",
            planning_as_of_date=start,
            daily_item_demand=(
                ItemDemandDaily("LOC_1", date(2026, 9, 1), "FRESH_1", Decimal("100"), 1),
                ItemDemandDaily("LOC_1", date(2026, 9, 2), "FRESH_1", Decimal("300"), 1),
            ),
            items=(item,),
            item_policies=(_policy("FRESH_1", item_type=ItemType.INGREDIENT, lead_days=0),),
            delivery_rules=(
                DeliveryCoverageRule(
                    "FRESH_RULE", "LOC_1", "TRANSGOURMET", StorageClass.FRISCH,
                    0, (1, 2), 0, 7, start, None, True, "PROPOSED_REVIEW",
                    Provenance.POLICY_DEFAULT,
                ),
            ),
            snapshots=(
                InventorySnapshot(
                    "LOC_1", "FRESH_1", datetime.fromisoformat("2026-08-31T00:00:00+02:00"),
                    Decimal("0"), provenance=Provenance.POLICY_DEFAULT,
                ),
            ),
            purchase_orders=(),
        )

        line = result.planning_lines[0]
        self.assertEqual(line.gross_requirement_g, Decimal("400"))
        self.assertEqual(line.safety_stock_g, Decimal("100.0"))
        self.assertEqual(line.raw_order_g, Decimal("500.0"))
        self.assertEqual(line.max_cover_cap_g, Decimal("400"))
        self.assertEqual(line.proposed_order_units, Decimal("0"))
        self.assertEqual(line.constraint_status, ConstraintStatus.NO_SAFE_POSITIVE_ORDER)
        self.assertEqual(
            line.binding_constraint,
            BindingConstraint.SHELF_LIFE_AND_MAX_COVER,
        )
        self.assertEqual(result.recommendations, ())
        codes = {issue.code for issue in result.issues}
        self.assertIn(ExceptionCode.MAX_COVER_CAP_BINDING, codes)
        self.assertIn(ExceptionCode.INFEASIBLE_ORDER_CONSTRAINTS, codes)

    def test_shelf_life_cap_subtracts_competing_stock(self) -> None:
        start = date(2026, 8, 31)
        item = Item(
            "SHORT", "Short life", StorageClass.KUEHL, Decimal("1000"),
            shelf_life_days=5, min_safety_days=Decimal("5"),
        )
        result = schedule_recommendations(
            run_id="run",
            planning_as_of_date=start,
            daily_item_demand=tuple(
                ItemDemandDaily(
                    "LOC_1", start + timedelta(days=offset), "SHORT", Decimal("1000"), 1
                )
                for offset in range(5)
            ),
            items=(item,),
            item_policies=(_policy("SHORT", item_type=ItemType.INGREDIENT, lead_days=0),),
            delivery_rules=(
                DeliveryCoverageRule(
                    "RULE", "LOC_1", "TRANSGOURMET", StorageClass.KUEHL,
                    None, (), None, 5, start, None, True, "SOURCE_VALUE",
                    Provenance.MANUAL,
                ),
            ),
            snapshots=(
                InventorySnapshot(
                    "LOC_1", "SHORT", datetime.fromisoformat("2026-08-31T00:00:00+02:00"),
                    Decimal("4"),
                ),
            ),
            purchase_orders=(),
        )

        line = result.planning_lines[0]
        self.assertEqual(line.raw_order_g, Decimal("6000"))
        self.assertEqual(line.shelf_life_cap_g, Decimal("1000"))
        self.assertEqual(line.proposed_order_units, Decimal("1"))
        self.assertEqual(line.projected_candidate_residual_at_expiry_g, Decimal("0"))
        self.assertEqual(line.binding_constraint, BindingConstraint.SHELF_LIFE)

    def test_hard_shelf_cap_rounds_down_to_safe_pack(self) -> None:
        start = date(2026, 8, 31)
        item = Item(
            "ROUND", "Round safely", StorageClass.KUEHL, Decimal("500"),
            shelf_life_days=1,
        )
        result = schedule_recommendations(
            run_id="run",
            planning_as_of_date=start,
            daily_item_demand=(
                ItemDemandDaily("LOC_1", start, "ROUND", Decimal("700"), 1),
            ),
            items=(item,),
            item_policies=(_policy("ROUND", item_type=ItemType.INGREDIENT, lead_days=0),),
            delivery_rules=(
                DeliveryCoverageRule(
                    "RULE", "LOC_1", "TRANSGOURMET", StorageClass.KUEHL,
                    None, (), None, 1, start, None, True, "SOURCE_VALUE",
                    Provenance.MANUAL,
                ),
            ),
            snapshots=(
                InventorySnapshot(
                    "LOC_1", "ROUND", datetime.fromisoformat("2026-08-31T00:00:00+02:00"),
                    Decimal("0"),
                ),
            ),
            purchase_orders=(),
        )

        line = result.planning_lines[0]
        self.assertEqual(line.shelf_life_cap_g, Decimal("700"))
        self.assertEqual(line.capped_order_g, Decimal("700"))
        self.assertEqual(line.proposed_order_units, Decimal("1"))
        self.assertEqual(line.constraint_status, ConstraintStatus.REDUCED_TO_SAFE_MULTIPLE)
        self.assertEqual(line.rounding_delta_g, Decimal("200"))
        self.assertEqual(line.projected_candidate_residual_at_expiry_g, Decimal("0"))

    def test_max_cover_cap_subtracts_competing_open_po(self) -> None:
        start = date(2026, 8, 31)
        item = Item(
            "PIPELINE", "Pipeline stock", StorageClass.RT, Decimal("1000"),
            min_safety_days=Decimal("5"), max_cover_days=Decimal("5"),
        )
        result = schedule_recommendations(
            run_id="run",
            planning_as_of_date=start,
            daily_item_demand=tuple(
                ItemDemandDaily(
                    "LOC_1", start + timedelta(days=offset), "PIPELINE", Decimal("1000"), 1
                )
                for offset in range(5)
            ),
            items=(item,),
            item_policies=(
                _policy("PIPELINE", item_type=ItemType.INGREDIENT, lead_days=0),
            ),
            delivery_rules=(
                DeliveryCoverageRule(
                    "RULE", "LOC_1", "TRANSGOURMET", StorageClass.RT,
                    None, (), None, 5, start, None, True, "SOURCE_VALUE",
                    Provenance.MANUAL,
                ),
            ),
            snapshots=(
                InventorySnapshot(
                    "LOC_1", "PIPELINE", datetime.fromisoformat("2026-08-31T00:00:00+02:00"),
                    Decimal("0"),
                ),
            ),
            purchase_orders=(
                PurchaseOrderLine(
                    "PO", "PO-LINE", "LOC_1", "TRANSGOURMET", "PIPELINE",
                    datetime.fromisoformat("2026-08-30T00:00:00+02:00"),
                    datetime.fromisoformat("2026-08-31T00:00:00+02:00"),
                    Decimal("4"), PurchaseOrderStatus.OPEN,
                ),
            ),
        )

        line = result.planning_lines[0]
        self.assertEqual(line.raw_order_g, Decimal("6000"))
        self.assertEqual(line.max_cover_cap_g, Decimal("1000"))
        self.assertEqual(line.proposed_order_units, Decimal("1"))
        self.assertEqual(line.binding_constraint, BindingConstraint.MAX_COVER)

    def test_incomplete_expiry_forecast_is_visible_and_not_unlimited(self) -> None:
        start = date(2026, 8, 31)
        item = Item(
            "LONG", "Long life", StorageClass.RT, Decimal("1000"),
            shelf_life_days=30,
        )
        result = schedule_recommendations(
            run_id="run",
            planning_as_of_date=start,
            daily_item_demand=tuple(
                ItemDemandDaily(
                    "LOC_1", start + timedelta(days=offset), "LONG", Decimal("100"), 1
                )
                for offset in range(7)
            ),
            items=(item,),
            item_policies=(_policy("LONG", item_type=ItemType.INGREDIENT, lead_days=0),),
            delivery_rules=(
                DeliveryCoverageRule(
                    "RULE", "LOC_1", "TRANSGOURMET", StorageClass.RT,
                    None, (), None, 7, start, None, True, "SOURCE_VALUE",
                    Provenance.MANUAL,
                ),
            ),
            snapshots=(
                InventorySnapshot(
                    "LOC_1", "LONG", datetime.fromisoformat("2026-08-31T00:00:00+02:00"),
                    Decimal("0"),
                ),
            ),
            purchase_orders=(),
        )

        line = result.planning_lines[0]
        self.assertFalse(line.forecast_through_expiry)
        self.assertEqual(line.shelf_life_cap_g, Decimal("700"))
        self.assertEqual(line.proposed_order_units, Decimal("0"))
        self.assertIn(
            ExceptionCode.SHELF_LIFE_COVERAGE_INCOMPLETE,
            {issue.code for issue in result.issues},
        )

    def test_forecast_evidence_horizon_is_location_wide_not_last_item_demand(self) -> None:
        start = date(2026, 8, 31)
        items = (
            Item("A", "Item A", StorageClass.RT, Decimal("100"), shelf_life_days=3),
            Item("B", "Item B", StorageClass.RT, Decimal("100")),
        )
        result = schedule_recommendations(
            run_id="run",
            planning_as_of_date=start,
            daily_item_demand=(
                ItemDemandDaily("LOC_1", start, "A", Decimal("100"), 1),
                ItemDemandDaily(
                    "LOC_1", start + timedelta(days=4), "B", Decimal("0"), 1
                ),
            ),
            items=items,
            item_policies=(
                _policy("A", item_type=ItemType.INGREDIENT, lead_days=0),
                _policy("B", item_type=ItemType.INGREDIENT, lead_days=0),
            ),
            delivery_rules=(
                DeliveryCoverageRule(
                    "RULE", "LOC_1", "TRANSGOURMET", StorageClass.RT,
                    None, (), None, 1, start, None, True, "SOURCE_VALUE",
                    Provenance.MANUAL,
                ),
            ),
            snapshots=(
                InventorySnapshot(
                    "LOC_1", "A", datetime.fromisoformat("2026-08-31T00:00:00+02:00"),
                    Decimal("0"),
                ),
                InventorySnapshot(
                    "LOC_1", "B", datetime.fromisoformat("2026-08-31T00:00:00+02:00"),
                    Decimal("0"),
                ),
            ),
            purchase_orders=(),
        )

        line_a = next(line for line in result.planning_lines if line.item_id == "A")
        self.assertTrue(line_a.forecast_through_expiry)
        self.assertNotIn(
            ExceptionCode.SHELF_LIFE_COVERAGE_INCOMPLETE,
            {
                issue.code
                for issue in result.issues
                if issue.record_ref == line_a.planning_line_id
            },
        )


class TransgourmetV1Tests(unittest.TestCase):
    def test_open_carton_po_maps_to_inner_pack_units(self) -> None:
        document = parse_transgourmet_order_text(
            """Bestelldetails
Kundendaten Bestelldatum
Kd-Nr.: EXAMPLE 26.08.2026, 10:00
Ihre Bestellnummer
PO-POD
Lieferung 1 Liefertag: 24.09.2026
Menge Preis
Test Pod 1kg 2 10,00 EUR
Art-Nr. 91001, Geb.: 5, BE: KT
Gesamt Lieferung 1 10,00 EUR
""",
            source_file="pod.pdf",
            source_file_sha256="a" * 64,
        )
        policy = _policy(
            "POD_1", item_type=ItemType.POD, lead_days=28,
            packs_per_order_unit="5", article="91001",
        )
        with tempfile.TemporaryDirectory() as directory, patch(
            "supply_planning.adapters.transgourmet_v1.scan_transgourmet_pdfs",
            return_value=((document,), {
                "scanned_pdf_count": 1,
                "ignored_pdf_count": 0,
                "unique_document_count": 1,
            }),
        ):
            result = normalize_transgourmet_pos(
                Path(directory),
                as_of_date=date(2026, 8, 26),
                location_id="LOC_1",
                item_policies=(policy,),
                timezone_name="Europe/Berlin",
            )

        self.assertEqual(result.mapped_open_line_count, 1)
        self.assertEqual(result.purchase_orders[0].open_qty_units, Decimal("10"))
        self.assertEqual(result.reviews, ())


if __name__ == "__main__":
    unittest.main()
