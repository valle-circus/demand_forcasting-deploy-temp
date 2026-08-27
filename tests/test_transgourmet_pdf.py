from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from supply_planning.adapters.canonical_csv import load_purchase_orders_csv
from supply_planning.adapters.errors import InputFileError
from supply_planning.adapters.transgourmet_pdf import (
    parse_transgourmet_order_text,
    write_transgourmet_csvs,
)
from supply_planning.domain.models import Provenance

SAMPLE_TEXT = """Bestelldetails
Kundendaten
Kd-Nr.: EXAMPLE
Bestelldatum
21.08.2026, 15:35
Ihre Bestellnum m er
PO-EXAMPLE
L ieferung 1 L iefertag: 24.08.2026
M enge Preis
Chicken Flakes geb raten TK 3kg
Art-Nr. 685245, Geb.: 3, BE: KG
4 93,30 €
L angkornreis TK 1kg
Art-Nr. 681759, Geb.: 10, BE: BT
1 53,40 €
Gesam t L ieferung 1 146,70 €
L ieferung 2 L iefertag: 28.08.2026
M enge Preis
Penne Rigate TK 1kg
Art-Nr. 551557, Geb.: 4, BE: BT
5 81,26 €
Gesam t L ieferung 2 81,26 €
"""

SAMPLE_LAYOUT_TEXT = """Bestelldetails
Kundendaten Bestelldatum
Kd-Nr.: EXAMPLE 21.08.2026, 15:35
Extrarechnung Ihre Bestellnummer
Nein PO-EXAMPLE
Lieferung 1 Liefertag: 24.08.2026
Menge Preis
Chicken Flakes gebraten TK 3kg 4 93,30 €
Art-Nr. 685245, Geb.: 3, BE: KG
Langkornreis TK 1kg 1 53,40 €
Art-Nr. 681759, Geb.: 10, BE: BT
Gesamt Lieferung 1 146,70 €
"""

SAMPLE_NO_DELIVERY_DATE_TEXT = """Bestelldetails
Kundendaten Bestelldatum
Kd-Nr.: EXAMPLE 25.08.2026, 15:35
Ihre Bestellnummer
PO-NO-DATE
Lieferung 1
Menge Preis
Penne Rigate TK 1kg 5 81,26 €
Art-Nr. 551557, Geb.: 4, BE: BT
Gesamt Lieferung 1 81,26 €
"""


class TransgourmetPdfTests(unittest.TestCase):
    def test_parses_multiple_deliveries_and_reconciles_totals(self) -> None:
        document = parse_transgourmet_order_text(
            SAMPLE_TEXT,
            source_file="example.pdf",
            source_file_sha256="a" * 64,
        )

        self.assertEqual(document.customer_po_reference, "PO-EXAMPLE")
        self.assertEqual(len(document.lines), 3)
        self.assertEqual(document.lines[0].supplier_article_number, "685245")
        self.assertEqual(document.lines[0].ordered_qty_units, 4)
        self.assertEqual(document.lines[2].delivery_number, 2)
        self.assertEqual(document.lines[2].expected_receipt_date, date(2026, 8, 28))
        self.assertTrue(document.order_at.isoformat().endswith("+02:00"))

    def test_rejects_partial_or_misread_delivery(self) -> None:
        with self.assertRaisesRegex(InputFileError, "does not match displayed total"):
            parse_transgourmet_order_text(
                SAMPLE_TEXT.replace("Gesam t L ieferung 1 146,70 €", "Gesam t L ieferung 1 1,00 €"),
                source_file="bad.pdf",
                source_file_sha256="b" * 64,
            )

    def test_parses_layout_text_without_broken_item_names(self) -> None:
        document = parse_transgourmet_order_text(
            SAMPLE_LAYOUT_TEXT,
            source_file="layout.pdf",
            source_file_sha256="c" * 64,
        )

        self.assertEqual(document.lines[0].item_description, "Chicken Flakes gebraten TK 3kg")
        self.assertEqual(document.lines[1].item_description, "Langkornreis TK 1kg")

    def test_writes_canonical_open_pos_and_keeps_full_history(self) -> None:
        document = parse_transgourmet_order_text(
            SAMPLE_TEXT,
            source_file="example.pdf",
            source_file_sha256="a" * 64,
        )
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            summary = write_transgourmet_csvs(
                [document],
                output_dir,
                as_of_date=date(2026, 8, 26),
                location_id="LOC_CENTRAL",
                allow_supplier_item_ids=True,
            )

            with (output_dir / "transgourmet_po_history.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                history = list(csv.DictReader(handle))
            with (output_dir / "open_pos.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                open_pos = list(csv.DictReader(handle))
            persisted_summary = json.loads(
                (output_dir / "import_summary.json").read_text(encoding="utf-8")
            )
            canonical_rows = load_purchase_orders_csv(
                output_dir / "open_pos.csv", Provenance.MANUAL
            )

            self.assertEqual(len(history), 3)
            self.assertEqual(len(open_pos), 1)
            self.assertEqual(open_pos[0]["item_id"], "TG-551557")
            self.assertEqual(open_pos[0]["open_qty_units"], "5")
            self.assertEqual(open_pos[0]["status"], "open")
            self.assertEqual(open_pos[0]["location_id"], "LOC_CENTRAL")
            self.assertEqual(
                [row["derived_status_as_of"] for row in history],
                ["closed", "closed", "open"],
            )
            self.assertEqual(len(canonical_rows), 1)
            self.assertEqual(canonical_rows[0].po_line_id, open_pos[0]["po_line_id"])
            self.assertEqual(summary["open_po_line_count"], 1)
            self.assertEqual(summary["same_day_closed_line_count"], 0)
            self.assertEqual(persisted_summary["source_version"], summary["source_version"])

    def test_liefertag_today_is_closed_and_excluded_from_open_pos(self) -> None:
        document = parse_transgourmet_order_text(
            SAMPLE_TEXT,
            source_file="example.pdf",
            source_file_sha256="a" * 64,
        )
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            summary = write_transgourmet_csvs(
                [document],
                output_dir,
                as_of_date=date(2026, 8, 24),
                location_id="LOC_CENTRAL",
                allow_supplier_item_ids=True,
            )

            with (output_dir / "open_pos.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                open_pos = list(csv.DictReader(handle))

            self.assertEqual(len(open_pos), 1)
            self.assertEqual(open_pos[0]["item_id"], "TG-551557")
            self.assertEqual(summary["same_day_closed_line_count"], 2)
            self.assertEqual(summary["closed_history_line_count"], 2)

    def test_missing_liefertag_is_open_but_quarantined_from_dated_netting(self) -> None:
        document = parse_transgourmet_order_text(
            SAMPLE_NO_DELIVERY_DATE_TEXT,
            source_file="no-date.pdf",
            source_file_sha256="d" * 64,
        )
        self.assertIsNone(document.lines[0].expected_receipt_date)

        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            summary = write_transgourmet_csvs(
                [document],
                output_dir,
                as_of_date=date(2026, 8, 26),
                location_id="LOC_CENTRAL",
                allow_supplier_item_ids=True,
            )

            with (output_dir / "transgourmet_po_history.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                history = list(csv.DictReader(handle))
            with (output_dir / "open_pos.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                dated_open_pos = list(csv.DictReader(handle))
            with (output_dir / "undated_open_pos.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                undated_open_pos = list(csv.DictReader(handle))

            self.assertEqual(history[0]["expected_receipt_date"], "")
            self.assertEqual(history[0]["derived_status_as_of"], "open")
            self.assertEqual(dated_open_pos, [])
            self.assertEqual(len(undated_open_pos), 1)
            self.assertEqual(undated_open_pos[0]["status"], "open")
            self.assertEqual(undated_open_pos[0]["reason"], "missing_liefertag")
            self.assertEqual(summary["undated_open_po_line_count"], 1)


if __name__ == "__main__":
    unittest.main()
