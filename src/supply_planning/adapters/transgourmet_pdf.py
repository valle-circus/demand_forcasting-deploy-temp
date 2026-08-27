from __future__ import annotations

import csv
import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from supply_planning.adapters.errors import InputFileError

HISTORY_FIELDS = (
    "source_file",
    "source_file_sha256",
    "source_content_sha256",
    "po_id",
    "customer_po_reference",
    "order_at",
    "delivery_number",
    "expected_receipt_date",
    "derived_status_as_of",
    "supplier_id",
    "supplier_article_number",
    "item_id",
    "item_description",
    "ordered_qty_units",
    "package_content_units",
    "base_unit_code",
    "line_total_eur",
    "provenance",
)

OPEN_PO_FIELDS = (
    "po_id",
    "po_line_id",
    "location_id",
    "supplier_id",
    "item_id",
    "ordered_at",
    "expected_receipt_at",
    "open_qty_units",
    "status",
)

UNDATED_OPEN_PO_FIELDS = (*OPEN_PO_FIELDS, "reason")

SUPPLIER_ITEM_FIELDS = (
    "supplier_article_number",
    "item_id",
    "latest_item_description",
    "package_content_units",
    "base_unit_code",
    "first_ordered_at",
    "last_ordered_at",
    "description_variant_count",
    "package_variant_count",
)

_ART_RE = re.compile(
    r"^Art-Nr\.\s*(?P<article>\d+),\s*Geb\.:\s*(?P<package>[^,]+),"
    r"\s*BE:\s*(?P<base_unit>\S+)\s*$",
    re.IGNORECASE,
)
_QUANTITY_PRICE_RE = re.compile(
    r"^(?P<quantity>\d+(?:[.,]\d+)?)\s+"
    r"(?P<price>[\d.]+,\d{2})\s*EUR\s*$",
    re.IGNORECASE,
)
_ITEM_QUANTITY_PRICE_RE = re.compile(
    r"^(?P<description>.+?)\s+(?P<quantity>\d+(?:[.,]\d+)?)\s+"
    r"(?P<price>[\d.]+,\d{2})\s*EUR\s*$",
    re.IGNORECASE,
)
_ORDER_AT_RE = re.compile(r"\b\d{2}\.\d{2}\.\d{4},\s*\d{2}:\d{2}\b")
_CUSTOMER_PO_RE = re.compile(r"\bPO-[A-Z0-9-]+\b", re.IGNORECASE)
_COPY_SUFFIX_RE = re.compile(r"\s\(\d+\)$")


@dataclass(frozen=True, slots=True)
class TransgourmetOrderLine:
    delivery_number: int
    expected_receipt_date: date | None
    supplier_article_number: str
    item_description: str
    ordered_qty_units: Decimal
    package_content_units: Decimal
    base_unit_code: str
    line_total_eur: Decimal
    article_occurrence: int


@dataclass(frozen=True, slots=True)
class TransgourmetOrderDocument:
    source_file: str
    source_file_sha256: str
    source_content_sha256: str
    order_at: datetime
    customer_po_reference: str | None
    lines: tuple[TransgourmetOrderLine, ...]

    @property
    def po_id(self) -> str:
        return f"TG-{self.order_at:%Y%m%d%H%M}-{self.source_content_sha256[:10].upper()}"


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _normalized_lines(raw_text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", raw_text).replace("\u00a0", " ")
    lines = []
    for raw_line in normalized.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if not line:
            continue
        line = re.sub(r"(?<=[A-ZÄÖÜ]) (?=[a-zäöüß])", "", line)
        lines.append(line.replace("€", "EUR"))
    return tuple(lines)


def _german_decimal(value: str, *, field: str, source_file: str) -> Decimal:
    normalized = value.replace(".", "").replace(",", ".").strip()
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise InputFileError(
            f"{source_file}: {field} value {value!r} is not a German-formatted number"
        ) from exc


def _parse_order_at(value: str, timezone: ZoneInfo, source_file: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%d.%m.%Y, %H:%M")
    except ValueError as exc:
        raise InputFileError(
            f"{source_file}: Bestelldatum {value!r} is not in DD.MM.YYYY, HH:MM format"
        ) from exc
    return parsed.replace(tzinfo=timezone)


def _delivery_header(line: str, source_file: str) -> tuple[int, date | None] | None:
    compact = _compact(line)
    match = re.fullmatch(
        r"Lieferung(?P<number>\d+)"
        r"(?:Liefertag:(?P<date>\d{2}\.\d{2}\.\d{4}))?",
        compact,
        re.IGNORECASE,
    )
    if match is None:
        return None
    if match.group("date") is None:
        return int(match.group("number")), None
    try:
        delivery_date = datetime.strptime(match.group("date"), "%d.%m.%Y").date()
    except ValueError as exc:
        raise InputFileError(
            f"{source_file}: Liefertag {match.group('date')!r} is not a valid date"
        ) from exc
    return int(match.group("number")), delivery_date


def _delivery_total(line: str, delivery_number: int, source_file: str) -> Decimal | None:
    compact = _compact(line)
    prefix = f"GesamtLieferung{delivery_number}"
    if not compact.casefold().startswith(prefix.casefold()):
        return None
    value = compact[len(prefix) :]
    if not value.upper().endswith("EUR"):
        raise InputFileError(
            f"{source_file}: delivery {delivery_number} total has no EUR amount"
        )
    return _german_decimal(
        value[:-3], field=f"delivery {delivery_number} total", source_file=source_file
    )


def _clean_description(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_transgourmet_order_text(
    raw_text: str,
    *,
    source_file: str,
    source_file_sha256: str,
    timezone_name: str = "Europe/Berlin",
) -> TransgourmetOrderDocument:
    """Parse one Transgourmet Bestelldetails PDF text and reconcile its totals."""

    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise InputFileError(f"unknown timezone {timezone_name!r}") from exc

    lines = _normalized_lines(raw_text)
    compact_text = "\n".join(_compact(line).casefold() for line in lines)
    if "bestelldetails" not in compact_text or "art-nr." not in compact_text:
        raise InputFileError(f"{source_file}: not a Transgourmet Bestelldetails export")

    content_text = "\n".join(lines)
    content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()
    order_at_match = _ORDER_AT_RE.search(content_text)
    if order_at_match is None:
        raise InputFileError(f"{source_file}: Bestelldatum was not found")
    order_at = _parse_order_at(order_at_match.group(), timezone, source_file)
    customer_po_match = _CUSTOMER_PO_RE.search(content_text)
    customer_po_reference = customer_po_match.group().upper() if customer_po_match else None

    current_delivery: tuple[int, date | None] | None = None
    totals: dict[int, Decimal] = {}
    extracted_lines: list[TransgourmetOrderLine] = []
    occurrences: dict[tuple[int, str], int] = {}
    article_row_count = 0
    index = 0
    while index < len(lines):
        line = lines[index]
        header = _delivery_header(line, source_file)
        if header is not None:
            current_delivery = header
            index += 1
            continue

        if current_delivery is not None:
            total = _delivery_total(line, current_delivery[0], source_file)
            if total is not None:
                totals[current_delivery[0]] = total
                index += 1
                continue

        article_match = _ART_RE.fullmatch(line)
        if article_match is None:
            index += 1
            continue

        article_row_count += 1
        if current_delivery is None:
            current_delivery = (1, None)
        if index == 0:
            raise InputFileError(f"{source_file}: incomplete item around line {index + 1}")
        quantity_match = (
            _QUANTITY_PRICE_RE.fullmatch(lines[index + 1])
            if index + 1 < len(lines)
            else None
        )
        quantity_follows_article = quantity_match is not None
        item_row_match = _ITEM_QUANTITY_PRICE_RE.fullmatch(lines[index - 1])
        if quantity_match is not None:
            description = lines[index - 1]
        elif item_row_match is not None:
            description = item_row_match.group("description")
            quantity_match = item_row_match
        else:
            raise InputFileError(
                f"{source_file}: item at line {index + 1} has no adjacent quantity/price row"
            )

        delivery_number, delivery_date = current_delivery
        article_number = article_match.group("article")
        occurrence_key = (delivery_number, article_number)
        occurrence = occurrences.get(occurrence_key, 0) + 1
        occurrences[occurrence_key] = occurrence
        extracted_lines.append(
            TransgourmetOrderLine(
                delivery_number=delivery_number,
                expected_receipt_date=delivery_date,
                supplier_article_number=article_number,
                item_description=_clean_description(description),
                ordered_qty_units=_german_decimal(
                    quantity_match.group("quantity"),
                    field="Menge",
                    source_file=source_file,
                ),
                package_content_units=_german_decimal(
                    article_match.group("package"),
                    field="Geb.",
                    source_file=source_file,
                ),
                base_unit_code=article_match.group("base_unit").upper(),
                line_total_eur=_german_decimal(
                    quantity_match.group("price"),
                    field="Preis",
                    source_file=source_file,
                ),
                article_occurrence=occurrence,
            )
        )
        index += 2 if quantity_follows_article else 1

    if not extracted_lines:
        raise InputFileError(f"{source_file}: no Transgourmet item lines were extracted")
    if article_row_count != len(extracted_lines):
        raise InputFileError(
            f"{source_file}: found {article_row_count} article rows but extracted "
            f"{len(extracted_lines)}; do not use a partial import"
        )

    calculated_totals: dict[int, Decimal] = {}
    for order_line in extracted_lines:
        calculated_totals[order_line.delivery_number] = (
            calculated_totals.get(order_line.delivery_number, Decimal("0"))
            + order_line.line_total_eur
        )
    for delivery_number, calculated_total in calculated_totals.items():
        displayed_total = totals.get(delivery_number)
        if displayed_total is None:
            raise InputFileError(
                f"{source_file}: delivery {delivery_number} has no displayed total"
            )
        if calculated_total != displayed_total:
            raise InputFileError(
                f"{source_file}: delivery {delivery_number} line total {calculated_total} "
                f"does not match displayed total {displayed_total}; do not use a partial import"
            )

    return TransgourmetOrderDocument(
        source_file=source_file,
        source_file_sha256=source_file_sha256,
        source_content_sha256=content_hash,
        order_at=order_at,
        customer_po_reference=customer_po_reference,
        lines=tuple(extracted_lines),
    )


def _read_pdf_text(path: Path) -> str:
    try:
        import pdfplumber
    except ImportError as exc:
        raise InputFileError(
            "Transgourmet PDF import requires pdfplumber; install the optional dependency "
            "with: python -m pip install -e \".[pdf-import]\""
        ) from exc

    try:
        logging.getLogger("pdfminer").setLevel(logging.ERROR)
        with pdfplumber.open(path) as document:
            return "\n".join(page.extract_text() or "" for page in document.pages)
    except InputFileError:
        raise
    except Exception as exc:
        raise InputFileError(f"cannot read PDF {path}: {exc}") from exc


def _looks_like_transgourmet(raw_text: str) -> bool:
    compact = _compact(unicodedata.normalize("NFKC", raw_text)).casefold()
    return "bestelldetails" in compact and "art-nr." in compact


def _preferred_copy(document: TransgourmetOrderDocument) -> tuple[bool, str]:
    stem = Path(document.source_file).stem
    return bool(_COPY_SUFFIX_RE.search(stem)), document.source_file.casefold()


def scan_transgourmet_pdfs(
    input_dir: Path,
    *,
    timezone_name: str = "Europe/Berlin",
) -> tuple[tuple[TransgourmetOrderDocument, ...], dict[str, int]]:
    if not input_dir.is_dir():
        raise InputFileError(f"{input_dir}: input directory does not exist")

    pdf_paths = sorted(input_dir.glob("*.pdf"), key=lambda path: path.name.casefold())
    if not pdf_paths:
        raise InputFileError(f"{input_dir}: no PDF files found")

    parsed: list[TransgourmetOrderDocument] = []
    ignored_pdf_count = 0
    for path in pdf_paths:
        raw_text = _read_pdf_text(path)
        if not _looks_like_transgourmet(raw_text):
            ignored_pdf_count += 1
            continue
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        parsed.append(
            parse_transgourmet_order_text(
                raw_text,
                source_file=path.name,
                source_file_sha256=file_hash,
                timezone_name=timezone_name,
            )
        )

    if not parsed:
        raise InputFileError(f"{input_dir}: no Transgourmet Bestelldetails PDFs found")

    by_content: dict[str, TransgourmetOrderDocument] = {}
    for document in parsed:
        existing = by_content.get(document.source_content_sha256)
        if existing is None or _preferred_copy(document) < _preferred_copy(existing):
            by_content[document.source_content_sha256] = document

    documents = tuple(
        sorted(by_content.values(), key=lambda doc: (doc.order_at, doc.source_content_sha256))
    )
    return documents, {
        "scanned_pdf_count": len(pdf_paths),
        "ignored_pdf_count": ignored_pdf_count,
        "matched_pdf_count": len(parsed),
        "unique_document_count": len(documents),
        "duplicate_document_count": len(parsed) - len(documents),
    }


def load_supplier_item_map(path: Path) -> dict[str, str]:
    try:
        handle = path.open("r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise InputFileError(f"cannot read item map {path}: {exc}") from exc
    with handle:
        reader = csv.DictReader(handle)
        required = {"supplier_article_number", "item_id"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise InputFileError(
                f"{path}: missing required columns {', '.join(sorted(missing))}"
            )
        result: dict[str, str] = {}
        for row_number, row in enumerate(reader, start=2):
            article = (row.get("supplier_article_number") or "").strip()
            item_id = (row.get("item_id") or "").strip()
            if not article or not item_id:
                raise InputFileError(
                    f"{path} row {row_number}: supplier_article_number and item_id are required"
                )
            if article in result:
                raise InputFileError(
                    f"{path} row {row_number}: duplicate supplier_article_number {article!r}"
                )
            result[article] = item_id
    return result


def _supplier_item_id(article_number: str) -> str:
    return f"TG-{article_number}"


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _atomic_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def write_transgourmet_csvs(
    documents: Sequence[TransgourmetOrderDocument],
    output_dir: Path,
    *,
    as_of_date: date,
    location_id: str,
    supplier_id: str = "TRANSGOURMET",
    item_map: Mapping[str, str] | None = None,
    allow_supplier_item_ids: bool = False,
    timezone_name: str = "Europe/Berlin",
    scan_counts: Mapping[str, int] | None = None,
) -> dict[str, object]:
    if not documents:
        raise InputFileError("no Transgourmet documents were supplied")
    if not location_id.strip():
        raise InputFileError("--location-id must be a stable nonblank planning location ID")
    if item_map is not None and allow_supplier_item_ids:
        raise InputFileError("use either --item-map or --allow-supplier-item-ids, not both")
    if item_map is None and not allow_supplier_item_ids:
        raise InputFileError(
            "provide --item-map or explicitly use --allow-supplier-item-ids"
        )
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise InputFileError(f"unknown timezone {timezone_name!r}") from exc

    article_numbers = {
        line.supplier_article_number for document in documents for line in document.lines
    }
    if item_map is not None:
        missing_articles = sorted(article_numbers - set(item_map))
        if missing_articles:
            preview = ", ".join(missing_articles[:10])
            suffix = "..." if len(missing_articles) > 10 else ""
            raise InputFileError(
                f"item map is missing {len(missing_articles)} Transgourmet article numbers: "
                f"{preview}{suffix}"
            )

    def item_id(article_number: str) -> str:
        if item_map is not None:
            return item_map[article_number]
        return _supplier_item_id(article_number)

    history_rows: list[dict[str, object]] = []
    open_po_rows: list[dict[str, object]] = []
    undated_open_po_rows: list[dict[str, object]] = []
    item_lines: dict[
        str, list[tuple[TransgourmetOrderDocument, TransgourmetOrderLine]]
    ] = {}
    same_day_closed_line_count = 0
    closed_history_line_count = 0
    for document in documents:
        for line in document.lines:
            selected_item_id = item_id(line.supplier_article_number)
            if document.order_at.date() > as_of_date:
                derived_status = "not_yet_ordered"
            elif (
                line.expected_receipt_date is None
                or line.expected_receipt_date > as_of_date
            ):
                derived_status = "open"
            else:
                derived_status = "closed"
                closed_history_line_count += 1
                if line.expected_receipt_date == as_of_date:
                    same_day_closed_line_count += 1
            history_rows.append(
                {
                    "source_file": document.source_file,
                    "source_file_sha256": document.source_file_sha256,
                    "source_content_sha256": document.source_content_sha256,
                    "po_id": document.po_id,
                    "customer_po_reference": document.customer_po_reference or "",
                    "order_at": document.order_at.isoformat(),
                    "delivery_number": line.delivery_number,
                    "expected_receipt_date": (
                        line.expected_receipt_date.isoformat()
                        if line.expected_receipt_date is not None
                        else ""
                    ),
                    "derived_status_as_of": derived_status,
                    "supplier_id": supplier_id,
                    "supplier_article_number": line.supplier_article_number,
                    "item_id": selected_item_id,
                    "item_description": line.item_description,
                    "ordered_qty_units": _decimal_text(line.ordered_qty_units),
                    "package_content_units": _decimal_text(line.package_content_units),
                    "base_unit_code": line.base_unit_code,
                    "line_total_eur": _decimal_text(line.line_total_eur),
                    "provenance": "manual_pdf",
                }
            )
            item_lines.setdefault(line.supplier_article_number, []).append((document, line))

            if derived_status != "open":
                continue

            po_line_id = (
                f"{document.po_id}-D{line.delivery_number}-"
                f"A{line.supplier_article_number}-N{line.article_occurrence}"
            )
            common_open_fields = {
                "po_id": document.po_id,
                "po_line_id": po_line_id,
                "location_id": location_id,
                "supplier_id": supplier_id,
                "item_id": selected_item_id,
                "ordered_at": document.order_at.isoformat(),
                "open_qty_units": _decimal_text(line.ordered_qty_units),
                "status": "open",
            }
            if line.expected_receipt_date is None:
                undated_open_po_rows.append(
                    {
                        **common_open_fields,
                        "expected_receipt_at": "",
                        "reason": "missing_liefertag",
                    }
                )
            else:
                expected_receipt_at = datetime.combine(
                    line.expected_receipt_date, time.min, tzinfo=timezone
                )
                open_po_rows.append(
                    {
                        **common_open_fields,
                        "expected_receipt_at": expected_receipt_at.isoformat(),
                    }
                )

    history_rows.sort(
        key=lambda row: (
            str(row["order_at"]),
            str(row["po_id"]),
            int(row["delivery_number"]),
            str(row["supplier_article_number"]),
        )
    )
    open_po_rows.sort(
        key=lambda row: (
            str(row["expected_receipt_at"]),
            str(row["po_id"]),
            str(row["po_line_id"]),
        )
    )
    undated_open_po_rows.sort(
        key=lambda row: (
            str(row["ordered_at"]),
            str(row["po_id"]),
            str(row["po_line_id"]),
        )
    )

    supplier_item_rows: list[dict[str, object]] = []
    package_variant_article_count = 0
    for article_number, pairs in sorted(item_lines.items()):
        ordered = sorted(pairs, key=lambda pair: pair[0].order_at)
        descriptions = {line.item_description for _, line in ordered}
        packages = {
            (line.package_content_units, line.base_unit_code) for _, line in ordered
        }
        if len(packages) > 1:
            package_variant_article_count += 1
        latest_document, latest_line = ordered[-1]
        supplier_item_rows.append(
            {
                "supplier_article_number": article_number,
                "item_id": item_id(article_number),
                "latest_item_description": latest_line.item_description,
                "package_content_units": _decimal_text(latest_line.package_content_units),
                "base_unit_code": latest_line.base_unit_code,
                "first_ordered_at": ordered[0][0].order_at.isoformat(),
                "last_ordered_at": latest_document.order_at.isoformat(),
                "description_variant_count": len(descriptions),
                "package_variant_count": len(packages),
            }
        )

    source_hash = hashlib.sha256(
        "\n".join(sorted(document.source_content_sha256 for document in documents)).encode(
            "utf-8"
        )
    ).hexdigest()
    source_version = f"transgourmet-pdf-{source_hash[:12]}"
    warnings = [
        (
            "Status is derived from the explicit as-of date: a missing or future "
            "Liefertag is open; a Liefertag on/before the as-of date is closed/received. "
            "PDFs expose ordered quantity, not remaining quantity, so open quantities "
            "still use the displayed ordered quantity."
        ),
        (
            "When Liefertag is present, expected_receipt_at uses 00:00 in "
            f"{timezone_name}. The current engine nets at daily grain."
        ),
    ]
    if allow_supplier_item_ids:
        warnings.append(
            "item_id uses provisional supplier-native IDs (TG-<article number>); replace "
            "them with an approved cross-system mapping before joining to a different item master."
        )
    if same_day_closed_line_count:
        warnings.append(
            f"{same_day_closed_line_count} history rows have Liefertag on the as-of date "
            "and were classified closed/received under the confirmed business rule."
        )
    if undated_open_po_rows:
        warnings.append(
            f"{len(undated_open_po_rows)} open rows have no Liefertag. They are retained "
            "in undated_open_pos.csv but excluded from canonical dated netting until an "
            "expected receipt date is supplied."
        )
    if package_variant_article_count:
        warnings.append(
            f"{package_variant_article_count} supplier article has multiple displayed "
            "Geb./BE combinations in the history; review it before accepting pack mapping."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    history_path = output_dir / "transgourmet_po_history.csv"
    open_pos_path = output_dir / "open_pos.csv"
    undated_open_pos_path = output_dir / "undated_open_pos.csv"
    supplier_items_path = output_dir / "transgourmet_supplier_items.csv"
    summary_path = output_dir / "import_summary.json"
    _atomic_csv(history_path, HISTORY_FIELDS, history_rows)
    _atomic_csv(open_pos_path, OPEN_PO_FIELDS, open_po_rows)
    _atomic_csv(
        undated_open_pos_path,
        UNDATED_OPEN_PO_FIELDS,
        undated_open_po_rows,
    )
    _atomic_csv(supplier_items_path, SUPPLIER_ITEM_FIELDS, supplier_item_rows)

    summary: dict[str, object] = {
        **dict(scan_counts or {}),
        "history_line_count": len(history_rows),
        "open_po_line_count": len(open_po_rows),
        "undated_open_po_line_count": len(undated_open_po_rows),
        "closed_history_line_count": closed_history_line_count,
        "same_day_closed_line_count": same_day_closed_line_count,
        "supplier_article_count": len(supplier_item_rows),
        "package_variant_article_count": package_variant_article_count,
        "as_of_date": as_of_date.isoformat(),
        "location_id": location_id,
        "supplier_id": supplier_id,
        "timezone": timezone_name,
        "source_version": source_version,
        "outputs": {
            "history": str(history_path),
            "open_pos": str(open_pos_path),
            "undated_open_pos": str(undated_open_pos_path),
            "supplier_items": str(supplier_items_path),
            "summary": str(summary_path),
        },
        "warnings": warnings,
    }
    _atomic_json(summary_path, summary)
    return summary


def import_transgourmet_pdfs(
    input_dir: Path,
    output_dir: Path,
    *,
    as_of_date: date,
    location_id: str,
    supplier_id: str = "TRANSGOURMET",
    item_map_path: Path | None = None,
    allow_supplier_item_ids: bool = False,
    timezone_name: str = "Europe/Berlin",
) -> dict[str, object]:
    documents, scan_counts = scan_transgourmet_pdfs(
        input_dir, timezone_name=timezone_name
    )
    item_map = load_supplier_item_map(item_map_path) if item_map_path else None
    return write_transgourmet_csvs(
        documents,
        output_dir,
        as_of_date=as_of_date,
        location_id=location_id,
        supplier_id=supplier_id,
        item_map=item_map,
        allow_supplier_item_ids=allow_supplier_item_ids,
        timezone_name=timezone_name,
        scan_counts=scan_counts,
    )
