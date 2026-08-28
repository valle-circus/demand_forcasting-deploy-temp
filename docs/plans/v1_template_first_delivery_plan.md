# Template-first local V1 delivery plan

**Created:** 2026-08-27

**Status:** local technical V1 complete on 2026-08-27; maintainer approval gate open

**Replaces:** the earlier proposal to adapt the maintainer's evolving workbook
layouts directly

## Goal

Prove one complete local planning run for one demo location using:

1. two project-owned Excel templates maintained by the planner;
2. a current Apicbase stock-report XLSX;
3. cumulative Transgourmet order PDFs; and
4. a deterministic engine result containing purchase recommendations,
   derivations, and exceptions.

The first milestone ends when the templates can be shared with the maintainer
and the same filled templates plus raw exports reproduce a validated local run.
The next milestone is a small maintainer-facing upload UI over the same table
contracts. Snowflake/Supabase persistence and API automation come after that.

## Decisions fixed for this milestone

- The project owns the workbook schema. The two supplied workbooks are source
  evidence used to prefill/migrate the first templates; their tab/column layout
  is not a permanent adapter contract.
- Item, pack, supplier/channel, stock crosswalk, and item policy data have one
  global row per `item_id`; they are not duplicated per location.
- `Demand_Plan`, `Menu_Calendar`, stock, open POs, delivery rules, runs, and
  recommendations carry `location_id`.
- BOM lines are location-independent unless a genuinely different recipe
  version later proves otherwise.
- Purchased pods and ordinary ingredients coexist in one item master and BOM.
  A pod is one purchasable BOM item; its internal recipe is not exploded for
  procurement.
- `Circus` remains a pod's official supplier, while `Transgourmet` is its
  ordering channel. The same PDF importer supplies open POs for both item types.
- For the local demonstration, the supplied menu/stock/PO examples are treated
  as one location, `LOC_DEMO_001`.
- The six-week demo repeats the available CW36 menu and daily demand values
  Monday-Saturday. This is explicitly labelled dummy data, not an observed
  committed future plan. Six weeks cover the proposed longest protection
  horizon of `28-day pod lead + 7-day weekly review = 35 calendar days`.
- For V1, the currently supplied menu remains effective until a later dated
  change supersedes it. Menu changes are assumed to be communicated at least
  four weeks before they take effect; this is no longer a maintainer question.
- OOS protection is not zero. Initial improvement proposals are `7` safety days
  for pods, `2` for ordinary TK/Kuehl/RT and `0.5` for fresh. The first two are
  approximately 20% of the proposed `lead + 7-day review` horizon. Fresh is
  lower because of its short MHD. `yield_factor=1.00` means no known
  deterministic production loss and is not the safety buffer.
- The Apicbase export timestamp is the V1 `counted_at` / latest-known stock
  timestamp. The future UI assigns the selected `location_id` at upload.
- Pod shelf life is approximated as order date plus 365 days in V1. The item
  master stores `shelf_life_days=365` and `shelf_life_anchor=ORDER_DATE` so the
  assumption can later be replaced by lot/expiry observations.
- Manual/raw inputs normalize to CSV-shaped table rows. A later UI, Snowflake,
  or Supabase implementation must reuse these field contracts rather than
  introduce a second business model.
- The legacy `×2.5` remains only in the historical compatibility profile. It is
  not a blocker or policy input for the template-driven improved V1.

## Maintainer artifacts

### 1. `Phase2_Master_Data_Template_v1.xlsx`

- `Items`: one global row per purchasable pod or ingredient, including stable
  ID, item type, official supplier, ordering channel, PO and stock mappings,
  pack/order conversion, storage, lead time, shelf-life policy, safety/yield,
  max cover, MOQ/case, active status, and provenance/review status.
- `Locations`: the stable planning locations available to uploads and plans.
- `Delivery_Rules`: location-aware delivery-to-service coverage and review
  fields. The confirmed fresh windows are prefilled.
- `Data_Dictionary` and `Lists`: exact field definitions and allowed values.

### 2. `Phase2_Planning_Input_Template_v1.xlsx`

- `Demand_Plan`: one row per
  `location_id × service_date × dish_id × forecast_version`.
- `Menu_Calendar`: one row per
  `location_id × service_date × dish_id × menu_version`.
- `BOM_Lines`: one effective-dated
  `dish_id × silo_id × item_id` line with grams per portion.
- `Data_Dictionary` and `Lists`: exact field definitions and allowed values.

All machine-read data tables have their header in row 1. IDs and dates remain
separate from display names. Yellow/review statuses are deliberate requests to
the maintainer; missing values are never silently treated as measured facts.

## Raw input and normalized table contracts

| Raw input | Upload context | Normalized output used by the engine | Later table path |
|---|---|---|---|
| Master-data template | workbook version/hash | `locations.csv`, `items.csv`, `delivery_rules.csv` plus mapping/config rows | Supabase or accepted master tables |
| Planning-input template | workbook version/hash | `forecast_daily.csv`, `menu_calendar.csv`, `bom_lines.csv` | accepted Snowflake forecast/menu/BOM tables |
| Apicbase stock XLSX | selected `location_id`; export timestamp from file | `inventory_snapshots.csv` plus rejected/unmapped-row review CSV | normalized stock snapshot table |
| Transgourmet PDFs | selected `location_id`; explicit as-of date | existing PO history, dated `open_pos.csv`, undated quarantine, mapping review | normalized PO/receipt tables |
| Engine run | planning as-of, source/config versions | recommendations CSV, derivations CSV/JSON, exceptions CSV | append-only Snowflake result/run tables |

Raw operational files remain private and ignored by git. Normalizers preserve
source filename/hash, import timestamp, selected location, and row-level error
reason so the future UI can display or correct rejected mappings without
changing the pure engine.

## Milestone 1 checklist — local template-driven V1

### A. Freeze the workbook contract

- [x] Create the two canonical templates.
- [x] Prefill all eight pod SKUs and the active CW36 pod/ingredient assortment.
- [x] Prefill a six-week one-location demonstration plan and reviewed BOM.
- [x] Include explicit missing fields such as MOQ/case, stock unit, PO mapping,
      safety, max cover, and delivery timing instead of hiding them.
- [x] Add data dictionaries, validation lists, provenance/status fields, and
      instructions.
- [x] Create the concise maintainer validation brief covering confirmed rules,
      V1 approximations, demo defaults, legacy-only factors, and open questions
      (`docs/descriptions/v1_assumptions_and_admin_validation.md`).
- [ ] Review the yellow/ambiguous fields with the maintainer and issue a dated
      approved workbook version and assumptions brief.

### B. Normalize maintained workbooks and raw exports

- [x] Add one strict XLSX reader for the two project-owned template schemas.
      Do not add adapters for arbitrary `CWxx_*` layouts.
- [x] Add the Apicbase stock-report reader: read the report header/time, accept
      an explicit upload `location_id`, map UID first then exact reviewed name,
      preserve fractional quantities, and quarantine unknown mappings/units.
- [x] Extend the existing Transgourmet invocation to accept the selected
      `location_id` and the reviewed composite PO mapping
      (`article number + exact description` where article alone is ambiguous).
- [x] Emit one versioned canonical bundle and source manifest from all four
      inputs. Each normalized file must be directly loadable as future table
      rows.

### C. Finish the minimum purchase-recommendation calculation

- [x] Complete work package 4, the recommendation engine:
  - [x] load lead/review, safety/yield, shelf/max-cover, MOQ/case and order-unit
        fields;
  - [x] calculate item protection horizons from dated demand;
  - [x] calculate safety as average dated demand over the protection horizon
        multiplied by maintained safety days;
  - [x] net latest usable stock and dated open POs once and retain unavoidable
        pre-arrival stockout exceptions;
  - [x] schedule fresh items from actual demand in confirmed service windows;
  - [x] apply zero floor, shelf-life, max-cover, MOQ and final order-unit/case
        rounding in that order while preserving derivation and exception
        records.

### D. Work package 5 — outputs and demonstration acceptance

- [x] Emit table-ready `planning_recommendations.csv`,
      `planning_derivations.csv`, `planning_exceptions.csv`, and deterministic
      run audit JSON.
- [x] Use one selected stock export, the cumulative PDF history, and the two
      filled templates for `LOC_DEMO_001`.
- [x] Verify every demand row has one active menu and effective BOM; aggregate
      shared items before any pack/carton rounding.
- [x] Verify pod requirements convert 1 kg consumption packs to five-pack
      order cartons according to reviewed order-unit data.
- [x] Verify open POs are included only once and same-day/past delivery dates
      follow the confirmed closed rule.
- [x] Verify stock quantity units and rejected mappings are visible, not
      guessed.
- [x] Verify fresh window coverage with unequal daily demand.
- [x] Verify a repeated identical run is byte/deterministically equivalent.
- [x] Run the full repository check and create a concise demo result/review
      pack for the maintainer.

### Acceptance evidence (2026-08-27)

- One-command scenario run: `improved-67fb3838775f` at the Apicbase export
  timestamp `2026-08-26T17:10:00+02:00`.
- Result: 16 netting items, 39 derivation lines, 23 dated recommendations
  across 11 items, 103 total proposed order units, and zero blockers.
- Pod outputs: 20 cartons `POD_91001`, 25 cartons `POD_91004`, and 20 cartons
  `POD_91005`; explicit 7-day safety is separate from base demand.
- Seven output artifacts were byte-identical on an immediate repeated run.
- Forty-four repository tests pass. Ruff/mypy were not available in the
  bundled runtime; compileall and unittest are the repository check baseline.
- Scenario-only zero stock was made explicit for four unmapped required items;
  seven unmatched open-PO lines were quarantined. No mapping was guessed.

### Milestone 1 exit criteria

- The maintainer can fill only the two templates and provide the two raw
  exports; no side CSV is manually maintained.
- One command normalizes all inputs and produces recommendations, derivations,
  exceptions, and a source/version audit for one selected location.
- All demo defaults and unresolved mappings are visible and cannot silently
  pass as production-approved values.
- The templates and data dictionary are stable enough to share as the required
  V1 format.

**Technical exit decision:** all four criteria are satisfied for the labelled
local scenario, so the local technical V1 milestone is complete. The open
maintainer checkbox above is a separate operational-approval gate: it blocks
trusted shadow/production use, not UI planning or implementation.

## Milestone 2 — maintainer upload UI

After the technical Milestone 1 exit, build only a thin UI over the same contracts:

- select a planning location;
- upload the two filled templates, current stock export, and PO PDFs;
- show validation/mapping errors and allow correction of supported manual
  fields;
- run the calculation and display/download recommendations and exceptions; and
- persist accepted master/rule data in Supabase or the agreed store and write
  run/recommendation history to Snowflake when those owners/contracts are ready.

No supplier dispatch, ERP write, approval workflow, statistical optimization,
or complex calendar integration belongs in this milestone.

**Foundation progress (2026-08-28):** the monorepo now contains the thin
FastAPI system boundary, React/TypeScript/Vite/Tailwind status shell, initial
Supabase master/run migration, and Render/Vercel configuration. This proves the
deployment seams but does not yet implement upload/run, authentication,
master-data editing, or result-review workflows. The granular checklist is in
`docs/plans/phase2_supply_planning_master_backlog.md`; architecture and
environment rules are in
`docs/descriptions/ui_api_and_persistence_foundation.md`.

### Maintainer-feedback gate inside Milestone 2

- UI planning, upload validation, schema-backed forms, local execution, and
  result downloads may start immediately against the completed contracts.
- Until the maintainer returns approved templates, the UI must display the
  demo policy/mapping status and must not label the result operational.
- Before shadow/production validation, load the returned templates, resolve
  stock/PO mappings and policy fields, rerun, and require zero blockers. This
  gate precedes operational sign-off; it does not create a second engine path.

## Non-blocking maintainer questions before operational use

1. For each pod, confirm which Transgourmet article/description is ordered,
   whether one order unit is the five-pack carton, and the true MOQ/case
   multiple.
2. For each active item, confirm what one Apicbase `Current Stock (qty)` unit
   represents and whether usable partial packs are included.
3. Resolve the duplicate/ambiguous Transgourmet article `350570` by exact
   description or corrected article number.
4. Approve or correct the proposed seven-day stocked review period and confirm
   whether the Monday recheck permits a normal reorder; fill material cut-off
   and receipt-availability fields. Lead durations remain confirmed as 3 days
   ordinary, 5 days fresh and 28 calendar days pods.
5. Approve or correct the initial safety proposal: 7 days pods, 2 days ordinary
   stocked and 0.5 day fresh; keep yield at 1.00 unless a deterministic
   item-specific loss is known; provide any hard max-cover values.

The menu-remains-effective rule and six-week dummy repetition, upload-selected
location, stock export timestamp,
pod 28-calendar-day lead, pod order-date-plus-365-day shelf-life approximation,
Transgourmet PO route, and four fresh coverage windows are decisions for the
local V1 and must not be re-asked as blockers.
