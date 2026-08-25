# Agent Scratchpad — Phase 2 Supply Planning

> Short execution context. Authoritative scope is the brief; priorities are in
> the master backlog; measured SQL counts are in the Snowflake evidence file.

## Goal

Replace the manual KW33/KW34 Phase 2 workbook calculation with an internal job
that consumes a daily Phase 1 forecast, applies BOM/stock/PO/config rules, and
writes explainable recommendations to Snowflake.

## Correct architecture — 2026-08-25

```text
Snowflake operational inputs ─┐
                              ├─> pure Python Phase 2 calculation
Supabase editable rules ──────┘              ↓
                                   Snowflake result tables

internal React UI + Python API ↔ Supabase rules
```

- Phase 1 is independent and supplies forecast portions by location/dish/day.
- Phase 2 owns BOM explosion, stock/open-PO netting, lead/review coverage,
  shelf life/max cover, pack/MOQ/case, fresh delivery rules, and internal
  recommendations.
- Supabase exists so non-technical users can edit application-owned rules.
- Snowflake remains authoritative for operational inputs and calculated output.
- The UI is configuration-focused. Approval, comments/assignment,
  supplier/ERP export, and dispatch are outside scope.
- “Delivery schedule” means simple configured weekdays/cut-offs, not an
  external calendar integration.

## Verified legacy baseline

- Displayed KW34 stocked-item arithmetic is:
  `Daily = round(g/day ÷ pack × 1.20, 2)`;
  `Need = ceil(Daily × 6)`;
  `Bridge = round(KW33 Daily × 2.5, 2)`;
  `After = round(max(0, Stock - Bridge), 1)`;
  `Order = ceil(max(0, Need - After))`.
- This reconciles 27/27 filled KW34 order cells and 28/28 continuing-item
  bridge values at displayed precision.
- Four positive calculated gaps have blank observed orders; two planned fresh
  ingredients are absent from the stock tab; Creme Fraiche/Schnittlauch expose
  master-data conflicts.
- The code implements this arithmetic, but automated tests still use synthetic
  rows. The real workbook golden fixture is the main unfinished M1 task.

## Implemented

- Canonical typed contracts, provenance, and actionable file validation.
- Three-level BOM explosion with pre-mixes and shared-item aggregation.
- `legacy_kw34/v1` calculation and deterministic audit CLI.
- Daily forecast/menu/BOM/item/inventory/open-PO file bundle.
- Pure dated event ledger, stock projection, and open-PO netting.
- Visible stale-stock, late-PO, and projected-stockout issues.
- Strict shadow/production source gates.
- 32 passing tests after removing unused approval/workflow scaffolding.

## Data status

- Required V1-V12 Snowflake verification is complete; do not rerun by default.
- Joel confirmed the old forecasts/recommendations and `BASE_INVENTORY` are
  abandoned. The old outputs remain reference evidence only.
- No live PO source is currently ingested into Snowflake. Deepali/Dor/Ilona
  identify the current Ops source; Joel/data platform then ingests it.
- The flattened/versioned BOM is a strong candidate. Physical silo-slot mapping
  remains unresolved but does not block ingredient-level planning.
- Waste, consumption, OOS, and forecast-error semantics are later calibration
  work, not core Phase 2 blockers.

## Immediate next steps

1. Build/run the minimal real KW33/KW34 fixture locally; commit only after the
   data-handling decision.
2. Wait for and record the already-sent Q1-Q13 Excel-owner answers.
3. Ask Joel for `data-transformation` access, service-account completion, and
   the Snowflake result schema/write/run-history pattern.
4. Continue Ops PO-source discovery and subsequent ingestion.
5. Implement a small Phase 2 config contract for the exact fields the UI will
   maintain; keep statistical calibration and complex optimization later.
6. Finish minimum improved recommendation calculations and tests.
7. Implement accepted Snowflake read adapters/result writer.
8. Create Supabase/config UI only after the config contract is stable.

## Risks

- Do not treat a refreshed abandoned model as authoritative.
- Do not mix Phase 1 forecast creation into this repository.
- Do not call synthetic/default values measured or calibrated.
- Do not silently infer business rules from Snowflake column names.
- Do not commit the workbook, raw production exports, or secrets without the
  recorded approval.
- Do not let files and Supabase become competing production config authorities.
- Do not add supplier/ERP writes or a planning-approval workflow.

## Verification

- Command: `scripts/check.ps1 -PythonExecutable <python-3.12-path>`.
- Current result: 32 tests pass; compilation and `git diff --check` are part of
  the wrapper/final audit.
- Ruff/mypy are configured but unavailable in the bundled runtime.
