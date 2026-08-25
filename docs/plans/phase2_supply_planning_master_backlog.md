# Phase 2 Supply Planning — Master Backlog

**Created:** 2026-08-22
**Status:** planning and KW34 validation complete; first M0/M1 foundation tranche implemented, real KW34 golden fixture and remaining adapters open
**Source of truth:** this file controls cross-session execution order and progress.
**Detailed context:** `docs/descriptions/phase2_supply_planning_brief.md`
**Working notes:** `docs/scratchpads/phase2_supply_planning_execution.md`
**Human actions:** `docs/plans/human_action_register.md`

## Goal

Replace the manual weekly workbook process with a trustworthy Phase 2 planning system that:

- consumes daily dish/location forecasts from Phase 1;
- explodes the three-level BOM into ingredient demand;
- nets dated stock and open POs;
- handles fresh and stocked items, supplier calendars, shelf life, MOQ/case, and menu transitions;
- produces auditable proposals and exceptions for human approval;
- starts with a deterministic Python CLI plus file fixtures as a technical validation path, then supports non-technical users through FastAPI, React, Tailwind, and authoritative durable storage.

## Delivery order

1. Freeze and clean the KW34 evidence.
2. Reproduce the workbook exactly with a file-driven Python script; this is a technical bootstrap, not the final planner interface.
3. Implement the improved engine using file fixtures and labelled placeholders.
4. Connect real SQL inputs and migrate approved configuration to authoritative durable storage.
5. Backtest and shadow-run with real data.
6. Build the non-technical UI.
7. Connect Phase 1 and only then consider operational dispatch.

Do not skip directly to the UI or database. The engine and its audit contract must be proven first.

## Priority definitions

- **P0:** required for the milestone exit; blocks dependent work.
- **P1:** required for a trustworthy first release but can follow the core path within the milestone.
- **P2:** hardening, scale, convenience, or optimization after the milestone's P0/P1 path works.
- **HUMAN BLOCKER:** needs an owner decision, credentials, source access, or approval. Development may continue with an explicitly documented placeholder only where stated.

## Global definition of done

- [ ] Input/output schemas, units, grain, IDs, and provenance are explicit.
- [ ] Pure engine code has no database, filesystem, API, UI, or clock dependency.
- [ ] Tests cover normal, boundary, missing-data, transition, and infeasible-constraint cases.
- [ ] Every proposal line contains derivation fields and exception codes.
- [ ] Placeholder/default values are labelled and run-mode validation is enforced.
- [ ] Input/config/code versions make a run reproducible.
- [ ] No real order is dispatched without a separate human approval and readback.
- [ ] Relevant brief, backlog, scratchpad, memory, README, and setup docs match reality.
- [ ] Secrets and raw production data are not committed.

## Human-input blocker register

| ID | Human input / access needed | Needed by | Allowed fallback before then | What it blocks |
|---|---|---|---|---|
| `H-01` | Approval to extract and commit a minimal/anonymized KW34 fixture; confirm supplier/data sensitivity | M0 | Keep calculations documented only | Reproducible golden tests in git |
| `H-02` | Confirm whether `Demand/Silo Load` means daily portions, refill level, or capacity-limited plan | M0/M1 | Treat as daily portions in `legacy_kw34` with assumption flag | Final Phase 1 contract semantics |
| `H-03` | Confirm stock-count timestamp and reason for the 2.5-day bridge | M0/M2 | Reproduce 2.5 in legacy; use explicit assumed timestamp in scenarios | Correct time-phased opening projection |
| `H-04` | Explain blank/reduced orders and `S/M/W/Fr`; identify current open-PO tracking | M0/M2 | Surface as unexplained exceptions; empty/manual PO fixture | Operational interpretation and approval |
| `H-05` | Approve canonical item/SKU IDs, aliases, pack sizes, storage classes; resolve Creme Fraiche, Schnittlauch, missing fresh rows | M0/M1 | Quarantine ambiguous rows; no silent choice | Complete BOM/order coverage |
| `H-06` | Supplier production/transport lead times, order cut-offs, delivery calendars, MOQ/case, split-delivery rules | M2 | Labelled supplier/class defaults | Production-ready scheduling |
| `H-07` | Sealed/opened shelf life, remaining-life/lot source, max-cover policy, override owner | M2/M4 | Conservative configured approximation with warning | High-confidence chilled proposals |
| `H-08` | Forward committed menu horizon and launch/discontinuation process | M2 | Hardcoded scenario calendar | Operational transition planning |
| `H-09` | Obtain `data-transformation` access, inspect abandoned-model lineage, decide the cross-repository ownership boundary, provision stable Snowflake access, and work with Ops/data platform to establish a new expected-receipt/open-PO ingestion because Joel confirmed none currently exists | M3/M4 | File/manual PO adapters with explicit provenance | Accepted real-data adapters, PO netting, and shadow inputs |
| `H-10` | Phase 1 output owner, delivery mechanism, schema/versioning, and first live sample | M6 | Hardcoded/CSV daily forecast | Live forecast integration |
| `H-11` | Decide new versus shared Supabase project; owner, region, billing, backup/retention, credentials | M3 | Local/file persistence | Durable multi-user storage |
| `H-12` | Define roles: config editor, planner, approver, admin, viewer; SSO/auth requirements | M5 | Local single-user development | Auth/RLS and approval UI |
| `H-13` | Agree shadow-run duration, service/waste thresholds, override rules, and sign-off owners | M4 | Produce comparison reports only | Operational acceptance |
| `H-14` | Approve output channel and any ERP/Xentral/supplier API credentials and dispatch controls | M6 | CSV export only | Automated dispatch |

### How to interpret the blockers

The register is a set of **stage-exit and promotion gates**, not a reason to pause all development. As of 2026-08-24, no unanswered business question blocks starting the repository scaffold, typed contracts, pure engine, CLI, or the `legacy_kw34` compatibility profile. Those paths must use fixture/scenario mode, explicit assumption flags, and non-sensitive synthetic or locally held fixture data until the corresponding gate is cleared.

- **Start now:** project scaffold, contracts, validation, exception catalog, pure calculation functions, CLI/application service, synthetic scenario tests, and KW34 displayed-value reproduction.
- **May be built with labelled assumptions:** improved inventory projection, pipeline netting, lead-time calendars, shelf-life caps, menu transitions, fresh-slot logic, safety/yield placeholders, SQL adapter interfaces, and preliminary UI information architecture.
- **Must not be claimed as business-validated yet:** final Phase 1 semantics, complete canonical item coverage, placed-order/weekday replication, calibrated lead/shelf-life/buffer policies, and fresh-delivery coverage.
- **Must wait for validated real inputs/authority:** accepted production SQL adapters, real-data backtests, shadow runs, Supabase/auth rollout, live proposal approval, and any supplier/ERP dispatch. Read access itself is already available.

### Business-question gate matrix

| Question | Work that can proceed while unanswered | What must wait for the answer | Primary gate |
|---|---|---|---|
| Q1 + Q4 — in-transit and `S/M/W/Fr` | Implement dated PO schema, empty/manual PO fixtures, pipeline netting, exception reporting, and the spreadsheet's calculated `Order` column | Identify the actual open-PO source with expected receipt dates; explain blank/reduced orders and weekday splits; approve operational netting | M2 business validation; M4 shadow |
| Q2 — lead times and calendars | Implement item/supplier overrides and calendar engine with labelled defaults and scenario tests | Production-ready order/receipt dates and stockout risk | M2 exit; M4 shadow |
| Q3 — shelf life | Implement sealed/opened fields, lot-ready interfaces, approximate caps, and infeasible-constraint tests | Trusted expiry/max-cover caps, especially for chilled/fresh items | M2 policy approval; M4 shadow |
| Q5 — Demand/Silo Load | Reproduce KW34 by treating it as daily demand under a legacy assumption; define a daily Phase 1 contract | Final semantic mapping, silo-capacity constraints, and live Phase 1 integration | M1 business sign-off; M6 live input |
| Q6 — stock count | Reproduce the literal 2.5-day bridge and implement timestamped inventory inputs/projection | Correct opening inventory timing and operational removal of the hard-coded bridge | M2 business validation; M4 shadow |
| Q7 — menu changes | Implement forward menu schema and launch/discontinuation scenarios | Production transition dates, late-PO flags, and menu-horizon validation against reality | M2 exit; M4 shadow |
| Q8 — 20% buffer | Keep exact `1.20` only in `legacy_kw34`; implement separate configurable yield and safety policies | Calibrated policy and replacement of provisional defaults | M4 calibration |
| Q9 — master data | Build stable-ID schemas, alias validation, quarantine rules, and explicit KW34 quality cases | Confirm authoritative SKU/pack/storage sources and owner-approved mappings; complete three-level BOM/order coverage | M1 fixture acceptance; M3 integration |
| Q10 — fresh products | Build configurable delivery-slot coverage with fixture calendars | Correct fresh order dates and consumption windows | M2 fresh-module sign-off; M4 shadow |
| Q11 — weekly process | Build run/approval domain objects and retain human approval as a hard invariant | Final cadence, urgent-order workflow, ownership, notifications, and UI workflow | M4 operations design; M5 UI |
| Q12 — other data used by the Excel owner | Build file adapters, provenance, placeholders, and `unavailable` metrics | Reconcile the owner's known inputs/systems with the separately validated Snowflake/source inventory | M3–M4 |
| Q13 — planner experience | Continue with proposal explanations, exceptions, overrides, and auditability as baseline requirements | Final UI priority, automation boundary, and acceptance workflow | M5 product design |

Question 14 in the supplied list is empty and creates no additional gate.

## Milestone 0 — Evidence, contracts, and fixture readiness

**Outcome:** a clean, approved, reproducible definition of what KW34 does and which gaps are unknown.

### P0 — Evidence validation

- [x] Record the source workbook URL/ID and read it without modifying the source.
- [x] Identify `Plan KW34` and `Stock KW34` as the first reference pair.
- [x] Reconcile all 27 filled stocked-item order cells at displayed-value level.
- [x] Reconcile all 28 continuing stocked-item bridge values to prior-week demand.
- [x] Document legacy rounding: `Daily` 2 dp, bridge 2 dp, `After` 1 dp, then ceiling.
- [x] Document four positive-gap blank order cells.
- [x] Document two plan ingredients absent from `Stock KW34`.
- [x] Correct target netting, safety-stock grain, and post-rounding cap logic in the brief.
- [ ] **HUMAN GATE `H-01`:** approve the fixture extraction/commit policy. This does not block scaffolding or synthetic tests; it blocks committing a real-data golden fixture.
- [ ] Obtain an approved raw workbook copy or formula walkthrough to confirm formula AST/cell references.
- [ ] Create a source manifest with workbook ID, modified timestamp, relevant tabs, extraction date, checksum, and caveats.

### P0 — Canonical contracts

- [x] Define typed schemas for `locations`, `forecast_daily`, `menu_calendar`, `bom_lines`, `items`, `suppliers`, `supplier_items`, `supplier_calendars`, `inventory_snapshots`, and `purchase_orders`.
- [x] Define typed output schemas for `planning_runs`, `planning_run_inputs`, `planning_lines`, `order_proposals`, `exceptions`, and `approvals`.
- [x] Add explicit unit suffixes (`_g`, `_units`, `_days`, `_at`, `_date`) and forbid ambiguous quantity fields.
- [x] Define stable `location_id`, `dish_id`, `silo_id`, `item_id`, `supplier_id`, and optional `supplier_item_id` rules.
- [x] Define provenance enum: `observed`, `manual`, `policy_default`, `empty_placeholder`, `unavailable`.
- [x] Define run modes: `fixture`, `scenario`, `shadow`, `operational` and initial critical-source placeholder gates.
- [x] Define exception-code catalog and severity (`blocker`, `warning`, `info`).
- [ ] **HUMAN GATES `H-02`–`H-05`:** resolve semantics/master-data questions or approve documented fixture assumptions before accepting M1 as business-complete. Implementation may start with assumption flags and quarantined rows.

### P1 — Fixture preparation

- [ ] Extract only the required KW33/KW34 plan and stock data into normalized fixture files.
- [ ] Preserve original labels alongside stable IDs and alias mappings.
- [ ] Add expected legacy outputs for all visible rows, including blanks and manual booking columns.
- [ ] Mark `Paprika - big`, `Mischsalat`, ambiguous Schnittlauch, and Creme Fraiche as explicit fixture quality cases.
- [ ] Prevent the source XLSX and unapproved production exports from entering git.

### P1 — Architecture decisions

- [ ] Record an ADR for script-first/application-service architecture.
- [ ] Record an ADR for separate `legacy_kw34` and `improved` policies.
- [ ] Record an ADR that CLI/CSV/YAML are bootstrap, test, import/export, and fallback interfaces—not the non-technical planner workflow.
- [ ] Record an ADR for files first and authoritative Supabase persistence at M3 once approved, with no dual operational configuration authority.
- [x] Select Python/runtime and core libraries: Python 3.12 standard library for the pure core and first CLI, with no third-party runtime dependency; add adapter/API dependencies only at their owning milestone.
- [x] Decide numeric representation and improved-engine precision/rounding boundaries: `Decimal` for planning quantities, no early improved-engine rounding, explicit legacy quantization only in `legacy_kw34`.

### Milestone 0 exit criteria

- [ ] Approved fixture policy and source manifest exist.
- [ ] Required schemas and exception codes are reviewed.
- [ ] Ambiguous rows are mapped, quarantined, or explicitly accepted as test cases.
- [ ] No high-impact claim in the brief is stated more strongly than the evidence supports.

## Milestone 1 — Reproduce the status quo as a Python CLI

**Outcome:** a deterministic script reproduces KW34 and exposes the workbook's silent gaps.

### P0 — Repository and quality scaffold

- [x] Create `pyproject.toml`, package layout, Python version, zero-runtime-dependency declaration, and `.env.example`.
- [x] Configure Ruff/mypy project metadata and a standard-library `unittest` verification wrapper. Ruff/mypy executables are not installed in the current runtime and remain a CI/tooling task.
- [ ] Add CI for lint/type/unit/integration tests.
- [x] Add README quick start and setup instructions.
- [x] Add fixture/data paths and workbook formats to `.gitignore` where production exports could land.

### P0 — File adapters and validation

- [ ] Implement XLSX and canonical multi-dataset CSV loaders with no calculation logic.
- [x] Implement the compatibility-specific legacy CSV loader with required-column/type checks and no calculation logic.
- [ ] Implement forward-fill parsing of hierarchical `Dish -> Silo -> Ingredient` rows.
- [ ] Validate required columns, types, positive pack sizes, allowed storage classes, and date/location grain.
- [ ] Validate stable-ID joins, alias coverage, duplicate IDs, orphan BOM lines, and conflicting pack sizes.
- [x] Emit human-readable legacy CSV errors with source file, row, field, value, and remedy; extend the same contract to canonical/XLSX adapters.
- [ ] Preserve raw source values and normalized values for audit.

### P0 — Legacy calculation profile

- [x] Implement BOM explosion and aggregation across dishes while preserving the silo/pre-mix path.
- [x] Implement the legacy `1.20` factor separately from future yield/safety stock.
- [x] Implement exact documented KW34 `Daily`, `Need`, bridge, `After`, and `Order` rounding.
- [x] Use the explicit previous-week daily input for the KW34 bridge.
- [ ] Implement stocked paths for `TK`, `Kuehl`, and `RT`.
- [ ] Implement fresh Sa/Mo/We/Fr average-day multiplier path.
- [x] Preserve blank/observed Order values as source evidence and emit structured difference exceptions; do not invent placed orders.
- [ ] Detect planned items missing from stock/order output.

### P0 — CLI and outputs

- [ ] Implement `plan validate` and `plan run --policy legacy_kw34` commands.
- [x] Implement the first `supply-plan legacy-run` / `python -m supply_planning legacy-run` fixture command with CSV input and audit JSON output.
- [x] Document the CLI as a developer/analyst, batch, troubleshooting, and recovery interface—not the final configuration UI.
- [ ] Write `order_proposals.csv`, `exceptions.csv`, `planning_lines.csv`, and `run_summary.json`.
- [ ] Include input hashes, config hash, code version, run timestamp, and run mode.
- [x] Include every currently implemented legacy intermediate and calculated-versus-observed comparison field.
- [x] Exit non-zero on input/schema blockers; allow quality warnings with explicit summary.

### P0 — Golden tests

- [ ] Assert all 27 filled KW34 stocked order cells match exactly.
- [ ] Assert the four positive-gap blank cells are reported as unexplained exceptions.
- [ ] Assert the two missing fresh rows are reported.
- [ ] Assert all 28 continuing bridge rows use the prior-week rate.
- [ ] Assert Creme Fraiche/Schnittlauch master conflicts fail or quarantine deterministically.
- [x] Add synthetic unit tests for rounding boundaries, zero demand, availability floor, determinism, blank-order exceptions, BOM aggregation/pre-mixes, and run-mode gates.

### P1 — Legacy usability

- [ ] Add a concise proposal summary by storage class and supplier/date where available.
- [ ] Add a diff report from generated versus source stock tab.
- [ ] Add clear labels that legacy output reproduces known workbook behavior and is not an improved recommendation.

### Milestone 1 exit criteria

- [ ] One documented command reproduces KW34 from approved files.
- [ ] Golden suite is green and deterministic across two clean runs.
- [ ] Every mismatch is either fixed or recorded as an explicit exception/fixture caveat.
- [ ] No database, UI, or supplier write is required.

## Milestone 2 — Improved engine with file inputs and placeholders

**Outcome:** corrected planning logic runs end to end without waiting for SQL, while clearly stating where defaults replace real data.

### P0 — Daily demand and menu model

- [ ] Implement the Phase 1 daily forecast contract and flat-KW34 fixture adapter.
- [ ] Implement location/date-aware menu assignments with service start/end.
- [ ] Aggregate shared ingredients across all active dishes before stopping an item.
- [ ] Validate menu horizon against the longest feasible replenishment horizon.
- [ ] Add launch, steady-state, discontinuation, and reactivation scenarios.

### P0 — Time-phased inventory and netting

- [ ] Build a dated event ledger for demand, on-hand snapshot, receipts/open POs, and candidate receipts.
- [ ] Compute supplier-calendar-aware candidate arrival and next replenishment arrival.
- [ ] Compute protection-period gross need and inventory position without double-counting demand.
- [ ] Simulate projected on-hand daily and emit pre-arrival stockout exceptions.
- [ ] Accept manual `open_pos.csv`; allow empty placeholder only in fixture/scenario mode.
- [ ] Support PO status/cancellability and flag receipts after final demand.

### P0 — Yield and safety placeholders

- [ ] Replace the legacy multiplier with separate `yield_factor` and safety stock in `improved` mode.
- [ ] Support `yield_factor_source = policy_default` until consumption/waste data exists.
- [ ] Support policy safety days when forecast sigma is absent.
- [ ] Implement root-sum-of-squares when daily sigma exists; document dish-error correlation assumption.
- [ ] Emit non-blocking calibration warnings and line-level provenance.
- [ ] Never label placeholder values as historical or model-calibrated.

### P0 — Constraints and scheduling

- [ ] Apply shelf-life and max-cover feasibility at receipt date.
- [ ] Apply MOQ and case rounding, then recheck hard caps.
- [ ] Emit `INFEASIBLE_ORDER_CONSTRAINTS` when no purchasable quantity satisfies policy.
- [ ] Distinguish configured shelf-life approximation from lot/expiry FEFO logic.
- [ ] Schedule orders to supplier order dates and expected receipt dates.
- [ ] Sum actual forecast days for fresh delivery-to-delivery coverage.

### P0 — Validation and comparison

- [ ] Add run-mode gates for unknown stock, open POs, pack size, lead time, and menu horizon.
- [ ] Produce side-by-side legacy versus improved results with reason codes for differences.
- [ ] Add scenario fixtures for long lead, open pipeline, empty pipeline, short shelf life, MOQ conflict, and menu retirement.
- [ ] Prove same inputs/config/code produce byte-stable normalized outputs apart from run metadata.

### P1 — Bootstrap policy schemas and offline administration

- [ ] Finalize documented `policy.yaml`, `items.csv`, and `suppliers.csv` templates.
- [ ] Label templates as fixture/development/import/fallback artifacts; do not describe them as the permanent non-technical planner workflow.
- [ ] Support supplier defaults plus item overrides and value provenance.
- [ ] Add dry-run config diff showing which proposal lines change.
- [ ] Add config version/hash to every run and line.
- [ ] **HUMAN BLOCKERS `H-06`–`H-08`:** replace or approve operational defaults.

### P2 — Advanced offline scenarios

- [ ] Add optional lead-time variability and correlated forecast-error policies.
- [ ] Add optional lot-level/FEFO fixture support.
- [ ] Add multi-location fixtures to prove no hidden single-site assumptions.

### Milestone 2 exit criteria

- [ ] Improved file-driven run completes with transparent placeholder warnings.
- [ ] All high-risk edge cases have deterministic tests and exceptions.
- [ ] Operational mode refuses unknown stock/open POs/pack size/lead time.
- [ ] Business owners can review legacy-versus-improved differences without reading code.

## Milestone 3 — SQL adapters and durable Supabase storage

**Outcome:** real operational inputs replace file placeholders, reviewed configuration migrates to one authoritative store, and runs/config are persistently auditable.

### P0 — Source discovery and fitness

- [x] Verify `CIRCUS_MODELS_READER` access to `BASE`, `INTERMEDIATE`, `REPORTING`, and `TECH_OPS` (140 physical tables).
- [ ] **HUMAN BLOCKER `H-09`:** identify the current Ops PO source with Deepali/Dor/Ilona, establish ingestion/modeling with Joel, obtain stable connection/repository access, and decide the implementation boundary before operational Snowflake adapters or replacement models are accepted. This blocks M4/operational PO netting, not file/scenario engine work.
- [x] Run and review V6/V8. On 2026-08-25 the three models refreshed sequentially for one location; forecasts cover five dates and the 76-line recommendation output is arithmetically coherent.
- [x] Record Joel's confirmation that the three generated models and `BASE_INVENTORY` are abandoned previous-data-team models and may be replaced; do not treat their current outputs as operational inputs or approved policy.
- [ ] Request GitHub access to [`data-transformation`](https://github.com/circus-kitchens/data-transformation), then inspect the abandoned definitions and upstream lineage.
- [ ] Agree whether `data-transformation` owns normalized Snowflake models/publication while this repository owns the pure planning calculation, or document another explicit boundary; avoid duplicate business logic.
- [ ] Receive the stable RSA-authenticated Snowflake service account from Joel through 1Password and document only the account/role/setup procedure, never credentials.
- [x] Run V7 and rule out `BASE_INVENTORY` as operational open-PO input: 106/106 lines are closed and fully delivered, last synced 2025-10-20.
- [x] Record Joel's confirmation that no purchase-order data is currently ingested into Snowflake to his knowledge; stop searching abandoned models for the operational feed.
- [ ] With Deepali/Dor/Ilona, document the current PO/expected-delivery system or sheet, process owner, history, change handling, and export/API capability.
- [ ] Agree ingestion with Joel/data platform—Fivetran only if appropriate—and publish a normalized PO-line/receipt-history model with remaining quantity and expected receipt date.
- [ ] Validate PO model grain, identifiers, units, remaining quantities, statuses, partial receipts, cancellations/date changes, history retention, completeness, and freshness before accepting the read-only adapter.
- [x] Run V8 candidate-key/basic-value and unit-placeholder checks. Duplicate/conflict diagnostics returned zero rows; 12 IDs are placeholder-only, six combine a real unit with null/zero placeholders, and one stable ID mixes `g` and `ml`. Treat the abandoned output as reference and make canonical-unit validation a replacement-model test.
- [x] Run V9 BOM checks: 1,193 clean current rows, 11,990 valid history rows, full materialized-menu coverage, zero tested revision-key duplicates, and complete positive pre-mix mappings. Physical silo/recipe-slot mapping remains open.
- [x] Run V3 join/cardinality checks and reject ingredient-only capacity joins; resources can change ingredient over time.
- [x] Test the first V3 active-menu/chamber path: zero of 2,576 stock keys resolved, but the raw sample proves `CHAMBER_ALIAS` is constant text, so the query tested the wrong position field.
- [ ] Run corrected V3B using active-menu matches across days, alternative ingredient IDs, and `SILO_RESOURCE_ID ↔ RECIPE_SLOT_INSERTING_POSITION` before requesting a separate map.
- [x] Complete V5: 76 rows/75 non-null ingredient IDs, one blank ID, zero bad pack quantities, zero missing units, seven missing EANs, ten missing Apicbase IDs, and no non-null duplicate/conflict exceptions.
- [x] Run V10 expiry checks: all 6,497 tested silo-days have expiry, but remaining-life outliers require semantic validation and do not define shelf-life policy.
- [x] Complete the saved V11 checks: `INT_UNIT_DAY_MENU` spans 2025-10-21 through 2026-08-24 across six units/26 menus and had no forward-day coverage on 2026-08-25; base rows extend later but mix operational-looking records with pilot/demo/training/far-future/terminated records. Forward commitment/source remains a business/source gate.
- [x] Run initial and lagged V12 checks and classify the raw source as high-frequency stock state with ingredient resets/corrections; enhanced same-ingredient analysis is optional calibration work.
- [x] Rerun dish-level V2 with only `CLOSED/SERVED`: 622 portions across 221 deployed dish-unit-days and 39 zero-sale days.
- [x] Finish the saved V1/V2B checks: six observed location names map one-to-one to unit serials; five selling/production units reconcile to 622 portions with 8.4–31.8 portions per service day. Stable location-ID and source-contract acceptance remain M3 work.
- [ ] Validate remaining source units, timestamps/timezones, completeness, freshness, retention, update cadence, and authority for each adapter actually selected.
- [ ] Prioritize current stock and open POs first; they materially affect every operational proposal.
- [ ] Validate the three-level BOM/pre-mix topology and map receipts, menu, sales, waste, OOS, stock, and refill/consumption sources with explicit coverage gaps.
- [ ] Define secure local/hosted secret handling and update `.env.example` without values.

### P0 — Read-only adapters

- [ ] Implement adapters behind the same schemas used by files.
- [ ] Add freshness, duplicate, allowed-value, referential, and join-coverage checks.
- [ ] Snapshot query parameters/source timestamps with each run.
- [ ] Compare SQL adapter output to equivalent file fixtures.
- [ ] Add retry/timeouts without hiding partial or stale data.

### P0 — Supabase decision and foundation

- [ ] **HUMAN BLOCKER `H-11`:** approve project strategy, owner, region, billing, retention, and credentials.
- [ ] Create in-repo migrations only after approval.
- [ ] Implement master/config tables: locations, items, suppliers, supplier-items, BOM, policy versions.
- [ ] Implement operational tables: menu calendar, forecasts, inventory snapshots, purchase orders.
- [ ] Implement audit tables: planning runs/inputs/lines, proposals, exceptions, approvals.
- [ ] Add immutable or append-only rules for run snapshots and approvals.
- [ ] Add seed data for local development; never seed private production data.
- [ ] Build and verify a one-time import path from reviewed CSV/YAML bootstrap configuration.
- [ ] Designate Supabase configuration versions as authoritative for operational runs and reject ambiguous file-plus-database authority.
- [ ] Keep file adapters for fixtures, controlled imports/exports, tests, and recovery only.

### P1 — Calibration sources

- [ ] Connect receipts and calculate actual lead-time distributions.
- [ ] Connect sales and align service dates/timezones/location/dish IDs.
- [ ] Connect OOS and quantify censored intervals/coverage.
- [ ] Connect waste and distinguish expiry, prep, trim, and unknown waste where possible.
- [ ] Connect lot/expiry data if available.
- [ ] Keep missing sources explicitly unavailable rather than blocking stock/PO integration.

### P1 — Persistence application layer

- [ ] Persist input/config snapshots before calculation.
- [ ] Persist line derivations, warnings, exceptions, and output hashes atomically.
- [ ] Add replay by `planning_run_id` and verify identical normalized result.
- [ ] Add config effective dating and change audit.

### P2 — Operational hardening

- [ ] Add source freshness monitoring and alerts.
- [ ] Add backup/restore and retention checks for Supabase.
- [ ] Add migration/rollback verification in CI.

### Milestone 3 exit criteria

- [ ] Stock and open-PO inputs run from real read-only sources with freshness checks.
- [ ] Supabase persistence is approved, migrated, documented, authoritative, and replayable; using another operational store requires an explicit superseding architecture decision.
- [ ] File adapters remain usable for fixtures and fallback.
- [ ] No SQL/source credential is stored in git or output artifacts.

## Milestone 4 — Backtest, calibration, and shadow validation

**Outcome:** evidence shows whether the improved policy is safer and useful before UI or operational adoption.

### P0 — Historical reconstruction

- [ ] Define available historical window and data completeness by source/week/location/item.
- [ ] Reconstruct forecasts, menus, stock, POs, receipts, and outcomes without look-ahead leakage.
- [ ] Backtest legacy and improved policies on identical information available at each historical run time.
- [ ] Separate model output differences from missing-data/placeholder effects.

### P0 — Evaluation metrics

- [ ] Define service-level/stockout metric using OOS-corrected demand where available.
- [ ] Define expiry and prep waste separately where available.
- [ ] Measure days of cover by storage class and item.
- [ ] Measure proposed/approved/ordered/received deltas and planner override rate.
- [ ] Measure unavoidable pre-arrival stockout and infeasible-constraint counts.
- [ ] Measure planner time and explanation/exception resolution burden.
- [ ] State unavailable metrics rather than substituting unlabelled proxies.

### P1 — Calibration

- [ ] Estimate yield factor only where actual/theoretical consumption coverage is sufficient.
- [ ] Clamp/fallback with sample-size and source labels.
- [ ] Estimate forecast error from Phase 1 or historical forecast snapshots; do not use realized demand as if it were a saved forecast.
- [ ] Apply OOS uncensoring method and sensitivity analysis.
- [ ] Calibrate lead-time variability from orders/receipts.
- [ ] Compare service/waste tradeoffs by storage class and scenario.

### P0 — Shadow runs

- [ ] Run legacy automation beside the manual planner first and reconcile every line.
- [ ] Run improved policy beside manual planning without dispatch.
- [ ] Capture planner explanations for blank/reduced/overridden lines.
- [ ] Review exceptions and false positives weekly.
- [ ] **HUMAN BLOCKER `H-13`:** agree duration, thresholds, and sign-off owners.
- [ ] Record signed decision to proceed, revise policy, or extend shadowing.

### Milestone 4 exit criteria

- [ ] Backtest methodology and limitations are documented and reproducible.
- [ ] Shadow output is stable across the agreed period.
- [ ] Material differences have understood reason codes or approved follow-up.
- [ ] Owners approve the policy/config baseline for UI exposure.

## Milestone 5 — FastAPI and React/Tailwind user interface

**Outcome:** non-technical planners can manage validated inputs/config, run planning, review derivations/exceptions, and approve/export proposals.

### P0 — API boundary

- [ ] Add FastAPI around the existing application service; no engine logic in routes.
- [ ] Define versioned API contracts for validation, run, result, config, history, approval, and export.
- [ ] Add job/status handling for runs longer than request timeouts.
- [ ] Add idempotency for run/approval actions.
- [ ] Add API tests against the same fixtures as the CLI.

### P0 — Auth and authorization

- [ ] **HUMAN BLOCKER `H-12`:** approve roles and auth/SSO requirements.
- [ ] Implement Supabase Auth/RLS if selected.
- [ ] Enforce viewer/planner/config-editor/approver/admin permissions server-side.
- [ ] Audit config changes, runs, approvals, exports, and overrides.

### P0 — Web foundation

- [ ] Select React app framework/build tool and record the decision.
- [ ] Add Tailwind design tokens and accessible component primitives.
- [ ] Add typed API client, query/cache strategy, routing, error boundaries, and test setup.
- [ ] Build responsive planner-first navigation and consistent loading/empty/error states.

### P0 — Planner workflows

- [ ] Run page: select location/date/policy/input version, validate, review warnings, execute dry run.
- [ ] Proposal table: supplier/date/storage filters, exact quantities, status, and exception summary.
- [ ] Proposal detail: derivation, input/config provenance, inventory timeline, caps, MOQ/case delta, and placeholder badges.
- [ ] Exception workflow: assign/resolve/comment/override with reason and audit.
- [ ] Approval/export: explicit confirmation, permission check, immutable approval record, CSV download; no supplier send.
- [ ] Run history: status, input/config versions, comparison, replay, and audit.

### P1 — Configuration workflows

- [ ] Item/SKU page with defaults/overrides, units, shelf life, storage class, provenance, and validation.
- [ ] Supplier page with lead times, calendars/cut-offs, MOQ/case, split/cancel rules.
- [ ] BOM/menu page with stable IDs, effective dates, alias warnings, and transition horizon.
- [ ] Inventory/open-PO manual entry/import as a temporary integration fallback.
- [ ] Policy version page with dry-run impact diff before activation.
- [ ] Route planner configuration changes through the authenticated API with audit records; require no direct CSV/YAML or Supabase-table editing.
- [ ] Prevent activation when operational blockers remain.

### P1 — UI quality

- [ ] Keyboard navigation, labels, contrast, focus, and screen-reader checks.
- [ ] Browser tests for critical run/review/approve/export paths.
- [ ] Visual QA at desktop/tablet widths used by planners.
- [ ] Friendly validation text; no raw stack traces.

### P2 — Convenience

- [ ] Saved filters/views and supplier-grouped export.
- [ ] Notifications for blocking exceptions or stale inputs.
- [ ] Comment/assignment workflow if multiple planners require it.

### Milestone 5 exit criteria

- [ ] A non-technical test user completes config → validate → run → review → approve → CSV export without developer help.
- [ ] The tested planner workflow requires neither repository-file editing nor direct database-table access.
- [ ] Permissions and audit readback are verified.
- [ ] UI and CLI produce the same normalized result for the same run inputs.
- [ ] Supplier dispatch remains disabled.

## Milestone 6 — Phase 1 integration and operationalization

**Outcome:** live daily forecasts and scheduled planning operate reliably; any dispatch integration is separately approved.

### P0 — Phase 1

- [ ] **HUMAN BLOCKER `H-10`:** obtain live sample, owner, transport, and schema/version policy.
- [ ] Implement Phase 1 adapter to the existing daily contract.
- [ ] Validate dates, locations, dishes, negative/null forecasts, sigma semantics, and horizon coverage.
- [ ] Compare live forecast adapter against equivalent file input.
- [ ] Add contract-version compatibility and rejection behavior.

### P0 — Scheduling and operations

- [ ] Add scheduled fresh and stocked runs with explicit timezone/cut-off handling.
- [ ] Add health, failure, stale-input, and incomplete-run monitoring.
- [ ] Add retries/idempotency and prevent duplicate proposals/approvals.
- [ ] Add runbook for source outage, UI outage, stale stock, and fallback file run.
- [ ] Add rollback to the last approved config/policy version.

### P1 — Operational exports

- [ ] Confirm approved CSV/Sheet/ERP output contract and owner.
- [ ] Add export reconciliation/readback.
- [ ] Keep proposal, approval, export, placed order, and receipt as separate states.
- [ ] **HUMAN BLOCKER `H-14`:** obtain explicit approval before any supplier/ERP write integration.

### P2 — Dispatch automation (separate release gate)

- [ ] Threat/risk review for wrong-recipient, duplicate-order, wrong-unit, stale-config, and partial-failure cases.
- [ ] Add dual confirmation or four-eyes control if required.
- [ ] Add idempotency keys, provider readback, reconciliation, and cancellation path.
- [ ] Pilot with a limited supplier/location and documented rollback.

### Milestone 6 exit criteria

- [ ] Live Phase 1 input is contract-validated and monitored.
- [ ] Scheduled runs are reliable and fallback procedure is tested.
- [ ] Operational output matches approved human workflow.
- [ ] Dispatch remains manual unless the separate P2 release gate is signed.

## Cross-cutting test matrix

- [ ] Multi-dish aggregation and pre-mix preservation.
- [ ] Multiple locations and timezone/cut-off boundaries.
- [ ] Zero/fractional forecast and menu start/end boundaries.
- [ ] Missing/duplicate/orphan IDs and alias collisions.
- [ ] Mixed/conflicting units and pack sizes.
- [ ] Open PO before, on, and after protection end.
- [ ] Stockout before candidate arrival.
- [ ] Full/empty/partially filled pipeline and cancellable/non-cancellable POs.
- [ ] Shelf-life shorter than lead time; max-cover cap.
- [ ] MOQ and case rounding below/above hard cap.
- [ ] Fresh delivery coverage using unequal daily demand.
- [ ] Launch, discontinuation, shared ingredient after dish retirement.
- [ ] Missing waste/OOS/sigma/receipt/lot data with correct provenance.
- [ ] Fixture/scenario/shadow/operational run-mode gates.
- [ ] Reproducibility and replay.
- [ ] Approval permissions, idempotency, and export readback.

## Immediate next execution slice

1. [ ] Wait for answers to the already-sent Q1-Q13 Excel-owner questionnaire; do not send a correction. Record the answers against the audience/topic map in brief section 10.
2. [x] Create storage-neutral normalized schema definitions, initial run-mode gates, and the exception-code catalog; mark files as bootstrap adapters and Supabase as the planned operational store.
3. [x] Scaffold the Python package and test tooling.
4. [x] Create a documented synthetic fixture and private-data ignore paths; keep real KW34-derived rows uncommitted until `H-01`/`HA-02` is cleared.
5. [x] Implement BOM explosion and legacy rounding.
6. [ ] After fixture approval, land the 27-cell KW34 golden test plus gap/missing-row assertions.
7. [x] Add the first compatibility CSV validation/run command and deterministic audit JSON; multi-file canonical validation and CSV report bundle remain open above.
8. [ ] Ask Deepali/Dor (optionally Ilona) for the PO-process/source walkthrough, then coordinate ingestion/modeling with Joel. In parallel request `data-transformation` access, complete the least-privilege RSA service-account setup, inspect lineage, and decide the cross-repository boundary. Corrected V3B is the only required SQL follow-up; enhanced V12 is optional calibration work.
9. [ ] Resolve or explicitly accept assumptions for `H-02`–`H-05`, then review Milestone 1 output with the current planner before accepting M1 or starting improved-policy sign-off.

## Dated progress log

- 2026-08-22: Repository initialized; AGENTS/MEMORY and engineering brief added.
- 2026-08-22: Linked workbook inspected read-only; KW34 legacy values independently reconciled.
- 2026-08-22: Brief corrected for bridge behavior, rounding, target netting, safety-stock grain, constraints, placeholders, script-first architecture, Supabase/UI boundary, and delivery sequence.
- 2026-08-22: Master backlog and execution scratchpad created. Implementation remains unstarted.
- 2026-08-24: Snowflake access confirmed; source-status documentation reconciled. Catalogued tables remain candidates until verification and owner/lineage checks pass. Access is no longer a blocker; expected-receipt/open-PO data, three-level BOM mapping, source authority, waste semantics, and planning policies remain stage gates.
- 2026-08-22: Clarified that CLI/CSV/YAML are technical bootstrap and fallback interfaces; the planned non-technical workflow is React/FastAPI backed by authoritative Supabase persistence after approval.
- 2026-08-24: Reclassified unanswered business questions as stage-exit/promotion gates rather than a global start blocker. M0/M1 scaffolding and scenario-safe engine work may begin while answers are collected in parallel.
- 2026-08-24: Added the root README as the concise engineer handover for project purpose, planned architecture, logic, data/config boundaries, delivery order, safeguards, and the documentation reading path.
- 2026-08-24: Implemented the first M0/M1 tranche: Python 3.12 package, canonical input/output dataclasses, provenance/run modes and critical-source gates, pure BOM explosion, isolated `legacy_kw34/v1`, legacy CSV adapter, deterministic audit CLI, synthetic fixture, and 17 passing tests. Added canonical-contract and human-action documentation; real KW34 golden tests remain gated.
- 2026-08-25: Reviewed V6/V7/V8 outputs. Current forecasts and generated recommendations refresh together for one location and reconcile internally. Joel then confirmed that these three models and `BASE_INVENTORY` are abandoned previous-data-team models that may be replaced in `data-transformation`; they are not operational sources of truth. GitHub access and an RSA-authenticated Snowflake service account are pending. The actual source with remaining quantity and expected receipt date remains the main operational data blocker.
- 2026-08-25: Reviewed the remaining V1-V12 exports and recorded them in `docs/scratchpads/snowflake_verification_evidence.md`. Forecast candidate keys pass the tested duplicate checks; the flattened/versioned BOM is clean and covers the materialized menu; ingredient-only silo-capacity joins are invalid; expiry coverage is high but policy remains manual; stock updates are state events rather than proven consumption; and the EUR 31k waste headline is reproducible only as a six-unit/83-day field sum with unconfirmed semantics. Superseded the earlier sales comparison and reduced the SQL backlog to focused follow-ups.
- 2026-08-25: Reviewed the 13:07-13:11 follow-ups. V8 placeholder semantics are classified and expose one mixed-unit ingredient in the abandoned model; corrected dish-level V2 is 622 portions; V12 transition deltas confirm resets/corrections; the first V3 physical-slot attempt is invalid because `CHAMBER_ALIAS` is constant and is superseded by corrected V3B. The open-PO-source question was sent to Joel; his later response is recorded in the next entry.
- 2026-08-25: Joel confirmed that PO data is not currently ingested into Snowflake to his knowledge and directed source discovery to Ops (Deepali/Dor/Ilona), with Fivetran a possible later ingestion route. This becomes `HA-13`: it blocks accepted real PO adapters, M4 shadow, and operational netting, but not pure/file engine work. The 13:33-13:35 exports close V5, V11, V1, and V2B; corrected V3B is the only required SQL follow-up.
