from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from supply_planning.adapters.errors import InputFileError
from supply_planning.adapters.transgourmet_pdf import scan_transgourmet_pdfs
from supply_planning.domain.models import (
    ItemPlanningPolicy,
    Provenance,
    PurchaseOrderLine,
    PurchaseOrderStatus,
)


def _normalized_description(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


@dataclass(frozen=True, slots=True)
class PoMappingReview:
    po_id: str
    po_line_id: str
    supplier_article_number: str
    supplier_description: str
    ordered_qty_order_units: Decimal
    expected_receipt_date: date | None
    reason: str
    remedy: str

    def as_dict(self) -> dict[str, str]:
        return {
            "po_id": self.po_id,
            "po_line_id": self.po_line_id,
            "supplier_article_number": self.supplier_article_number,
            "supplier_description": self.supplier_description,
            "ordered_qty_order_units": format(self.ordered_qty_order_units, "f"),
            "expected_receipt_date": (
                self.expected_receipt_date.isoformat()
                if self.expected_receipt_date is not None
                else ""
            ),
            "reason": self.reason,
            "remedy": self.remedy,
        }


@dataclass(frozen=True, slots=True)
class PoNormalizationResult:
    purchase_orders: tuple[PurchaseOrderLine, ...]
    reviews: tuple[PoMappingReview, ...]
    source_version: str
    scanned_pdf_count: int
    ignored_pdf_count: int
    unique_document_count: int
    open_source_line_count: int
    mapped_open_line_count: int


def normalize_transgourmet_pos(
    input_dir: Path,
    *,
    as_of_date: date,
    location_id: str,
    item_policies: Iterable[ItemPlanningPolicy],
    timezone_name: str,
) -> PoNormalizationResult:
    if not location_id.strip():
        raise InputFileError("selected location_id must not be blank")
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise InputFileError(f"unknown planning timezone {timezone_name!r}") from exc

    documents, scan_counts = scan_transgourmet_pdfs(
        input_dir, timezone_name=timezone_name
    )
    policies_by_article: dict[str, list[ItemPlanningPolicy]] = {}
    for policy in item_policies:
        if policy.supplier_id != "TRANSGOURMET" or not policy.supplier_article_number:
            continue
        policies_by_article.setdefault(policy.supplier_article_number, []).append(policy)

    purchase_orders: list[PurchaseOrderLine] = []
    reviews: list[PoMappingReview] = []
    open_source_line_count = 0
    for document in documents:
        for line in document.lines:
            if document.order_at.date() > as_of_date:
                continue
            is_open = (
                line.expected_receipt_date is None
                or line.expected_receipt_date > as_of_date
            )
            if not is_open:
                continue
            open_source_line_count += 1
            po_line_id = (
                f"{document.po_id}-D{line.delivery_number}-"
                f"A{line.supplier_article_number}-N{line.article_occurrence}"
            )
            policies = policies_by_article.get(line.supplier_article_number, [])
            normalized_line_description = _normalized_description(line.item_description)
            matches = [
                policy
                for policy in policies
                if not policy.supplier_description_match
                or _normalized_description(policy.supplier_description_match)
                in normalized_line_description
            ]

            reason: str | None = None
            remedy: str | None = None
            if line.expected_receipt_date is None:
                reason = "missing_liefertag"
                remedy = "Enter an expected receipt date before including this open PO in dated netting."
            elif not policies:
                reason = "unmapped_supplier_article"
                remedy = (
                    "Add the article number and reviewed description to the Items tab, "
                    "or confirm that this open line is outside the selected assortment."
                )
            elif not matches:
                reason = "supplier_description_mismatch"
                remedy = (
                    "Correct po_description_match for this article or confirm the supplier article mapping."
                )
            elif len(matches) > 1:
                reason = "ambiguous_supplier_article_description"
                remedy = (
                    "Use distinct reviewed descriptions for every item sharing this supplier article."
                )

            if reason is not None:
                reviews.append(
                    PoMappingReview(
                        po_id=document.po_id,
                        po_line_id=po_line_id,
                        supplier_article_number=line.supplier_article_number,
                        supplier_description=line.item_description,
                        ordered_qty_order_units=line.ordered_qty_units,
                        expected_receipt_date=line.expected_receipt_date,
                        reason=reason,
                        remedy=remedy or "Review the line.",
                    )
                )
                continue

            policy = matches[0]
            purchase_orders.append(
                PurchaseOrderLine(
                    po_id=document.po_id,
                    po_line_id=po_line_id,
                    location_id=location_id,
                    supplier_id=policy.supplier_id,
                    item_id=policy.item_id,
                    ordered_at=document.order_at,
                    expected_receipt_at=datetime.combine(
                        line.expected_receipt_date, time.min, tzinfo=timezone
                    ),
                    open_qty_units=line.ordered_qty_units * policy.packs_per_order_unit,
                    status=PurchaseOrderStatus.OPEN,
                    provenance=Provenance.OBSERVED,
                )
            )

    purchase_orders.sort(
        key=lambda row: (row.expected_receipt_at, row.po_id, row.po_line_id)
    )
    reviews.sort(
        key=lambda row: (
            row.expected_receipt_date or date.min,
            row.po_id,
            row.po_line_id,
        )
    )
    source_hash = hashlib.sha256(
        "\n".join(
            sorted(document.source_content_sha256 for document in documents)
        ).encode("utf-8")
    ).hexdigest()
    return PoNormalizationResult(
        purchase_orders=tuple(purchase_orders),
        reviews=tuple(reviews),
        source_version=f"transgourmet-pdf-{source_hash[:12]}",
        scanned_pdf_count=int(scan_counts["scanned_pdf_count"]),
        ignored_pdf_count=int(scan_counts["ignored_pdf_count"]),
        unique_document_count=int(scan_counts["unique_document_count"]),
        open_source_line_count=open_source_line_count,
        mapped_open_line_count=len(purchase_orders),
    )
