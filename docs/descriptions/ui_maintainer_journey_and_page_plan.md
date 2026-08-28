# Maintainer UI journey and three-page plan

**Status:** high-level product and UX direction defined 2026-08-28; the
monorepo foundation exists, but the domain pages, APIs, source persistence,
authentication, and detailed visual design are not implemented

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
| **Locations ready to plan** | Locations with an active master version, sufficient forecast/menu/BOM horizon, an accepted stock snapshot, and a known PO source state. Opens data freshness. | Minimal tables exist; repository writes and readiness API are missing. |
| **Locations at risk** | Distinct locations whose latest completed run has a projected stockout or unavoidable pre-arrival shortage inside its active risk horizon. Opens the filtered location view. | Engine and summary table exist; persistence writer/latest-run API are missing. |
| **Items at risk** | Distinct location/item pairs with a structured stockout risk in the latest current run. Display earliest risk date. | `NettingResult.first_stockout_date` and its table column exist; repository/API are missing. |
| **Recommendations due** | Positive proposals whose `order_date` is today/past, grouped by location. Label “recommendations”, never “orders”. | Recommendation/run tables exist; repository/API are missing. |
| **Blocking issues** | Blockers in current imports or latest runs; warnings are shown separately. Links to the relevant dataset or location. | Run exceptions and compact import issue JSON exist; repository/API are missing. |
| **Latest planning run** | Status, planning-as-of time, completion time, location, and whether its inputs are still current. | Required columns/import references exist; current-input comparison/API are missing. |
| **Open PO lines due soon** | Mapped observed open lines with expected receipt date in a visible window. Missing-date lines stay quarantined. | PO-line table exists; import writer/API are missing. |
| **POs placed in last 7 days** | Count distinct observed supplier documents and lines by order date. Quantities are broken down by valid order unit or item; no mixed-unit grand total. | `po_id`/ordered fields exist; the importer must persist full observed history rather than only run-ready open lines. |
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
| Supabase server readiness | `apps/api/supply_planning_api/supabase.py` |
| Complete local orchestration reference | `src/supply_planning/application/run_template_v1.py` |
| Master/planning workbook schemas | `src/supply_planning/adapters/template_xlsx.py` |
| Apicbase stock normalization | `src/supply_planning/adapters/apicbase_stock_xlsx.py` |
| Transgourmet parsing/normalization | `src/supply_planning/adapters/transgourmet_pdf.py`, `transgourmet_v1.py` |
| Pure calculation result | `ImprovedRunResult` in `src/supply_planning/application/run_improved.py` |
| CSV/JSON/review outputs | `src/supply_planning/adapters/v1_outputs.py` |
| Domain/result records | `src/supply_planning/domain/models.py`, `engine/netting.py` |
| Current prototype schema and demo data | `supabase/migrations/202608280001_ui_foundation.sql`, `202608280002_ui_workflow_inputs.sql`, `supabase/seed.sql` |

### 9.2 Planned API surface

These are handover contracts, not implemented endpoints:

| Area | Planned endpoint group |
|---|---|
| Identity and locations | `GET /api/v1/me`, `GET /api/v1/locations` |
| Cockpit | `GET /api/v1/overview` |
| Location readiness/data | `GET /api/v1/locations/{location_id}/planning-status`, `/inventory`, `/purchase-orders` |
| Source imports | `POST /api/v1/imports/master-data`, `/planning-input`, `/stock`, `/purchase-orders`; `GET /api/v1/imports` and `/{import_id}` |
| Master versions | `GET/POST /api/v1/master-data/versions`, `PATCH .../{version_id}`, `POST .../{version_id}/validate`, `POST .../{version_id}/activate` |
| Runs | `POST /api/v1/planning-runs`, `GET /api/v1/planning-runs/{run_id}` |
| Results/exports | `GET .../{run_id}/recommendations`, `/risks`, `/export.csv`, `/export.json` |

All domain endpoints require an authenticated maintainer. The run request
references the location, active master version, latest accepted input versions,
and planning cutoff. Files are imported before the run; the run button does not
silently accept a second hidden file set.

### 9.3 Application-service boundary

`run_template_v1(...)` currently combines file loading, normalization, writing
temporary canonical CSVs, reloading them, calculation, and local result files.
For the UI, preserve it as the local acceptance/recovery path while extracting
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

### 10.1 What the two migrations now provide

The two additive migrations define the persistence needed for the first
prototype data flows. For the connected-UI handoff, the maintainer reports both
as applied manually through the Supabase SQL Editor; repository/API integration
and independent server-side schema verification remain open:

| Tables | UI capability supported after repositories/auth exist |
|---|---|
| `master_data_versions`, `locations`, `items`, `item_policy_overrides`, `delivery_rules` | Versioned master/rule drafts and active version. |
| `planning_runs`, `planning_run_inputs` | Run identity, status, reproducibility metadata. |
| `planning_lines`, `planning_recommendations`, `planning_exceptions` | Recommendation table, derivation drawer, run issues and exports. |
| `source_imports` | Data & settings cards, freshness, compact validation issues, file metadata, and immutable import history. |
| `forecast_daily`, `menu_calendar`, `bom_lines`, `inventory_snapshots`, `purchase_order_lines` | Normalized accepted inputs for readiness, location views, and run assembly. |
| `planning_netting_results` | Item risk, first stockout, projected balance, and Overview/location summaries. |
| `planning_projection_days` | Daily stock, demand, PO receipt, candidate receipt, and stockout timeline for location-level explanation and charts. |

RLS is enabled and browser roles currently have no table access. Keep domain
reads/writes behind FastAPI. The browser Supabase client is for Auth, not a
parallel domain-data path.

The schema files are:

- `supabase/migrations/202608280001_ui_foundation.sql` — master data plus
  portable run/derivation/recommendation/exception contracts; and
- `supabase/migrations/202608280002_ui_workflow_inputs.sql` — minimal source
  import, normalized input, run traceability, netting-summary, and daily-
  projection extension.

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
attributes prove the need. Master change-event history is also deferred until
the edit/activation workflow is implemented; active-version immutability is
still required before enabling writes.

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
- internal Auth method and whether all maintainers have the same edit rights;
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

1. Configure cloud projects and implement Supabase Auth/JWT authorization.
2. Add the three-route application shell and shared status/empty/error
   components while retaining the existing readiness checks.
3. Verify the reported-applied schema from FastAPI and implement repository
   interfaces for the workflow tables.
4. Build **Data & settings** upload cards and import APIs for stock, PO PDFs,
   planning workbook, and master workbook.
5. Persist normalized sources and implement the location readiness API.
6. Split the application orchestration, implement one persisted synchronous
   run, and build **Location planning** with result details and downloads.
7. Persist netting summaries and daily projections, then build the **Overview**
   cockpit over latest current runs.
8. Add draft/edit/validate/activate master data and the weekly menu editor.
9. Run representative maintainer usability sessions, component/E2E tests,
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
- update a master draft without modifying the active version in place;
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
