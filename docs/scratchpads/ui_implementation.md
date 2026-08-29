# UI implementation scratchpad (three connected maintainer pages)

> Working notes for the frontend slice defined in
> `docs/claude_code_first_ui_pages_brief.md`. Companion to
> `docs/scratchpads/ui_and_supabase_foundation.md` (which covers the backend/
> Supabase/deployment foundation). Authoritative product behavior stays in
> `docs/descriptions/ui_maintainer_journey_and_page_plan.md`; the ordered work
> packages live in `docs/plans/ui_implementation_backlog.md`.
>
> Update this file after every meaningful decision or finding so context
> survives across chats and compaction.

## Goal

Build the connected React/Tailwind maintainer workspace — `/overview`,
`/locations/:locationId`, `/data` — against the implemented FastAPI contract,
without duplicating any Python parsing, planning, or KPI logic in TypeScript.

## Status

- Branch: `ui_implementation`.
- 2026-08-29: **WP0 and WP1 complete and verified.** `pnpm check` green — lint,
  typecheck, 55 tests, production build. The application shell, sign-in gate,
  navigation, and the typed API/error/formatting library are in place. Verified
  in a real browser against the live API: sign-in renders, the gate blocks
  `/data` when signed out, mobile holds at 375 px, no console errors, and the
  status line reports `API ready · development` with all migrations reachable.
- 2026-08-29: **The full authenticated chain is verified end to end.** The
  maintainer signed in with a real admin-created Supabase account in a live
  browser. Observed on the wire: CORS preflight `OPTIONS /api/v1/locations` →
  200, then `GET /api/v1/locations` → **404**, and the UI rendered the
  "No active master data yet" first-run state with its link to Data & settings —
  not an error page. That exercises Supabase Auth → persisted session → bearer
  token → FastAPI verification → domain read → typed error → first-run state.
- React StrictMode double-mounts effects in dev, so the browser network log
  shows paired `readiness` requests where the first is `ERR_ABORTED`. That is
  the abort handling in `useApiResource` working, not a fault; StrictMode does
  not double-invoke in production builds.
- Next: WP3 — Data & settings. It must come first, because on this environment
  nothing else can load until a master workbook is imported and activated (see
  the environment-scoping gotcha below).

## What we learned (facts verified in this repo, not guesses)

### Frontend starting point

- `apps/web` is a Vite 8 + React 19.2 + TypeScript 5.9 + Tailwind v4 app with
  `node_modules` installed and a prior successful build in `dist/`.
- It contains exactly four source files of substance: `App.tsx` (connection
  status shell), `components/StatusCard.tsx`, `lib/api.ts` (readiness fetch
  only), `lib/supabase.ts` (lazy Auth client, `browserSupabaseConfigured`).
- **There is no router and no test runner.** `package.json` has no
  `react-router`, no `vitest`, no Testing Library. `pnpm check` =
  `lint && typecheck && build` only.
- Tailwind v4 is configured through `@tailwindcss/vite`; theme tokens live in
  `src/styles.css` under `@theme`. There is no `tailwind.config.js`.
- `vite.config.ts` proxies `/api` to `http://localhost:8000` in dev, so a
  local run works with `VITE_API_BASE_URL` empty.
- Existing visual language: `stone-950` dark hero, `lime-300` accent,
  `rounded-[2rem]`, `stone-100` page background. Marketing-weight, not a dense
  operational workspace.
- `tsconfig.app.json` is strict with `noUnusedLocals`/`noUnusedParameters` and
  `"include": ["src"]` — test files under `src` are covered; a separate
  include or config is needed if tests live outside `src`.

### API contract (read from source, not assumed)

- Error envelope is `{ error: { code, message, details } }` from both the
  `ApiError` handler and the `HTTPException` handler in `main.py`. FastAPI
  request-validation (422) still returns its own `detail` array shape, so the
  client must handle **both**.
- Typed error codes exist: `persistence_unavailable` (503), `not_found` (404),
  `validation_failed` (422), plus conflicts (409) such as
  `production_mode_disabled`, `master_source_missing`,
  `master_source_not_accepted`.
- `GET /api/v1/readiness` is public and returns
  `{status: ready|degraded, service, version, environment, supabase:{status,message}}`
  where `supabase.status` is `ready | not_configured | unavailable`.
- `GET /api/v1/me` returns `{user_id, email, role:"maintainer"}`.
- `GET /api/v1/locations` returns
  `{master_data_version_id, locations:[{location_id, location_name, timezone, active}]}`
  and **only active locations**. This is the sole source of `location_name` and
  `timezone` for display.
- `GET /api/v1/locations/{id}/planning-status` returns
  `{location_id, ready, blockers:[{code,message}], sources:{master_data_version,
  planning_input, stock, purchase_orders}, latest_run, latest_run_is_current,
  proposal_only}`. Each `sources.*` value is a full `source_imports` row (or
  the master version row), so all freshness timestamps, coverage dates, record
  counts and validation issues come from here.
- Blocker codes emitted today: `master_missing`, `planning_input_missing`,
  `stock_missing`, `purchase_orders_missing`.
- `GET /api/v1/overview` returns
  `{as_of_date, kpis:{locations_ready, locations_total, items_at_risk,
  recommendations_due, blocking_issues, open_purchase_order_lines},
  latest_run_at, locations:[{location_id, ready, items_at_risk, latest_run,
  latest_run_is_current, blockers}], proposal_only}`.
- `GET /api/v1/planning-runs/{run_id}` returns the **entire** run:
  `{run, summary:{recommendation_count, issue_count, blocker_count,
  items_at_risk}, inputs, planning_lines, recommendations, exceptions,
  netting_results, projection_days, proposal_only}`.
- `POST /api/v1/planning-runs` body is
  `{location_id, planning_as_of_at (tz-aware, required), run_mode:"scenario",
  master_data_version_id?, planning_input_import_id?, stock_import_id?,
  purchase_orders_import_id?}` and returns the same full run payload.
  `run_mode:"production"` is rejected with 409 `production_mode_disabled`.
- Import responses are `source_imports` rows: `id, dataset_type, location_id,
  status, source_version, source_as_of_at, coverage_start_date,
  coverage_end_date, file_names, file_count, total_bytes, content_hash,
  parser_version, record_count, warning_count, error_count, validation_issues,
  metadata, supersedes_import_id, created_at, created_by`.
  `status` is one of `received|validating|accepted|accepted_with_warnings|rejected`.
- `validation_issues` entries are `{code, severity, dataset, record_ref,
  message, remedy}` — `remedy` is present, so every issue can render an action.
- Multipart field names: `file` (master, planning-input, stock),
  `files` (purchase-orders); plus `location_id` form field for stock and POs,
  and `as_of_at` (tz-aware datetime) for POs.
- Master versions: `GET /api/v1/master-data/versions` (filtered to the API's
  `APP_ENV` environment, newest first) and
  `POST /api/v1/master-data/versions/{version_id}/activate`.
- Table shapes the UI renders directly come from migration 002 and are known:
  `inventory_snapshots` (+ API adds `item_name`, `pack_size_g`),
  `purchase_order_lines` (`derived_status` is `open|closed|undated`,
  `mapping_status` is `mapped|unmapped|description_mismatch|ambiguous`),
  `planning_netting_results`, `planning_projection_days`, `planning_lines`.
- The derivation drawer has every field it needs on `planning_lines`:
  `gross_requirement_g, yield_factor(+provenance), adjusted_requirement_g,
  safety_stock_g(+provenance), usable_on_hand_g, open_po_due_g, raw_order_g,
  shelf_life_cap_g, max_cover_cap_g, capped_order_g, order_unit_size_g,
  moq_order_units, case_multiple_order_units, proposed_order_units,
  rounding_delta_g, protection_days, coverage_start/end_date, data_status`.

### Contract gaps and sharp edges found while reading

1. **`/overview` cannot render the data-freshness panel or location names.**
   Its `locations[]` rows have no `location_name`, no `sources`, and no
   earliest-risk date. Journey doc §5.2 items 3–4 require stock `counted_at`,
   PO import time, forecast-through date, active master version, and earliest
   risk date per location. Workaround for this slice: `GET /locations` plus one
   `GET /locations/{id}/planning-status` per location (N is small). Logged as a
   proposed contract enhancement for Codex, not a blocker.
2. **`/inventory` and `/purchase-orders` return 404 when no accepted import
   exists** (`NotFoundError`). The UI must render that specific 404 as an
   actionable "no accepted stock/PO import yet → upload one" empty state, never
   as a generic error. `planning-status` is the reliable existence check.
3. **CSV/JSON downloads need the `Authorization` header**, so a plain
   `<a href>` cannot be used. They must be authenticated `fetch` → `Blob` →
   `URL.createObjectURL` → programmatic click → revoke.
4. **The run is synchronous and unbounded in duration.** No job id, no polling
   endpoint. The client needs a long/absent timeout, an explicit
   "this can take a while, keep the tab open" state, and hard duplicate-submit
   prevention (the backlog item for deterministic `run_id` idempotency is still
   unchecked upstream).
5. **The run response includes every `projection_days` row** (items x horizon
   days). Potentially large. Render lazily (chart only inside the opened item
   drawer); do not build a page-level chart over all items.
6. `overview.kpis.items_at_risk` and `recommendations_due` are only counted
   when `latest_run_is_current` is true, which matches the "stale calculation"
   rule — the UI must not recompute or fill these in.
7. `GET /locations` returns only `active` locations; an inactive location
   reachable by URL will 404 from the location lookup. Handle that route case.
8. `planning_runs.status` is `started|completed|blocked|failed`; `blocked` and
   `failed` arrive as a persisted run, not as an HTTP error.

### Environment / deployment reality — VERIFIED LIVE 2026-08-29

The repo docs said migration 003 and cloud configuration were unverified. The
maintainer corrected this, and a live local probe confirmed the correction:

- Root `.env` has `APP_ENV`, `CORS_ORIGINS`, `SUPABASE_URL`,
  `SUPABASE_SECRET_KEY` all set. `apps/web/.env.local` has all three
  `VITE_*` values set. Both files are gitignored (`.env`, `.env.*`).
- Ran `uvicorn apps.api.supply_planning_api.main:app` on port 8011 and probed:
  - `GET /api/v1/health` → `200 {"status":"ok", ..., "environment":"development"}`
  - `GET /api/v1/readiness` → `200 {"status":"ready", "supabase":
    {"status":"ready","message":"Supabase REST and all required backend
    migrations are reachable."}}`
- The readiness probe verifies the required tables **and** the migration-003
  transaction RPCs, so **migration 003 is applied**. Connected mode works today.
- Auth boundary confirmed: unauthenticated and bad-token domain requests both
  return `401 {"error":{"code":"invalid_session","message":"Sign in again
  before using the planning application.","details":{}}}`.
- Consequence: **no preview/demo mode is needed or wanted** (D4 dropped). The
  UI is built and reviewed against the real API from the start.

### The environment-scoping gotcha (affects the very first screen)

- `APP_ENV=development`, but `supabase/seed.sql` inserts its master version with
  `environment = 'prototype'`.
- `_load_master()` filters `master_data_versions` by
  `environment = eq.{app_environment}` and `status = eq.active`
  (`services.py:1024-1035`). `import_master_data` writes
  `environment: app_environment` (`services.py:572`), and
  `list_master_versions` filters the same way (`services.py:991`).
- Therefore **the synthetic seed is invisible to the API in `development`**, and
  on a fresh environment `GET /locations` raises
  `NotFoundError("Active master-data version", "development")` → **404, not an
  empty list**. `GET /overview` fails the same way, since it calls
  `list_locations()` first.
- Two consequences for the UI:
  1. A dedicated **first-run state** is required: a 404 from `/locations` means
     "no active master version in this environment yet → upload the master
     workbook", not "something broke". This is a distinct state from empty and
     from unavailable.
  2. It confirms the data-first build order (D7): nothing works until a master
     workbook is imported **and activated** in this environment. Data &
     settings is genuinely the first buildable page.
- To see the seed data instead, `APP_ENV` would have to be `prototype`. Not
  recommended — importing the real master workbook is the intended path and
  exercises the real code.

## Key decisions (proposed 2026-08-29 — pending maintainer review)

See `docs/plans/ui_implementation_backlog.md` section "Decisions to confirm"
for the full rationale and alternatives. Summary:

- D1: add `react-router-dom` v7 for the three URL-shaped routes. *(pending)*
- D2: **CONFIRMED 2026-08-29.** No server-cache library. Hand-written
  `useApiResource` hook + explicit refetch. Rationale: freshness honesty is the
  product's core message and a silent cache fights it; the journey doc asks for
  small page-focused hooks.
- D3: add `vitest` + `@testing-library/react` + `jsdom` + `user-event` as
  devDependencies; add `pnpm test` and fold it into `pnpm check`. *(pending)*
- D4: **DROPPED 2026-08-29.** A preview/fixture mode was proposed only because
  the repo docs said migration 003 and cloud config were unverified. Both are in
  fact live (see the verified section above), so bypassing a working backend
  would add risk for no benefit. The UI is built against the real API only.
- D5: **CONFIRMED 2026-08-29.** Keep the stone/lime brand identity but retune to
  a dense workspace scale (`rounded-xl`, tighter type, lime reserved for primary
  action + active nav, strict semantic status palette with icon + text).
- D6: English UI labels; German source terms preserved verbatim where they name
  a source artifact (`Liefertag`, `Bestelldetails`, `Frisch`/`TK`/`Kühl`/`RT`).
  *(pending)*
- D7: **CONFIRMED by evidence 2026-08-29.** Build order follows journey doc §13
  — shell → Data & settings → Location planning → Overview. The environment
  scoping gotcha above makes this a hard dependency, not a preference.
- D8: **CONFIRMED 2026-08-29.** 6–15 locations expected, so the location
  selector is a plain dropdown `<select>`-style control showing each location's
  readiness badge per option. No search combobox, no segmented control.

## Open questions for the maintainer

- Confirm D1, D3 and D6 (the two dependency additions and the label language).
- Language: English-only labels confirmed, or bilingual?
- Are approved freshness thresholds available yet? Until they are, the UI shows
  raw ages and the server's readiness verdict only, and invents no thresholds.
- Should the run button offer a `planning_as_of_at` override, or always use
  "now" in the location timezone? Default proposal: "now", with an advanced
  disclosure for an explicit cutoff.
- Is there a safe test Auth user (admin-created email/password) that can be used
  for connected smoke testing, and a master workbook safe to import into the
  `development` environment?

## Risks / gotchas (do not forget)

- Never send `SUPABASE_SECRET_KEY` to the browser; only `VITE_*` values.
- Never parse XLSX/PDF or recompute planning/KPI values in TypeScript.
- Never query Supabase domain tables from React — Auth only.
- Never replace an API error with synthetic data.
- Do not edit `src/supply_planning`, `apps/api`, `supabase/migrations`, or
  planning tests in this slice.
- Do not add approval, supplier-send, ERP, comments, assignment, or order
  placement anywhere in the UI.
- Every recommendation stays visibly proposal-only.
- Do not display actual waste, actual OOS, or mixed-unit total quantities.
- Do not claim live/connected success without evidence that migration 003,
  Auth, and credentials are present.

## RESOLVED BLOCKER — Node.js was missing (2026-08-29)

Resolved the same day: the maintainer installed Node 24.19.0 (npm 11.17.0,
corepack 0.35.0) via `winget`. Two follow-on facts worth keeping:

- **`corepack enable` needs administrator rights** and fails with
  `EPERM ... C:\Program Files\nodejs\yarn.ps1`, so there is no `pnpm` shim on
  PATH. `corepack pnpm <command>` works and is what this agent uses. The
  maintainer can get a plain `pnpm` by running `corepack enable` once in an
  elevated terminal.
- **A shell started before the install has a stale PATH.** Prefix commands with
  `export PATH="/c/Program Files/nodejs:$PATH"` until the session restarts.
- Because `check` previously re-invoked `pnpm lint` etc., it broke without the
  shim. It now chains `eslint . && tsc -b && vitest run && vite build` directly,
  which works under any package manager.

The original finding, kept for context:

## Original blocker — Node.js was not installed (found 2026-08-29)

Verified, not inferred:

- `node`, `npm`, `pnpm` and `corepack` are all absent from `PATH` (11 entries,
  none node-related). No `C:\Program Files\nodejs`, no `HKLM:\SOFTWARE\Node.js`
  registry entry, no `nvm`/`fnm`/`volta` directory, and no `node.exe` anywhere
  under the user profile.
- Yet `apps/web/node_modules` is populated and was last written
  **2026-08-28 08:54**, and `.pnpm-store/v11` exists at the repository root. So
  a toolchain was present yesterday and is not present now. `node_modules` is
  gitignored, so it was installed locally rather than synced.
- `winget` **is** available at
  `%LOCALAPPDATA%\Microsoft\WindowsApps\winget.exe`.

Consequences: cannot install `react-router-dom` or the Vitest toolchain, cannot
run `pnpm check`, `pnpm test`, or `pnpm dev`, and cannot type-check anything
written. Source files can still be authored; nothing can be verified.

Proposed fix (needs maintainer approval — this installs software, and Kandji
MDM is present on this machine):

```
winget install OpenJS.NodeJS.LTS
corepack enable
```

Then from `apps/web`: `pnpm install`, and the WP0 tooling steps can proceed.

## Commands

- UI dev: `pnpm dev` from `apps/web` (proxies `/api` to localhost:8000).
- UI checks: `pnpm check` from `apps/web`.
- API dev: `uvicorn apps.api.supply_planning_api.main:app --reload` from root.
- Python checks: `scripts/check.ps1 -PythonExecutable <python>`.

## Next steps

1. Maintainer reviews the plan in `docs/plans/ui_implementation_backlog.md`.
2. On approval, execute WP0 to WP6 in order, updating this scratchpad and the
   backlog checkboxes after each work package.
