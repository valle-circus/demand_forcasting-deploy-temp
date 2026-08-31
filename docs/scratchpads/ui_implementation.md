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
- Berlin replay `improved-9bd06fb63c77` has one actionable long-lead pod risk
  on 26 September before the 30 September candidate receipt. Hamburg replay
  `improved-7383aef1b01e` has all five items covered; stock and four accepted
  open-PO lines explain several zero recommendations. Both runs have zero
  blockers and byte-identical replays.
- Fresh, TK, Kuehl, RT and pod cases are all represented. The fresh showcase is
  deliberately scoped through 12 September while the six-week demand/menu
  horizon remains available for the 35-day pod policy.
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

## Deferred: cross-ingredient coverage chart (2026-08-31)

Maintainer proposed an executive bar chart — ingredients on one axis, days of
coverage on the other, stacked to show what stock already on order adds.

**Deferred until a location has realistic ingredient counts.** The demo packet
has one ingredient, so sorting, colour, label crowding and the top-N question
cannot be judged. Revisit at roughly 20+ ingredients.

Two findings worth keeping:

- **Do not compute days of cover as `stock / average daily demand`.** It is
  planning logic in React, and it is wrong: it assumes flat demand while the
  engine projects day by day through the dated forecast. The two would disagree
  precisely on lumpy, menu-driven items — the ones that matter — and the
  browser's smoother number would look more reassuring than the truth.
- **The stacked split is not available from persisted data.** `NettingResult`
  has no days-of-cover field and no breakdown of cover contributed by usable
  stock, by open POs, and by the proposed receipt.

When it is built:

- Horizontal bars. Ingredient names are long and rotated axis labels are a
  dataviz anti-pattern.
- Sorted worst-first, coloured by `actionable_risk_status` disposition.
- A reference line at the decision horizon, so a bar that falls short of what
  this order must cover is obvious.

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
