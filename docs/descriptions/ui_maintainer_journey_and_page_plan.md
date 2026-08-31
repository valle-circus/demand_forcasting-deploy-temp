# Maintainer UI journey and three-page plan

**Status:** product/UX direction and authenticated FastAPI/Supabase backend are
implemented. Claude has built the connected Data & settings and first Location
planning slices. Codex completed the v2 horizon/MHD backend on 2026-08-30;
migration 004, frontend adoption of its explicit fields, Overview, and final
hardening remain.

## 1. Product outcome and primary user

The product is an internal supply-planning workspace for the person who
maintains planning inputs and reviews ordering recommendations. This document
calls that person the **maintainer**. The maintainer should be able to answer
three questions without understanding the Python implementation:

1. **Is the planning situation healthy, current, and trustworthy?**
2. **What needs attention for a selected location, and what does the latest
   calculation recommend?**
3. **Which source data or maintained rules must be refreshed or corrected?**

The first release is not an order-placement application. It calculates and
exports internal proposals. It does not approve, send, or track the execution
of supplier orders, write to an ERP, assign work, or provide comments.

The current UI foundation lives in `apps/web`; the HTTP boundary lives in
`apps/api`; the calculation and source parsers remain in
`src/supply_planning`. The deployment and security boundaries are defined in
`ui_api_and_persistence_foundation.md`.

## 2. Experience principles

1. **Start with readiness and risk, not raw tables.** The first screen tells
   the maintainer whether the data is current, whether a run is trustworthy,
   and where action is needed.
2. **Every risk leads to an action.** A stale-stock warning links to the stock
   upload; a mapping issue links to the maintained item mapping; a location
   risk links to that location's planning view.
3. **Keep observed facts separate from proposals.** Stock and imported POs are
   observed/manual inputs; calculated orders are recommendations. A
   recommendation is never shown as a placed PO.
4. **Make freshness impossible to miss.** Show both the source timestamp and
   the UI import timestamp. For Transgourmet PDFs, “last imported” is not the
   same as a live supplier-portal refresh.
5. **Use the user's units.** Display packs, cartons/order units, grams, and
   dates explicitly. Do not sum heterogeneous item quantities into a
   misleading “total quantity” card.
6. **Explain before asking for trust.** Each recommendation can reveal the
   demand, usable stock, open PO quantity, safety policy, caps, MOQ, and
   rounding that produced it.
7. **Correct at the source boundary.** Stock exports and PO PDFs are replaced
   or re-imported, not edited line by line. Maintained item, menu, BOM, and
   planning-rule data use validated drafts and version history.
8. **Keep one calculation path.** React presents API results; it never parses
   XLSX/PDF files or reimplements planning arithmetic.
9. **Show uncertainty honestly.** Use the existing measured/observed, manual,
   policy/proposal, and unknown distinctions. Demo or unapproved data remains
   visibly non-operational.
10. **Keep the first release small.** Three top-level pages, a small number of
    actionable summaries, and progressive detail are enough.

## 3. Information architecture and application shell

The application has a persistent left-hand navigation on desktop and a drawer
on smaller screens. It contains exactly three primary destinations:

| Route | Navigation label | Main question |
|---|---|---|
| `/overview` | **Overview** | Are all locations and inputs healthy, and what needs attention now? |
| `/locations/:locationId` | **Location planning** | What is happening at this location, and what should we order? |
| `/data` | **Data & settings** | What must be uploaded, reviewed, or maintained? |

Settings are deliberately part of **Data & settings**, not a fourth top-level
page. Subsections or tabs inside a page are allowed; they do not become new
primary navigation items.

```text
┌──────────────────┬─────────────────────────────────────────────────────┐
│ P2 Supply Plan   │ Page title        Data status       User/session    │
│                  ├─────────────────────────────────────────────────────┤
│ Overview         │ Proposal/demo or blocking alert strip               │
│ Location planning│                                                     │
│ Data & settings  │ Page-specific summary, actions, tables and detail   │
│                  │                                                     │
│ Environment      │                                                     │
│ API/data status  │                                                     │
└──────────────────┴─────────────────────────────────────────────────────┘
```

The shell should provide:

- the three navigation links and active state;
- an environment label such as prototype/production;
- a compact API/data dependency status;
- the authenticated user and sign-out action once Auth exists;
- a persistent proposal/demo banner until the operational gate passes; and
- accessible keyboard navigation, text labels in addition to colour/icons,
  and location-timezone-aware timestamps.

The existing `apps/web/src/App.tsx` is only a connection-status shell. It is
the starting point for the application shell, not the final page layout.

## 4. Primary maintainer journey

### 4.1 Normal planning cycle

```text
Open Overview
      │
      ├─ data/run healthy ────────────────┐
      │                                   ▼
      └─ stale/missing/blocking ─> Data & settings
                                          │ upload or correct
                                          │ validate and accept version
                                          ▼
Select Location planning <────── readiness becomes current
      │
      ├─ review stock, POs and risks
      ├─ compute latest recommendation
      ├─ resolve blockers if necessary ──> Data & settings
      └─ inspect derivation and download CSV/JSON
                                          │
                                          ▼
                              Overview reflects latest run
```

1. The maintainer signs in and lands on **Overview**.
2. The overview states whether each location is ready to plan. Missing or
   stale inputs are more prominent than business KPIs based on stale data.
3. The maintainer drills into a risk location, or follows a corrective link to
   **Data & settings**.
4. Uploads are validated server-side. An accepted import updates a normalized,
   immutable source version; it does not automatically run planning.
5. On **Location planning**, the maintainer sees exactly which active master
   version and latest accepted source versions will be used.
6. **Compute latest recommendation** performs a preflight and starts one run.
   The first implementation remains synchronous, with clear validating,
   running, completed, blocked, and failed states.
7. A completed result shows recommendations, risks, derivations, and
   exceptions. The maintainer can download canonical CSV or JSON generated by
   the API.
8. The overview then points to the new latest run. No action in this journey
   marks a recommendation as ordered.

### 4.2 Update cadence

The UI should make different maintenance rhythms visible:

| Rhythm | Typical action |
|---|---|
| Before a planning run / after a stock count | Replace the location's Apicbase stock export |
| When supplier information changes | Add the newest cumulative Transgourmet PDFs |
| Weekly | Import the maintained forecast/menu plan and review the next menu period |
| Every few weeks / when a rule changes | Create a master-data draft, edit it, validate it, and activate it |
| Each main/recheck cycle | Compute and review the latest location recommendation |

The visible menu window can emphasize the next four weeks, but validation must
still require demand/menu coverage through the longest active protection
horizon. The current pod proposal is 28 lead days plus a 7-day review period,
so the engine's demo uses more than four weeks of dated inputs.

## 5. Page 1 — Overview cockpit

### 5.1 Purpose

The overview is an exception-first cockpit across all locations. Within a few
seconds, the maintainer should know:

- whether planning data is ready and current;
- whether the latest run completed or is blocked;
- which locations/items are at risk before replenishment can arrive;
- whether any recommendation is due to be considered now; and
- where the maintainer should go next.

### 5.2 Layout priority

1. **Alert/readiness strip:** highest-severity global problem, proposal/demo
   status, and one corrective action.
2. **Five compact KPI cards:** readiness, risk, due recommendations, blockers,
   and latest-run status.
3. **Location risk table:** sortable locations with risk counts, earliest risk
   date, latest stock time, latest run, and a drill-down action.
4. **Data freshness panel:** stock, PO import, forecast horizon, active menu,
   and active master version by location.
5. **Latest planning activity:** most recent runs and their completed/blocked/
   failed state.
6. **Observed PO activity:** a secondary summary of recent and still-open
   supplier documents when normalized PO history exists.

### 5.3 KPI and insight definitions

The initial cockpit should prefer the following metrics. “Availability” below
means whether the current code/schema can support the metric without inventing
new business facts.

| Metric | Definition and action | Availability |
|---|---|---|
| **Locations ready to plan** | Locations with an active master version, an accepted planning input, stock snapshot, and known PO source. Opens data freshness. | Implemented in the Overview/planning-status API; approved freshness thresholds remain future policy. |
| **Locations at risk** | Distinct locations whose latest current run has a projected stockout inside its horizon. Opens the filtered location view. | Implemented from persisted netting summaries. |
| **Items at risk** | Distinct location/item pairs whose latest current run has `actionable_risk_status = at_risk`; display `first_stockout_within_horizon_date`. A later full-forecast shortage is secondary context. | Implemented in the v2 run/Overview read models. |
| **Recommendations due** | Positive proposals whose `order_date` is today/past, grouped by location. Label “recommendations”, never “orders”. | Implemented from persisted recommendations. |
| **Blocking issues** | Blockers in current imports or latest current runs; warnings remain separate. | Implemented for current run blockers and import readiness. |
| **Latest planning run** | Status, planning-as-of time, completion time, location, and whether its inputs are still current. | Implemented; a newer accepted import makes the prior run stale. |
| **Open PO lines due soon** | Mapped observed open lines with expected receipt date in a visible window. Missing-date lines stay quarantined. | PO history and open state are persisted; date-window presentation belongs in React. |
| **POs placed in last 7 days** | Count distinct observed supplier documents and lines by order date. Quantities are broken down by valid order unit or item; no mixed-unit grand total. | Full observed PDF history is persisted; the first Overview response exposes open-line activity, while a seven-day refinement may follow. |
| **Shelf-life / max-cover attention** | Count items where a cap binds or ordering constraints create excess cover. Do not call this actual waste. | Existing planning exceptions support a first proxy. |
| **Potential waste** | Requires expiry/lot, actual disposal, or an agreed risk definition. Keep out of the first KPI row until that evidence exists. | Not currently supported. |

Counts are based on the latest completed run whose input versions still match
the latest accepted inputs. If a newer source import exists, the old KPI remains
visible but is labelled **stale calculation** rather than silently presented as
current.

## 6. Page 2 — Location planning

### 6.1 Purpose and header

This is the operational working page for one planning/inventory location. The
header contains:

- a searchable location selector;
- location name, timezone, and active/inactive status;
- latest stock `counted_at`, latest PO **imported at**, forecast-through date,
  active menu version, and active master-data version;
- latest run status and planning-as-of time; and
- the primary **Compute latest recommendation** button.

The run button is disabled with a plain-language reason when required input is
missing or invalid. A stale-but-allowed source uses a warning and explicit
confirmation based on server policy; the browser must not invent freshness
thresholds.

### 6.2 Page sections

Use three secondary tabs or segmented views within this page:

#### A. Risk & stock (default)

**Every quantity in this view must name its time window.** Maintainer review on
2026-08-30 found the table unreadable without it, because two different windows
are in play and the numbers look inconsistent when neither is stated:

| Value | Source | Window |
|---|---|---|
| Demand, closing balance, first stockout | `planning_netting_results` | `projection_start_date` → `projection_end_date`, the whole projection |
| Requirement, caps, proposed quantity | `planning_lines` | `coverage_start_date` → `coverage_end_date`, the order coverage window |

`ending_projected_balance_g` additionally assumes **only the candidate receipt
this run proposes** and nothing ordered after it. Shown without that caveat it
reads as a forecast shortfall rather than an artefact of a single-delivery
projection.

The order/protection window is the default operational view. `Needed` must not
use full-forecast demand as its primary value; show **Demand to protect through
<coverage end>** from the active planning line. A shortage after that date is
secondary **future replan expected** context, not an at-risk item. Full-forecast
shortage must not feed the default risk filter, run summary, or Overview KPI.
The uploaded forecast end is a data-coverage fact, not an editable global
planning horizon.

Shelf life never reduces demand, but the proposal must demonstrate whether the
candidate can be consumed before expiry. Show estimated expiry, exact versus
policy-approximation basis, projected candidate residual at expiry, and an
incomplete-forecast warning. The v2 backend returns this supply-position-aware
candidate evidence explicitly. `policy_approximation` is still not exact lot
MHD and must not be described as proof of actual waste avoidance.

Each row expands in place to show that item's daily projected balance from
`planning_projection_days`, with the zero crossing, deliveries already on order,
and the delivery this run proposes all marked and named in text. Historical
balance before the run date is not available: no daily history is persisted.
The default chart range is the active recommendation window, with optional
display-only zoom to four weeks or the full forecast. Existing and proposed
receipts show their quantities, the series uses discrete daily steps/straight
segments rather than smoothing, and cumulative uncovered demand is not labelled
as negative physical stock.

- summary counts for stockout risk, unavoidable pre-arrival risk, overdue open
  POs, and shelf/max-cover attention;
- an item table with item, storage class, usable stock, expected PO receipts,
  forecast demand horizon, projected first stockout date, projected closing
  balance, and risk severity;
- a small item-level projected-balance chart only when daily projection rows
  are persisted; and
- filters for risk only, storage class, supplier/channel, and item search.

“Overstock” remains a planning proxy based on cover/cap evidence. “Waste” is
not claimed without expiry or disposal data.

#### B. Open POs

- observed PO/document ID, supplier, item, ordered date, expected receipt date,
  open quantity with unit, mapping state, and source import time;
- filters for due soon, future, missing date/quarantined, and mapping issue;
- a compact six-week observed-activity summary when history is available; and
- a link to refresh PO PDFs in **Data & settings**.

The PDF-based V1 considers a line with a future `Liefertag` open. A missing
date is quarantined from dated netting. Today/past is treated as closed for the
current adapter. The UI must explain that this is derived from imported PDFs,
not live confirmation from the supplier portal.

#### C. Recommendation

- run status, run ID, planning-as-of time, code/policy/master/input versions,
  and proposal status;
- a table with order date, expected receipt date, supplier, item, proposed
  order units, unit type, packs, grams, and exception indicator;
- filters for due now, delivery date, storage class, supplier, and exception;
- a row detail drawer showing gross requirement, yield adjustment, safety
  stock, usable on-hand, open PO due, raw order, caps, MOQ/case rounding, and
  final recommendation; and
- **Download CSV** and **Download JSON** actions generated from the persisted
  canonical run, not reconstructed in the browser.

The result uses three levels of progressive disclosure. The primary table is
for scanning, focusable info popovers define unfamiliar metrics and their time
windows, and the drawer is the audit view. Required warnings and remedies stay
visible in the row/drawer and are never hover-only.

The run read model supplies `planning_line_explanations` from the exact
immutable master version used by the run. It includes the item/storage/pack
context, shelf-life/safety/max-cover values, lead time, shelf-life anchor,
supplier/channel, MOQ/case/order-unit settings, delivery/review rule,
provenance/data status, protection mode, and explicit evidence scope. The
shared `explanation_context.field_lineage` maps calculated fields to their
owning datasets/policy inputs; the existing run `inputs` rows retain exact
versions and hashes. Claude must join this context by `planning_line_id` and
format it, not reconstruct it.

The deepest currently supported view can reconcile the persisted arithmetic
and daily item-level demand. It cannot claim exact MHD for existing stock,
historical daily stock, or dish/silo-level demand contributions because those
rows are not currently persisted in the result contract. These are visible
evidence limits and later backend/data extensions, never values inferred by
the browser.

### 6.3 Run interaction

The primary action follows this state flow:

```text
Idle → preflight → validating → running → completed
             └───────────────→ blocked (actionable issues)
                              → failed  (safe retry/support message)
```

The preflight identifies the selected versions and cutoff. On completion, the
page moves to the new result. On a blocker, it displays file/record/field,
message, and remedy where available, with a link to the relevant Data &
settings section. Duplicate clicks must not create different results for the
same deterministic input snapshot.

## 7. Page 3 — Data & settings

### 7.1 Purpose and page structure

This page combines source intake with infrequently changed maintained data. It
has two clear groups:

1. **Planning inputs** — frequently replaced/imported operational files.
2. **Maintained data & rules** — versioned data that can be viewed and, where
   appropriate, edited through validated drafts.

The current local runner receives four upload groups but normalizes them into
nine datasets. The UI should show both levels: simple upload cards for the
maintainer and dataset-specific status after validation.

### 7.2 Upload-to-code mapping

| Upload card | Current file contract | Existing Python integration | Update behavior | UI view/edit |
|---|---|---|---|---|
| **Master data & rules** | `Phase2_Master_Data_Template_v1.xlsx`: `Items`, `Locations`, `Delivery_Rules` | `load_master_template` in `src/supply_planning/adapters/template_xlsx.py` | Import creates a draft master version; activation is separate and transactional. | View/edit normalized items, policies, locations, and delivery rules in a draft. Never edit the active version in place. |
| **Forecast, menu & BOM** | `Phase2_Planning_Input_Template_v1.xlsx`: `Demand_Plan`, `Menu_Calendar`, `BOM_Lines` | `load_planning_template` in `src/supply_planning/adapters/template_xlsx.py` | Import creates immutable normalized source versions. Initially one workbook updates the three datasets together. | Forecast is upload/review first. Menu needs a later weekly draft editor. BOM can use a controlled, infrequent draft editor after the import workflow is stable. |
| **Current stock** | Standard Apicbase `Stock Report` XLSX, selected location | `normalize_apicbase_stock` in `src/supply_planning/adapters/apicbase_stock_xlsx.py` | Replace latest accepted snapshot for the location while preserving normalized snapshot history. `counted_at` comes from the export, not upload time. | Summary only: source location, counted time, records, mapped/unmapped items. Correct the export or item mapping; do not edit stock lines. |
| **Purchase-order PDFs** | One or more cumulative Transgourmet `Bestelldetails` PDFs, selected location | `scan_transgourmet_pdfs` and `normalize_transgourmet_pos` in `src/supply_planning/adapters/transgourmet_pdf.py` and `transgourmet_v1.py` | Add/deduplicate observed documents by content/document identity and refresh normalized open/history views. | Summary only: documents, recent orders, open/mapped/quarantined lines. Correct mappings or upload newer PDFs; do not edit observed PO lines. |

The generated local output path in `run_template_v1` proves the complete
adapter sequence. The future API should reuse the loaders/normalizers directly
and split import from run execution; it must not shell out to the CLI.

### 7.3 Dataset cards and upload interaction

Each upload card shows:

- selected location or global scope;
- accepted file type and whether one or multiple files are expected;
- source timestamp, imported timestamp, uploader, source version/content hash,
  record count, and parser version;
- accepted, accepted-with-warnings, rejected, or superseded state;
- data coverage such as forecast-through date or PO document range;
- mapping/error counts and a **Review issues** action; and
- **Drop files or browse** as the primary update action.

Upload states are: empty, selected, uploading, validating, accepted,
accepted-with-warnings, and rejected. Validation happens in FastAPI/Python.
Errors identify file, sheet/record, field, message, and remedy. The browser may
check file extension/size for fast feedback but never treats that as domain
validation.

Accepted imports do not overwrite audit history and do not automatically
activate a master draft or trigger a plan. Stock is replacement-by-new-snapshot;
PO PDFs are cumulative/deduplicated; master/planning workbooks create versions.
Because activation is the required completion of Step 1, a newly imported
master draft must expose an inline **Activate master data and continue** action
in the Step 1 card. The separate version list remains the audit/history surface;
Step 2's blocked state should link or move focus back to the inline action.

### 7.4 Maintained-data workflow

The maintained-data area uses a version banner, searchable table, and a detail
drawer/form:

1. show the current active version and its activation time/user;
2. create a draft copied from the active version or imported workbook;
3. edit supported fields with field-level validation and provenance;
4. run full cross-record/domain validation;
5. show a before/after change summary; and
6. activate the valid draft atomically, making it immutable.

The first editable grids should be:

- items and item policies: identity/display, supplier mapping, pack/order unit,
  stock mapping, storage class, lead time, shelf life, safety/yield, max cover,
  MOQ, and case multiple;
- location and delivery rules;
- weekly menu calendar after its version/activation semantics are agreed; and
- BOM lines later, because recipe changes require referential and effective-date
  validation.

Forecast rows, observed stock rows, and observed PO rows are not manually
corrected in the UI. Mapping/policy corrections happen in maintained data; bad
source data is re-exported/re-uploaded.

## 8. Data readiness and status language

All three pages use the same server-calculated readiness model:

| State | Meaning | UI treatment |
|---|---|---|
| **Ready** | Required datasets exist, validate, and meet the applicable freshness/horizon policy. | Run enabled. |
| **Ready with warnings** | A run is permitted but contains stale/proposal/other warning evidence. | Warning plus explicit evidence; no silent downgrade. |
| **Blocked** | A required dataset, mapping, active version, or horizon is missing/invalid. | Run disabled; direct corrective action. |
| **Running** | A deterministic run is executing. | Prevent duplicate submission; show progress state. |
| **Stale calculation** | A completed run exists, but one or more newer accepted input versions exist. | Result remains viewable but is not labelled current. |
| **No run yet** | Inputs may be ready, but no result exists for the location. | Clear first-run action. |

Provenance labels should use plain language with a tooltip for the canonical
value: **Observed**, **Manual**, **Proposal/default**, **Unavailable**, and
**Known empty**. Risk is displayed with icon, text, and colour; colour alone is
never the status carrier.

## 9. API and backend handover

### 9.1 Current integration points

| Capability | Current code |
|---|---|
| FastAPI factory/system endpoints | `apps/api/supply_planning_api/main.py` |
| Auth/session verification | `apps/api/supply_planning_api/auth.py` |
| Domain route contract | `apps/api/supply_planning_api/routes.py`, generated `/docs` |
| Import/run/read services | `apps/api/supply_planning_api/services.py` |
| Portable/Supabase repository and schema probe | `apps/api/supply_planning_api/repository.py`, `supabase.py` |
| Complete local orchestration reference | `src/supply_planning/application/run_template_v1.py` |
| Master/planning workbook schemas | `src/supply_planning/adapters/template_xlsx.py` |
| Apicbase stock normalization | `src/supply_planning/adapters/apicbase_stock_xlsx.py` |
| Transgourmet parsing/normalization | `src/supply_planning/adapters/transgourmet_pdf.py`, `transgourmet_v1.py` |
| Pure calculation result | `ImprovedRunResult` in `src/supply_planning/application/run_improved.py` |
| CSV/JSON/review outputs | `src/supply_planning/adapters/v1_outputs.py` |
| Domain/result records | `src/supply_planning/domain/models.py`, `engine/netting.py` |
| Current prototype schema and demo data | migrations `202608280001`, `202608280002`, `202608290003`, `202608300004`; `supabase/seed.sql` |

### 9.2 Implemented API surface

These are implemented, authenticated contracts. The generated OpenAPI document
at `/docs` is authoritative for request fields and multipart names:

| Area | Planned endpoint group |
|---|---|
| Identity and locations | `GET /api/v1/me`, `GET /api/v1/locations` |
| Cockpit | `GET /api/v1/overview` |
| Location readiness/data | `GET /api/v1/locations/{location_id}/planning-status`, `/inventory`, `/purchase-orders` |
| Source imports | `POST /api/v1/imports/master-data`, `/planning-input`, `/stock`, `/purchase-orders`; `GET /api/v1/imports` and `/{import_id}` |
| Master versions | `GET /api/v1/master-data/versions`, `POST .../{version_id}/activate`; workbook upload creates a validated draft |
| Runs | `POST /api/v1/planning-runs`, `GET /api/v1/planning-runs/{run_id}` |
| Results/exports | `GET .../{run_id}/recommendations`, `/risks`, `/export.csv`, `/export.json` |

All domain endpoints require an authenticated maintainer. The run request
references the location, active master version, latest accepted input versions,
and planning cutoff. Files are imported before the run; the run button does not
silently accept a second hidden file set.

### 9.3 Application-service boundary

`run_template_v1(...)` currently combines file loading, normalization, writing
temporary canonical CSVs, reloading them, calculation, and local result files.
The API preserves it as the local acceptance/recovery path and implements
small application services for:

- importing/validating each source type into canonical records;
- persisting an accepted immutable input version;
- assembling a `CanonicalInputBundle` from selected repository versions;
- running `run_improved_plan(...)`; and
- persisting/exporting the one canonical `ImprovedRunResult`.

FastAPI owns authentication, multipart limits, temporary directories, cleanup,
and repository transactions. Python adapters own parsing and validation. The
engine remains unaware of HTTP and Supabase.

## 10. Supabase schema assessment and minimal workflow model

### 10.1 What the four migrations now provide

Migrations 001 and 002 define the tables. Migration 003 adds immutable-version
guards and narrow transaction RPCs used by the FastAPI repository. Migration
004 adds the corrected actionable-risk and shelf-life derivation contract plus
the v2 planning persistence RPC. The maintainer reports 001–003 applied through
the SQL Editor; 004 must be applied before the next connected planning run:

| Tables | Implemented backend capability |
|---|---|
| `master_data_versions`, `locations`, `items`, `item_policy_overrides`, `delivery_rules` | Versioned master/rule drafts and active version. |
| `planning_runs`, `planning_run_inputs` | Run identity, status, reproducibility metadata. |
| `planning_lines`, `planning_recommendations`, `planning_exceptions` | Recommendation table, derivation drawer, candidate expiry/cap/residual/rounding evidence, run issues and exports. |
| `source_imports` | Data & settings cards, freshness, compact validation issues, file metadata, and immutable import history. |
| `forecast_daily`, `menu_calendar`, `bom_lines`, `inventory_snapshots`, `purchase_order_lines` | Normalized accepted inputs for readiness, location views, and run assembly. |
| `planning_netting_results` | Explicit actionable-risk status/window, full-forecast context, projected balance, and Overview/location summaries. |
| `planning_projection_days` | Daily stock, demand, PO receipt, candidate receipt, and stockout timeline for location-level explanation and charts. |

RLS is enabled and browser roles currently have no table access. Keep domain
reads/writes behind FastAPI. The browser Supabase client is for Auth, not a
parallel domain-data path.

The schema files are:

- `supabase/migrations/202608280001_ui_foundation.sql` — master data plus
  portable run/derivation/recommendation/exception contracts; and
- `supabase/migrations/202608280002_ui_workflow_inputs.sql` — minimal source
  import, normalized input, run traceability, netting-summary, and daily-
  projection extension; and
- `supabase/migrations/202608290003_ui_backend_transactions.sql` — immutable
  finalized inputs/active master rows, atomic import/activation/run functions,
  and service-role-only execution grants; and
- `supabase/migrations/202608300004_actionable_risk_and_shelf_life.sql` —
  additive v2 risk/MHD derivation columns and `persist_planning_run_v2`.

`supabase/seed.sql` contains one clearly synthetic location/item/import/run/risk
example for UI development. It is not operational evidence and must never be
seeded into production.

### 10.2 Deliberately simplified for the prototype

The schema stays deliberately small while preserving the daily engine output
needed for an actionable location view:

- `source_imports` holds the small file-name/hash/count list, compact JSON
  validation issues, metadata, timestamps, and supersession link in one row;
- `purchase_order_lines` retains `po_id`, so recent PO/document counts can use
  distinct IDs without a separate header table;
- `planning_netting_results` stores one typed item summary and
  `planning_projection_days` stores its daily balance points; and
- no KPI/materialized-summary tables exist. Overview metrics are queries over
  accepted imports and the latest current run.

Split source files, validation issues, or PO headers into dedicated tables only
when per-file status, issue volume, raw-file retention, or document-level
attributes prove the need. Master change-event history is deferred until
field-level editing is implemented; active-version immutability and
transactional activation are already enforced by migration 003.

The dashboard does not require stored KPI tables in the prototype. Query or
compute summaries from the latest current run and accepted imports. Add
materialized summaries only after measured performance requires them.

### 10.3 Raw-file and Snowflake boundary

Do **not** store a filled XLSX/PDF as a Postgres binary column. The prototype
stores its normalized rows, file metadata, hashes, provenance, and selected
version. Raw files are processed in a request-scoped temporary directory and
deleted by default. If replay/audit requirements justify retention, use a
private Supabase Storage bucket with an approved owner, duration, access, and
deletion policy.

Supabase is the prototype persistence adapter. Snowflake remains the intended
future operational/input and result-history store. Keep API response contracts
and repository interfaces persistence-neutral so the frontend and engine do
not change when a Supabase repository is replaced by a Snowflake repository.

## 11. Frontend component handover

The current frontend has `App.tsx`, `StatusCard.tsx`, `lib/api.ts`, and a lazy
Auth client in `lib/supabase.ts`. A practical next structure is:

```text
apps/web/src/
├── app/
│   ├── AppShell.tsx
│   └── routes.tsx
├── components/
│   ├── SideNavigation.tsx
│   ├── PageHeader.tsx
│   ├── StatusBadge.tsx
│   ├── FreshnessBadge.tsx
│   ├── KpiCard.tsx
│   ├── DataTable.tsx
│   ├── EmptyState.tsx
│   └── ErrorSummary.tsx
├── features/
│   ├── overview/
│   │   ├── OverviewPage.tsx
│   │   ├── LocationRiskTable.tsx
│   │   └── DataFreshnessPanel.tsx
│   ├── location-planning/
│   │   ├── LocationPlanningPage.tsx
│   │   ├── RunStatusPanel.tsx
│   │   ├── RiskStockTable.tsx
│   │   ├── OpenPoTable.tsx
│   │   ├── RecommendationTable.tsx
│   │   └── RecommendationDrawer.tsx
│   └── data-settings/
│       ├── DataSettingsPage.tsx
│       ├── DatasetCard.tsx
│       ├── FileDropzone.tsx
│       ├── ImportIssueList.tsx
│       ├── VersionBanner.tsx
│       ├── MasterDataGrid.tsx
│       └── MenuCalendarEditor.tsx
└── lib/
    ├── api.ts
    ├── supabase.ts
    ├── formatting.ts
    └── types.ts
```

This is a component boundary, not a request to build a generic design system.
Reuse the visual language of the foundation shell where helpful. Add a router
for the three URLs. Keep a typed API client and feature-specific loading/error/
empty states; avoid introducing a large client-state framework until the flows
require one.

## 12. Detailed-design questions still open

These do not block the high-level plan, but a designer/engineer should resolve
them before polishing screens:

- actual location count and naming, which affects selector/search behavior;
- whether production should replace prototype admin-created email/password
  accounts and the all-authenticated-users-are-maintainers policy with SSO/
  role tiers;
- approved stock/forecast/PO freshness thresholds and who may override a
  warning;
- whether raw uploads require private retention for replay/audit;
- exact master-version and menu-version activation ownership;
- whether PO documents can be reliably associated with locations from source
  data or require explicit selection;
- which ordering units should be displayed first for each item/category;
- whether an item projection chart materially helps the maintainer after table
  testing; and
- final terminology/language (English, German, or bilingual labels).

## 13. Suggested implementation order

1. Apply migration 004; Supabase/Auth and migrations 001–003 are already
   configured in the development environment.
2. Keep the implemented three-route React shell, sign-in/session handling, and shared
   status/empty/error components.
3. Keep the implemented **Data & settings** workflow and finish the inline
   master-activation UX.
4. Update **Location planning** to consume the v2 risk/MHD fields and correct
   chart/label semantics.
5. Build **Overview** against the implemented current-run summary.
6. Add field-level master/menu editing only as a separately scoped follow-up;
   workbook draft import and activation are sufficient for the first UI slice.
7. Run representative maintainer usability sessions, component/E2E tests,
   accessibility checks, and the existing operational-approval gate.

This order builds the information needed by the location and overview pages
before those pages depend on placeholder KPIs. Detailed visual design can run
in parallel against the page contracts in this document.

## 14. UX acceptance criteria

The first useful prototype is complete when a maintainer can:

- sign in and navigate the three pages without losing the selected location;
- see why a location is ready, warned, or blocked;
- upload each of the four current file groups and receive actionable validation;
- see source and import timestamps without confusing the two;
- upload and activate a validated master draft without modifying the prior
  active version in place;
- compute exactly one recommendation from visible input versions;
- identify the earliest stockout/arrival risk and its remedy;
- explain a recommended quantity from its stored derivation;
- download canonical CSV and JSON for the selected run;
- distinguish observed POs from calculated recommendations everywhere; and
- use the experience with keyboard navigation and without relying on colour
  alone.

The prototype is not complete merely because the three routes render. Its
success is that a maintainer can decide what needs attention, correct the right
source, reproduce a run, and understand the proposal without opening local
scripts or workbooks.
