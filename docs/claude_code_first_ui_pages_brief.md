# Claude Code brief — first connected maintainer UI

Copy the instruction below into Claude Code from the repository root.

---

You are working in the `demand_forcasting` repository. Build the first
**connected, testable vertical slice** of the internal Phase 2 supply-planning
application. This is no longer a presentation-only UI task.

The local template-driven planning-engine V1 is complete and tested. The
React/FastAPI monorepo foundation and Supabase table definitions also exist.
Assume the maintainer has manually applied both SQL files through the Supabase
SQL Editor:

- `supabase/migrations/202608280001_ui_foundation.sql`
- `supabase/migrations/202608280002_ui_workflow_inputs.sql`

Do not rerun, rewrite, drop, or replace those applied migrations. If an
additional database function or schema correction is genuinely required, add a
new forward-only `003` migration that is safe to paste into the Supabase SQL
Editor. Never delete live tables or data merely to make development easier.

## Read before editing

Read these files in order and treat them as one coherent handover:

1. `AGENTS.md` — mandatory boundaries, safety rules, documentation, and checks.
2. `MEMORY.md` — durable decisions and the difference between the completed
   calculation V1 and the unfinished application integration.
3. `docs/descriptions/ui_maintainer_journey_and_page_plan.md` — primary product
   and UX specification: maintainer journey, three pages, KPIs, states,
   component map, API surface, schema mapping, and acceptance criteria.
4. `docs/descriptions/ui_api_and_persistence_foundation.md` — monorepo,
   FastAPI/React boundary, Supabase security, environments, and deployment.
5. `docs/plans/phase2_supply_planning_master_backlog.md` — implementation order;
   work through the smallest coherent parts of Milestone 2B-2F.
6. `docs/scratchpads/ui_and_supabase_foundation.md` — current facts, decisions,
   risks, and known gaps. It is supporting context, not an authoritative spec.
7. `apps/api/supply_planning_api/` and `tests/test_api_foundation.py` — current
   API only has health/readiness; there are no domain repositories or routes.
8. `apps/web/src/`, `apps/web/package.json`, and `apps/web/.env.example` — current
   React/Tailwind status shell and browser-safe Supabase Auth configuration.
9. The two migrations above and `supabase/seed.sql` — exact persistence shapes.
   The seed is synthetic and must not be applied to a real/production project.
10. Existing Python integration points; reuse them rather than duplicating them:
    - `src/supply_planning/application/run_template_v1.py`
    - `src/supply_planning/application/run_improved.py`
    - `src/supply_planning/adapters/template_xlsx.py`
    - `src/supply_planning/adapters/apicbase_stock_xlsx.py`
    - `src/supply_planning/adapters/transgourmet_pdf.py`
    - `src/supply_planning/adapters/transgourmet_v1.py`
    - `src/supply_planning/engine/netting.py`

Inspect the current repository and working tree before assuming this brief is
perfectly current. Preserve unrelated user changes.

## Current state you must not misrepresent

- The planning calculation works locally from the four maintained input groups.
- The engine already returns recommendations, exceptions, netting summaries,
  and daily inventory projections.
- Supabase tables are assumed applied, with RLS enabled and browser roles denied.
- FastAPI currently only exposes `/`, `/api/v1/health`, and
  `/api/v1/readiness`. It does not yet persist or read domain data.
- React currently does not provide the three domain pages or working imports,
  planning runs, or result views.
- Therefore the schema is **not yet connected to the application**. Implement
  that connection before claiming that the real workflow is testable.

## Goal and user journey

Deliver this honest end-to-end maintainer journey:

1. An authenticated maintainer opens **Overview** and sees readiness, freshness,
   current risks, and the latest persisted run—not hard-coded operational data.
2. In **Data & settings**, the maintainer uploads and validates the four current
   source groups:
   - master-data workbook;
   - forecast/menu/BOM planning workbook;
   - selected-location Apicbase stock XLSX; and
   - selected-location cumulative Transgourmet PDFs.
3. Accepted imports become immutable visible versions in Supabase. Uploading a
   file must not silently execute planning.
4. In **Location planning**, the maintainer sees the exact selected source
   versions and readiness, then starts one synchronous planning run.
5. Python assembles the accepted versions, calls the existing pure engine, and
   persists the run, inputs, derivations, recommendations, exceptions, netting
   summaries, and daily projections.
6. The location results survive a page refresh, can be explained, and can be
   downloaded as canonical CSV/JSON.
7. **Overview** reflects the latest current persisted run. If a newer accepted
   input exists, the older run is labelled stale rather than silently treated
   as current.

The first implementation may remain proposal/shadow-oriented. It must never
imply that a supplier order was placed.

## Implementation order

### 1. Verify configuration and applied schema safely

- Never print or return secret values.
- Use `SUPABASE_URL` and `SUPABASE_SECRET_KEY` only in FastAPI/Render.
- Use `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` only for browser
  authentication. Never put the server secret in Vite.
- Strengthen the server readiness/schema probe so it verifies at least one
  foundation table and the expected `source_imports` and
  `planning_projection_days` relations.
- If configured credentials or expected tables are unavailable, keep domain
  actions disabled and report the exact non-secret blocker. Do not fall back to
  pretending an upload or run succeeded.

### 2. Add the authenticated API boundary

- Require a valid Supabase user access token for every domain endpoint; keep
  health/readiness public.
- Keep authorization isolated behind a small dependency/protocol so roles can
  be refined later. For this private prototype, do not invent a complex role
  hierarchy: a valid authenticated project user may be treated as a maintainer,
  but document that temporary policy and test rejection of missing/invalid
  tokens.
- React should use the existing Supabase browser client for Auth only and send
  the access token to FastAPI. React must not query or mutate domain tables
  directly.

### 3. Implement portable repositories and application services

- Define small repository protocols at the application boundary and a Supabase
  implementation behind them. Keep `src/supply_planning` independent from
  HTTP, Supabase, React, and deployment concerns.
- Reuse the existing `httpx` boundary unless another dependency is materially
  justified. Do not add the Supabase Python SDK merely as a thin wrapper.
- Map typed Python records to the existing tables without changing calculation
  semantics or recomputing risk in SQL/TypeScript.
- Separate import, assemble, calculate, and persist concerns from the current
  combined `run_template_v1` orchestration while preserving that local CLI path
  as a tested recovery/fixture workflow.
- Persist one run and all of its inputs/results atomically. If REST calls cannot
  provide a real transaction, add one narrow SQL RPC in a new `003` migration;
  do not call several writes “atomic” when they are not. Preserve deterministic
  `run_id` retry behavior.

### 4. Implement the smallest API surface that supports the journey

Follow the response concepts in section 9 of the UI journey document. At
minimum implement and test:

- `GET /api/v1/me`
- `GET /api/v1/locations`
- `GET /api/v1/overview`
- `GET /api/v1/locations/{location_id}/planning-status`
- `GET /api/v1/locations/{location_id}/inventory`
- `GET /api/v1/locations/{location_id}/purchase-orders`
- `GET /api/v1/imports` and `GET /api/v1/imports/{import_id}`
- `POST /api/v1/imports/master-data`
- `POST /api/v1/imports/planning-input`
- `POST /api/v1/imports/stock`
- `POST /api/v1/imports/purchase-orders`
- the minimal validate/activate action needed for a master-data draft;
- `POST /api/v1/planning-runs`
- `GET /api/v1/planning-runs/{run_id}`
- server-generated recommendation CSV and JSON downloads.

Upload endpoints must use the existing Python parsers. Add explicit file
type/size/count limits, selected-location validation where required, isolated
request-scoped temporary directories, cleanup on success and failure,
content-hash deduplication, and planner-friendly errors without stack traces.
Do not store raw XLSX/PDF bytes in Postgres. Do not make Render's temporary
filesystem a durable store.

Keep imports separate from execution. A run must reference the visible accepted
import IDs and active master version it actually used.

### 5. Build and connect the React pages

- Add a responsive application shell with persistent desktop side navigation
  and a small-screen drawer.
- Add routes:
  - `/overview` — **Overview**
  - `/locations/:locationId` — **Location planning**
  - `/data` — **Data & settings**
- Preserve compact API/Supabase readiness and visible proposal/demo warnings.
- Add a typed API client and small page-focused hooks. Avoid a large state
  framework or generic design-system project.
- Use the information hierarchy and components in sections 5-7 and 11 of
  `ui_maintainer_journey_and_page_plan.md`:
  - Overview: readiness alert, five KPI cards, location-risk table, freshness,
    latest-run activity, and secondary observed PO activity.
  - Location planning: selector/header, selected inputs, readiness/preflight,
    Risk & stock, Open POs, Recommendation views, run states, daily projection
    detail/chart where useful, explanation drawer, and CSV/JSON actions.
  - Data & settings: Planning inputs and Maintained data & rules, four upload
    cards, versions/freshness, validation issues, and explicit re-upload versus
    edit/activate behavior.
- Implement loading, empty, warning, blocked, unauthorized, stale, and error
  states. Unsupported actions stay disabled with a visible reason.
- If a typed demo adapter remains for visual development, connected mode must
  never silently fall back to it. Demo data must be visibly labelled and kept
  separate from API responses.

## Non-negotiable boundaries

- Do not redesign the planning algorithm or create a second calculation path.
- Do not parse XLSX/PDF or calculate recommendations in TypeScript.
- Do not allow the browser to query Supabase domain tables directly.
- Do not expose the Supabase server secret or log file contents/tokens.
- Keep observed POs separate from calculated recommendations.
- Keep stable IDs, grams, pack/carton units, timestamps, provenance, source
  versions, proposal status, and exception codes explicit.
- Do not label potential overstock/cap evidence as actual waste.
- Do not add approval, comments, assignment, supplier-send, ERP write, or order-
  placement workflows.
- Do not store raw customer files, extracted PDFs, credentials, or production
  rows in git, fixtures, documentation, or screenshots.
- Preserve the future Snowflake cutover through repository interfaces; do not
  fork the engine or browser contract for Supabase.

## Verification

- Add unit tests for auth dependencies, repository mapping, import services,
  run persistence, latest-current/stale selection, and API response/error
  contracts.
- Use dependency-injected fake repositories for fast tests and add a live
  Supabase smoke test only when a development project and safe test account/data
  are explicitly configured. Do not seed or delete production data.
- Run:
  - `scripts/check.ps1 -PythonExecutable <python>` from the repository root;
  - focused Ruff and mypy checks for all new Python/API files; and
  - `pnpm check` from `apps/web`.
- Exercise the complete browser journey locally or in the configured preview:
  authenticate, upload safe test inputs, inspect validation/version metadata,
  run one location, refresh, reopen the persisted result, verify Overview, and
  download CSV/JSON.
- Verify responsive navigation, keyboard/focus/error handling, and all honest
  unavailable states.
- Update the relevant Milestone 2 backlog checkboxes, UI scratchpad, repository
  memory, README/environment examples, and API documentation with exactly what
  is implemented and what remains unavailable.

## Definition of done

Do not stop after creating attractive static pages. The slice is done only when:

- an authenticated UI action reaches FastAPI;
- FastAPI uses the existing Python adapters/engine;
- accepted imports and a completed/blocked run are persisted in Supabase;
- recommendations, exceptions, netting summaries, and daily projections can be
  read back after a refresh;
- the location and Overview pages render those persisted records;
- unavailable or unapproved behavior remains explicitly labelled; and
- all applicable checks pass.

If live credentials, Auth configuration, or the expected applied tables are
missing, implement and test the portable code with fakes, leave unsafe actions
disabled, and report the exact external configuration blocker. Never claim the
live workflow passed unless it was actually exercised end to end.

---
