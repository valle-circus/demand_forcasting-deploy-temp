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

### The four uploads are a strict sequence, not four independent cards

Read from `services.py` while starting WP3. The journey doc presents four
upload cards side by side, which describes the steady state; a fresh
environment has a hard order:

1. **Master workbook** (global) — no prerequisites. Creates a **draft**, never
   an active version.
2. **Activate the master version** — a separate, explicit action. Everything
   below fails until it happens.
3. **Planning workbook** (global) — calls `_load_master()`, then
   `_validate_planning_references` rejects any location or item not present and
   active in the master version (`services.py:738`).
4. **Stock** (per location) — needs the active master, the location within it,
   **and** an accepted planning workbook already covering that location, else
   `409 planning_input_missing` (`services.py:776`).
5. **Purchase orders** (per location) — needs the active master and the
   location within it; `as_of_at` must carry a timezone offset.

Design consequence: the cards are numbered and each computes its own
prerequisite state from what actually exists, showing the blocking reason and
pointing at the card that unblocks it. Four cards presented as equals would
strand a maintainer in a sequence of 409s on a fresh environment.

### How imports report their outcome

- **Rejected → `422 ValidationError`**, not a 201 with `status: "rejected"`.
  The rejected row *is* persisted and its id comes back in
  `details.import_id`, so the failure still appears in history.
- **Accepted with warnings → 201** with `status: "accepted_with_warnings"`
  (`_accepted_status` returns it whenever `warning_count > 0`).
- **Duplicate content hash → 201 returning the *existing* accepted row**
  (`_find_duplicate`, matched on dataset + hash + location). Re-uploading the
  same file is idempotent, so the UI must not report a fresh import when the
  response is actually an older record — compare the returned id against what
  was already known.

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

## WP3 progress note (2026-08-29)

Data & settings is built and verified against the live API. Design decisions
worth keeping:

- The four upload cards are **numbered steps**, because the API enforces an
  order (see "The four uploads are a strict sequence" above). Each card
  computes its own prerequisite and names the step that unblocks it, so the
  maintainer never discovers the order by collecting 409s.
- `UploadCard` owns its file state. An earlier split between page and card
  meant the upload button could never enable — worth remembering if the card is
  ever refactored to be controlled.
- Duplicate uploads are real: the API de-duplicates on content hash and returns
  the **existing** row with 201. The card compares the returned id against the
  ids it already knew and says "already imported" instead of claiming a new
  version.
- A rejection is a 422, and the rejected import is still persisted. The card
  shows its id so the attempt stays traceable in history.
- The page must render when `GET /locations` 404s, because this page is where
  that gets fixed. Only a non-404 failure renders an error.

Still to build: WP4 (Location planning) and WP5 (Overview).

## Design system adopted (2026-08-30)

The `circus-ui` skill was created after WP3 shipped, and reviewing WP3 against
it found real defects, not just taste:

- **Paragraphs above forms** — an explicit anti-pattern. Each of the four cards
  carried a purpose paragraph plus a footer sentence, on top of a two-paragraph
  page intro. Roughly 65% of that text is now gone or behind a disclosure.
- **The action was far from the file it acts on.** The upload button sat below
  the dropzone but above a tall "Currently in use" block. It is now directly
  under the dropzone, full width.
- **Emoji as iconography** (`⚑` in the proposal banner) — replaced with lucide.
- **ALL CAPS labels** ("CURRENTLY IN USE", "STEP 1") — sentence case now.
- **Wrong accent.** Lime was never the brand; the accent is emerald `#0B8459`,
  and it is a budget of roughly one element per screen.
- **16px base** — internal tools read at desk distance, so base is 14px with
  the root rem left at 16px so Tailwind's 4px spacing scale is unaffected.
- **No motion tokens and no reduced-motion block.** Both added.

Stack now matches the skill: shadcn/ui (Base UI primitives, Nova preset,
lucide icons, Geist), `motion` for transitions. Components are vendored under
`src/components/ui/` — we own and edit them, so the 40px touch-target floor was
applied by editing `button.tsx` rather than overriding at call sites.

Notes for later:

- `corepack enable` needs admin, so shims were installed to `~/.local/bin`
  instead; that directory must be on PATH for `pnpm` and the shadcn CLI.
- The `@` alias has to be declared in **both** `vite.config.ts` and
  `vitest.config.ts` — a separate vitest config does not inherit it.
- ESLint exempts `src/components/ui/**` from `react-refresh/only-export-components`;
  the vendored files export variants next to components by design.
- Base UI's `Button` warns if it renders a non-button. `EmptyState` uses a
  styled `Link` instead, which is also correct semantically since it navigates.

## Structural fix: activation completes step 1

Codex found this by doing the first real upload, and the maintainer hit it too:
activation lived only in the version list far below the upload cards, so the
first-run journey stalled after step 1 with no visible way forward.

Now: a draft shows **Draft ready** in the step 1 header and an
**Activate master data and continue** button inside the step 1 card. The
version list below is the audit and replacement surface, not the way to
continue. Blocked steps 2–4 render a **Go to step N** button that scrolls to
and focuses the step that unblocks them.

## WP4 done — Location planning (2026-08-30)

Verified live: signed in, computed a scenario run for `LOC_UI_DEMO_001` from
Codex's test packet, and read the result back. Real numbers throughout —
1 of 1 items runs out, first stockout 11 Sep, ends at -31 kg, one proposal of
7 order units from TRANSGOURMET, and the derivation drawer showing the full
chain with the engine's own rounding exception quoted underneath.

The proposal is 7 units, not the packet's documented 6. That is expected: the
run used "now" as the cutoff rather than the packet's
`2026-08-29T12:00:00+02:00`, and the README says a later cutoff legitimately
changes PO status, coverage and the recommendation. Use the exact cutoff if the
packet's oracle number needs reproducing.

Decisions worth keeping (fuller notes in
`apps/web/src/features/location-planning/NOTES.md`):

- **The drawer never recomputes.** Every value is a stored field, and "a cap
  bound" / "raised to the minimum" comes from `planning_exceptions`, never from
  a browser-side comparison. A test feeds a deliberately inconsistent line to
  hold that line.
- The projection chart is hand-drawn SVG rather than the charting stack: one
  series, no axes, no legend — only the zero crossing matters. Flagged as a
  deliberate deviation from the skill's stack, revisit if it grows.
- Tabs live in `?tab=`, so Overview can deep-link into a filtered view in WP5
  and a refresh keeps the view.
- Purchase orders load only when their tab is open; the run payload carries
  every item's every horizon day, so the chart renders one item's rows only.

Two defects found by verifying rather than by tests:

- While the last run was being fetched the page said "No result yet". On a slow
  load that could push someone into starting a second synchronous calculation.
  Loading, failed-to-load and genuinely-absent are now distinct.
- Raw ISO dates in the drawer footer.

Superseded on 2026-08-30: Codex has supplied the corrected backend contract.
WP5 and the Location horizon/MHD slice may continue after migration 004 is
applied; React must consume the explicit fields rather than recreate the
classification.

## Risk & stock rebuilt after maintainer review (2026-08-30)

Feedback, and what it exposed.

### The horizon was never stated — a real defect

The risk table read "in stock 2 kg, needed 42 kg, on order 2 kg" with no time
frame, and the numbers looked mutually inconsistent because **they answer
different windows**:

- `netting_results.gross_requirement_g` (42 kg) covers
  `projection_start_date -> projection_end_date`, the **whole projection**
  (30 Aug -> 11 Oct, 43 days in the demo run).
- `planning_lines.gross_requirement_g` (9 kg) covers
  `coverage_start_date -> coverage_end_date`, the **order coverage window**
  (10 protection days).
- `ending_projected_balance_g` (-31 kg) is the balance at the end of the
  projection **assuming only the one candidate receipt** this run proposes.

The table now states the window once above it, adds a "Lasts N days" column,
and moves the closing balance into the expanded detail with the assumption
spelled out. Verified against the live run before changing anything.

### Shelf life does not reduce what is needed

Asked directly, so recorded: `recommend.py:99-123` applies shelf life as
`capped = min(capped, shelf_life_cap_g)`. It limits **how much may be ordered
at once**, and never shrinks the requirement. Said in plain words in the
expanded row.

Follow-up correction after maintainer review: that sentence was technically
true but not sufficient. The old cap used gross adjusted demand through
expiry and does not subtract projected on-hand/other receipts competing for the
same demand. It therefore does **not** prove that the candidate will be consumed
before MHD. UI copy must stop at “policy cap recorded” until the backend returns
candidate residual-at-expiry evidence.

The same review found a contract mismatch: `first_stockout_date` spans the full
uploaded forecast, while `_netting_issues` scopes actionable stockout to the
planning-line coverage end. The current React helper and API/Overview summary
use the full-horizon field and therefore report the demo item at risk even
though shortage starts only after the current 10-day decision window. Tracked
in `docs/plans/planning_horizon_and_shelf_life_correction_plan.md`; do not fix it
by duplicating horizon comparisons in React. The v2 backend now persists
`actionable_risk_status` and `first_stockout_within_horizon_date`; those are the
frontend contract.

### The chart existed but was unreachable

It was inside a Sheet on the Risk & stock row, and the maintainer clicked a
Proposals row. Now the risk row expands in place with the chart inline. That is
also what they asked for, so the two converged.

Rebuilt on **Recharts** via shadcn `chart` rather than the earlier hand-drawn
SVG, since it now needs an axis, reference lines and a tooltip — at that point
it is a real chart and the `circus-ui` stack applies. Per `dataviz`: one series
so no legend box, status colour reserved for the zero line, and both the
stockout and the delivery markers stated in text as well as colour.

- solid red line at zero, labelled "Empty"
- dashed red vertical at `first_stockout_date`
- dotted blue verticals where `open_po_receipts_g > 0` (already on order)
- dotted green verticals where `candidate_receipts_g > 0` (proposed delivery)

### One ingredient view, not two

The maintainer asked for an additional tab listing every planned ingredient
with a per-ingredient stock chart. That is the same item set the Risk & stock
tab already covers — `netting_results` has one row per planned item — so it was
built into that tab instead of a fourth one. Flagged for confirmation.

### Not possible from persisted data

"A bit into the past" for context. `planning_projection_days` starts at the run
date; no historical daily balance is stored. `inventory_snapshots` gives sparse
per-import counts, which would be misleading if drawn as one series with a
projection. Logged as a contract observation rather than faked.

### On order now shows weight

`open_qty_units` counts **packs**, and `netting.py:245` converts with
`open_qty_units * pack_size_g`. The tab applies the same pack size from the
stock snapshot, so the weight on screen matches what netting used — confirmed
against the demo run's `open_po_due_g` of 2000 g.

### Process note

An `apps/web/src/features/location-planning/NOTES.md` was created and then
removed. `AGENTS.md` already designates `docs/scratchpads/` for cross-session
notes and `docs/descriptions/` for behaviour — a new location beside the code
fragments that. Keep frontend notes here.

## Backend horizon/MHD correction completed (2026-08-30)

- Engine policy version is now
  `template-recommendation-v2-2026-08-30`; the changed policy produces a new
  deterministic run id instead of returning an old idempotent result.
- Candidate sizing floors unmet pre-arrival demand out of the controllable
  stock position. A later proposal cannot repair an earlier missed service.
- Shelf-life and max-cover caps simulate a tagged candidate while consuming
  projected on-hand, accepted POs, and earlier planned receipts first.
- Pack/MOQ rounding cannot exceed a hard cap. The engine either uses the
  largest safe purchasable multiple or returns
  `no_safe_positive_order` plus `INFEASIBLE_ORDER_CONSTRAINTS`.
- Netting persists `at_risk`, `covered`, or `not_evaluated` for the active
  item-specific horizon. Full-forecast first shortage remains separate.
- Planning lines persist expiry, cap basis, forecast completeness, projected
  candidate residual, max-cover end, binding constraint, constraint status,
  and rounding direction.
- Exact UI packet replay `improved-ded5498f7198`: 6 packs; covered through
  2026-09-07; first full-forecast shortage 2026-09-10; 2 kg balance at the
  action horizon; expiry 2026-09-30; residual 0; shelf cap 27 kg; max-cover cap
  11 kg.
- Verification: 83 Python tests pass; focused Ruff and strict mypy on changed
  engine/API modules pass. Full-project mypy still has pre-existing adapter
  typing errors outside this tranche.
- Overview now supplies location labels/timezone, four source-freshness rows,
  earliest actionable-risk date, and `locations_at_risk` in one response; WP5
  must not fan out to one status request per location.
- External next step: Valentin runs
  `supabase/migrations/202608300004_actionable_risk_and_shelf_life.sql` in the
  Supabase SQL Editor. Readiness then requires `persist_planning_run_v2`.
- Frontend next step: update TypeScript response types and render/filter the
  explicit v2 fields; fix chart range/receipt labels/discrete geometry and
  continue WP5. Do not edit Python or migrations in that handover.

## Explainability handover refinement (2026-08-30)

- The planning-run API now returns `planning_line_explanations` from the exact
  immutable master version used by the run: item/storage/pack, shelf-life and
  safety/max-cover values, lead/anchor, supplier/channel, MOQ/case, delivery/
  review rule, provenance, protection mode and evidence scope.
- `explanation_context.field_lineage` maps the calculation fields to the
  normalized input datasets or policy fields; existing run inputs carry exact
  versions/hashes and daily projections carry item demand and receipt events.
- Claude must implement a scan layer, focusable definitions, and a derivation/
  source-lineage drawer. Required warnings are not hover-only.
- Current honest limits: no exact lot MHD for existing inventory, no historical
  daily stock series, and no persisted dish/silo contribution rows. Those are
  backend/data follow-ups, not calculations for React.

## Two-location colleague-demo packet and LLM follow-up (2026-08-30)

- The synthetic packet beside the original smoke-test files now contains one
  global master/planning pair for `LOC_DEMO_BERLIN_001` and
  `LOC_DEMO_HAMBURG_002`, plus one Apicbase-style stock workbook and one
  parseable Transgourmet PDF per location. Its README owns the exact 2 September
  cutoffs and upload order.
- Berlin replay `improved-098d7fc2acfa` has one actionable long-lead pod risk
  on 26 September before the 30 September candidate receipt. Hamburg replay
  `improved-c2f5d6806fd5` has all five items covered; stock and four accepted
  open-PO lines explain several zero recommendations. Both runs have zero
  blockers and byte-identical replays.
- Fresh, TK, Kuehl, RT and pod cases are all represented. The fresh showcase is
  deliberately scoped through 12 September while the six-week demand/menu
  horizon remains available for the 35-day pod policy.
- On 2 September the first live master upload exposed a contract mismatch:
  the synthetic rice row used display-like order unit `BAG`, while persistence
  accepts only `PACK` or `CARTON`. The packet now encodes its 5 kg bag as one
  `PACK`, and the XLSX adapter rejects unsupported order units before the
  persistence transaction so maintainers receive a file/row/field error rather
  than a generic `503`.
- Optional LLM assistance is now tracked in master backlog 2H and UI WP7: one
  grounded Overview executive summary and one plain-language recommendation
  explanation. The model is presentation-only; persisted engine fields remain
  authoritative, and raw uploads/credentials are excluded from the prompt.

## v2 backend adoption — semantics, not types (2026-08-31)

Codex corrected the planning logic (`b5c819d`) and the change is **semantic**,
not a type upgrade. Every affected label, filter, badge and test was reviewed.

### What the browser must no longer decide

Deleted, because their business meaning came from the wrong field:

| Removed | Why | Replacement |
|---|---|---|
| `riskLevel()` | Called any non-null `first_stockout_date` "at risk", sweeping in shortages far past the item's own protection horizon | `riskDisposition()` reading `actionable_risk_status` |
| `daysOfCover()` | Counted days to a full-forecast shortage, including zero-demand calendar days | **Covered through** `risk_horizon_end_date` |
| `horizonDays()` | Described the full projection as if it were the decision window | The decision window is the planning line's `coverage_end_date` |

### The five label changes that mattered

- **Needed → To protect.** Now `planning_lines.gross_requirement_g`, the demand
  this order must cover. Full-forecast demand is secondary context in the
  expanded row.
- **Lasts N days → Covered through <date>**, or "short from <date>" when the
  shortage falls inside the decision window.
- **Ending −31 kg → Uncovered demand … if no further orders are placed.** A
  negative balance is a running backlog, not physical stock; `uncoveredDemandG`
  flips the sign so it can be named for what it is.
- **Runs out (later) → Replan later.** Covered now, short after the horizon.
- **not_evaluated → "Not enough data"**, never folded into covered and never
  counted as zero risk.

### Verified live on a fresh v2 run (`improved-6e39406bde2f`)

The same item that previously screamed "Runs out — at risk" now reads
**"Replan later"** with *"All 1 ingredients are covered for this decision"* —
because `actionable_risk_status = covered`, `first_stockout_within_horizon_date
= null`, and the forecast shortage on 12 Sep falls after the 09 Sep horizon.
`projected_balance_at_risk_horizon_end_g = 2000` matches Codex's documented
+2 kg oracle.

Chart: defaults to the decision horizon with a display-only **Full forecast**
toggle, straight daily segments (not a smoothed curve, which would imply a zero
crossing on a day it never happened), receipts labelled **On order +2.0 kg** and
**Proposed +8.0 kg**, and plotted stock floored at zero so a backlog is never
drawn as negative stock.

Drawer: shelf-life evidence (estimated expiry, leftover at expiry, and the
`policy_approximation` caveat stated **inline**, never hover-only), constraint
status and binding constraint when anything bound, and the policy context
(lead time, review cadence, shelf life, max cover) from
`planning_line_explanations`.

### New: the definition layer

`components/InfoHint.tsx` — a focusable, click-toggled popover for "what does
this column mean and which window does it use". Deliberately limited to
nice-to-know: required warnings, blockers, approximations and remedies are all
rendered inline, because anyone who never opens a popover would otherwise miss
them.

### Not yet adopted

`/overview` now returns the complete read model — `location_name`, `timezone`,
`earliest_risk_date`, per-location `sources`, `locations_at_risk` and
`items_risk_not_evaluated`. The types are in place, so **WP5 must consume it
directly and must not fan out one `planning-status` call per location**, which
was the earlier workaround. The contract observation asking for those fields is
now resolved.

## Cross-ingredient coverage chart — backend ready (updated 2026-09-01)

Maintainer proposed an executive bar chart — ingredients on one axis, days of
coverage on the other, stacked to show what stock already on order adds.

The React view remains deferred until migration 005 is applied and a fresh v3
run exists. The demo packet has one ingredient, so sorting, colour, label
crowding and the top-N question still need roughly 20+ ingredients for honest
visual QA.

Two findings worth keeping:

- **Do not compute days of cover as `stock / average daily demand`.** It is
  planning logic in React, and it is wrong: it assumes flat demand while the
  engine projects day by day through the dated forecast. The two would disagree
  precisely on lumpy, menu-driven items — the ones that matter — and the
  browser's smoother number would look more reassuring than the truth.
- **Resolved in backend v3:** `NettingResult` and persisted rows now carry
  scenario totals plus explicit incremental open-PO/proposal days, dates,
  lower-bound flags, extension evidence status, late-receipt flags, and item
  protection-horizon days.
  The API response includes availability/semantics context so legacy v2 rows
  cannot silently look like zero coverage.

When it is built:

- Horizontal bars. Ingredient names are long and rotated axis labels are a
  dataviz anti-pattern.
- Sorted worst-first, coloured by `actionable_risk_status` disposition.
- A reference line at the decision horizon, so a bar that falls short of what
  this order must cover is obvious. The horizon is item-specific, so use a
  per-row marker rather than one global line.
- Solid stock segment, lighter accepted-PO extension, and visibly
  proposal-only final extension. Render forecast-limited values as `at least N`
  and explain late receipts that cannot bridge an earlier gap.

Backend evidence: schema version 3 in `run_improved.py`, coverage fields in
`engine/netting.py`, API context in `services.py`, and migration
`202609010005_event_aware_supply_coverage.sql`. Claude should edit only React
types/components/tests for this slice.

## WP5 done — Overview (2026-08-31)

Built directly on the v2 read model. Verified on the wire that the page issues
exactly **one** `GET /api/v1/overview` — the earlier 1+N fan-out plan is dead
and must not come back.

Decisions:

- **The alert is one thing, not a list.** `topAlert` picks the single most
  urgent location and gives it somewhere to go. Blocked outranks at-risk,
  because a blocked kitchen cannot be assessed at all; stale outranks never-run,
  because a stale number actively misleads while an absent one merely misses.
- **"not known" is not zero.** Counts derived from planning results render
  `not known` when no current run backs them anywhere, and a stale location's
  risk cell shows a dash. Rendering `0` would claim an all-clear nobody
  established — the same class of lie as the old first_stockout_date risk.
- **All clear is stated, not implied.** With nothing wrong the strip says so
  rather than rendering an empty alert box.
- Two KPIs carry `InfoHint` definitions, because "ingredients needing an order"
  and "not fully checked" both depend on which window they mean.

Remaining from the journey doc §5.2 and deliberately not built: the data
freshness panel and observed-PO activity as separate blocks. Source freshness is
already a column in the location table, and the secondary PO summary adds a
block nobody asked for on a page whose job is "what needs attention now". Flag
if that call is wrong.

Next: WP6 — states sweep, accessibility, responsive, and honest handoff notes.

## WP6 done — hardening and handover (2026-08-31)

The initial backlog is complete. Handover: `docs/plans/ui_slice_handover.md`.

**Two real accessibility defects found and fixed.** The expandable risk row and
the recommendation row were `onClick` handlers on `<tr>`: unreachable by
keyboard entirely, and on touch they selected text instead of opening. Both are
now real `<button>` elements with `aria-expanded`, pinned by keyboard tests.
Worth remembering as a pattern — a clickable table row is not an accessible
control, however convenient it is to write.

Verified in a real browser at 375 px and 1440 px: tables scroll inside their own
container so the page body never scrolls sideways, KPI cards stack, the sidebar
becomes a drawer, and the projection chart stays legible.

One tooling note: in the browser pane's mobile emulation, synthetic clicks on
the row time out and can select text. The DOM confirmed `aria-expanded="true"`
and the detail row present, so it is an emulation artifact rather than a product
fault — but check the DOM rather than the screenshot when a mobile interaction
looks like it failed.

**Exercised live:** sign-in, first-run state, all four imports, activation, a v2
run, risk table, projection chart, derivation drawer, Overview.
**Not exercised:** more than one ingredient, more than one location, the
download save dialog, and any deployed environment. That last gap is the main
reason the handover's first recommendation is to get realistic data in.

## Coverage chart built on the v3 contract (2026-09-01)

Codex's event-aware coverage backend is adopted. The chart sits at the top of
Risk & stock: horizontal, worst-first, three stacked segments per ingredient.

Every segment is a persisted day count. `open_po_coverage_extension_days` and
`proposal_coverage_extension_days` are stacked **directly** — scenarios are
never subtracted, and stock is never divided by demand.

Verified live on a fresh v3 run: 2 days on hand + 2 from open POs + 8 from the
proposal = 12, against a 10-day target. Rendered widths measured in the DOM at
125/125/502 px, matching 2:2:8 exactly.

States handled:

- **Legacy v2 run** — gated on `coverage_context`, showing "Compute a fresh
  recommendation to see supply coverage" and stating the values are absent, not
  zero. Confirmed live against the pre-migration run.
- **`forecast_limited`** — "at least N days", never a bare N.
- **`not_observable`** — "not measurable, supply before it already covers the
  whole forecast". Never "adds nothing".
- **Receipt after a gap** — explained rather than shown as a silent zero.
- Item-specific `protection_horizon_days` marker per row, never one global line.

Two bugs found by inspecting the DOM rather than the screenshot:

- Segments rendered **0 px wide**. The flex container was `absolute left-0`
  with no right edge, so it shrank to fit and the percentage children resolved
  against zero. `inset-0` fixes it. The screenshot only looked "faint", which is
  why the measurement mattered.
- The proposal stripe used `--circus-accent-soft` on a near-white track and was
  effectively invisible. Now the accent at 45% through `color-mix`.

### Planning cutoff control added

The demo packet aged out: today is 2026-09-01 and its forecast starts
2026-08-31, so `run_improved.py` correctly refuses with "forecast_daily
contains service dates before planning_as_of_at". The run button previously
always sent "now" with no way to plan as of an earlier instant.

Added the advanced cutoff disclosure that was in the original WP4 blueprint but
never built. It is a **cutoff**, not a horizon slider — the correction plan
forbids the latter because it would let a user hide risk; choosing the instant a
run is made is a different and legitimate thing.

### Contract observation for Codex

That `ValueError` reaches the browser as a generic 500 "The planning service
could not complete the request", because it is caught by the sanitized
`internal_error` handler. But its message is planner-facing and actionable —
"provide a forward snapshot or move planning_as_of_at". It should be a 422 with
the message so the maintainer can act on it, rather than a log line only a
developer sees.

## Coverage bar made readable (2026-09-01)

The bar showed only a total ("12 days") with no way to see what each segment
contributed, so the number read as unexplained.

- **Inline numbers in each segment** — `2`, `+2`, `+8` — rendered only where a
  segment is at least 9% of the track, so narrow ones do not overflow.
- **A detail card on hover and keyboard focus**, giving each scenario's days
  and the date it covers through, then the total and the item's target. The
  bar row is `tabIndex={0}`, and `:focus-visible` was verified to match so the
  card is genuinely keyboard-reachable, not hover-only.
- **The target marker now overhangs the bar** vertically, so "how far must this
  reach" survives sitting next to a long bar.

Per `circus-ui`, essential information is never hover-only: the total, the
target comparison and the risk badge stay visible on the row. The card carries
the arithmetic, which is nice-to-know.

### Scale: one shared axis, deliberately

`scaleMax` spans all rows, so bar lengths are comparable between ingredients —
30 days renders 2.5× longer than 12. Known trade-off: an item needing 30 days
and holding 25 draws *longer* than one needing 5 and holding 8, though the
first is short and the second is fine. The per-item target marker and the amber
total are what resolve it. Normalising each bar to its own target would fix the
"is it enough" read but destroy cross-ingredient comparison, which is the thing
that was actually asked for. Revisit only with real multi-item data.

## Location page density and hierarchy pass (2026-09-01)

Maintainer review found the page flat and text-heavy. Six fixes:

1. **Freshness strip condensed.** Only the three facts that change a decision
   stay visible — stock age, order age, result currency — with master version
   and forecast end behind a **More** disclosure. It was a full-width row of
   five labelled values before.
2. **Tabs given a visible track.** They read as squeezed because the shadcn
   default track is `bg-muted` (`#fafafa`) with a **white** active tab: white on
   near-white. The vendored component now has a bordered track, a lifted active
   tab with a ring and semibold label, and `h-9`. Left alignment kept — see
   below.
3. **Hierarchy separated.** Section headings are `text-base font-semibold`;
   summaries dropped to `text-xs` muted so they stop competing with headings.
4. **Three full-forecast stat lines removed** from the expanded row. Nobody was
   acting on them.
5. **Sentences cut.** The expanded row no longer opens with "X is covered
   through … The forecast runs short on …, which a later review handles" — the
   table row already says both. Only genuinely additional facts remain, as
   short lines: unfixable shortfalls and incomplete evidence. The chart footer
   is now "Reaches zero 12 Sept · whole days only" instead of two sentences.
6. **Toggle selected state made visible.** `aria-pressed:bg-muted` resolved to
   `#fafafa` — indistinguishable from the page. Now accent-soft fill, accent
   border and accent text. Verified: pressed `rgb(230,246,239)` on
   `rgb(11,132,89)`, unpressed `rgb(250,250,250)` on `rgb(231,231,233)`.

### Why the tabs stay left-aligned

Asked whether they should be centred. They should not. Tabs are a navigation
control for the content directly beneath them, and left alignment keeps them on
the same scan line as everything else on the page — the title, the freshness
facts, the table's first column. Centring would float them away from the panel
they control and break that column. The real problem was contrast, not
position, and fixing the track solved it.

### Note on the vendored shadcn defaults

Twice now the cause of a "looks broken" report has been a shadcn default
resolving to `--muted`, which this theme maps to `#fafafa`. Anything relying on
`bg-muted` to signal state is invisible here. Check that first when a control
looks stateless.

## Status semantics corrected (2026-09-01)

The maintainer asked why an item with 4 days of cover, a 10-day target and an
8-day proposal showed **Replan later** rather than **at risk**. The question
exposed a real labelling defect.

`actionable_risk_status` is computed in `netting.py` from `result.days`, the
projection **including the candidate receipt**. So it answers *"does this plan
work?"*, not *"what happens if you do nothing?"*:

- `at_risk` — short **even with the proposal applied**; the proposal is not
  enough
- `covered` — no shortage inside the protection window **once the proposal is
  placed**
- `not_evaluated` — the projection did not reach the window's end

My labels contradicted that. "Replan later" implied no action was needed on an
item whose proposal is the very thing saving it, and "Needs an order" for
`at_risk` was wrong because *every* row with a proposal needs an order — the
distinction is whether it suffices.

Now:

| Disposition | Label | Meaning |
|---|---|---|
| `unavoidable` | Too late to fix | Shortfall lands before any delivery could arrive |
| `at_risk` | Still short | Short even with the proposal |
| `not_evaluated` | Not enough data | Evidence stopped early |
| `covered` / `future_replan` | Covered | Covered once the proposal is placed |

The column is renamed **With this order**, with a hint saying it assumes the
order is placed. A later forecast dip is secondary text under the badge
("dips again 12 Sept"), not the status itself.

## InfoHint fixed and portalled

The popover was unreadable in table headers for two compounding reasons:

1. It inherited `whitespace-nowrap` from `TableHead`, forcing the whole
   explanation onto one line.
2. The table sits in an `overflow-x-auto` wrapper. Overflow on one axis
   computes to `auto` on the other, so the popover was clipped by the scroll
   container.

It now renders through `createPortal` to `document.body`, positioned from the
trigger's rect and clamped to the viewport. Verified: 256×98px, wrapped,
`white-space: normal`, no right-edge overflow.

## Tabs centred

Asked twice, so centred. Recorded reasoning for the left-aligned alternative:
tabs control the panel beneath them and left alignment keeps them on the same
scan line as the title and the table's first column. Reversible by removing
`mx-auto` from the `TabsList` in `LocationPlanningPage`.

## Status column reframed to "without ordering" (2026-09-01)

The maintainer rejected the previous framing outright, correctly: a status that
counts the proposed order **will always read Covered**, because the engine
proposes exactly enough to cover the window. Zero information.

The decision-useful question is what happens if the order is *not* placed — or
cannot be. `with_open_po_first_uncovered_date` is exactly that: the earliest day
stock plus already-accepted orders cannot serve. Comparing it to
`risk_horizon_end_date` gives the flag, and both are engine-produced dates, so
nothing is re-projected. Because the first uncovered date is by definition the
earliest such day, a date on or before the window end always means a real gap.

Severity ladder now:

| Badge | Meaning |
|---|---|
| Too late to fix | Shortfall lands before any delivery could arrive |
| Order not enough | Short **even with** the proposal — `actionable_risk_status = at_risk` |
| Not enough data | Evidence stopped before the window ended |
| **At risk** — short *date* unless ordered | Accepted supply runs out inside the window; the proposal fixes it |
| Covered — without ordering | Accepted supply carries the window on its own |

### Filter renamed to avoid contradicting the badge

With the badge reporting the without-ordering truth, nearly every row with a
proposal reads **At risk** — which is correct, but it would then contradict a
filter called "Needs attention" that excluded those rows. The filter is now
**Problems only** and still keys off `actionable_risk_status`, so it means
"ordering does not solve this". Two genuinely different questions, each labelled
as what it is.

### Open question for Codex

`actionable_risk_status` is specified as the source for "the row status, and
Overview meaning". The row status now answers the without-ordering question
instead, because the specified field is tautological in that cell. Overview KPIs
and the location filter still use the backend status unchanged. An explicit
`risk_without_proposal_status` would remove the date comparison from React
entirely and is the cleaner long-term contract.

## Page-load latency investigation (2026-09-03)

### Symptom reproduced by the current design

The maintainer reports roughly 3–4 seconds before each page becomes useful,
including a full wait when returning to Data & settings only seconds after
leaving it. This is consistent with the code path: `useApiResource` has no
cache, every route mount starts in `loading`, and unmount aborts/discards the
page's state. React Router replaces the route component, so back navigation is
not a return to retained data; it is a new load.

Do not reuse the old rationale that a cache would falsify freshness. The API's
source/import timestamps describe the returned snapshot. A short session cache
can render that exact snapshot immediately, state when it is refreshing, and
invalidate it after writes without inventing a newer source time.

### Read-only measurements

Probes used the configured development Supabase project, returned only counts/
timings, and made no writes. They invoked `PlanningBackend` locally, so they
exclude browser → API latency and the remote Supabase Auth verification that
each domain endpoint performs.

| Backend operation | Database reads | Current timing |
|---|---:|---:|
| `list_locations` | 5 | 402–489 ms |
| `planning_status` | 11 | 764–843 ms |
| `inventory` | 7 | 535–550 ms |
| `get_planning_run` | 12 | 699–769 ms |
| `overview` (2 active locations) | 35 | 2,444–2,485 ms |
| `list_imports` | 1 | 198 ms |
| `list_master_versions` | 1 | 123 ms |

Location initial mount calls locations, status, and inventory. The latest run
is enabled only after status returns its id, so useful result content waits on
an approximately 1.5-second direct-backend waterfall before browser/API/Auth
overhead. Total route work is 35 database reads plus four separately
authenticated API calls.

Data & settings starts imports, versions, locations, and selected-location
status. Only imports + versions gate the entire scaffold, but all four routes
still recreate their Auth and database work on every remount.

The latest-run response was 121.7 KiB with 230 projection rows. This is not the
first bottleneck at current scale, though it is already listed as an unbounded
contract observation and should be re-measured with realistic data.

### Connection churn is confirmed, not inferred

Both `SupabaseCanonicalStore._request` and
`SupabaseIdentityVerifier.verify` open a new `httpx.AsyncClient` for every
operation. A read-only prototype using one shared client changed timings as
follows:

| Read | New client each operation | Shared client |
|---|---:|---:|
| locations | 489 ms | 239 ms |
| status | 764 ms | 520 ms |
| inventory | 550 ms | 390 ms |
| latest run | 738 ms | 461 ms |
| Overview | 2,444 ms | 1,625 ms |

That 29–51% range makes connection reuse a justified first tranche, but the
remaining 1.6-second Overview read proves it is not sufficient alone.

### Query-shape findings

- `_load_master` reads the active/version row and four master tables. It is
  repeated by locations, planning status, inventory, and planning-line
  explanations.
- `planning_status` uses 11 reads in the current two-location data state,
  including candidate planning-import coverage checks, three latest source
  paths, latest run, and run inputs.
- `get_planning_run` reads the run, six result tables, then reloads five master
  tables for explanations.
- Overview correctly exposes one browser endpoint, but internally calls full
  planning status sequentially per location, then reads netting,
  recommendations, blockers, and open POs per location. It is a backend N+1.
- React Strict Mode may double initial effects in `pnpm dev`. Keep Strict Mode;
  correct cache/deduplication instead of hiding the behavior in development.

### Chosen sequence

1. Implement regression tests, shared backend HTTP-client lifetime, and the
   session-scoped stale-while-revalidate resource cache with explicit mutation
   invalidation. Verify immediate revisit UX and measure again.
2. Reduce remaining database round trips: set-based Overview, shared master
   loads in composed requests, and a Location bootstrap read model only if the
   post-tranche-1 waterfall is still material.
3. Only then consider projection splitting/prefetch, deployment tier/region,
   cold-start mitigation, or local JWT verification.

Detailed checklist, acceptance criteria, risks, and the exact baseline live in
`docs/plans/ui_performance_optimization_plan.md`. WP8 in the UI backlog and 2I
in the master backlog track completion.

## Page-load tranche 1 implementation (2026-09-03)

### What changed

- `resourceCache.ts` now owns successful browser resources in memory for a
  named 10-minute fresh window. The maintainer confirmed this on 2026-09-03
  because current sources change only through manual workflows; explicit
  Refresh and mutation invalidation remain authoritative. Keys cover readiness, Overview, locations,
  imports, master versions, per-location status/inventory/POs, and run id.
- Same-key requests share one in-flight promise. Route unmount no longer aborts
  a request that a remount or second subscriber can use.
- A recent route remount renders the known result immediately. Stale or
  invalidated data remains visible while it revalidates; a failed refresh is
  shown inline with Retry instead of replacing the useful page with an error.
- Resource state is tagged by key so changing locations inside the mounted page
  cannot flash the previous location's data while subscriptions change.
- Successful imports, master activation, and planning-run creation invalidate
  the exact dependent keys. The returned planning run primes its own cache.
- Sign-out, rejected/expired sessions, restored-session ownership setup, and a
  user-id change clear all cached domain data. The cache is never persisted.
- FastAPI supplies one lazily created `SupabaseHttpClient` to both
  `SupabaseIdentityVerifier` and `SupabaseCanonicalStore`, then closes it during
  application shutdown. Auth verification still occurs per browser request.

### Verification and measured outcome

All automated checks passed: 93 Python tests; focused Ruff and strict mypy;
156 Vitest tests across 13 files; ESLint; TypeScript; and the Vite production
build. Tests explicitly cover recent remount, stale background refresh,
deduplication, invalidation, refresh failure, cache clearing, authenticated-user
change, key changes, mutation invalidation, shared transport, and shutdown.
The shell navigation regression exercises Overview → Data & settings → Overview
and asserts one Overview request and no second full-page loading state.

Three consecutive direct backend read cycles using the implemented pooled
client produced:

| Read | Median | Range | Reads |
|---|---:|---:|---:|
| locations | 240 ms | 238–717 ms | 5 |
| planning status | 614 ms | 583–872 ms | 11 |
| inventory | 400 ms | 395–404 ms | 7 |
| latest run | 538 ms | 536–541 ms | 12 |
| Overview | 1,866 ms | 1,827–1,887 ms | 35 |

The 717 ms locations sample was the first warm-up; the next two were 238 and
240 ms. Overview improved by about 24–25% relative to the original observed
2,444–2,485 ms range, but keeping all 35 reads leaves it too slow. This is the
evidence for tranche 2: reduce query count rather than tune cache duration or
add a more complex frontend library.

The production build also reports a 1,178.08 KiB minified JavaScript chunk
(355.92 KiB gzip). That may affect cold initial asset load, but it cannot cause
the old repeated API wait on a route revisit. Keep it in tranche 3 unless the
authenticated trace shows asset execution is material.

### Remaining gate and next work

- Run the real authenticated browser sequence for first visit and immediate
  revisit on Overview, Data & settings, and one Location. Capture request count,
  whether known content ever disappears, and time to useful content.
- Direct measurements justified starting query reduction before that browser
  session was available. Tranche 2 is now complete below; the browser sequence
  remains the shared acceptance gate for both tranches.

## Page-load tranche 2 implementation (2026-09-03)

### Implemented query plan

- Added request-scoped metrics using a context variable. The application logs
  only method, route template, response status, total time, aggregate Auth and
  PostgREST call counts, and aggregate upstream durations. It does not retain
  URLs/query strings, tokens, identifiers, row values, or file contents.
- Location metadata now needs the active version plus the location table (two
  reads), instead of loading all four master tables. Planning status batches
  planning-import coverage, location imports, current runs, and run inputs.
- Overview uses those set-based reads once and groups current run results and PO
  sources in Python. Tests require exactly 10 reads with both two and six active
  locations, so adding locations cannot restore the old per-location N+1.
- `GET /api/v1/locations/{location_id}/view` composes the existing locations,
  status, inventory, and latest-run payloads. It shares one active master load;
  if a historical run references another master it still loads that immutable
  version to preserve explanation semantics. The response does not calculate a
  second planning result. Open POs stay lazy until the Orders tab is opened.
- Location initial load is now one browser/Auth request and 16 PostgREST reads,
  down from four requests and 35 reads. The frontend primes the existing
  derived cache keys from the composed response, so other consumers retain the
  same contracts and invalidation behavior.
- Data & settings keeps its existing reads. Imports and versions are one read
  each, locations is two, status is six, and recent successes are shared by the
  10-minute session cache. There was no measured reason to add a separate page
  endpoint.

### Direct evidence and verification

The reusable read-only probe at `scripts/measure_ui_performance.py` runs the
production PostgREST adapter, checks that the composed Location payload equals
independent calls, and prints only timings/counts. Five cycles produced:

| Read | Median | Range | Reads |
|---|---:|---:|---:|
| locations | 168 ms | 167–183 ms | 2 |
| planning status | 409 ms | 403–675 ms | 6 |
| composed Location view | 797 ms | 776–4,193 ms | 16 |
| inventory | 383 ms | 378–401 ms | 7 |
| latest run | 650 ms | 596–702 ms | 12 |
| Overview | 727 ms | 707–873 ms | 10 |

Run it with
`.venv\Scripts\python.exe scripts\measure_ui_performance.py --cycles 5`.
It is read-only but requires the configured Supabase network path.
Overview is about 61% faster than the tranche-1 median and about 70% faster than
the original measurement, with 71% fewer reads. The Location view uses 54%
fewer reads than the original route. One 4.19-second Location outlier confirms
that an upstream/network stall can still make an uncached first visit slow; the
10-minute cache prevents return navigation from paying it again.

All automated checks passed after this tranche: 98 Python tests; 157 Vitest
tests across 13 files; Ruff; strict mypy; ESLint; TypeScript; and the Vite
production build. Response-equivalence, route/Auth, privacy-safe metrics,
constant Overview query count, legacy-import fallback, one-request Location
loading, cache priming, and mutation invalidation have focused coverage.

### Decisions, risks, and next step

- Batching is sufficient at the current scale. Do not add a database view, RPC,
  materialized summary, or in-process master cache now.
- Batched latest-source and latest-run helpers make a constant number of calls
  but currently group returned metadata history in Python. Reassess pagination
  or a database read model only if history-table row volume becomes material.
- The remaining acceptance gate is the real authenticated browser sequence for
  first visit and immediate revisit on all three pages. Capture browser request
  counts, loading-state continuity, and time to useful content; include deployed
  Auth, Render, CORS, asset, and rendering time.

## Visual system review — the palette was a placeholder (2026-09-04)

Maintainer report: the UI still looks crowded, paddings and margins too small,
visual structure poor, "not modern and sophisticated". Also asked where the
colour palette came from and whether it can be more modern while staying on
brand.

### Where the palette came from

`apps/web/src/styles.css` implements the `circus-ui` skill's **example** token
block verbatim, including the emerald accent `#0B8459`. The skill's own text
says of that block: *"Replace the accent hexes below with the exact brand values
if the design team has them."* Nobody did, so a placeholder shipped as the
product's identity.

### What Circus Group actually uses

Read directly from the custom properties in the live stylesheet at
`circus-group.com` on 2026-09-04. These are the brand's own variable names:

| Brand variable | Value | Meaning |
|---|---|---|
| `--base-color-brand--blue` | `#2d62ff` | **the brand accent** |
| `--color--1a1a1a` | `#1a1a1a` | body ink |
| `--circus-white` | `#fafafa` | page ground |
| `--light-white` / `--color--eeeff1` | `#eeeff1` | secondary surface |
| `--color--576d68` | `#576d68` | slate green, tertiary |
| `--base-color-system--success-green` | `#cef5ca` | success fill |
| `--base-color-system--success-green-dark` | `#114e0b` | success text |
| `--base-color-system--error-red` | `#f8e4e4` | error fill |
| `--base-color-system--error-red-dark` | `#3b0b0b` | error text |
| `--color--error` | `#f2655c` | error mark |
| `--color--circus-live` | `#ff3636` | live/broadcast — **not for tools** |
| `--color--focus` | `#d0e6e1` | focus mint |

Type: **PolySans** display, **Inter** body. The app is on Geist.

Two conclusions. First, the accent is blue, not green. Second — and this is the
substantive one, not the cosmetic one — **green currently means two
incompatible things at once**: it is the brand accent (Compute recommendation,
active nav item, pressed Toggle, dropzone hover) *and* it is the success status
(Covered, Accepted, Ready). A maintainer scanning the Risk & stock table sees
one hue for "click this" and "this is fine". Moving the accent to the brand
blue separates them and frees green to only ever mean good.

### Why it reads as crowded

Not padding. **There is no figure/ground.** The canvas, the sidebar and every
card are all `#FFFFFF`, separated by `#E7E7E9` hairlines, with almost every
string set at 12-14px. Nothing recedes, so everything competes.

Note that D5 originally specified exactly the right thing — *"`stone-50` page,
`white` surfaces, `stone-200` hairlines"*. That intent was lost when the
`circus-ui` tokens were adopted, because the skill maps `--circus-bg: #ffffff`
and `--circus-surface: #fafafa`, i.e. the inverse. Restoring the tint is a
one-line change with more effect than any amount of extra padding.

### Audit — everything found

**Cross-cutting**

- Uniform block spacing: `space-y-6` on Overview, `space-y-5` on Location
  planning give the page header, alert strip, KPI row and table the same gap,
  so nothing groups with anything.
- Only two type steps in real use (12px and 14px) plus a couple of 24px
  numbers. No 16px tier, so the pages are a flat field of small text.
- `--radius-lg` is 10px and buttons use `rounded-lg`, so controls and cards
  share a radius and read as the same kind of object.
- Default `Button` height is `h-8` (32px), under the 40px touch target the
  shop-floor requirement asks for.
- `StatusBadge` is a grey outline with coloured text: the colour is a 1px
  stroke and a 6px dot, and every status weighs the same.

**Overview** (`features/overview/OverviewPage.tsx`)

- Alert strip, KPI tiles and the table all use identical
  `rounded-lg border border-border` — one visual weight for three roles.
- KPI values are colour-coded *and* the pills are coloured *and* the status
  text is coloured. Warning/danger is doing three jobs at once.
- `TableCell` is `p-2`: 8px of horizontal padding, so the first column nearly
  touches the card edge. Rows land near 36px against the 44px target. The
  header is 14px regular — the same weight as data — and not sticky.

**Location planning** (`features/location-planning/LocationPlanningPage.tsx`)

- Five stacked strips of metadata before any content: title, location select
  plus badges, `FreshnessStrip`, `BlockerList`, the stale warning, then tabs.
  This is the single biggest density problem in the app.
- `RunAction` stacks up to four right-aligned ragged-left lines under the
  primary button.
- Risk & stock does three jobs: coverage chart, table, per-row projection
  chart on expand.
- Three `InfoHint` triggers in one header row — a sign the column labels are
  not carrying their weight.
- `CoverageChart` paints "on order" with `bg-info/55`, a status colour used as
  a chart series. In stock, on order, proposed is an ordered sequence and
  wants its own single-hue ramp.

**Data & settings** (`features/data-settings/DataSettingsPage.tsx`)

- Four full-width accent buttons, plus "Activate master data and continue" —
  five primary actions on one screen. Nothing reads as the next step.
- The page's premise is "import the four sources in order" but the step number
  is a 12px `text-faint` digit.
- Dropzone copy exposes internal template filenames
  (`Phase2_Master_Data_Template_v1.xlsx`).
- Three `PlannedFeatureCard`s advertise unbuilt features inside a working tool.

**Shell** (`app/AppShell.tsx`, `components/BrandMark.tsx`)

- The sticky top bar carries only an email and Sign out; its whole left side is
  empty on desktop.
- The brand mark is **"P2"** — an internal phase code used as the logo.

### Two real defects found while reviewing

1. **The location picker renders the raw ID.** The page `<h1>` says "Demo
   Kitchen Berlin" while the `Select` beneath it says `LOC_DEMO_BERLIN_001`.
   Base UI's `Select.Value` renders the *value*, not the selected item's label,
   unless `items` is supplied on `Select.Root`. Affects the Location planning
   header and the Data & settings location scope picker.
2. **`text-faint` carries essential content.** `RiskStockTab`'s `StatusCell`
   renders "short 08 Sept 2026 without the proposal" in `#9A9BA1` — 2.8:1 on
   white, failing WCAG AA. That line changes an ordering decision; it cannot
   sit at placeholder contrast. `--faint` is for placeholders only.

Minor: the `running` tone in `StatusBadge` uses `animate-pulse`, which loops
indefinitely. The one permitted looping animation is the loading skeleton.

### Not changed: the centred tabs

Flagged in review as the only centred element on a left-aligned page. Left
alone deliberately — the maintainer asked for centred tabs twice (see **Tabs
centred**, 2026-09-01), and that is a maintainer decision, not a defect. Still
reversible by removing `mx-auto` from the `TabsList`.

### Proposed token set

Full swatches, contrast maths and a before/after specimen:
https://claude.ai/code/artifact/07471639-7a5a-4de3-a404-5c1ef65d7ee2

Contrast checked against the surface each token actually sits on: accent
`#2D62FF` 4.9:1 with white text, `--accent-strong` `#1E4BD8` 6.9:1 as link
text, `--muted` `#6E7482` 4.7:1, `--secondary` `#5A5F6B` 6.4:1, and every
status pair between 6.6:1 and 8.3:1.

### Skill corrected

`circus-ui` was updated in the same pass so the placeholder cannot ship again:
real brand values, the accent/success collision named explicitly, the
canvas-vs-surface rule, tinted status pairs, a chart ramp separate from status,
and a standing instruction that example hexes are never shipped unverified.

## Visual system implemented (2026-09-04)

Branch `ui_visual_system`, three commits, `pnpm check` green throughout
(ESLint, TypeScript, 168 Vitest tests, production build).

### The token migration, and the one trap in it

`--circus-surface` used to mean `#FAFAFA`, the tinted inset. The canvas is now
that value, so `surface` was re-pointed to `#F2F3F5` and keeps its "sunken"
role. That is why ~20 existing `bg-surface` call sites needed **no** change:
they all meant "an inset strip", and they still do, just with enough contrast
to be visible against the new canvas. What did change is the set of containers
that should *lift* — KPI tiles, table wrappers, the top alert, `BlockerList`,
`ErrorState` — which gained `bg-card`.

`--background` deliberately stays white. It is the *component* ground (inputs,
popovers, outline buttons, cards), not the page ground; the shell paints the
page with the new `bg-canvas`. Mapping `--background` to the canvas instead
would have tinted every input and outline button on a white card.

Radius now differentiates: `--radius-lg` 8px for controls, `--radius-xl` 12px
for containers. Every feature-level `rounded-lg` was a container, so they all
moved to `rounded-xl`; the vendored controls keep `rounded-lg` and shrank from
10px to 8px for free.

`--circus-info` was deleted. It only existed to be misused as a chart series.

### The regression the browser caught

Source hexes are not the thing to check — the *resolved* token on the *actual*
surface is. Measuring in the running app found one failure introduced by this
work: the new 11px uppercase table header is `--muted` on `--sunken`, which
came out at **4.22:1**. Below AA, and 11px bold does not qualify as large text.

Fixed in the token rather than at the call site: `--circus-muted` darkened
`#6E7482` → `#666B78`, which holds 4.80:1 on sunken, 5.33:1 on white and
5.11:1 on canvas. Every other `text-muted-foreground` on a tinted strip — the
`UploadCard` prerequisite box, the step marker, the freshness labels — was
carrying the same flaw and is fixed by the same change.

Measured after the fix, from the running app:

| Pair | Ratio |
|---|---|
| ink on canvas | 16.67 |
| muted on card / canvas / sunken | 5.33 / 5.11 / 4.80 |
| subtle on card | 6.39 |
| accent-text on card | 6.88 |
| white on accent | 4.88 |
| input outline on card | 3.24 |
| success / warning / danger / neutral pill | 8.28 / 6.63 / 7.40 / 7.14 |

### Sticky table headers: dropped, with a reason

The table lives in an `overflow-x-auto` wrapper. Overflow on one axis computes
to `auto` on the other, so the wrapper is a scroll container and a sticky
`thead` would anchor to something that never scrolls vertically. Same root
cause as the `InfoHint` clipping fixed on 2026-09-01. It needs the wrapper
restructured; deferred rather than shipped half-working.

### Two things the review got wrong, caught by reading before cutting

1. **The purchase-order upload instruction.** Flagged as a three-line paragraph
   of helper text. It is not: `datasets.test.ts` pins three specific claims in
   it and `b09f8d3` added it on purpose. It is what stops a maintainer losing
   PO lines by uploading only the newest file. Left alone.
2. **The centred tabs.** Flagged as the only centred element on a left-aligned
   page. The maintainer asked for centred twice (**Tabs centred**, 2026-09-01).
   Left alone.

One thing the review got right but that needed a replacement rather than a
deletion: the three `PlannedFeatureCard`s were carrying a real boundary — where
item policies, the menu calendar and the BOM actually come from. Deleting them
outright would have dropped that. The sentence is now in the section they sat
under, and `dataSettings.test.tsx` checks for the boundary instead of the
roadmap.

### Not verified

The three authenticated screens have not been looked at against real data —
signing in needs credentials. Tests and the token measurements cover the
mechanics; nobody has seen Overview, Location planning or Data & settings
rendered with the new system.
