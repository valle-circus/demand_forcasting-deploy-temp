# Phase 2 Canonical Data Contracts

**Status:** v1 contracts and canonical CSV/netting tranche implemented on 2026-08-25

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

When a source uses different names or grains, its adapter must transform, validate, and document that mapping. The engine must not import a database client or reference source-specific table/column names.

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
| `location_id` | string | yes | Stable kitchen/site ID |
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

For the KW34 fixture, the weekly manual value is repeated across applicable service dates under an explicit legacy assumption. This does not decide whether `Demand/Silo Load` ultimately means sales demand, loading, or a capacity-constrained plan.

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

Aliases and supplier article numbers belong in mapping/supplier-item data, not in `item_id`.

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

Lot/expiry inventory is intentionally separate and optional until a source is available.

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

An observed query returning zero rows is valid. An unavailable source represented by an empty placeholder is not equivalent and blocks shadow/production use.

### 3.11 Implemented canonical CSV package

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
netting result is emitted in shadow/production mode. Lead-time/delivery-rule policy
gates remain open until scheduling is implemented.

## 5. Canonical output contracts

The v1 typed output records define the calculation-to-Snowflake boundary even
though the improved engine does not populate every record yet. Supabase is not
the result store.

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
the normalized input hash, run mode/status, source statuses, structured issues,
and one dated netting result per location/item. Each result retains the opening
stock, daily demand and receipt events, daily signed balances, in-horizon PO
quantity, overdue and post-horizon PO quantities, first projected stockout,
and the unrounded net requirement in grams.

The selected snapshot is treated as the opening balance at the projection
start. If its calendar date is older, the assumption is a warning in
fixture/scenario mode and a blocker in shadow/production mode unless a current
snapshot or complete dated event bridge is supplied. Receipts dated on a
service day are available before that day's demand. Stale POs dated before the
start are reported but not silently counted; POs after the horizon are reported
separately. Candidate receipts are scenario inputs and remain separate from
open POs and from the net-requirement calculation.

This tranche deliberately stops before configured yield/safety policy, protection-period
selection, shelf-life/max-cover constraints, MOQ/case rounding, supplier
scheduling, recommendation rounding, Snowflake persistence, Supabase
configuration, or the internal UI.

## 6. SQL/source discovery deliverable

For each real source, obtain a read-only schema/DDL or column catalog, primary/stable keys, grain, timezone semantics, update cadence, retention, allowed statuses, and a small approved sample. The adapter mapping must then document:

1. source table/view and columns;
2. canonical target fields;
3. transformations and unit conversions;
4. key/join coverage;
5. freshness and duplicate rules; and
6. fields that remain manual, defaulted, or unavailable.

Candidate sources and current gaps are tracked in `docs/descriptions/data_requirements.md`. Human timing and ownership are tracked in `docs/plans/human_action_register.md`.
