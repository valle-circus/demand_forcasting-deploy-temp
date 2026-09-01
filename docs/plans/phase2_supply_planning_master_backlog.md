# Phase 2 Supply Planning — Master Backlog

**Created:** 2026-08-22

**Rebased:** 2026-08-27 for the template-first local V1

**Source of truth:** this file controls priority and milestone status.

**Active implementation checklist:**
`docs/plans/v1_template_first_delivery_plan.md`

**Repository cleanup register:**
`docs/plans/legacy_and_deprecation_register.md`

## Goal and boundary

This repository consumes a daily dish forecast and calculates auditable
ingredient and purchase recommendations:

```text
daily dish demand + dated menu/BOM + item/rule master
                  + current stock + open POs
                                  ↓
       recommendations + derivations + exceptions
```

Phase 1 forecasting is an upstream input and is not implemented here. Supplier
dispatch, ERP writes, and an approval workflow are outside scope.

The pure Python engine remains independent from files, UI, and databases. The
same canonical rows must support local files now, a maintainer UI next, and
Snowflake/Supabase persistence later.

## Active delivery sequence

### Milestone 1 — local template-driven V1

**Outcome:** one selected location can be planned locally from two maintained
templates, one Apicbase stock export, and cumulative Transgourmet PDFs.

- [x] Define canonical daily forecast, menu, three-level BOM, item, stock, PO,
      provenance, and audit contracts.
- [x] Implement three-level BOM explosion, daily aggregation, current-stock
      selection, dated PO projection/netting, source gates, and deterministic
      audit output.
- [x] Implement the interim private Transgourmet PDF importer, including
      content deduplication, total reconciliation, history, dated open rows,
      undated quarantine, and the confirmed `Liefertag` rule.
- [x] Create and prefill the two project-owned Excel templates with the new
      pod/ingredient/menu evidence and a labelled six-week one-location demo.
- [x] Create one maintainer-facing assumptions/parameters/questions brief so
      active values are not hidden in code or spread across documentation.
- [ ] **Operational approval gate:** obtain maintainer review of the templates,
      yellow/ambiguous fields, and
      assumptions brief.
- [x] **Work package 1 — template readers:** implement strict readers for the
      two project-owned workbook schemas.
- [x] **Work package 2 — stock normalizer:** implement the Apicbase stock-report
      XLSX normalizer with upload-selected
      `location_id`, export timestamp as `counted_at`, and UID/exact-name
      mapping review.
- [x] **Work package 3 — PO mappings:** feed the reviewed item/location mapping
      into the Transgourmet importer.
- [x] **Work package 4 — recommendation engine:** finish protection horizons,
      explicit safety/yield, dated netting, fresh scheduling, shelf/max-cover,
      MOQ/case and order-unit logic, with visible derivations/exceptions.
- [x] **Work package 4 correctness follow-up:** make shelf/max-cover caps
      supply-position-aware, distinguish actionable protection-horizon risk
      from full-forecast visibility, and persist explicit MHD basis/residual/
      incomplete-forecast evidence. See
      `docs/plans/planning_horizon_and_shelf_life_correction_plan.md`.
- [x] **Work package 5 — acceptance run and outputs:** emit table-ready
      recommendation, derivation, exception and audit files, then validate the
      complete one-location demonstration.

Detailed steps and exit criteria are in
`docs/plans/v1_template_first_delivery_plan.md`.

### Milestone 2 — maintainer upload UI

**Outcome:** an authenticated maintainer uses a three-page workspace to see
cross-location readiness/risk, inspect and calculate one location's proposal,
and upload or maintain the controlled source data without running local code.

Detailed architecture and environment boundaries are in
`docs/descriptions/ui_api_and_persistence_foundation.md`; the customer journey,
page contracts, KPI definitions, component map, API handover, and schema gaps
are in `docs/descriptions/ui_maintainer_journey_and_page_plan.md`; living
implementation notes are in `docs/scratchpads/ui_and_supabase_foundation.md`.
The granular frontend execution plan for the remaining 2D/2E/2F checkboxes —
screen blueprints, component inventory, ordered work packages WP0–WP6, and the
decisions awaiting maintainer confirmation — is in
`docs/plans/ui_implementation_backlog.md`, with its working notes in
`docs/scratchpads/ui_implementation.md`. Those files execute this milestone;
the checkboxes below remain the milestone authority.

#### 2A — repository, API and deployment foundation

- [x] Preserve `src/supply_planning` as the calculation/application package and
      add separate `apps/api` and `apps/web` deployables without moving engine
      code.
- [x] Add the FastAPI process-health and optional sanitized Supabase-readiness
      endpoints with explicit CORS configuration.
- [x] Add a minimal React/TypeScript/Vite/Tailwind shell that consumes the API
      status and preserves the demo/proposal warning.
- [x] Add separate browser/server environment examples so elevated Supabase
      credentials cannot be bundled by Vite.
- [x] Add a Render Blueprint, Vercel app configuration, pinned Python line, and
      local development instructions.
- [x] Add the initial Supabase migration for versioned master rows and portable
      canonical run/output rows, with RLS enabled and browser roles denied.
- [x] Add API foundation tests and frontend lint/type/build checks.
- [ ] Select/create the actual Supabase, Render, and Vercel projects; enter
      environment values; apply migrations; and verify deployed CORS/readiness.

#### 2B — authenticated maintainer boundary

- [ ] Choose the internal Supabase Auth method and define maintainer roles.
- [x] Verify Supabase user access tokens in FastAPI for every domain endpoint.
- [x] Add least-privilege authorization tests; reserve the server secret for
      controlled API operations after authorization.
- [ ] Define session-expiry, access-removal, audit-user, and non-production
      preview behavior.

#### 2C — source-import and canonical-input persistence

- [x] Define the four upload groups, normalized dataset/version behavior, raw
      file boundary, current Python integration points, and missing prototype
      tables in `ui_maintainer_journey_and_page_plan.md`.
- [x] Add a minimal additive migration for compact `source_imports` metadata/
      issues, normalized forecast/menu/BOM/stock/PO rows, run traceability, and
      typed item-level netting summaries plus daily projections; defer separate
      file/issue/PO-header and KPI/materialized-summary tables and do not store
      file bytes in Postgres.
- [x] Add a clearly synthetic seed covering imports, active master data, one
      location/item/run/recommendation/risk, plus static schema/seed/RLS tests.
- [x] Add repository interfaces and Supabase implementations that keep the
      application/API contracts portable to future Snowflake repositories.
- [x] Add authenticated import endpoints for master workbook, planning
      workbook, selected-location stock XLSX, and selected-location cumulative
      PO PDFs.
- [x] Add multipart file type/size/count limits, isolated temporary processing,
      cleanup on success/failure, content-hash deduplication, and safe parser
      errors before enabling uploads.
- [x] Reuse `load_master_template`, `load_planning_template`,
      `normalize_apicbase_stock`, and Transgourmet parsers directly; never parse
      operational files in React or shell out to the CLI.
- [x] Persist immutable accepted source versions through the API repositories
      with source/import timestamps,
      location scope, uploader, parser version, hashes, record/mapping counts,
      provenance, warnings, and supersession links.
- [ ] Define and implement one server-side readiness calculation for active
      master, input horizon, stock freshness, and known PO-source state.

#### 2D — Data & settings page

- [x] Define the two page groups, dataset cards, drop-zone states, update
      semantics, validation presentation, and upload-to-adapter mapping.
- [x] Build the three-route application shell, side navigation, authenticated
      user/environment status, persistent demo/proposal banner, and responsive
      navigation drawer.
- [x] Build upload cards for master data, forecast/menu/BOM, current stock, and
      cumulative PO PDFs, with explicit global/location scope.
- [x] Show source timestamp separately from imported timestamp, plus version,
      horizon/document range, record count, mapping/validation status, and
      current/superseded state.
- [x] Show actionable file/sheet/record/field/remedy errors and link mapping
      issues to the relevant maintained data.
- [x] Keep stock and observed PO lines summary-only: correction means re-export,
      re-upload, or correct the maintained mapping, never inline editing.
- [x] Add import/version history and clear accepted-with-warnings/rejected/known-
      empty states without automatically activating a master draft or running
      planning.

#### 2E — Location planning page and persisted run

- [x] Define the location header, readiness/preflight, Risk & stock, Open POs,
      Recommendation subviews, run state machine, derivation drawer, and export
      behavior.
- [x] Add location, planning-status, latest inventory, open-PO, and import-
      version endpoints over normalized persisted inputs.
- [x] Extract import/assemble/run/persist application services from the current
      combined `run_template_v1` orchestration while preserving that local
      acceptance/recovery path.
- [x] Add one authenticated synchronous planning-run endpoint that references
      the visible location, active master version, accepted source versions,
      and deterministic cutoff.
- [x] Persist `planning_runs`, selected source imports, lines,
      recommendations, and exceptions atomically; add explicit run location and
      completion metadata.
- [x] Make deterministic `run_id` persistence retry-idempotent and reject a
      reused ID with a different input hash; cover the RPC contract statically.
- [x] Prevent duplicate browser submissions while a synchronous run is in
      flight. Guarded by an in-flight ref rather than the disabled attribute
      alone, since a fast second click lands before React re-renders; covered
      by a test asserting two rapid clicks produce one request.
- [x] Build the location selector, freshness/preflight strip, run action, and
      validating/running/completed/blocked/failed states.
- [x] Build risk/stock, open-PO, and recommendation tables with plain-language
      units, provenance, filters, and empty/error states.
- [x] Correct the item risk/read-model contract so demand, receipts, coverage,
      shortage, and shelf-life feasibility are explicit for the active
      recommendation horizon; full-forecast shortage remains secondary context.
- [x] Build the recommendation derivation drawer and server-generated canonical
      CSV/JSON downloads; never reconstruct calculations in TypeScript.
- [x] Keep every recommendation visibly proposal-only; do not add placement,
      approval, supplier-send, comments, assignment, or ERP status.

#### 2F — Overview cockpit and risk persistence

- [x] Define the exception-first cockpit hierarchy, actionable KPI definitions,
      latest-current-run rule, and unsupported/unsafe aggregations.
- [x] Add the `planning_netting_results` table contract for first stockout,
      projected balances, overdue POs, and unavoidable shortage, plus the
      `planning_projection_days` contract matching Python's daily output.
- [x] Persist each Python `NettingResult` summary and its daily projection rows
      atomically with its run through the repository adapter.
- [x] Add latest-current-run selection per location so a result becomes
      **stale calculation** when a newer accepted source version exists.
- [x] Extend normalized Transgourmet persistence to observed document/line
      history for recent-PO counts while preserving the current open/missing-
      date caveats.
- [x] Add the overview endpoint with data readiness, risk locations/items,
      recommendations due, blocker/warning counts, latest runs, freshness, and
      secondary observed PO activity.
- [x] Correct `/overview` and run-summary `items_at_risk` so they count only
      backend-classified actionable-horizon risk, not any stockout anywhere in
      the uploaded forecast.
- [x] Build KPI cards, location-risk table, data-freshness panel, latest-run
      activity, and direct corrective/drill-down actions.
- [x] Keep actual waste, supplier service level, actual OOS, and mixed-unit
      total quantity out until authoritative definitions/data exist; label
      shelf/max-cover evidence only as attention or potential risk.
- [x] Apply forward migration
      `202608300004_actionable_risk_and_shelf_life.sql` in the development
      Supabase SQL Editor. Applied; readiness reports ready on v2 API code and
      a v2 run was computed successfully on 2026-08-31.

#### 2G — versioned maintained-data and menu editing

- [ ] Map existing Locations, Items/item policy, and delivery-rule records to
      draft/active repositories; keep workbook import/export as a controlled
      interchange path, not a second editable authority after cutover.
- [ ] Implement draft creation/copy, field and cross-record validation,
      before/after change summary, transactional activation, one active version
      per environment, and active-version immutability.
- [ ] Persist user/time/change history and the exact config hash used by each
      run.
- [ ] Build searchable item/policy and location/delivery-rule grids with detail
      drawers/forms; do not start with an unbounded spreadsheet clone.
- [ ] Define separate planning-input version/activation semantics and then add
      the weekly menu calendar editor; preserve daily rows and the longest
      active lead+review horizon.
- [ ] Add controlled BOM editing only after referential/effective-date
      validation and ownership are agreed. Keep forecast upload/review-only in
      the first slice.

#### 2H — retention, observability, usability and acceptance

- [ ] Decide whether raw uploads are process-and-delete or retained in private
      object storage; record owner, purpose, duration, deletion, and access.
- [ ] Add request/run correlation IDs, structured logs without source contents
      or keys, safe dependency errors, and basic failure monitoring.
- [ ] Add API integration tests and frontend component/E2E coverage for the
      approved workflows.
- [ ] Test keyboard navigation, focus/error handling, timezone/unit labels,
      responsive side navigation, and status communication without colour.
- [ ] Run representative cockpit/location/data tasks with the maintainer and
      correct information hierarchy and terminology before visual polish.
- [ ] After the deterministic Overview and derivation experience is stable,
      evaluate an optional grounded LLM assistance layer: a concise executive
      Overview summary plus a plain-language **Explain this quantity** action.
      It may summarize only persisted readiness, risk, demand, stock, open-PO,
      lead/review, shelf/max-cover, MOQ/case, rounding and exception fields; it
      must not calculate, override, approve, or place a recommendation. Keep
      the normal source/derivation UI as the auditable fallback and define
      privacy, retention, latency, cost and evaluation gates before enabling it.
- [ ] Validate representative runs with the maintainer and require the existing
      operational gate before showing shadow/production-ready status.

**Entry decision:** UI planning and implementation may start. The completed
local scenario contracts are stable. Maintainer feedback is a gate before the
UI can present a run as operational/shadow-approved, not before the upload and
review experience is built.

Do not add supplier dispatch, ERP writes, approval workflow, complex calendar
integration, or optimization in this milestone.

### Milestone 3 — persistence and source automation

**Outcome:** accepted operational sources and run history no longer depend on
local files, without changing engine contracts.

- [ ] Agree Snowflake result schema, write grants, run-history/latest-view
      behavior, and scheduling ownership.
- [ ] Complete least-privilege service-account and `data-transformation`
      access.
- [ ] Persist application-maintained item/rule data in the agreed Supabase or
      master-data store with versions/change history.
- [ ] Use the prototype Supabase run/output tables only until the Snowflake
      result owner/schema/write path is accepted.
- [ ] Implement and cut over to append-only run/recommendation/exception
      history in Snowflake without changing engine/output contracts.
- [ ] Replace manual forecast/menu, stock, and PO inputs individually only when
      an accepted API/table has proven grain, IDs, units, freshness, lineage,
      and ownership.
- [ ] Keep the local file path as fixture/import/recovery support.

### Milestone 4 — shadow validation and scheduling

- [ ] Compare representative improved runs with the maintainer's decisions.
- [ ] Separate calculation differences from missing-source/policy effects.
- [ ] Approve initial rules and operating measures.
- [ ] Schedule idempotent runs with freshness gates, retries, failure logging,
      and a runbook.

## Repository hygiene and compatibility cleanup

- [x] Inventory active runtime, compatibility-only code, unused definitions,
      misleading names and archive candidates without moving files.
- [ ] Add active `v1-run` CLI coverage, then clean stale package `__init__`
      facades that still import or advertise legacy symbols.
- [ ] Remove or explicitly revive unused domain records; do not hide unused
      scaffolding in a generic legacy folder.
- [ ] Rename the active `improved_*` profile to neutral planning terminology
      after the UI/API boundary is fixed.
- [ ] After maintainer feedback and a corrected real-input rerun, decide
      whether the KW34 compatibility feature remains supported. Move or delete
      the complete feature atomically.
- [ ] Archive completed discovery artifacts only after their source/persistence
      or maintainer gate closes.

The exact paths, classifications and gates are maintained in
`docs/plans/legacy_and_deprecation_register.md`.

## Historical compatibility track — not a Milestone 1 blocker

The KW33/KW34 profile remains regression evidence, not the recurring input
format:

- [x] Reconcile 27/27 filled stocked order cells and 28/28 bridge values.
- [x] Isolate the legacy `1.20`, six-day horizon, and `×2.5` arithmetic.
- [x] Implement compatibility CSV/audit and synthetic tests.
- [ ] Decide whether a sanitized real fixture may be committed or remains
      private.
- [ ] Add the real workbook extraction/golden assertions if that fixture is
      approved.
- [ ] Preserve the four likely missed blanks and fresh-path differences as
      explicit evidence.

Understanding the operational meaning of `×2.5` can improve the historical
walkthrough, but it does not affect the dated template-driven V1 policy.

## Current status

| Area | Status |
|---|---|
| Canonical contracts and validation | Implemented for nine normalized datasets plus table-ready results |
| Project-owned workbook templates | Created and prefilled; maintainer review open |
| BOM explosion and dated stock/PO projection | Implemented |
| Actual purchase recommendation calculation | Implemented and locally accepted in scenario mode |
| Transgourmet PDF normalization | Implemented; unresolved lines are quarantined for maintainer mapping |
| Apicbase stock XLSX normalization | Implemented for the observed standard report; unresolved rows are visible |
| Live Snowflake input dependency for local V1 | None |
| Snowflake result persistence | Later; ownership/schema open; portable Supabase prototype tables scaffolded |
| Supabase prototype store | Migrations 001–004 and Auth are verified in development; additive event-aware-coverage migration 005 must be applied before the next v3 run |
| Maintainer UI | Connected Auth shell, Overview, Location planning, and Data & settings implemented by Claude; coverage-v3 chart adoption and realistic multi-item QA remain |
| Current repository check | Coverage-v3 focused engine/API/schema tests, Ruff, and strict mypy pass; full-suite result is recorded in dated progress; `apps/web` was not edited by Codex |

## Source of truth for local V1

| Information | V1 source | Location-aware? | Maintainer action |
|---|---|---:|---|
| Items, pods, pack/order mapping, policy fields | `Phase2_Master_Data_Template_v1.xlsx` → `Items` | No | maintain one row per item and resolve review flags |
| Planning locations | master template → `Locations` | Defines locations | maintain stable IDs |
| Delivery/service coverage rules | master template → `Delivery_Rules` | Yes | maintain per applicable location/rule |
| Daily demand | `Phase2_Planning_Input_Template_v1.xlsx` → `Demand_Plan` | Yes | maintain dated portions and version |
| Menu schedule | planning template → `Menu_Calendar` | Yes | maintain dated active dishes/version |
| Dish → silo → item BOM | planning template → `BOM_Lines` | No | maintain effective recipe rows |
| Current usable stock | Apicbase stock-report XLSX | Yes, selected at upload | export current view and choose location |
| Open POs | Transgourmet PDFs | Yes, selected at upload | maintain cumulative PDF folder |
| Recommendations/results | engine-generated CSV/JSON | Yes | no manual input |

The supplied `CW36_*` and pod metadata workbooks are migration evidence only.
The implementation reads the project-owned schema; it does not chase arbitrary
future tab/column changes in those source workbooks.

## Snowflake and Supabase boundary

A complete controlled local V1 needs no current Snowflake runtime table. The
previously investigated forecast/recommendation models and `BASE_INVENTORY` are
abandoned and must not be wired into the run.

Snowflake remains the intended home for an accepted future Phase 1 forecast,
normalized operational inputs when ingestion exists, and append-only Phase 2
run/recommendation history. During the manual-file prototype, Supabase is the
replaceable store for application-maintained item/rule data, normalized
immutable input versions, and portable run outputs. Raw uploads are not stored
as Postgres binaries. This exception is an adapter choice and neither platform
is a reason to delay the local template-driven milestone.

## Remaining human gates

The authoritative details are in `human_action_register.md`. For Milestone 1,
the short maintainer questions are:

1. pod Transgourmet article/description, ordered unit, MOQ, and case multiple;
2. Apicbase stock quantity unit and partial-pack treatment per active item;
3. resolution of duplicate/ambiguous article `350570`;
4. approval/correction of the proposed seven-day stocked review period plus
   cut-off/receipt fields; ordinary/fresh/pod lead durations remain confirmed
   as 3/5/28 days; and
5. approval/correction of the proposed safety policy (`7` days pods, `2` days
   ordinary stocked, `0.5` day fresh), item-specific yield losses if any, and
   hard max-cover values.

The original local acceptance fixture uses one selected location. The separate
2 September colleague-demo packet exercises two synthetic locations so Overview
can show cross-location prioritisation; each run is still location-scoped. The
supplied menu remains effective until superseded and is repeated across six
dated dummy weeks, stock export time is latest knowledge, pod lead is 28
calendar days, pod shelf life is approximated as order date plus 365 days,
Transgourmet remains the pod ordering channel, and the four fresh service
windows are unchanged.

## Cross-cutting verification

- [x] Multi-dish aggregation and pre-mix/pod preservation.
- [x] Multiple locations and shared ingredients in canonical engine tests.
- [x] Zero forecast, duplicate/orphan/menu/BOM/input validation, and
      deterministic replay.
- [x] Open PO within/after horizon, same-day receipt ordering, stale inventory,
      and placeholder source gates.
- [x] Strict template-schema and provenance tests.
- [x] Apicbase mapping/unit/fractional-stock tests.
- [x] Lead/review horizon, proposed safety-days policy, and unavoidable
      pre-arrival stockout tests.
- [x] Fresh unequal-day coverage tests.
- [x] Shelf-life/max-cover/MOQ/case/order-unit boundary tests.
- [x] Lumpy-demand continuous coverage tests for stock, accepted POs, proposal,
      late receipts after a gap, and forecast-limited lower bounds.
- [x] Full local template → normalized inputs → recommendation acceptance run.

## Immediate next slice

1. Send the two templates, assumptions brief, maintainer review summary, and
   recommendation/exception outputs to the maintainer.
2. Apply `202609010005_event_aware_supply_coverage.sql` in the Supabase SQL
   Editor, then verify readiness and one fresh v3 workflow. Existing v2 rows do
   not gain coverage values retroactively.
3. Have Claude render the cross-ingredient coverage chart from the explicit v3
   fields without TypeScript calculation, then QA it with 20+ ingredients.
4. Keep the completed Overview and v2 Location risk/MHD semantics intact while
   completing frontend hardening.
5. Add field-level master/menu editing only after the workbook draft/activation
   import and version semantics are proven; keep proposal status explicit.
6. Receive corrected/approved templates and answers; resolve the four stock
   mappings, seven currently unmatched open-PO lines, item policy fields, and
   fresh timing/pack-cap decisions.
7. Rerun the same one-command workflow and pass the operational-approval gate
   before shadow/production use.
8. Treat Supabase input/result persistence as the documented prototype adapter and
   preserve the future Snowflake cutover boundary.

## Dated progress

- 2026-09-01: completed event-aware coverage schema/run contract v3. Python now
  projects usable stock, accepted open POs, and proposed receipts as distinct
  nested supply scenarios against dated lumpy demand, persists exact runway
  dates/lower-bound/extension/late-gap fields, and exposes them through FastAPI
  with an explicit semantic and legacy-run availability context. Added forward
  migration 005 and kept React unchanged for Claude's presentation-only slice.
  All 87 Python tests plus focused Ruff/strict mypy pass. SQL schema tests are
  static; the migration still needs its real SQL-Editor application check.

- 2026-08-22 to 2026-08-25: legacy reconstruction, canonical contracts,
  validation, BOM explosion, dated projection/netting, and Snowflake source
  investigation completed.
- 2026-08-26: Excel-owner answers reconciled; Transgourmet PDF importer
  implemented; new menu/pod sheets and two Apicbase stock examples analysed.
- 2026-08-27: route rebased to project-owned templates. Two prefilled workbook
  templates and the template-first local V1 plan were created. The supplied
  workbooks are now migration evidence, not recurring adapter contracts; the UI
  is explicitly the next milestone after a complete local recommendation run.
- 2026-08-27: all five local V1 work packages completed. Scenario run
  `improved-67fb3838775f` produced 23 dated recommendations across 11 items with
  zero blockers; seven result files replayed byte-identically and 44 tests
  passed. UI work is unblocked; maintainer approval remains the gate before
  operational/shadow use.
- 2026-08-28: completed Milestone 2A repository foundation: thin FastAPI
  health/readiness boundary, React/TypeScript/Vite/Tailwind status shell,
  server/browser environment separation, initial RLS-denied Supabase
  master/run migration, Render/Vercel configuration, dedicated UI
  specification/scratchpad, 48 passing Python tests, and passing frontend
  lint/type/build checks. No cloud project is linked and no domain workflow or
  authenticated database write is implied by this scaffold.
- 2026-08-28: defined the Milestone 2 maintainer experience as three top-level
  pages (Overview, Location planning, Data & settings), including the primary
  journey, actionable KPI semantics, page states/components, current adapter
  mapping, planned API surface, source-import/netting persistence gaps, and an
  ordered 2C-2H implementation backlog. The domain pages remain unimplemented;
  the subsequent minimal schema implementation is recorded below.
- 2026-08-28: added the intentionally minimal `002` workflow migration and a
  synthetic seed. One import table carries compact file/validation metadata;
  five canonical input tables plus netting-summary and daily-projection tables
  support the first pages. Separate file, issue, PO-header, and KPI/materialized-
  summary tables are deferred. For the connected-UI handoff, the maintainer
  reports both migrations applied through the Supabase SQL Editor; live schema
  verification and API repository writes remain open.
- 2026-08-29: completed the backend vertical slice. Added authenticated domain
  routes, server-only portable/Supabase repositories, controlled imports using
  the existing Python adapters, immutable normalized versions, master
  activation, synchronous scenario runs, atomic result persistence including
  netting/daily projections, Overview/location/read/download contracts, and a
  forward SQL-Editor migration `003` for transactions/immutability. All 65
  Python tests plus focused backend Ruff and strict mypy checks pass. Live
  Supabase verification still requires migration 003 and environment/Auth
  configuration; the Claude handover is now frontend-only.
- 2026-08-30: completed the protection-horizon/MHD correctness follow-up.
  Python now persists explicit actionable-risk status and a tagged-candidate,
  supply-position-aware shelf/max-cover derivation; unsafe pack/MOQ rounding is
  reduced to a safe multiple or withheld. FastAPI run/Overview summaries use
  the v2 status, and forward migration `004` adds only the required derivation
  columns plus `persist_planning_run_v2`. Exact packet replay
  `improved-ded5498f7198` remains a safe 6-pack proposal with zero current-
  horizon stockouts and zero candidate residual at estimated expiry. All 81
  Python tests and focused Ruff/mypy checks pass. Applying migration `004` is
  the only remaining backend-environment action before Claude adopts the new
  fields in React.
