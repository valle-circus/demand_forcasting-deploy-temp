# MEMORY.md

Long-term project memory for durable, high-impact facts and decisions. This is
not a task log or a replacement for the detailed engineering brief.

## Scope and usage

- Read relevant entries before implementation or design work.
- Keep entries concise and update them in place when a decision changes.
- Each entry includes a date, the decision/fact, evidence artifact path(s), and
  status (`active` or `superseded`).
- Put temporary findings, commands, and session notes in a topic scratchpad, not
  here.
- Never store secrets or private operational data here.

## Active memory

- 2026-09-01: **The event-aware per-item supply-coverage backend contract v3 is
  implemented; only migration 005/live verification and Claude's React chart
  remain.** Coverage means consecutive calendar days from projection start
  whose dated demand is fully served, not stock divided by average demand.
  Zero-demand days count, a fully served zero-closing-balance day counts, the
  first unmet-demand day does not, and late receipts cannot repair an earlier
  gap. Python calculates nested on-hand, accepted-open-PO, and proposed-receipt
  scenarios and persists totals, dates, forecast-limited lower-bound flags,
  incremental days with exact/lower-bound/not-observable evidence, late-gap
  flags, and item-specific protection-horizon days.
  Proposals remain visibly not ordered; existing stock/open-PO lot MHD remains
  unavailable. Run schema v3, FastAPI `coverage_context`, and
  `persist_planning_run_v3` prevent React from recreating the logic and prevent
  legacy v2 nulls from appearing as zero. Apply
  `supabase/migrations/202609010005_event_aware_supply_coverage.sql` in the SQL
  Editor, create a fresh v3 run, then hand only the chart/types/tests to Claude.
  Evidence: `src/supply_planning/engine/netting.py`,
  `src/supply_planning/application/run_improved.py`,
  `apps/api/supply_planning_api/services.py`,
  `supabase/migrations/202609010005_event_aware_supply_coverage.sql`, and
  `docs/claude_code_first_ui_pages_brief.md`. Verification: all 87 Python
  tests, focused Ruff, and strict mypy pass; no live PostgreSQL/Supabase syntax
  application was available locally. Status: `active`.

- 2026-08-31: **The three-page maintainer UI is built, connected and verified;
  the frontend slice of Milestone 2 (2D/2E/2F) is complete.** A maintainer can
  sign in, read Overview, import all four sources in order, activate a master
  version, compute one location's run, inspect risk, the daily stock
  projection and every proposal's full derivation, and download the
  server-generated CSV/JSON. Three rules are enforced in code and pinned by
  tests: no planning arithmetic in the browser (`planning.ts` reads fields, and
  a test feeds a deliberately inconsistent line to prove the UI shows what the
  engine stored); risk comes from `actionable_risk_status`, never from a
  stockout date — the three helpers that derived meaning from
  `first_stockout_date`, full-projection demand or date arithmetic were deleted
  during v2 adoption; and a count with no current run behind it renders
  **not known**, never `0`. Migration 004 is applied and readiness reports ready
  on v2 code. Stack is React 19 + Vite + Tailwind v4 + shadcn/ui on Base UI,
  lucide, Geist, motion and Recharts, following the `circus-ui` skill. Verified:
  `pnpm check` passes with 128 tests, plus a live browser journey against real
  Supabase Auth and a v2 run. **Not verified:** more than one ingredient or
  location, and any deployed environment. Evidence:
  `docs/plans/ui_slice_handover.md`,
  `docs/plans/ui_implementation_backlog.md`,
  `docs/scratchpads/ui_implementation.md`, and `apps/web/src`. Status: `active`.

- 2026-08-30: **The actionable-horizon and candidate-MHD backend v2 contract is
  implemented; its React adoption and migration 004 application were completed
  on 2026-08-31.**
  Full uploaded-forecast projection stays a data visibility window, while the
  actionable horizon is item-specific lead plus review/delivery cadence.
  Netting now persists `at_risk`, `covered`, or `not_evaluated` plus the exact
  evaluated window, and FastAPI run/Overview summaries no longer count a later
  full-forecast shortage as current risk. Candidate sizing cannot repair
  pre-arrival shortage. Shelf-life/max-cover use a conservative tagged-candidate
  projection that consumes projected stock, accepted POs, and earlier planned
  receipts first; hard caps are never silently exceeded by MOQ/case rounding.
  Planning lines persist expiry, approximation basis, forecast completeness,
  residual at expiry, binding constraint, and safe rounding outcome. Exact
  UI-packet replay `improved-ded5498f7198` remains a safe 6-pack proposal,
  covered through 7 Sep with a future-context shortage on 10 Sep and zero
  candidate residual at estimated expiry. Do not add one global run-horizon
  slider; React only formats/filters the explicit v2 fields. The Overview read model also
  carries location metadata, freshness, and earliest actionable risk without
  browser-side recomputation. The run read model now exposes per-line item,
  lead/review, shelf-life, safety, max-cover, pack/MOQ/case and delivery-rule
  context from the exact immutable master version, plus field lineage and
  explicit evidence limits for a frontend audit drawer. Verification: 83
  Python tests plus focused Ruff/mypy. Evidence:
  `docs/plans/planning_horizon_and_shelf_life_correction_plan.md`,
  `src/supply_planning/application/run_improved.py`,
  `src/supply_planning/engine/recommend.py`,
  `apps/api/supply_planning_api/services.py`, and
  `supabase/migrations/202608300004_actionable_risk_and_shelf_life.sql`.
  Status: `active`.

- 2026-08-29: **The authenticated maintainer backend contract and connected
  Data & settings page are implemented; Location planning and Overview remain.**
  A persistent side
  navigation links Overview (cross-location readiness/risk), Location planning
  (stock/PO risk, visible input versions, compute, explanation, CSV/JSON), and
  Data & settings (four controlled upload groups plus versioned master/menu
  edits). Imports are separate from execution: FastAPI/Python normalizes files
  into immutable visible source versions, and a run references those versions.
  Two migrations now define the prototype tables: the initial master/run/output
  foundation and an intentionally minimal workflow extension with one compact
  `source_imports` table, normalized forecast/menu/BOM/stock/PO rows, run/input
  references, item-level netting summaries, and daily projection rows. A third
  forward migration adds finalized-input and active-master immutability plus
  atomic import, activation, and full-run persistence RPCs. FastAPI now verifies
  Supabase sessions, treats any valid project user as a prototype maintainer
  (the first UI uses admin-created email/password accounts),
  reuses the existing XLSX/PDF adapters and pure engine, and exposes all
  Overview/location/import/run/read/download endpoints behind a portable
  repository. Separate
  file, issue, PO-header, and KPI/materialized-summary tables are deferred; a
  synthetic seed supports UI development. The maintainer applied all three
  migrations manually through the Supabase SQL Editor; live readiness verifies
  all 18 required tables and all four transaction RPCs, and an admin-created
  Auth user has completed the browser-to-FastAPI session boundary. Raw
  XLSX/PDF bytes stay out of Postgres and dashboard
  risk comes from typed Python results, not duplicated browser/SQL calculations.
  Mixed item units are not combined into a misleading quantity KPI, and cap
  evidence is not labelled actual waste. Evidence:
  `docs/descriptions/ui_maintainer_journey_and_page_plan.md`,
  `supabase/migrations/202608280002_ui_workflow_inputs.sql`,
  `supabase/migrations/202608290003_ui_backend_transactions.sql`,
  `apps/api/supply_planning_api/services.py`,
  `supabase/seed.sql`,
  `docs/plans/phase2_supply_planning_master_backlog.md`, and
  `docs/scratchpads/ui_and_supabase_foundation.md`. A parser-verified synthetic
  upload packet under
  `outputs/01a043ce-e551-7492-b41a-bee3c09a1d99/ui_test_packet/` exercises all
  four source groups and replays to one 6-pack scenario proposal; it is not
  production seed data. Valid XLSX inputs without optional worksheet-dimension
  metadata are accepted by both stock and API audit readers; Excel midnight
  datetimes in date-only planning fields are normalized; and unexpected API
  failures retain sanitized CORS-enabled error responses. The first connected
  master upload and activation succeeded. Verification: 70 Python tests,
  focused Ruff/mypy, and
  the frontend `pnpm check` with 82 tests pass. The first remote write journey
  with that packet remains a maintainer-run development smoke test. Status:
  `active`.

- 2026-08-28: **The UI/API/Supabase monorepo foundation was implemented, while
  domain workflows and cloud resources remain deliberately unconfigured.** The
  pure engine stays in `src/supply_planning`; `apps/api` provides FastAPI
  process health plus a sanitized optional Supabase readiness probe, and
  `apps/web` provides a React/TypeScript/Vite/Tailwind status shell that keeps
  demo/proposal values visibly non-operational. The initial Supabase migration
  creates versioned location/item/rule tables and portable canonical
  run/input/line/recommendation/exception tables with RLS enabled and browser
  roles denied. Vercel is configured for `apps/web`; Render builds from the
  repository root. During the prototype, Supabase may temporarily persist the
  canonical result contracts, but Snowflake remains the long-term result-store
  direction and the calculation contract must not fork. No Supabase project is
  linked; for the connected-UI handoff both migrations are reported manually
  applied through the Supabase SQL Editor. No elevated key is in browser code, and no
  upload/auth/master-edit/result-write endpoint exists yet. Verification: 48
  Python tests, focused Ruff/mypy, `pip check`, frontend lint/type/build and
  peer checks passed; live API/Vite/proxy HTTP checks passed. Evidence:
  `docs/descriptions/ui_api_and_persistence_foundation.md`,
  `docs/plans/phase2_supply_planning_master_backlog.md`,
  `docs/scratchpads/ui_and_supabase_foundation.md`, `apps/api`, `apps/web`,
  `supabase/migrations/202608280001_ui_foundation.sql`, and `render.yaml`.
  Status: `superseded` by the 2026-08-29 backend-contract entry above.

- 2026-08-27: **Repository history is classified before any cleanup move.**
  The active `v1-run` contract is the two project-owned templates, one raw
  Apicbase stock export and cumulative Transgourmet PDFs; no original KW/CW
  workbook adapter participates in that path. The isolated KW34
  engine/application/CSV/CLI/test feature is compatibility code. Stale package
  facades, six unused domain records and active `improved_*` names are separate
  cleanup/revive/rename concerns and must not be hidden in a generic legacy
  folder. Historical Snowflake/report evidence belongs in a documentation
  archive only after its active gate closes. Evidence:
  `docs/plans/legacy_and_deprecation_register.md` and
  `docs/plans/phase2_supply_planning_master_backlog.md`. Status: `active`.

- 2026-08-27: **The local template-driven technical V1 is complete; maintainer
  approval is an operational gate, not a UI-start gate.** Strict readers load
  the two project-owned workbook schemas; the Apicbase adapter reads the
  standard stock-report export timestamp, preserves fractional stock, maps UID
  then exact reviewed name, and exposes scenario-only zero assumptions; the
  Transgourmet adapter reuses the PDF parser, applies the confirmed
  `Liefertag` cutoff and converts order units to inner packs using maintained
  mappings. The pure engine now calculates item-specific lead+review coverage,
  explicit safety/yield, fresh service windows, shelf/max-cover, MOQ/case and
  final pack/carton rounding, then writes table-ready recommendations,
  derivations, exceptions, mapping reviews and deterministic audit output.
  Scenario run `improved-67fb3838775f` at
  `2026-08-26T17:10:00+02:00` produced 23 dated recommendations across 11 items,
  103 order units and zero blockers; seven result files replayed byte-identically
  and 44 tests pass. Four stock gaps used visible scenario-zero rows and seven
  open-PO lines were quarantined; these are not production facts. UI/Supabase
  schema work may start against the stable contracts, but the UI must label
  proposal values until the maintainer returns approved/corrected templates and
  a rerun passes the operational gate. Evidence:
  `docs/plans/v1_template_first_delivery_plan.md`,
  `docs/plans/phase2_supply_planning_master_backlog.md`,
  `docs/descriptions/v1_assumptions_and_admin_validation.md`, and
  `docs/scratchpads/phase2_supply_planning_execution.md`. Status: `active`.

- 2026-08-27: **The recurring local V1 is template-first and has one active
  delivery path.** The project owns `Phase2_Master_Data_Template_v1.xlsx`
  (`Items`, `Locations`, `Delivery_Rules`) and
  `Phase2_Planning_Input_Template_v1.xlsx` (`Demand_Plan`, `Menu_Calendar`,
  `BOM_Lines`). The supplied `CWxx_*` and pod metadata workbooks are migration
  evidence used to prefill these schemas, not recurring layouts that adapters
  must support. Item data are global; demand/menu are location-aware; BOM is
  location-independent. Purchased pods and ordinary ingredients coexist as
  first-class `Dish -> Silo -> Item` components. Pods store official supplier
  `Circus`, ordering channel `Transgourmet`, 28-calendar-day lead, 1 kg inner
  packs, five packs/carton, and the V1 expiry approximation order date + 365
  days. The local demo uses `LOC_DEMO_001`, repeats the current menu/demand for
  six dated dummy weeks (the menu remains effective until superseded), and
  treats the Apicbase export timestamp as current `counted_at`; a future upload
  selects location. Initial improved-policy proposals are a seven-day stocked
  review period, safety days of `7` pods, `2` ordinary stocked and `0.5` fresh,
  and `yield_factor=1.00` unless deterministic loss is known. These preserve
  the intent of the old 20% extra-demand buffer to reduce OOS risk without
  treating the old global `1.20` as yield. The
  maintainer edits only the two templates and drops
  cumulative Transgourmet PDFs plus a current Apicbase stock XLSX. Normalizers
  produce table-ready CSVs. No current Snowflake input is required for this
  milestone. That deterministic local run is now complete, so the upload UI may
  begin under the separate maintainer-approval gate above. Evidence:
  `docs/plans/v1_template_first_delivery_plan.md`,
  `docs/plans/phase2_supply_planning_master_backlog.md`,
  `docs/descriptions/canonical_data_contracts.md` section 3.11, and
  `docs/scratchpads/phase2_supply_planning_execution.md`. Status: `active`.

- 2026-08-26: **The interim Transgourmet PDF-to-CSV bridge is implemented and
  locally validated.** `scripts/extract_transgourmet_pos.ps1` scans local
  `Bestelldetails` PDFs, ignores unrelated files, deduplicates normalized
  document content, fails on partial extraction or delivery-total mismatch, and
  writes private history, supplier-item review, canonical `open_pos.csv`, and a
  deterministic summary/source version under ignored `data/private/`. The
  2026-08-26 local run found 80 unique documents, 364 history lines and 47
  supplier articles. The confirmed rule is: missing/future `Liefertag` is open;
  today/past is closed/received. At that cutoff, 356 history lines are closed
  (including 14 same-day lines), while the 8 strictly future-dated rows pass the
  canonical PO parser; no current line lacks `Liefertag`. Missing-date open rows
  are retained in a separate undated-open CSV rather than assigned an invented
  receipt date. One
  supplier article has multiple displayed package/base-unit combinations and
  remains a pack-mapping review item. The PDF
  does not provide remaining quantity, partial receipt/cancellation detail, or
  receipt time. Therefore ordered quantity copied to open quantity, 00:00
  delivery time, `REWE_CENTRAL_PREP`, and `TG-<article>` IDs are explicit interim
  assumptions, not accepted production facts. Raw PDFs/generated CSVs stay
  outside git; API/Snowflake ingestion and approved location/item mappings
  remain open. This one adapter also covers Circus-labelled pod orders because
  the orders are placed through Transgourmet; no separate Circus PO register is
  needed. Evidence:
  `src/supply_planning/adapters/transgourmet_pdf.py`,
  `tests/test_transgourmet_pdf.py`, `README.md`, and
  `docs/scratchpads/phase2_supply_planning_execution.md`. Status: `active`.

- 2026-08-25: **Architecture and scope correction.** Phase 1 is an independent
  upstream input that produces forecast portions by location/dish/service day.
  This repository is Phase 2: BOM explosion, stock/open-PO netting, and internal
  purchase recommendations using lead/review, shelf life/max cover, pack/MOQ/
  case, storage behaviour, simple delivery rules, and explicit safety/yield
  config. Snowflake owns operational inputs and calculated result tables.
  Supabase owns only application-managed editable planning rules and their
  change history; an internal React/Python UI exists so non-technical users can
  maintain those rules. The UI is not a proposal-approval, supplier-send, ERP,
  comments, or assignment workflow. Delivery schedules are simple config data,
  not an external calendar integration. CSV/JSON remain fixture/test/recovery
  adapters. The displayed KW33/KW34 formula is implemented and reconciles 27/27
  filled orders plus 28/28 bridge values, but the real workbook golden fixture
  is not yet automated; current tests are synthetic. Evidence: `README.md`,
  `docs/descriptions/phase2_supply_planning_brief.md` sections 3-4 and 9,
  `docs/plans/phase2_supply_planning_master_backlog.md`, and
  `docs/scratchpads/phase2_supply_planning_execution.md`. Status: `active`.

- 2026-08-26: **Excel-owner Q1-Q13 answers are reconciled; HA-01 is complete.**
  `Demand/Silo Load` is the expected dishes sold per day across three REWE sales
  units combined at one central prep/purchasing location, based on roughly two
  weeks of consumption plus campaigns, customer-approved and manually trend-
  adjusted. An explicit service-location-to-planning-location map is therefore
  required; never copy the combined value to each unit. Pending Transgourmet
  orders are reviewed in the supplier portal, downloaded as PDFs, analysed
  outside the workbook, and subtracted before final quantities; this includes
  pod orders. The four blank KW34 gaps were probably missed. Current lead
  lead durations are confirmed as 3 days standard and 5 days fresh; pods are confirmed at
  4 calendar weeks and are non-cancellable. Fresh coverage is `Sat→Mon`,
  `Mon→Tue+Wed`, `Wed→Thu+Fri`, and
  `Fri→Sat`. Operators upload usable-stock counts to Apicbase, while its master
  data is currently stale and Excel is the operational fallback; supplier
  article numbers exist. Creme Fraiche is `5000 g`, current Schnittlauch is the
  distinct `250 g` product, and `Oel` equals `Sonnenblumenoel`. Exact PO export/
  API fields, stock quantity/partial-pack semantics, `S/M/W/Fr` status,
  cut-offs, storage capacity, and approved safety/yield rules remain focused
  gates. Local V1 separately fixes a menu-valid-until-superseded rule with six
  dummy weeks, upload-selected location, export time as `counted_at`, and pod
  expiry as order date + 365
  days. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` sections 3-5 and 10;
  `docs/plans/human_action_register.md` HA-01/HA-04/HA-06/HA-08/HA-11/HA-12;
  `docs/reports/planner-questionnaire-review/source_notes.md`. Status: `active`.

- 2026-08-26: **The historical feedback-V1 source plan is retained only as a
  compatibility track.** Use the original
  KW33/KW34 workbook already available as the historical comparison fixture and
  preserve workbook/tab/week provenance for every extracted value; do not ask
  the Excel owner to resend historical forecast, menu, stock, or item data.
  This track does not block the template-driven local V1. Keep raw manual Transgourmet downloads outside git and
  transform them into versioned `open_pos.csv`; the API is a later automation
  path. For recurring new-standard runs, the superseding active entry above
  replaces six human-maintained CSVs with two maintained workbooks and two raw
  drops. Apicbase recipe/item data are not a V1 blocker because the reduced
  assortment is maintained manually; its stock export remains a required
  operational snapshot. Forecast moves from the dated manual plan to the future
  Phase 1 Snowflake table; editable rules remain manual/versioned until
  Supabase exists.
  Evidence: `docs/descriptions/data_requirements.md` interim V1 source map;
  `docs/scratchpads/phase2_supply_planning_execution.md`. Status: `superseded`.

- 2026-08-24: **A correction notice supersedes four earlier same-day entries.**
  Findings first recorded on 2026-08-24 were produced under the Lightdash
  service role, which reads 1 of 4 accessible schemas, and several were then
  generalised to "not found anywhere". That inference was invalid. The broader
  Snowflake catalogue contains candidate fields for storage type, expiry,
  supplier information and pre-mix decomposition. Their presence retracts the
  claims of absence, but it does **not** establish authoritative master data,
  shelf-life policy, a supplier master, or whether pre-mixes are purchased or
  assembled on site. Standing rule adopted: no claim of absence without naming
  the role and scope searched; no aggregate headline without a saved query that
  reproduces it; no inference recorded as a measurement. Evidence:
  `docs/descriptions/data_requirements.md` evidence rules and corrections.
  Status: `active`.

- 2026-08-24: **Access is not a blocker.** Role `CIRCUS_MODELS_READER` reads
  `BASE` (49 tables), `INTERMEDIATE` (7), `REPORTING` (58) and `TECH_OPS` (26)
  in `ANALYTICS` — 140 tables, all physical tables, no views. No permission
  request to the data team is required. Separately, the Lightdash service role
  reads only `LOOKER_STUDIO_CIRCUS` (46 `LS_` views), so Lightdash is not a
  usable discovery tool for this project. Evidence:
  `docs/descriptions/data_requirements.md` access note. Status: `active`.

- 2026-08-25: **The discovered forecast/recommendation models are abandoned
  previous-data-team models, despite still producing closely timed outputs.**
  `REPORTING.FACT_CG_PURCHASE_ORDERS` (76 rows) carries `DEMAND_IN_WINDOW`,
  `ON_HAND_QTY`, `DEMAND_PLUS_SAFETY`, `NET_QTY_NEEDED`, `PACKAGES_TO_ORDER`,
  `EST_ORDER_COST` and `GENERATED_AT_UTC`; it is generated netting output, not
  a source purchase-order ledger. V6/V8 measured the three models refreshing
  sequentially around 04:31-04:32 Berlin time on 2026-08-25 for one location.
  Forecasts cover five dates; the 76 recommendations contain 73 `Sufficient`
  and 3 `Order Today` lines. Net, pack rounding, and cost reconcile on every
  row, and positive-demand rows use an exact 1.05 uplift. The tested dish
  `date × location × PLU` and ingredient
  `date × location × ingredient_id × unit` duplicate/conflict queries returned
  zero rows. Dish rows pass basic value checks. The ingredient follow-up found
  12 IDs with placeholder-only null/zero rows, six with a real unit plus those
  placeholders, and one stable ID (`Rotes Thai Curry`) mixing `g` and `ml`;
  none of the null-unit rows is nonzero.
  Caveats remain one missing recommendation ingredient ID, two missing prices,
  only `FRESH`/`FROZEN`, and one-location coverage. Joel confirmed that these
  models, together with `BASE_INVENTORY`, are abandoned and may be replaced with
  this project's logic in the `data-transformation` repository. They are useful
  reference evidence, not live inputs or approved policy. GitHub access to that
  repository and the division of responsibilities between its data models and
  this repository's pure planning engine remain to be decided.
  Evidence: `docs/scratchpads/snowflake_verification_evidence.md` V6/V8;
  `scripts/snowflake_verification.sql` blocks V6/V8. Status: `active`.

- 2026-08-25: **The flattened/versioned BOM is a measured strong candidate;
  physical silo identity remains open.**
  `REPORTING.FACT_CG_MENU_DISH_INGREDIENTS` has 1,193 current rows across 52
  menus, 122 PLUs and 120 ingredients, with complete keys, positive grams and
  zero tested revision-key duplicates. All 763 materialized unit-days/26 menu
  keys resolve to it. `DIM_MENU_DISH_INGREDIENTS_HISTORY` has 11,990 valid
  intervals. The raw `BASE_RECIPE_*` topology and positive pre-mix mappings
  exist, but an ingredient-only stock/BOM join is many-to-many and does not
  preserve the required `Dish -> Silo -> Ingredient` identity. A first physical
  path resolved 0/2,576 stock keys, but the raw sample proves the tested
  `CHAMBER_ALIAS` is constant text and therefore not the physical position.
  Corrected V3B then tested 2,576 stock keys: 610 lack active-menu/detailed-menu
  context, 1,636 match through `INGREDIENT_KEY`, but zero match
  `SILO_RESOURCE_ID -> RECIPE_SLOT_INSERTING_POSITION` and no exact physical
  slot resolves. The tested direct position join is rejected. Inspect
  `data-transformation`/upstream lineage for an authoritative
  unit/resource/dock-to-effective-slot bridge; if absent, ask Joel or the
  robot/menu data owner. This blocks capacity use, not pure/file engine work.
  Evidence:
  `docs/scratchpads/snowflake_verification_evidence.md` V9/V3;
  `docs/descriptions/data_requirements.md` D8. Status: `active`.

- 2026-08-25: **`BASE_INVENTORY` is ruled out as the operational open-PO
  source.** V7 returned 106 lines across 35 POs: every line is `Closed`, ordered
  quantity equals delivered quantity, and no line is undelivered. The last sync
  is 2025-10-20; all 106 nonblank `DELIVERED_ON` strings fail `TRY_TO_DATE`;
  there is no order-created or expected-receipt timestamp. `BASE_STOCKS` has 21
  one-location rows last synced 2025-10-30 and every supplier article number is
  missing. Joel additionally confirmed that `BASE_INVENTORY` is an abandoned
  previous-team model and, to his knowledge, **no PO data is currently ingested
  into Snowflake**. Deepali, Dor, and Ilona are the recommended Ops contacts for
  the current source/process, with Deepali likely knowing the details. After
  discovery, Joel's team can establish ingestion—potentially with Fivetran—and
  a normalized model. This blocks real PO adapter acceptance, shadow runs, and
  production netting; it does not block the pure engine, manual/file PO
  fixtures, or scenario tests. MOQ, case size, and simple delivery weekdays
  remain controlled manual-policy inputs unless an authoritative source is
  found.
  Evidence:
  `docs/descriptions/data_requirements.md` D10-D12;
  `scripts/snowflake_verification.sql` block V7. Status: `active`.

- 2026-08-25: **Silo stock fields exist, but dish-capacity and daily-load
  semantics are not yet established.** `FACT_UNIT_SILO_STOCK_DAILY` carries
  `MAXIMUM_AMOUNT`, `REFILL_THRESHOLD`,
  `START_OF_DAY_AMOUNT`, `END_OF_DAY_AMOUNT`, `NET_DEPLETION`, `REFILL_COUNT`
  and `EXPIRATION_DATE`. A direct ingredient-only join to flattened BOM grams
  is measured many-to-many for 62 ingredient IDs and must not be used to claim
  dish capacity. In a 200-row stock sample, 11 of 25 resources carry multiple
  ingredients over time; mapping `RESOURCE_ID`/`DOCK_ID` to the effective
  unit/menu/recipe slot is required. Raw stock contains 148,158 high-frequency
  state updates across 34 silos in the tested period, and daily
  `NET_DEPLETION` includes a negative day. The lagged profile has 147,980
  transitions: 17,691 ingredient changes, 91,831 unchanged states and gross
  positive/negative movement above 15 tonnes with jumps above 7 kg.
  `REFILL_COUNT` has no quantity, so D7 remains open pending reset filtering and
  event semantics. Expiry is
  present on all 6,497 tested silo-days but does not define shelf-life policy.
  Evidence: `docs/scratchpads/snowflake_verification_evidence.md` V3/V10/V12;
  `scripts/snowflake_verification.sql` blocks V3/V10/V12;
  `docs/descriptions/data_requirements.md` D7-D8. Status: `active`.

- 2026-08-24: **Apicbase is a source candidate, not one accepted authority.**
  `BASE_INGREDIENT_LIST` carries `APICBASE_ID` alongside `EAN`, `QUANTITY`
  (pack size) and `PACKAGE_PRICE`. The Excel owner later confirmed that prep-
  kitchen operators upload stock counts to Apicbase and that it is the intended
  recipe/item source, but also reported a master-data maintenance backlog that
  forces current Excel use. Assess stock, BOM, and item master separately; do
  not assume Apicbase or Xentral authority from names alone. Evidence:
  `docs/descriptions/data_requirements.md` D5/D8/D9. Status: `active`.

- 2026-08-24: **`FACT_CG_SALES_DAILY` cannot satisfy D1.** It has no dish
  dimension; grain is `DAY x LOCATION_NAME x CUSTOMER_ID x REVENUE_SOURCE`
  with aggregate measures only (`TOTAL_DISHES_SOLD`, `UNIQUE_DISHES_SOLD`).
  Dish-level sales are in `REPORTING.FACT_CG_SALES` (22,894 rows, one row per
  line item, carrying `DAY`, `UNIT_SERIAL`, `LOCATION_NAME`, `PLU`,
  `DISH_NAME`, `IS_REFUNDED`). This is the most robust correction of the day
  and is measured, not inferred. Evidence:
  `docs/descriptions/data_requirements.md` D1. Status: `active`.

- 2026-08-25: **The old three-location `Demand/Silo Load` comparison is
  superseded.** A zero-inclusive
  corrected V2 dish run for 2026-08-17 through 2026-08-22 uses only
  `CLOSED/SERVED` rows and finds 622 portions, 221 dish-unit-days, 39 zero-sale
  dish-unit-days and a maximum dish-unit-day of 15. The provisional 626 total
  is superseded. V1 maps each of six observed location names to one unit serial;
  corrected V2B reconciles the 622 portions across five selling/production
  units at 8.4–31.8 portions per service day. Do not quote the former 82.5/day,
  27.5/location-day, 3.2x or 9.5x results. The 2026-08-26 planner response now
  confirms the workbook field is expected sold dishes/day across all three REWE
  units combined at central prep, not capacity. The measured Snowflake sales
  definition and stable roll-up mapping remain separate source-contract work.
  Evidence:
  `docs/scratchpads/snowflake_verification_evidence.md` V1/V2;
  `scripts/snowflake_verification.sql` blocks V1/V2. Status: `active`.

- 2026-08-25: **Waste field sums are reproducible, but physical/valuation
  semantics remain unverified; item-master coverage is only partially checked.**
  V4 measured 5,699 rows across six units, 63 ingredients and 314 unit-days
  (2026-06-01 through 2026-08-22), summing `WASTE_QTY_G` to 3,750.3 kg and
  `WASTE_VALUE_EUR` to EUR 31,339. This is not one dish or unit. The row-level
  waste/EOD ratio has median 0.771 and p90 0.912, a derivation warning rather
  than proof. Do not call or share it as physical waste until Joel defines the
  fields and valuation. V5 found 76 item rows/75 non-null IDs, one blank ID,
  zero bad pack quantities, zero missing units, seven missing EANs, ten missing
  Apicbase IDs, and no non-null duplicate/conflict exceptions. Evidence:
  `docs/scratchpads/snowflake_verification_evidence.md` V4/V5;
  `docs/descriptions/data_requirements.md` D3/D9. Status: `active`.

- 2026-08-22: This repository is for Phase 2 supply-planning automation only:
  BOM explosion, time-phased inventory projection, netting, constraints,
  delivery scheduling, and auditable order proposals. No approved live Phase 1
  has been confirmed; Joel confirmed on 2026-08-25 that the catalogued forecast
  models are abandoned previous-team models. Forecasting must remain a
  pluggable upstream input rather than being embedded in this engine. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` sections 1-3. Status:
  `active`.

- 2026-08-22: Project status was discovery and KW34 value-level validation
  complete; implementation had not started. This status was replaced by the
  first implementation tranche on 2026-08-24. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` scope/status,
  `docs/plans/phase2_supply_planning_master_backlog.md`. Status: `superseded`.

- 2026-08-24: The first M0/M1 foundation tranche is implemented. It includes a
  Python 3.12 package, canonical typed input/output contracts, provenance and
  run-mode gates, pure daily BOM explosion preserving pre-mixes, the isolated
  `legacy_kw34/v1` displayed-value calculation, a compatibility CSV adapter,
  deterministic audit JSON/CLI, a safe synthetic fixture, and 17 passing
  tests. Real KW34 golden fixtures, full canonical/XLSX adapters, improved
  planning, SQL, persistence, API, and UI remain open. Evidence:
  `src/supply_planning/`, `tests/`, `README.md`,
  `docs/descriptions/canonical_data_contracts.md`, and
  `docs/plans/phase2_supply_planning_master_backlog.md`. Status: `superseded`
  by the 2026-08-25 implementation state below.

- 2026-08-25: The first unblocked M2 file-engine tranche is implemented. A
  required source manifest and canonical CSV adapters load daily forecasts,
  location/date menu assignments, effective BOM lines, items, timestamped
  inventory, and manual/observed/placeholder `open_pos.csv` with actionable
  field, key, duplicate, and referential validation. The pure engine now emits
  a dated event ledger and signed daily inventory projection, nets in-horizon
  open POs once, and reports overdue, post-horizon, post-final-demand, and
  stockout conditions. Unknown critical inputs warn in fixture/scenario mode
  and fail closed with zero netting results in shadow/production mode. The
  deterministic `improved-run` CLI and synthetic multi-location fixture are
  covered by the repository's 32 passing tests after scope cleanup. Yield/safety policy,
  protection-period selection, constraints, supplier/fresh scheduling,
  recommendation rounding, Snowflake adapters/result writing, Supabase config,
  and the internal configuration UI remain open. Evidence:
  `src/supply_planning/adapters/canonical_csv.py`,
  `src/supply_planning/engine/netting.py`,
  `src/supply_planning/application/run_improved.py`,
  `tests/fixtures/synthetic_improved/`,
  `docs/descriptions/canonical_data_contracts.md`, and
  `docs/plans/phase2_supply_planning_master_backlog.md`. Status: `active`.

- 2026-08-24: The first core and CLI intentionally use only the Python 3.12
  standard library and `Decimal`; Ruff/mypy are configured but are not installed
  in the current bundled runtime. Canonical contracts are storage-neutral engine
  boundaries and do not assume future Snowflake/ERP/Supabase schemas. Source
  adapters must map real schemas into these contracts. Evidence: `pyproject.toml`,
  `src/supply_planning/domain/models.py`,
  `docs/descriptions/canonical_data_contracts.md`. Status: `active`.

- 2026-08-22: The reference source is `Supply_Planning_Rewe.xlsx`, an Office
  workbook stored in Google Drive with file ID
  `1W0fwiO_mf7pQ6G0Oqmp6QE92MCljrXQ-`; it was modified 2026-08-21 and inspected
  read-only on 2026-08-22. `Plan KW34` and `Stock KW34` are the first golden
  reference, with KW33 needed for bridge demand. Connector validation exposed
  displayed values rather than the formula AST, so the current evidence is
  value-level until a raw-formula review or owner walkthrough occurs. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` scope and validation
  conclusion, `docs/scratchpads/phase2_supply_planning_execution.md`. Status:
  `active`.

- 2026-08-22: The minimum Phase 2 demand interface is daily and location-aware,
  with `location_id`, stable `dish_id`, `service_date`, and
  `forecast_portions`. An upstream `date` column must be mapped explicitly.
  The engine must not be designed around one flat weekly
  demand number. Evidence: `docs/descriptions/phase2_supply_planning_brief.md`
  section 3. Status: `active`.

- 2026-08-22: Core domain invariants are the three-level
  `Dish -> Silo -> Ingredient` BOM, storage class as a first-class attribute,
  grams as the internal unit, and purchasable packs as the order unit. Pre-mixes
  must remain represented as silos. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` sections 4 and 6. Status:
  `active`.

- 2026-08-22: The KW34 legacy compatibility profile is now precisely
  reconstructed at displayed-value level: buffered `Daily` is rounded to two
  decimals; `Need = ceil(Daily × 6)`; the bridge uses **KW33** daily demand ×
  `2.5` rounded to two decimals; `After` is rounded to one decimal; and
  `Order = ceil(max(0, Need − After))`. This matches all 27 filled KW34 stocked
  order cells and all 28 bridge values for continuing stocked items. Legacy
  rounding must stay isolated from improved-engine precision. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` sections 4.2 and 5.9,
  `docs/scratchpads/phase2_supply_planning_execution.md`. Status: `active`.

- 2026-08-22: KW34 contains material data-quality/audit cases that golden tests
  must preserve: four stocked rows have a positive gap and blank order cell;
  `Paprika - big` and `Mischsalat` are in `Plan KW34` but absent from
  `Stock KW34`; Creme Fraiche is planned with a 1,000 g pack but netted as 5,000
  g; Schnittlauch appears with 250/500/1,000 g pack sizes; and multiple item/name
  and storage-label variants exist. The blank/missing rows may have been handled
  outside the sheet and must be called unexplained rather than proven missed
  orders. Evidence: `docs/descriptions/phase2_supply_planning_brief.md` sections
  4.3 and 5.2-5.7, `docs/scratchpads/phase2_supply_planning_execution.md`.
  Status: `active`.

- 2026-08-22: The current operating model is Monday-Saturday with delivery slots
  Saturday, Monday, Wednesday, and Friday. `Frisch` holds no stock and is planned
  from delivery to delivery; `TK`, `Kuehl`, and `RT` are stocked classes. These
  values should be configurable rather than hard-coded into engine functions.
  Evidence: `docs/descriptions/phase2_supply_planning_brief.md` sections 2 and
  4.3. Status: `active`.

- 2026-08-22: The target planning horizon is item-specific lead time plus review
  period, adjusted to actual supplier order/delivery calendars. Gross demand
  through that protection period is an inventory-position target, not
  automatically the new order quantity. Correct netting subtracts on-hand and
  dated open POs once, then uses a daily projection to detect stockout before the
  candidate receipt. The earlier target equation double-counted pre-arrival
  demand and is superseded. It remains unknown whether planners duplicate orders
  or track the pipeline outside the sheet and suppress visible cells manually.
  Evidence: `docs/descriptions/phase2_supply_planning_brief.md` sections 5.1,
  5.2, and 7. Status: `active`.

- 2026-08-22: Deterministic yield loss and stochastic safety stock are separate
  concepts, but statistical calibration is not a first-release requirement.
  Keep the spreadsheet `x1.2` only in the legacy profile. The minimum improved
  profile uses simple explicit, versioned yield and safety-day settings edited
  through the Phase 2 configuration UI. Forecast-error sigma, OOS uncensoring,
  and empirical waste calibration are later work. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` sections 5.3, 7, and 8 and
  `docs/plans/phase2_supply_planning_master_backlog.md`. Status: `active`.

- 2026-08-22: Missing waste, OOS, forecast-error, receipt, and lot/expiry data do
  not block file-based engine development. Fixture/scenario runs use explicit
  policy placeholders/defaults and carry value provenance into every line.
  Missing current stock, canonical pack/SKU, lead time, or open-PO visibility is
  allowed only in fixture/scenario modes and blocks trusted production output. Missing
  data is never silently converted to observed zero. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` sections 7-9,
  `docs/plans/phase2_supply_planning_master_backlog.md`. Status: `active`.

- 2026-08-22: The engine should be pure and deterministic: calculation functions
  have no database or filesystem access, policy is held in validated config, and
  input snapshots plus config/version metadata make runs reproducible. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` sections 9.1-9.4. Status:
  `active`.

- 2026-08-22: Target constraints floor the raw need, compute shelf-life and
  max-cover feasibility, cap the unrounded candidate, apply MOQ/case rounding,
  and then **recheck hard caps**. If supplier rounding and a hard cap conflict,
  the engine emits an infeasible-constraints exception instead of silently
  violating a cap or supplier rule. Binding caps, unavoidable stockouts, and
  config gaps remain visible with derivation/provenance. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` section 7. Status:
  `active`.

- 2026-08-22: Phase 2 was originally described as producing proposals followed
  by a coded approval workflow. The derivation requirement remains valid, but
  the workflow scope is superseded: outputs are internal Snowflake planning
  recommendations and approval/dispatch features are not part of this project.
  Evidence: `docs/descriptions/phase2_supply_planning_brief.md` sections 7 and
  9. Status: `superseded`.

- 2026-08-22: Planning must explicitly handle menu launches and
  discontinuations. It requires a forward committed menu horizon longer than
  the longest lead time, item-level last-order offsets and pipeline
  cancellability, and exceptions for open POs arriving after final service.
  Evidence: `docs/descriptions/phase2_supply_planning_brief.md` sections 7, 9.4,
  and 10. Status: `superseded` as a first-release requirement. Basic
  forecast/menu coverage and late-PO flags remain active; advanced transition
  optimization is later work.

- 2026-08-22: The implementation architecture is script-first but not
  throwaway: one Python application service wraps a pure engine; the CLI calls
  it first, later FastAPI and React/Tailwind call the same use case. The CLI and
  CSV/YAML files are a **technical bootstrap interface** for approved fixtures,
  deterministic tests, local development, initial import, recovery, and export;
  they are not the intended configuration workflow for non-technical planners.
  When the operational UI begins, approved Supabase Postgres tables become the
  system of record for master data, policy versions, runs, proposals, and
  approvals. Planners edit through React -> FastAPI, not by editing YAML, CSV,
  or database tables directly. File and database adapters implement the same
  validated schemas so the engine does not change, and operational mode must not
  permit competing file/database authorities. Supabase project creation,
  ownership, region, auth/RLS, retention, and credentials require human approval.
  Evidence: `docs/descriptions/phase2_supply_planning_brief.md` sections 9.1-9.7,
  `docs/plans/phase2_supply_planning_master_backlog.md`. Status: `superseded`
  by the 2026-08-25 Snowflake-results/Supabase-config correction.

- 2026-08-22: Delivery order is locked unless a documented blocker changes it:
  M0 evidence/contracts; M1 exact KW34 Python CLI; M2 improved file-driven engine
  with labelled placeholders; M3 SQL and optional Supabase persistence; M4
  backtest/shadow validation with real data; M5 FastAPI + React/Tailwind UI; M6
  live Phase 1 and operations. Supplier/ERP dispatch is a separate final release
  gate and remains disabled through the first UI. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` section 11,
  `docs/plans/phase2_supply_planning_master_backlog.md`. Status: `superseded`
  by the simplified 2026-08-25 master backlog.

- 2026-08-24: Unanswered planning-process questions are treated as staged
  promotion gates, not a global development blocker. Repository scaffolding,
  typed contracts, the pure engine, CLI, synthetic scenario tests, and the
  `legacy_kw34` displayed-value profile may start immediately with explicit
  assumptions and provenance. Answers and real source access become mandatory
  before the affected feature is accepted as business-correct, shadow-tested,
  or used for trusted production results. In particular, unknown current stock,
  canonical SKU/pack, lead time/calendar, demand semantics, or open-PO pipeline
  must never pass the production-mode gate. Evidence:
  `docs/plans/phase2_supply_planning_master_backlog.md` blocker interpretation
  and business-question gate matrix; `docs/scratchpads/phase2_supply_planning_execution.md`.
  Status: `active`.

- 2026-08-22: `docs/plans/phase2_supply_planning_master_backlog.md` is the
  source-of-truth execution backlog; the topic scratchpad is
  `docs/scratchpads/phase2_supply_planning_execution.md`. Update both during
  implementation and after meaningful decisions. Evidence: those files and
  `AGENTS.md`. Status: `active`.

- 2026-08-24: `docs/plans/human_action_register.md` is the source of truth for
  manual actions, requested information, owners, timing, allowed fallback, and
  the exact milestone each item blocks. The current M1 actions are process
  answers/evidence (`HA-01`), the KW34 fixture commit policy (`HA-02`), and raw
  formula evidence if available (`HA-03`); none blocks continued synthetic
  engineering. Evidence: that register and the backlog's question-to-gate
  matrix. Status: `active`.

- 2026-08-25: **Question audiences are separated.** The already-sent Q1-Q13
  questionnaire belongs to the person who builds and uses the Excel workbook;
  it asks about their manual process, hidden logic, assumptions, overrides, and
  known sources. It needs no correction or Snowflake terminology. Joel answered
  the existing-model question: the four named models are abandoned. The only
  immediate open-PO question is now answered: no PO data is currently ingested
  into Snowflake to his knowledge. Valentin should identify the Ops source with
  Deepali/Dor/Ilona, then coordinate ingestion/modeling with Joel. GitHub access to
  `data-transformation` and a stable RSA-authenticated Snowflake service account
  are separate setup actions. BOM joins, silo keys, menu coverage, stock events,
  grain, freshness, and other technical matters are investigated through SQL
  first. The waste-definition question is deferred until waste will be shared
  or used for calibration. Evidence: `docs/descriptions/phase2_supply_planning_brief.md`
  section 10 and `docs/plans/human_action_register.md`. Status: `superseded` by
  the received-answer reconciliation dated 2026-08-26.

## Open high-impact questions

These are intentionally unresolved and must not be silently converted into
implementation assumptions:

- For future Phase 1 automation, which stable IDs/effective mapping roll service
  locations into an inventory/planning location, and where does the two-week
  consumption signal originate? Local V1 instead uses the selected planning
  location and must not duplicate an already combined forecast.
- Which repository owns each part of the target implementation: normalized
  Snowflake input/output models in `data-transformation` versus the pure Phase 2
  calculation engine in this repository? Inspect the data-model repository
  after access is granted and decide explicitly so logic is not duplicated.
- Which of `WASTE_QTY_G`, `STRANDED_QTY_G` and `SILO_END_OF_DAY_QTY_G` is
  physical disposal, and how is `WASTE_VALUE_EUR` valued? This blocks later
  calibrated yield, not an explicit manual V1 value.
- Can Transgourmet expose a safe CSV/export/API with stable PO/line/article IDs,
  outstanding units, statuses, expected receipts, partial receipts,
  cancellations/date changes, and history? Pods use this same ordering source;
  the remaining pod-specific question is article/order-unit mapping. Snowflake
  still has no PO ingestion to Joel's knowledge.
- For local V1, confirm pod article/description, five-pack carton order unit,
  MOQ/case; resolve article `350570`; and approve/correct the proposed safety
  values (`7` pod, `2` ordinary stocked, `0.5` fresh), deterministic yield loss
  if any, and hard max-cover values.
- What unit does Apicbase `Current Stock (qty)` use for each active item, and
  how are usable opened/partial packs represented? Local V1 already selects the
  planning location at upload and uses row-1 export time as `counted_at`.
- Approve/correct the proposed seven-day stocked review period, confirm whether
  Monday is a normal reorder opportunity, and provide material cut-offs/
  availability events or item exceptions around the confirmed 3-day standard,
  5-day fresh and 28-calendar-day pod lead durations.
- Beyond the confirmed Penne freezer-space split, what capacity, pipeline,
  pack/case, or other constraints explain calculated-versus-delivery-cell
  differences, and do those cells mean intended, placed, confirmed, or
  delivered units?
- Is silo capacity binding, and does sealed or opened shelf life govern each
  item?
- Does the planner's Q12 “currently no” mean that no additional historical data
  exists, or only that the forecast sheet, Apicbase, Transgourmet history, and
  Snowflake candidates are not currently used/trusted for weekly planning?
- Which catalogued Snowflake models are authoritative and operationally fit for
  stock, BOM, menu, sales, waste and OOS, and how should the newly identified
  Ops PO/receipt source be ingested and modeled? Read access itself is resolved.
- Which Snowflake schema/table/write pattern owns run history and the latest
  Phase 2 result, and will Joel's service account have the required grants?
- Which Supabase project/region/owner and minimal internal authentication
  approach should be used when editable config and the UI begin?

Evidence for all questions:
`docs/descriptions/phase2_supply_planning_brief.md` section 10. Status: `active`.
