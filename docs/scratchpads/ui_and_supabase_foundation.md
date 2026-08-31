# UI and Supabase foundation scratchpad

> Living notes for the maintainer UI, HTTP API, prototype Supabase persistence,
> and Vercel/Render deployment foundation. Keep this concise and update it after
> each meaningful slice; authoritative behavior belongs in `docs/descriptions/`.

## Goal

- Carry the completed monorepo foundation into a small, coherent maintainer
  product: three top-level pages that expose readiness/risk, per-location
  planning, and controlled data/settings maintenance without duplicating the
  Python calculation or implying supplier order placement.

## Current plan

- [x] Add the deployable API and browser application without moving the pure engine.
- [x] Add a safe optional Supabase readiness connection and initial typed tables.
- [x] Document the prototype persistence exception and environment boundaries.
- [x] Verify Python tests, frontend checks, API endpoints, and the local web/API route.
- [x] Define the maintainer journey, Overview cockpit, Location planning, Data
  & settings, page states, KPI semantics, component map, and UX acceptance.
- [x] Map the four upload groups to current Python adapters and identify the
  source-import, PO-history, and netting-result schema gaps.
- [x] Add the deliberately minimal source-import/input/netting/daily-projection
  migration and a synthetic seed for UI development.
- [x] Implement the Auth boundary, schema-aware readiness, portable/Supabase
  repository, four import services, immutable persistence, synchronous run,
  atomic outputs, and UI read/download endpoints.
- [x] Apply migration 003 and configure Auth/API values to verify the backend
  against the real Supabase project.
- [x] Build Data & settings and the first Location planning slice.
- [ ] Apply migration 004 and verify one v2 planning persistence/read journey.
- [ ] Finish the v2 Location presentation, Overview, and then versioned
  master/menu editing in that dependency order.

## Key decisions (and why)

- 2026-08-28: Keep one repository with separate deployables under `apps/api`
  and `apps/web`; the engine stays under `src/supply_planning` so HTTP and UI
  concerns cannot leak into calculations.
- 2026-08-28: Use React + TypeScript + Vite + Tailwind for the internal UI and
  FastAPI for the thin HTTP boundary. The UI remains presentation-only.
- 2026-08-28: Supabase may temporarily store versioned master data and planning
  outputs during the prototype. The canonical output contract remains portable
  so Snowflake can replace the persistence adapter later.
- 2026-08-28: Browser code receives only Supabase publishable credentials.
  Elevated Supabase credentials stay in the Render API environment.
- 2026-08-28: Raw workbooks/PDFs are not persisted by this foundation. Future
  uploads use temporary processing unless a separately approved private-storage
  retention policy is added.
- 2026-08-28: Use exactly three primary side-navigation destinations:
  **Overview**, **Location planning**, and **Data & settings**. Settings and
  upload subsections do not become additional top-level pages.
- 2026-08-28: The default journey is exception-first: establish readiness on
  Overview, correct/import data in Data & settings, calculate/review one
  location, and return to an updated cockpit.
- 2026-08-28: Separate import from execution. Accepted uploads create visible,
  immutable normalized source versions; the run action references those
  versions and never carries a hidden second file set.
- 2026-08-28: Supabase Postgres holds normalized rows and metadata during the
  prototype, not XLSX/PDF bytes. A private object bucket is optional only after
  a retention decision.
- 2026-08-28: The cockpit uses actionable readiness/risk/current-run metrics.
  It does not aggregate mixed packs/cartons into one total or label cap evidence
  as actual waste.
- 2026-08-28: Keep the workflow schema minimal: one `source_imports` record
  holds compact file/validation metadata; five normalized input tables and one
  netting-summary table support the first pages. Persist the engine's daily
  projection rows because they directly support risk explanation and the
  location stock timeline. Separate source-file, issue, PO-header, and KPI/
  materialized-summary tables remain deferred until real usage proves they are
  needed.
- 2026-08-28: Keep a small `supabase/seed.sql` with synthetic, proposal-labelled
  imports/master/run/risk rows so UI work has reproducible shapes before real
  uploads exist. Never seed those rows into production.
- 2026-08-29: Treat any valid Supabase project user as a maintainer for the
  private prototype. The browser uses Supabase only for Auth and sends the
  access token to FastAPI; domain tables remain denied to browser roles.
- 2026-08-29: Use server-only PostgREST behind `CanonicalStore`. Migration 003
  provides narrow atomic functions for imports, activation, and full planning
  result persistence plus immutable finalized-source/active-master guards.
- 2026-08-29: Raw uploads remain request-temporary and are deleted after
  parsing. Accepted normalized rows and audit metadata persist; no file bytes
  are stored in Postgres.

## What we learned (facts, not guesses)

- The local technical V1 and its typed input/output contracts are complete;
  the UI may start before maintainer approval, but proposal values must remain
  visibly labelled.
- `run_template_v1` already orchestrates the two templates, stock workbook,
  PDF directory, selected location, and deterministic cutoff.
- The repository had no API, web application, Supabase migrations, or Node
  workspace before this slice.
- A fresh Windows virtual environment needs the declared `tzdata` package for
  `ZoneInfo("Europe/Berlin")`; the existing test suite exposed this immediately.
- The real local processes served the page with HTTP 200, returned API
  `health=ok`, reported the expected unconfigured Supabase state, and routed
  `/api/v1/readiness` successfully through the Vite proxy.
- Final verification passed 48 Python tests, focused Ruff/mypy checks for the
  new API, `pip check`, frontend lint/type/build, and frontend peer checks.
- The four UI upload groups map to existing integration points: the two fixed
  workbook loaders, Apicbase stock normalizer, and Transgourmet PDF
  parser/normalizer. `run_template_v1` is the complete local orchestration
  reference but currently combines import and execution.
- The foundation migration already covers versioned item/location/rule data and
  run/line/recommendation/exception outputs. It does not cover normalized
  forecast/menu/BOM/stock/PO versions, import issues, PO document history, or
  persisted `NettingResult` summaries/daily projections.
- The engine already exposes `first_stockout_date`, projected balances, overdue
  open PO quantity, and unavoidable pre-arrival shortage in `NettingResult`.
  Persisting those typed outputs is preferable to recreating risk in SQL or
  TypeScript.
- The additive `202608280002_ui_workflow_inputs.sql` migration now materializes
  the minimum source, `NettingResult` summary, and daily-projection shapes.
  Static tests verify table/seed column references, RLS/revokes, and run/import
  traceability; the local machine does not currently have Supabase CLI,
  PostgreSQL, or Docker for a real `db reset`.
- The maintainer applied all three migrations manually in the Supabase SQL
  Editor. On 2026-08-29 the configured server boundary verified all 18 required
  tables and all four transaction RPCs with no missing paths.
- Final schema-slice verification passed the full 52-test Python suite plus
  focused Ruff and mypy checks for `tests/test_supabase_schema.py`.
- The backend vertical slice now exposes authenticated identity, imports,
  locations/readiness, inventory, observed PO history, master activation,
  planning run/result/risk, Overview, and CSV/JSON endpoints. The complete
  calculation output, including daily projections, is persisted by one RPC.
- Backend verification now passes all 83 Python tests plus focused Ruff and
  strict mypy on the changed v2 engine/API boundary. OpenAPI generation
  confirms every expected `/api/v1` route.
- Root server credentials and an admin-created Auth user are configured for the
  development project. Claude verified the authenticated browser -> FastAPI
  journey; Codex independently verified the full live schema contract.
- A synthetic connected-workflow packet now exists under
  `outputs/01a043ce-e551-7492-b41a-bee3c09a1d99/ui_test_packet/`, with the PO
  PDF under `output/pdf/ui_test_packet/`. The existing adapters accept all four
  sources, and a deterministic scenario replay at
  `2026-08-29T12:00:00+02:00` completes with one 6-pack proposal.
- The packet exposed a valid-XLSX compatibility edge: some producers omit
  optional worksheet dimension metadata, leaving `max_row=None` in openpyxl
  read-only mode. Both the Apicbase adapter and the API's post-validation audit
  row reader now iterate populated rows instead of relying on that optional
  metadata. The first browser upload exposed the second occurrence after the
  authoritative template validation had already passed.
- Unexpected API exceptions are converted to a sanitized `internal_error`
  response inside the configured CORS boundary. This prevents browsers from
  masking a server failure as a misleading CORS rejection while keeping stack
  traces and upstream details out of planner-facing responses.
- The first connected master workbook upload and explicit activation succeeded.
  Its UX exposed that activation is easy to miss when available only in the
  lower version-history section; the frontend handover now requires an inline
  **Activate master data and continue** action in Step 1.
- The next connected planning-workbook upload exposed that Excel date cells may
  reach the API audit-row reader as midnight `datetime` values. Date-only
  canonical fields now normalize that representation before joining parsed and
  source rows; the exact demo packet reaches persistence preparation with 42
  forecast rows, 42 menu rows, and one BOM row.
- The corrected Overview read model now keeps actionable-horizon semantics and
  returns location metadata, source freshness, current-run status, earliest
  actionable risk, and `locations_at_risk` without a browser-side N+1 status
  request.

## Open questions / unknowns

- Whether production should replace prototype admin-created email/password
  accounts and the any-authenticated-user maintainer policy with SSO/role tiers.
- What retention period, if any, is approved for uploaded source files?
- Will production master data ultimately remain in Supabase or move to
  Snowflake with the results?
- Which Render and Vercel projects/domains will be used for preview and
  production environments?
- What are the approved freshness thresholds for stock, forecast/menu horizon,
  and the PO source, and may a maintainer override a warning?
- Do all maintainers have the same rights to import, edit drafts, and activate
  versions?
- Which language and item/order-unit labels should the first UI use?
- Can every Transgourmet document be assigned to one location from source
  evidence, or must upload location remain an explicit maintained choice?

## Next steps

- Use the synthetic packet for the first manual upload/activation/import/run/
  read journey in the approved development project. Its README records the
  strict upload sequence, safe cutoff, and expected result.
- Verify deployed Render/Vercel CORS and the persisted UI journey once both
  deployments, rather than the local Vite/FastAPI pair, are in use.
- Turn `ui_maintainer_journey_and_page_plan.md` into low-fidelity designer
  wireframes and validate hierarchy/terminology with the maintainer.
- Hand `docs/claude_code_first_ui_pages_brief.md` to the frontend implementer;
  it now excludes backend work and points to the implemented OpenAPI contract.
- Build the three-route shell and Data & settings UI first, then Location
  planning and Overview against persisted backend responses.
- 2026-08-29: the frontend implementer picked this up. Frontend planning,
  findings, decisions and work packages now live in
  `docs/plans/ui_implementation_backlog.md` and
  `docs/scratchpads/ui_implementation.md`. Keep this scratchpad for the
  backend/Supabase/deployment foundation; do not duplicate frontend notes here.

## Risks / gotchas (things not to forget)

- Never expose `SUPABASE_SECRET_KEY` to Vite or commit it.
- Keep all calculations and business validation in Python; do not duplicate
  recommendation logic in React.
- Do not label scenario/demo recommendations as operational before the
  maintainer gate passes.
- Render local files are temporary; database or private object storage is
  required for intentionally retained data.
- The in-app visual browser check could not initialize because the installed
  Browser plugin requested a missing newer `browser-service.mjs` runtime. Build,
  live HTTP, Vite-proxy, and API checks passed; repeat interactive visual QA
  after the Codex Browser plugin/runtime versions align.
- Supplier dispatch, ERP writes, approval workflow, and complex calendars stay
  outside scope.

## Commands / environment notes

- Python verification: `scripts/check.ps1 -PythonExecutable <python>`.
- API development: `uvicorn apps.api.supply_planning_api.main:app --reload`.
- UI development: run `pnpm dev` from `apps/web`.
- Frontend verification: run `pnpm check` from `apps/web`.
- Focused API quality checks cover `apps/api/supply_planning_api`, the touched
  engine adapter/orchestrator files, and the backend/schema test modules.

## 2026-08-30 actionable-risk/MHD v2 follow-up

- A fourth additive migration now exists:
  `202608300004_actionable_risk_and_shelf_life.sql`.
- It adds explicit item risk-window and candidate expiry/cap/residual fields plus
  `persist_planning_run_v2`; it does not replace or delete any table.
- Migrations 001–003 remain applied. Migration 004 must be run manually in the
  Supabase SQL Editor before the next connected v2 planning run.
- The API readiness probe now requires the v2 RPC, so a missing migration is
  visible instead of failing only during persistence.
