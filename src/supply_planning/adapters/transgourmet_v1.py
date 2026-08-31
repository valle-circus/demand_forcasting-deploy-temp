from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Literal
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
    observed_lines: tuple[ObservedPoLine, ...]
    reviews: tuple[PoMappingReview, ...]
    source_version: str
    content_hash: str
    scanned_pdf_count: int
    ignored_pdf_count: int
    unique_document_count: int
    open_source_line_count: int
    mapped_open_line_count: int


@dataclass(frozen=True, slots=True)
class ObservedPoLine:
    po_id: str
    po_line_id: str
    location_id: str
    supplier_id: str
    supplier_article_number: str
    supplier_description: str
    item_id: str | None
    ordered_at: datetime
    expected_receipt_at: datetime | None
    ordered_qty_order_units: Decimal
    open_qty_units: Decimal | None
    package_content_units: Decimal
    source_base_unit_code: str
    line_total_eur: Decimal
    derived_status: Literal["open", "closed", "undated"]
    mapping_status: Literal[
        "mapped",
        "unmapped",
        "description_mismatch",
        "ambiguous",
    ]
    mapping_message: str | None
    provenance: Provenance = Provenance.OBSERVED


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
    for item_policy in item_policies:
        if (
            item_policy.supplier_id != "TRANSGOURMET"
            or not item_policy.supplier_article_number
        ):
            continue
        policies_by_article.setdefault(
            item_policy.supplier_article_number, []
        ).append(item_policy)

    purchase_orders: list[PurchaseOrderLine] = []
    observed_lines: list[ObservedPoLine] = []
    reviews: list[PoMappingReview] = []
    open_source_line_count = 0
    for document in documents:
        for line in document.lines:
            if document.order_at.date() > as_of_date:
                continue
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

            mapping_status: Literal[
                "mapped", "unmapped", "description_mismatch", "ambiguous"
            ]
            mapping_reason: str | None = None
            mapping_remedy: str | None = None
            policy: ItemPlanningPolicy | None = None
            if not policies:
                mapping_status = "unmapped"
                mapping_reason = "unmapped_supplier_article"
                mapping_remedy = (
                    "Add the article number and reviewed description to the Items tab, "
                    "or confirm that this open line is outside the selected assortment."
                )
            elif not matches:
                mapping_status = "description_mismatch"
                mapping_reason = "supplier_description_mismatch"
                mapping_remedy = (
                    "Correct po_description_match for this article or confirm the "
                    "supplier article mapping."
                )
            elif len(matches) > 1:
                mapping_status = "ambiguous"
                mapping_reason = "ambiguous_supplier_article_description"
                mapping_remedy = (
                    "Use distinct reviewed descriptions for every item sharing this "
                    "supplier article."
                )
            else:
                mapping_status = "mapped"
                policy = matches[0]

            if line.expected_receipt_date is None:
                derived_status: Literal["open", "closed", "undated"] = "undated"
                expected_receipt_at = None
            else:
                expected_receipt_at = datetime.combine(
                    line.expected_receipt_date, time.min, tzinfo=timezone
                )
                derived_status = (
                    "open" if line.expected_receipt_date > as_of_date else "closed"
                )

            is_open_source = derived_status in {"open", "undated"}
            if is_open_source:
                open_source_line_count += 1

            review_reason = mapping_reason
            review_remedy = mapping_remedy
            if derived_status == "undated" and mapping_status == "mapped":
                review_reason = "missing_liefertag"
                review_remedy = (
                    "Enter an expected receipt date before including this open PO in dated netting."
                )

            if policy is None or derived_status == "undated":
                open_qty_units: Decimal | None = None
            elif derived_status == "closed":
                open_qty_units = Decimal("0")
            else:
                open_qty_units = line.ordered_qty_units * policy.packs_per_order_unit

            observed_lines.append(
                ObservedPoLine(
                    po_id=document.po_id,
                    po_line_id=po_line_id,
                    location_id=location_id,
                    supplier_id="TRANSGOURMET",
                    supplier_article_number=line.supplier_article_number,
                    supplier_description=line.item_description,
                    item_id=policy.item_id if policy is not None else None,
                    ordered_at=document.order_at,
                    expected_receipt_at=expected_receipt_at,
                    ordered_qty_order_units=line.ordered_qty_units,
                    open_qty_units=open_qty_units,
                    package_content_units=line.package_content_units,
                    source_base_unit_code=line.base_unit_code,
                    line_total_eur=line.line_total_eur,
                    derived_status=derived_status,
                    mapping_status=mapping_status,
                    mapping_message=review_reason,
                )
            )

            if is_open_source and review_reason is not None:
                reviews.append(
                    PoMappingReview(
                        po_id=document.po_id,
                        po_line_id=po_line_id,
                        supplier_article_number=line.supplier_article_number,
                        supplier_description=line.item_description,
                        ordered_qty_order_units=line.ordered_qty_units,
                        expected_receipt_date=line.expected_receipt_date,
                        reason=review_reason,
                        remedy=review_remedy or "Review the line.",
                    )
                )
                continue
            if derived_status != "open" or policy is None or expected_receipt_at is None:
                continue
            purchase_orders.append(
                PurchaseOrderLine(
                    po_id=document.po_id,
                    po_line_id=po_line_id,
                    location_id=location_id,
                    supplier_id=policy.supplier_id,
                    item_id=policy.item_id,
                    ordered_at=document.order_at,
                    expected_receipt_at=expected_receipt_at,
                    open_qty_units=line.ordered_qty_units * policy.packs_per_order_unit,
                    status=PurchaseOrderStatus.OPEN,
                    provenance=Provenance.OBSERVED,
                )
            )

    purchase_orders.sort(
        key=lambda row: (row.expected_receipt_at, row.po_id, row.po_line_id)
    )
    observed_lines.sort(key=lambda row: (row.ordered_at, row.po_id, row.po_line_id))
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
        observed_lines=tuple(observed_lines),
        reviews=tuple(reviews),
        source_version=f"transgourmet-pdf-{source_hash[:12]}",
        content_hash=source_hash,
        scanned_pdf_count=int(scan_counts["scanned_pdf_count"]),
        ignored_pdf_count=int(scan_counts["ignored_pdf_count"]),
        unique_document_count=int(scan_counts["unique_document_count"]),
        open_source_line_count=open_source_line_count,
        mapped_open_line_count=len(purchase_orders),
    )
