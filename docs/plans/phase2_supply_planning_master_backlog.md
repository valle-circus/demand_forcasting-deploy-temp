# Phase 2 Supply Planning — Master Backlog

**Created:** 2026-08-22
**Reconciled:** 2026-08-25 after scope correction
**Source of truth:** this file controls implementation order and status.
**Detailed evidence:** `docs/descriptions/phase2_supply_planning_brief.md` and
`docs/scratchpads/snowflake_verification_evidence.md`.

## Goal and boundary

Automate the Phase 2 calculation currently performed in the KW33/KW34 Excel
workbook:

```text
Phase 1 daily dish forecast
        + menu/BOM + stock + open POs + editable Phase 2 rules
        ↓
internal ingredient and purchase recommendations in Snowflake
```

Phase 1 produces forecast portions by `location_id × dish_id × service_date`.
It is an independent upstream input and is not implemented in this repository.

Phase 2, this repository, determines ingredient requirements and recommended
purchase quantities. Stock, open POs, lead time, shelf life, pack size,
delivery cadence, MOQ/case, and storage class belong to Phase 2 because they
change what must be available or purchased.

Sales, OOS, waste, and forecast error are useful for Phase 1 or later Phase 2
calibration. They are not required to reproduce the initial workbook logic.

## Target architecture

| Component | Responsibility |
|---|---|
| Snowflake source models | Forecast, menu/BOM, item identity/pack data, stock, and open POs |
| Supabase | Versioned application-owned rules editable by internal users |
| Internal React UI + Python API | Validate and edit lead time, shelf life, storage-class defaults, safety settings, MOQ/case, and simple delivery rules |
| Pure Python engine | Deterministic Phase 2 calculation with no database/UI code |
| Snowflake result tables | Run metadata, recommendation lines, derivations, and exceptions |

CSV/JSON remain fixture, test, development, import, and recovery formats. They
are not the final non-technical workflow.

The UI is an internal configuration tool. This backlog contains no supplier or
ERP dispatch integration and no proposal-approval workflow.

## Current status

| Area | Status |
|---|---|
| KW33/KW34 displayed-value reconstruction | Complete: 27/27 filled orders and 28/28 bridge values reconciled |
| Real KW33/KW34 automated golden fixture | Open: synthetic tests only; private/local or approved sanitized fixture needed |
| Canonical file contracts and validation | Implemented |
| Three-level BOM explosion | Implemented |
| Dated stock/open-PO ledger and netting | Implemented for file inputs |
| Full configurable Phase 2 policy | Not implemented |
| Required Snowflake discovery SQL | Complete; no required rerun remains |
| Live Snowflake adapters/output writes | Not implemented; access/output design pending |
| Live PO source | Missing from Snowflake; Ops/data-platform workstream open |
| Supabase configuration store | Planned, not created |
| Internal configuration UI | Planned after config schemas/integration |

The repository verification wrapper currently passes 32 tests.

## Definition of done for the first useful release

- [ ] A daily Phase 1 forecast can be read through a documented adapter.
- [ ] Menu/BOM, item/pack, stock, and PO inputs are validated at stable-ID grain.
- [ ] The Phase 2 result matches approved KW33/KW34 legacy fixtures where the
      legacy profile is selected.
- [ ] The improved profile produces explainable ingredient and pack
      recommendations from approved Phase 2 rules.
- [ ] Snowflake result rows include a run ID, calculation time, input/config
      versions, intermediate values, and exceptions.
- [ ] Rerunning the same inputs/config is deterministic and does not create
      uncontrolled duplicate output.
- [ ] Non-technical users can edit the approved planning-rule fields through
      the internal UI without editing repository files or database rows.
- [ ] No missing source or policy value is silently converted to zero.
- [ ] No supplier/ERP write is implemented.

## Human and access gates

The detailed requests and owners are in `human_action_register.md`.

| Gate | Needed for | Does not block |
|---|---|---|
| Excel-owner Q1-Q13 answers | Business interpretation and final legacy/improved sign-off | Synthetic implementation and adapter scaffolding |
| KW33/KW34 fixture handling decision | Committed golden fixture | Private/local validation |
| Snowflake service account and `data-transformation` access | Live adapter tests and lineage inspection | Pure engine work |
| Snowflake output ownership/schema/write pattern | End-to-end persistence | Output contract and writer interface |
| Current PO source and ingestion | Complete production netting | Manual/synthetic PO scenarios |
| Approved lead-time/shelf-life/MOQ/delivery-rule values | Business-valid improved recommendations | Parameterized calculations and tests |
| Supabase project/access | Persistent non-technical rule editing | Engine and Snowflake adapter work |
| Live Phase 1 forecast contract | Scheduled production runs | Manual/file forecast testing |

## Milestone 0 — Evidence and contracts

**Outcome:** preserve what the workbook actually does and keep unknowns visible.

- [x] Record the workbook and relevant `Plan KWxx`/`Stock KWxx` tabs.
- [x] Reconcile all 27 filled KW34 stocked-order cells at displayed precision.
- [x] Reconcile all 28 continuing bridge values to KW33 demand.
- [x] Document the exact rounding order and constants.
- [x] Document four positive-gap blank order cells.
- [x] Document `Paprika - big` and `Mischsalat` missing from `Stock KW34`.
- [x] Document Creme Fraiche/Schnittlauch pack-size conflicts and label drift.
- [x] Define daily Phase 1 input and three-level BOM contracts.
- [x] Define source provenance and actionable validation errors.
- [ ] Decide whether the real fixture may be committed, anonymized, or must
      remain private.
- [ ] Obtain raw formula evidence or an owner walkthrough if available.
- [ ] Produce the minimal real KW33/KW34 fixture locally or in approved form.

## Milestone 1 — Legacy KW33/KW34 parity

**Outcome:** one deterministic command reproduces the manual baseline before
we replace its assumptions.

- [x] Implement isolated `legacy_kw34/v1` stocked-item arithmetic.
- [x] Preserve exact displayed rounding and the `1.20`, `6`, and `2.5` values.
- [x] Use previous-week `Daily` for the bridge.
- [x] Preserve observed blank/different order cells as exceptions.
- [x] Add a compatibility CSV adapter and deterministic JSON audit.
- [x] Add synthetic boundary and determinism tests.
- [ ] Implement the workbook-to-fixture extraction/adapter needed for actual
      KW33/KW34 rows.
- [ ] Add golden assertions for all 27 filled order cells and 28 bridge cells.
- [ ] Add explicit assertions for the four blanks, two missing fresh rows, and
      master-data conflicts.
- [ ] Implement and validate the fresh Sa/Mo/We/Fr legacy path.
- [ ] Review all differences with the Excel owner and record explanations.

### Milestone 1 exit

- [ ] The approved real fixture runs with one documented command.
- [ ] All known filled cells match or have an explicit accepted explanation.
- [ ] Blank/missing/conflicting rows remain visible.

## Milestone 2 — Minimum improved Phase 2 engine

**Outcome:** replace the workbook's structural weaknesses without building
advanced optimization or infrastructure first.

### Implemented foundation

- [x] Load daily forecast, menu, BOM, items, inventory, and `open_pos.csv`.
- [x] Validate required fields, types, stable-ID joins, duplicates, units,
      effective BOM coverage, menu coverage, and timezone-aware timestamps.
- [x] Explode and aggregate shared ingredients by location/day.
- [x] Build a pure dated inventory/open-PO event ledger.
- [x] Net demand without double-counting it.
- [x] Emit projected stockout, stale-stock, overdue-PO, and late-PO exceptions.
- [x] Fail closed in shadow/production mode when a critical source is unknown.
- [x] Prove deterministic improved audit output with synthetic scenarios.

### Next core calculation

- [ ] Define one small versioned config contract for:
  - lead time and review period;
  - shelf life/max cover where used;
  - storage-class behaviour;
  - pack size and optional MOQ/case size;
  - simple delivery weekdays/cut-off only where they affect the calculation;
  - safety/yield values and provenance.
- [ ] Calculate the protection horizon from lead time plus review/delivery
      cadence; do not restore an unexplained global six-day target.
- [ ] Keep legacy `1.20` only in `legacy_kw34`; make the improved safety/yield
      rule explicit and simple until calibration exists.
- [ ] Apply shelf-life/max-cover only when configured and expose a binding cap.
- [ ] Apply pack, MOQ, and case rounding once at the end.
- [ ] Report infeasible cases when rounding conflicts with a hard cap.
- [ ] Implement fresh delivery-to-delivery coverage from actual daily forecast.
- [ ] Produce internal `PlanningRecommendation` rows with derivations and
      exception codes; do not add workflow statuses or approvals.
- [ ] Add focused tests for zero demand, long lead, empty/open pipeline, late
      receipt, fresh unequal days, shelf-life cap, MOQ/case boundary, and shared
      ingredients.

### Explicitly later, not P0

- [ ] Statistical safety stock from forecast sigma.
- [ ] Yield calibration from physical consumption/waste.
- [ ] OOS uncensoring and forecast-quality analysis.
- [ ] Lot-level FEFO.
- [ ] Complex multi-supplier optimization or split deliveries.
- [ ] Advanced launch/discontinuation optimization beyond validating the
      supplied forecast/menu horizon.

### Milestone 2 exit

- [ ] File-driven recommendations are explainable and deterministic.
- [ ] Every default/manual rule is labelled with provenance/version.
- [ ] Results can be compared line-by-line with the legacy profile.

## Milestone 3 — Snowflake inputs, Snowflake outputs, and Supabase configuration

**Outcome:** replace file placeholders with real sources while giving internal
users a durable place to maintain Phase 2 rules.

### Snowflake and data-platform work

- [x] Verify broad read access and complete V1-V12 source investigation.
- [x] Record that the discovered forecast/recommendation models and
      `BASE_INVENTORY` are abandoned.
- [x] Rule out current Snowflake tables as a usable live PO ledger.
- [ ] Obtain `data-transformation` repository access.
- [ ] Receive Joel's RSA Snowflake service account through 1Password.
- [ ] Agree with Joel:
  - which upstream transformations belong in `data-transformation`;
  - which Python job/repository owns Phase 2 calculation;
  - the target Snowflake database/schema/table names;
  - whether result runs append or replace a latest view;
  - required read/write grants and scheduling owner.
- [ ] Work with Deepali/Dor/Ilona to identify the PO source and have data
      platform ingest a normalized PO/receipt history.
- [ ] Implement read adapters only for accepted sources with freshness,
      uniqueness, unit, key, and coverage checks.
- [ ] Implement an idempotent Snowflake result writer.
- [ ] Persist `run_id`, `generated_at`, input snapshot/version, active config
      version/hash, recommendation derivations, and exceptions.
- [ ] Reconcile each SQL adapter against an equivalent reviewed file fixture.

### Supabase configuration

- [ ] Approve project owner, region, environments, credentials, backup, and
      retention before creating infrastructure.
- [ ] Store only application-owned editable configuration and its change
      history in Supabase; Snowflake remains the source/output warehouse.
- [ ] Start with the minimum tables needed for active policy version,
      storage-class defaults, item overrides, supplier-item constraints, and
      simple delivery schedules.
- [ ] Validate configuration before activation and keep one authoritative
      active version per environment.
- [ ] Include the active config version/hash in every Snowflake result run.
- [ ] Keep CSV/YAML only for fixtures, controlled import/export, and recovery.

### Milestone 3 exit

- [ ] Accepted real inputs can run through the engine.
- [ ] Results are written safely and reproducibly to Snowflake.
- [ ] An active Supabase config version can replace bootstrap files.
- [ ] Unknown PO/current-stock/forecast inputs block production output.

## Milestone 4 — Internal validation against the manual process

**Outcome:** demonstrate usefulness before scheduling the job broadly.

- [ ] Run legacy output beside the Excel owner and reconcile every line.
- [ ] Run improved results beside the manual plan for representative weeks.
- [ ] Capture reasons for overrides, blanks, emergency orders, and fresh-slot
      changes.
- [ ] Separate calculation differences from missing-source and policy effects.
- [ ] Agree simple first-release measures: missing-demand coverage, projected
      stockout warnings, recommendation differences, and planner time.
- [ ] Add waste/service-level calibration only when definitions and historical
      coverage are trustworthy.
- [ ] Record the decision to continue, adjust rules, or extend comparison.

## Milestone 5 — Internal configuration UI and scheduled job

**Outcome:** non-technical users maintain the Phase 2 rules and the internal job
runs reliably.

### Minimum UI

- [ ] Add a thin Python API over validated Supabase configuration operations.
- [ ] Add internal authentication appropriate to the hosting environment.
- [ ] Let authorized internal users view/edit:
  - storage-category defaults;
  - item/supplier overrides;
  - lead time and review period;
  - shelf life/max cover;
  - MOQ/case size;
  - fresh/stocked classification and simple delivery schedule;
  - safety/yield setting and provenance.
- [ ] Validate before save/activation and show clear field-level errors.
- [ ] Show current active version and basic change history.
- [ ] Optionally provide a read-only result/exception view if it materially
      helps users; Snowflake remains the result store.

The first UI does not include proposal approval, assignment/comments, supplier
send, ERP export, or a broad planning workflow.

### Scheduled internal job

- [ ] Connect the accepted live Phase 1 daily forecast contract.
- [ ] Schedule the Snowflake/Supabase → engine → Snowflake run.
- [ ] Add idempotency, retries, freshness checks, failure logging, and a small
      runbook.
- [ ] Verify that a failed run cannot replace the last successful result view.

### Milestone 5 exit

- [ ] A non-technical user can safely edit and activate the supported rules.
- [ ] A scheduled run writes reproducible internal Snowflake output.
- [ ] Source/config failures remain visible and do not produce trusted results.

## Cross-cutting tests

- [x] Multi-dish aggregation and pre-mix preservation.
- [x] Multiple locations and shared ingredients.
- [x] Zero forecast and deterministic replay.
- [x] Duplicate/orphan/menu/BOM/input validation.
- [x] Open PO within/after horizon and same-day receipt ordering.
- [x] Missing/placeholder source gates and stale inventory.
- [ ] Real KW33/KW34 parity cases.
- [ ] Fresh unequal daily demand and delivery-to-delivery coverage.
- [ ] Lead/review horizon boundaries.
- [ ] Shelf-life/max-cover and MOQ/case conflicts.
- [ ] Supabase config validation/version selection.
- [ ] Snowflake read/write idempotency and failure behavior.

## Immediate next execution slice

1. [x] Correct the architecture and backlog: Snowflake inputs/results,
   Supabase editable rules, internal config UI, no approval/dispatch workflow.
2. [ ] Build or run the minimal real KW33/KW34 fixture locally; commit only
   after the recorded data-handling decision.
3. [ ] Record the Excel-owner answers when received and map them to the legacy
   and improved rules above.
4. [ ] Ask Joel to confirm the Snowflake output ownership/schema/write pattern,
   finish service-account provisioning, and grant `data-transformation` access.
5. [ ] Continue the Ops PO-source/ingestion workstream.
6. [ ] Implement the small Phase 2 config contract and the remaining minimum
   calculation rules; keep advanced calibration out of P0.
7. [ ] Implement Snowflake adapters/result writer once source contracts and
   access are accepted.
8. [ ] Create Supabase/config UI only after the config contract is stable.

## Dated progress

- 2026-08-22: Workbook inspected read-only; KW33/KW34 displayed values and
  known gaps were reconstructed.
- 2026-08-24: First M0/M1 Python foundation implemented with synthetic tests.
- 2026-08-25: Snowflake V1-V12 investigation completed; abandoned models and
  missing PO ingestion confirmed with Joel/data platform.
- 2026-08-25: Canonical file adapters, BOM explosion, dated event ledger,
  open-PO netting, strict gates, deterministic audit output, and synthetic
  improved scenarios implemented.
- 2026-08-25: Scope reconciled after architecture drift. Phase 1 remains the
  independent daily forecast input. Phase 2 owns ingredient/order calculation.
  Snowflake owns operational inputs/results; Supabase plus an internal UI owns
  editable Phase 2 rules. Approval/dispatch workflows and speculative advanced
  optimization were removed from the active plan.
