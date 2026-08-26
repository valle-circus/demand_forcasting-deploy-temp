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
- Four positive calculated gaps have blank observed orders; the owner thinks
  they were missed. Two planned fresh ingredients are absent from the stocked
  path because they are ordered per fresh window. Creme Fraiche is `5000 g`,
  current Schnittlauch is the distinct `250 g` product, and `Oel` maps to
  `Sonnenblumenoel`.
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
- No live PO source is currently ingested into Snowflake. The current process is
  Transgourmet pending-order history downloaded as PDFs and netted outside the
  workbook. An approved export/API and normalized ingestion remain open.
- Prep-kitchen operators upload manual usable-stock counts to Apicbase, but the
  owner reports stale Apicbase master data. Assess stock, BOM, and item-master
  fitness separately through read-only evidence.
- The flattened/versioned BOM is a strong candidate. Physical silo-slot mapping
  remains unresolved but does not block ingredient-level planning.
- Waste, consumption, OOS, and forecast-error semantics are later calibration
  work, not core Phase 2 blockers.

## Interim feedback-V1 source decision — 2026-08-26

- Use the original KW33/KW34 workbook as the complete historical comparison
  fixture. Extract its forecast, menu/week context, stock, item/pack values, and
  other available fields with workbook/tab/week provenance; do not ask the Excel
  owner to resend data before the first comparison.
- Keep raw manual Transgourmet downloads outside git and transform them into a
  versioned `open_pos.csv`. Transgourmet API access is later automation, not a
  prerequisite for the feedback V1.
- Where recurring input cannot yet come from an accepted automated source,
  maintain a versioned manual CSV source of truth. Do not silently treat the
  historical workbook as a live source.
- The immediate data-analyst request is read-only Apicbase access/API
  documentation or exports for current stock, BOM/recipes, item master/pack
  sizes, and IDs needed to map Transgourmet article numbers. Validate these
  domains separately because the Apicbase master is reported stale.
- Forecast moves from a manual `forecast_daily.csv` to the future Phase 1
  Snowflake table. Menu may come with Phase 1 only if the contract explicitly
  includes the complete active dish/date schedule; otherwise its future source
  remains open.
- Planning rules such as shelf life, lead time, delivery windows, safety/yield,
  MOQ/case, and capacity use versioned manual config first and Supabase later.
- The authoritative field-by-field source table is in
  `docs/descriptions/data_requirements.md`, "Interim V1 source map".

## Planner answers received — 2026-08-26

- `Demand/Silo Load` is forecast dishes sold/day across all three REWE sales
  units combined because prep and purchasing are centralized. It is based on
  roughly two weeks of consumption plus campaigns, customer-approved, manually
  trend-adjusted, and entered as one flat weekly rate.
- The target needs an explicit service-location → central-planning-location map;
  never replicate the combined workbook value across the three units.
- Current Transgourmet lead assumptions are about 3 days standard and 5 days
  fresh. Future pods are about one month and non-cancellable. Exact calendar/
  cut-off/item rules remain open.
- Fresh coverage is `Sat→Mon`, `Mon→Tue+Wed`, `Wed→Thu+Fri`, `Fri→Sat`.
- The Thursday main order is rechecked Monday after inventory. `S/M/W/Fr` are
  delivery-day allocations; their exact placed/confirmed/delivered status is
  still open. Penne is split/reduced because of freezer space.
- The planner does not know why the bridge is `2.5`; exact count time and
  opened/partial-pack handling also remain open.
- The legacy 20% is a broad assumption. Keep it only in compatibility mode;
  improved yield/safety settings still need separate approval.

## Immediate next steps

1. Build/run the minimal real KW33/KW34 fixture from the workbook already
   available; commit only after the data-handling decision.
2. Implement/use the manual Transgourmet raw-file-to-`open_pos.csv` path; never
   store supplier credentials or raw private exports in the repository.
3. Ask the data analyst/Apicbase owner for read-only access or exports for stock,
   BOM, item/pack data, and cross-system IDs, then validate freshness and fields.
4. Return to the Excel owner only after the first comparison, with specific
   differences that require interpretation or policy approval.
5. Ask Joel for `data-transformation` access, service-account completion, and
   the Snowflake result schema/write/run-history pattern.
6. Continue normalized PO/receipt ingestion after source-contract validation.
7. Implement a small Phase 2 config contract for the exact fields the UI will
   maintain; keep statistical calibration and complex optimization later.
8. Finish minimum improved recommendation calculations and tests.
9. Implement accepted Snowflake read adapters/result writer.
10. Create Supabase/config UI only after the config contract is stable.

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
