# Phase 2 Canonical Data Contracts

**Status:** v1 contracts and canonical CSV/netting tranche implemented on
2026-08-25; manual forecast/planning-location semantics reconciled 2026-08-26

**Code:** `src/supply_planning/domain/models.py`

**Purpose:** define stable engine shapes while keeping physical storage separate:
Snowflake supplies operational inputs and receives results; Supabase supplies
application-owned editable planning rules; CSV remains a fixture/test adapter.

## 1. Boundary and mapping rule

These are **engine contracts**, not claims about physical source schemas.

```text
Snowflake / CSV / XLSX
                 ↓ source-specific adapter
       canonical contracts in this document
                 ↓
          pure planning engine
```

When a source uses different names or grains, its adapter must transform,
validate, and document that mapping. In particular, service/sales locations may
roll up to one inventory/planning location. The adapter must aggregate each
service location exactly once and emit the planning `location_id` used by
forecast, menu, stock, and POs. It must not replicate an already aggregated
forecast across child units. The engine must not import a database client or
reference source-specific table/column names. Add a separate effective-dated
location-map dataset only when the accepted Phase 1 source requires it.

## 2. Shared conventions

- Stable IDs are strings and are the only join keys. Names are display fields.
- Daily demand uses `service_date`; an upstream `date` column maps to it explicitly.
- Timestamps must be timezone-aware at adapter boundaries. Locations and suppliers carry IANA timezone names.
- Grams are the internal requirement unit. Packs/cases use explicit `_units` fields.
- Planning arithmetic uses `Decimal`; floats are not used for order calculations.
- Field suffixes state the unit or grain: `_g`, `_units`, `_days`, `_date`, `_at`.
- Every source carries provenance: `observed`, `manual`, `policy_default`, `empty_placeholder`, or `unavailable`.
- Effective-dated records use inclusive `effective_from` and optional inclusive `effective_to`.
- Source adapters must validate keys, units, duplicates, allowed values, and referential coverage before engine calls.

## 3. Canonical input datasets

### 3.1 `locations`

**Key:** `location_id`

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `location_id` | string | yes | Stable inventory/planning kitchen or site ID |
| `location_name` | string | yes | Display name only |
| `timezone` | string | yes | IANA timezone, e.g. `Europe/Berlin` |
| `active` | boolean | yes | Soft-delete flag |

### 3.2 `forecast_daily`

**Unique grain:** `location_id + dish_id + service_date + forecast_version`

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `location_id` | string | yes | FK to `locations` |
| `dish_id` | string | yes | Stable dish ID |
| `service_date` | date | yes | Daily service date |
| `forecast_portions` | decimal | yes | Expected portions, non-negative |
| `forecast_version` | string | yes | Manual/file/model version |
| `provenance` | enum | yes | Value provenance |

For the KW34 fixture, the weekly manual value is repeated across applicable
service dates under an explicit legacy assumption. The Excel owner confirmed
that `Demand/Silo Load` is expected dishes sold per day across three REWE sales
units combined at the central prep kitchen. It is not physical silo capacity.
The fixture therefore uses one central planning `location_id`; future per-unit
forecasts must be mapped/aggregated to that location rather than added on top of
the combined manual value.

### 3.3 `menu_calendar`

**Unique grain:** `location_id + dish_id + service_date + menu_version`

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `location_id` | string | yes | FK to `locations` |
| `dish_id` | string | yes | Stable dish ID |
| `service_date` | date | yes | Date the dish is planned for service |
| `menu_version` | string | yes | Committed menu snapshot/version |
| `active` | boolean | yes | Whether the dish is served that day |
| `provenance` | enum | yes | Value provenance inherited from the input manifest |

### 3.4 `bom_lines`

**Key:** `bom_line_id`; business grain is effective-dated `dish_id + silo_id + item_id`.

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `bom_line_id` | string | yes | Stable line ID |
| `dish_id` | string | yes | Parent dish |
| `silo_id` | string | yes | Physical silo or named pre-mix |
| `item_id` | string | yes | Purchasable ingredient/component |
| `grams_per_portion` | decimal | yes | Positive ingredient grams per portion |
| `effective_from` | date | yes | First valid service date |
| `effective_to` | date | no | Last valid service date |
| `provenance` | enum | yes | Value provenance inherited from the input manifest |

The engine preserves the `Dish -> Silo -> Item` path during explosion. It may aggregate only after this derivation exists.

### 3.5 `items`

**Key:** `item_id`

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `item_id` | string | yes | Stable internal item/SKU key |
| `item_name` | string | yes | Display name |
| `storage_class` | enum | yes | `TK`, `Kuehl`, `RT`, or `Frisch` |
| `pack_size_g` | decimal | yes | Positive grams per purchasable pack |
| `shelf_life_days` | integer | no | Sealed/opened meaning still requires business confirmation |
| `min_safety_days` | decimal | no | Item override; otherwise policy default |
| `max_cover_days` | decimal | no | Hard cover cap |
| `active` | boolean | yes | Soft-delete flag |
| `provenance` | enum | yes | Source/default status |

Aliases and supplier article numbers belong in mapping/supplier-item data, not
in `item_id`. The owner-confirmed current examples are Creme Fraiche `5000 g`,
Schnittlauch as the distinct `250 g` product, and `Oel` mapped to
`Sonnenblumenoel`; none should be joined by display name in a live adapter.

### 3.6 `suppliers`

**Key:** `supplier_id`

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `supplier_id` | string | yes | Stable supplier key |
| `supplier_name` | string | yes | Display name |
| `timezone` | string | yes | Timezone used for cut-offs |
| `default_planning_lead_time_days` | integer | no | Non-negative supplier default used by Phase 2 |
| `active` | boolean | yes | Soft-delete flag |

### 3.7 `supplier_items`

**Business key:** `supplier_id + item_id`; effective dating can be added when the first source requires it.

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `supplier_id` | string | yes | FK to `suppliers` |
| `item_id` | string | yes | FK to `items` |
| `supplier_item_id` | string | no | Supplier article/SKU |
| `planning_lead_time_days` | integer | no | Item override used by Phase 2 |
| `moq_units` | decimal | yes | Minimum order, zero means none |
| `case_size_units` | decimal | yes | Positive rounding multiple |
| `order_cutoff_local` | time | no | Item-specific cut-off override |
| `active` | boolean | yes | Soft-delete flag |
| `provenance` | enum | yes | Source/default status |

### 3.8 `delivery_schedule_rules`

**Key:** `delivery_schedule_id`

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `delivery_schedule_id` | string | yes | Stable rule ID |
| `supplier_id` | string | yes | FK to `suppliers` |
| `location_id` | string | yes | FK to `locations` |
| `order_weekday` | integer | yes | Monday `0` through Sunday `6` |
| `order_cutoff_local` | time | yes | Supplier-local order cut-off |
| `delivery_weekday` | integer | yes | Monday `0` through Sunday `6` |
| `active` | boolean | yes | Soft-delete flag |

This is simple Phase 2 configuration such as weekly order/delivery weekdays. It
is not an external calendar integration. Holiday or one-off exception support
is deferred until a real requirement proves it necessary.

### 3.9 `inventory_snapshots`

**Unique grain:** `location_id + item_id + counted_at`

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `location_id` | string | yes | Stock location |
| `item_id` | string | yes | Stocked item |
| `counted_at` | timestamp | yes | Exact count timestamp |
| `usable_on_hand_units` | decimal | yes | Usable full packs; excludes known unusable stock |
| `partial_pack_g` | decimal | yes | Usable partial-pack grams, default zero |
| `provenance` | enum | yes | Observed/manual/default status |

Lot/expiry inventory is intentionally separate and optional until a source is
available. The current manual stock process excludes expired, damaged,
reserved, and otherwise unusable goods before upload to Apicbase. Exact count
time and partial/open-pack representation remain adapter-acceptance questions;
do not infer `partial_pack_g = 0` from their absence.

### 3.10 `purchase_orders`

**Key:** `po_line_id`; `po_id` groups lines.

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `po_id` | string | yes | Purchase-order ID |
| `po_line_id` | string | yes | Stable PO-line ID |
| `location_id` | string | yes | Receiving location |
| `supplier_id` | string | yes | Supplier |
| `item_id` | string | yes | Ordered item |
| `ordered_at` | timestamp | yes | Order placement time |
| `expected_receipt_at` | timestamp | yes | Current expected receipt time |
| `open_qty_units` | decimal | yes | Outstanding purchasable units |
| `status` | enum | yes | `open`, `confirmed`, `partially_received`, `closed`, or `cancelled` |
| `provenance` | enum | yes | Observed/manual/default status |

An observed query returning zero rows is valid. An unavailable source represented
by an empty placeholder is not equivalent and blocks shadow/production use.
The current manual process reads Transgourmet pending orders from downloaded
PDFs and nets them outside the workbook. This includes pod orders: `Circus` is
the official pod supplier label, while `Transgourmet` is the ordering channel.
The target supplier-item contract must therefore preserve both concepts; the
current single `supplier_id` field is insufficient for that distinction and is
a recorded extension before supplier datasets are loaded. The PDF source does
not waive any canonical field: a portal export/API adapter must still provide
stable line IDs, outstanding units, status, and expected receipt time.

#### Interim Transgourmet PDF adapter

`python -m supply_planning transgourmet-import` and the Windows wrapper
`scripts/extract_transgourmet_pos.ps1` implement the temporary manual adapter
outside the pure engine. The importer:

- detects `Bestelldetails` PDFs while ignoring unrelated files in the selected
  directory;
- extracts order timestamp, scheduled delivery date when present, supplier article number,
  description, displayed order quantity, package-content count/base-unit code,
  and line value;
- deduplicates re-downloads by normalized document-content hash;
- fails rather than emitting partial data if any item is not parsed or the sum
  of extracted line values differs from a displayed delivery total; and
- writes a complete `transgourmet_po_history.csv`, a supplier-item review file,
  canonical dated `open_pos.csv`, `undated_open_pos.csv`, and an
  `import_summary.json` source version.

The importer is the one interim PO route for both pods and ordinary
ingredients. No separate Circus order register or adapter is required.

For an explicit as-of date, the confirmed portal rule derives status as follows:
a missing or future `Liefertag` is `open`; a `Liefertag` on/before the as-of date
is `closed`/received. Only future-dated open rows enter canonical `open_pos.csv`;
their date is encoded at 00:00 in the configured timezone. Missing-date open
rows remain in `undated_open_pos.csv` and full history, because the current
engine cannot net a receipt safely without its date. The PDF supplies ordered
quantity, not remaining quantity, so the interim outputs copy ordered quantity
to `open_qty_units`. Partial receipts, cancellations, date changes, and receipt
time remain unavailable from these files. The adapter accepts an explicit
`supplier_article_number,item_id` map; its opt-in `TG-<article number>` IDs are
provisional until the cross-system mapping is approved. Use the summary's
`source_version` with `provenance=manual` in the canonical source manifest.
This path is suitable for controlled file/scenario work; it does not remove the
production gate for remaining quantity, receipt-event detail, accepted
item/location IDs, API ingestion, and freshness/ownership checks.

### 3.11 Project-owned maintainer-facing V1 files

The project owns two fixed workbook schemas. The supplied `CWxx_*` and pod
metadata workbooks were used to populate the first version; they are migration
evidence, not recurring layouts that adapters must chase. The maintainer edits
the project-owned files and makes two raw-file drops. Normalizers, not the
maintainer, emit the canonical CSV/table rows.

#### `Phase2_Master_Data_Template_v1.xlsx`

`Items` has one global row per canonical purchasable item. It is deliberately
not location-aware:

| Field group | Exact fields |
|---|---|
| Identity | `item_id`, `item_name`, `item_type`, `active` |
| Supplier/channel and PO match | `official_supplier`, `ordering_channel`, `po_article_no`, `po_description_match` |
| Inner pack / ordered unit | `inner_pack_article_no`, `inner_pack_ean`, `order_unit_ean`, `pack_size_g`, `packs_per_order_unit`, `order_unit` |
| Stock crosswalk | `stock_qty_unit`, `apicbase_uid`, `apicbase_stock_item_name` |
| Planning policy | `storage_class`, `lead_time_calendar_days`, `shelf_life_days`, `shelf_life_anchor`, `min_safety_days`, `yield_factor`, `max_cover_days`, `moq_order_units`, `case_multiple_order_units` |
| Review/audit | `data_status`, `source_note` |

`item_type` is `POD` or `INGREDIENT`; `storage_class` is exactly `TK`, `Kuehl`,
`RT`, or `Frisch`; `order_unit` is `PACK` or `CARTON`; `stock_qty_unit` is
`PACK` or `ORDER_UNIT`. IDs/EANs are text identifiers. Unknown MOQ/case, stock
unit, mappings, or policy values remain explicit review fields rather than
being inferred from a blank cell.

Pods store `official_supplier=Circus` and
`ordering_channel=Transgourmet`. The current `9100x` carton to `100x` inner-pack
mapping is materialized from an exact unique name match. It is never repeated
as an unconstrained runtime fuzzy join. Pod V1 policy uses
`lead_time_calendar_days=28`, `shelf_life_days=365`, and
`shelf_life_anchor=ORDER_DATE`. The initial safety proposal uses
`min_safety_days=7` for pods, `2` for ordinary stocked items and `0.5` for
fresh; `yield_factor=1.00` unless deterministic loss is known. This means
estimated pod expiry is order date plus 365 days until a real lot/expiry source
exists, while shortage protection remains explicit and reviewable.

`Locations` has:
`location_id, location_name, timezone, active, data_status, source_note`.
Future uploads select one of these IDs. The local demonstration uses
`LOC_DEMO_001`; a source filename/header does not silently override the selected
planning location.

`Delivery_Rules` has:
`delivery_rule_id, location_id, ordering_channel, storage_class,
delivery_weekday, covered_service_days, order_weekday, order_cutoff_local,
receipt_available_local, review_period_days, effective_from, effective_to,
active, data_status, source_note`.
The four confirmed fresh windows are prefilled as `Sat→Mon`,
`Mon→Tue+Wed`, `Wed→Thu+Fri`, and `Fri→Sat`. Missing cut-off/receipt times remain
review fields. A proposed weekly stocked review rule uses
`review_period_days=7`; confirm whether the Monday recheck is a normal reorder
opportunity. No external calendar integration is implied.

`Data_Dictionary` and `Lists` are part of the file contract. Machine-read data
tabs have headers in row 1.

#### `Phase2_Planning_Input_Template_v1.xlsx`

`Demand_Plan` is location-aware and has:
`location_id, service_date, dish_id, dish_name, forecast_portions,
forecast_version, provenance, source_note`.

`Menu_Calendar` is location-aware and has:
`location_id, service_date, dish_id, dish_name, menu_version, active,
provenance, source_note`.

`BOM_Lines` is not location-aware and has:
`bom_line_id, dish_id, dish_name, silo_id, silo_name, item_id, item_name,
grams_per_portion, effective_from, effective_to, active, provenance,
source_note`.

A purchased pod is one `item_id`; its internal recipe is not a procurement
line. The demo file repeats the supplied CW36 daily values across six dated
Mon-Sat weeks under explicit dummy provenance. This covers the proposed
`28-day pod lead + 7-day review = 35-day` protection horizon. Operational use
must replace those rows with a maintained plan covering the longest active
protection horizon; the current menu remains effective until superseded.

#### Controlled raw inputs and table-ready normalization

- `data/private/incoming/transgourmet_pdfs/`: cumulative top-level archive of
  downloaded `Bestelldetails` PDFs for ingredients and pods. The existing
  importer deduplicates re-downloads and derives open status from `Liefertag`.
- `data/private/incoming/apicbase_stock/`: current stock-report XLSX. The
  upload/run supplies an explicit `location_id`; row-1 export time is the V1
  latest-known `counted_at`. The implemented adapter maps UID first and an exact
  reviewed stock name second and quarantines unknown mappings/units.
- `data/private/incoming/manual/`: dated snapshots of the two maintained
  templates with filename, hash, version/export time, and selected location
  retained in the run manifest.

The implemented workbook normalizer emits `locations.csv`, `items.csv`,
`delivery_rules.csv`, `forecast_daily.csv`, `menu_calendar.csv`, and
`bom_lines.csv`. The stock and PO normalizers emit `inventory_snapshots.csv`
and `open_pos.csv` plus row-level mapping/quarantine outputs. These are local
files now and future database rows later; they are not additional files the
maintainer edits. Raw operational files remain ignored by git.

### 3.12 Implemented canonical CSV package

`python -m supply_planning improved-run` reads one directory containing:

| File | Canonical dataset |
|---|---|
| `source_manifest.csv` | Source-level `dataset`, `provenance`, and `source_version` declarations |
| `forecast_daily.csv` | `forecast_daily` |
| `menu_calendar.csv` | `menu_calendar` |
| `bom_lines.csv` | `bom_lines` |
| `items.csv` | `items` |
| `inventory_snapshots.csv` | `inventory_snapshots` |
| `open_pos.csv` | `purchase_orders` |

The manifest must declare every dataset exactly once. Its provenance is copied
onto the parsed rows and retained in the audit output. A zero-row
`open_pos.csv` is valid only when its manifest state is explicit: `observed` or
`manual` means a known empty result; `empty_placeholder` or `unavailable`
means the pipeline is unknown. Supplying data rows under placeholder or
unavailable provenance is rejected.

The adapter validates required fields, ISO dates and timezone-aware timestamps,
enums, decimals, booleans, duplicate canonical keys, item references, partial
pack bounds, effective BOM coverage, and active-menu coverage before invoking
the engine. Errors identify the file, row or stable key, field, and remedy.
The checked-in `tests/fixtures/synthetic_improved/` directory is synthetic;
private operational extracts must not be committed.

## 4. Run modes and gates

| Mode | Placeholder policy | Intended use |
|---|---|---|
| `fixture` | allowed with warnings | Golden/synthetic tests |
| `scenario` | allowed with warnings | Offline what-if development |
| `shadow` | unknown critical sources block | Comparison with real planner runs |
| `production` | unknown critical sources block | Scheduled internal Snowflake result generation |

Critical sources currently enforced in code are `forecast_daily`,
`menu_calendar`, `bom_lines`, `items`, `inventory_snapshots`, and
`purchase_orders`. Pack size is validated by the item contract. Unknown or
placeholder critical sources warn in fixture/scenario mode and block before any
netting result is emitted in shadow/production mode. Lead-time/delivery-rule
policy values are loaded and used by scheduling; proposal/default statuses stay
visible until the maintainer approves them.

## 5. Canonical output contracts

The V1 typed output records define a persistence-neutral calculation boundary,
and the template-driven improved engine now populates them. Snowflake remains
the intended long-term result store. Under the explicit 2026-08-28 prototype
exception, the same records may be persisted temporarily in Supabase; this does
not change their grain, identifiers, audit requirements, or proposal-only
meaning.

### 5.1 `planning_runs`

One record per reproducible execution: `run_id`, `schema_version`, `policy_profile`, `policy_version`, `run_mode`, `planning_as_of_at`, `created_at`, `input_hash`, `config_hash`, `code_version`, and `status`. Timestamps are supplied by orchestration and must be timezone-aware; pure engine code does not read the clock.

### 5.2 `planning_run_inputs`

One record per dataset snapshot used by a run: `run_id`, `dataset`, `source_version`, `content_hash`, `provenance`, and `record_count`. This distinguishes a verified zero-row result from a missing or empty placeholder.

### 5.3 `planning_lines`

One derivation record per run/location/item/supplier candidate. It retains stable IDs, `order_date`, `expected_delivery_date`, `gross_requirement_g`, yield and safety values plus provenance, `usable_on_hand_g`, `open_po_due_g`, `raw_order_g`, shelf-life/max-cover caps, `capped_order_g`, `proposed_order_units`, and `rounding_delta_g`.

### 5.4 `planning_recommendations` and `exceptions`

- `planning_recommendations` contain recommendation/run/line IDs, location,
  supplier where known, item, calculated `order_date`, expected delivery date,
  and recommended purchasable units.
- `exceptions` persist a structured code, severity, message, remedy, and optional planning-line reference.

These are internal planning outputs, not placed purchase orders. Approval,
supplier send, ERP export, assignment, and comment workflows are outside the
current contract.

### 5.5 Current legacy audit envelope

The current `legacy_kw34/v1` CLI emits deterministic JSON containing:

- `schema_version`, `profile`, `run_id`, `run_mode`, and SHA-256 `input_hash`;
- a run summary;
- every legacy intermediate (`daily_units`, `need_units`, `bridge_units`, `after_units`, calculated and observed order);
- source row references; and
- structured issue codes, severity, message, and remedy.

### 5.6 Current improved-file audit envelope

The implemented `improved_file/v1` path emits deterministic JSON containing
the normalized input hash, explicit policy version, run mode/status, source
statuses, structured issues, one dated netting result per location/item,
planning derivations and purchase recommendations. Each netting result retains
the opening stock, daily demand and receipt events, signed balances, in-horizon
PO quantity, overdue and post-horizon PO quantities, first projected stockout,
and unrounded net requirement in grams. Separate table-ready CSVs persist final
order units, all policy intermediates, exceptions and mapping reviews.

The selected snapshot is treated as the opening balance at the projection
start. If its calendar date is older, the assumption is a warning in
fixture/scenario mode and a blocker in shadow/production mode unless a current
snapshot or complete dated event bridge is supplied. Receipts dated on a
service day are available before that day's demand. Stale POs dated before the
start are reported but not silently counted; POs after the horizon are reported
separately. Candidate receipts are scenario inputs and remain separate from
open POs and from the net-requirement calculation.

Configured yield/safety, protection-period selection, shelf-life/max-cover,
MOQ/case, supplier scheduling and recommendation rounding are implemented for
the local V1. The repository now contains the API/web foundation and an
unapplied Supabase migration for versioned master and canonical output tables.
Database-to-domain repositories, authenticated writes, upload/run endpoints,
and applied cloud resources remain later adapter/persistence work.

## 6. SQL/source discovery deliverable

For each real source, obtain a read-only schema/DDL or column catalog, primary/stable keys, grain, timezone semantics, update cadence, retention, allowed statuses, and a small approved sample. The adapter mapping must then document:

1. source table/view and columns;
2. canonical target fields;
3. transformations and unit conversions;
4. key/join coverage;
5. freshness and duplicate rules; and
6. fields that remain manual, defaulted, or unavailable.

Candidate sources and current gaps are tracked in `docs/descriptions/data_requirements.md`. Human timing and ownership are tracked in `docs/plans/human_action_register.md`.
