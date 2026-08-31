# UI implementation backlog — three connected maintainer pages

**Status:** proposed 2026-08-29. **Not approved, not started.** No frontend
code has been written for this plan.

**Scope:** frontend only. Everything under `src/supply_planning`, `apps/api`,
`supabase/migrations`, and the Python tests is out of bounds for this slice.

**Relationship to other documents**

| Document | Role |
|---|---|
| `docs/descriptions/ui_maintainer_journey_and_page_plan.md` | Authoritative product/UX contract. This plan implements it; it never overrides it. |
| `docs/descriptions/ui_api_and_persistence_foundation.md` | Runtime, security, environment boundaries. |
| `docs/claude_code_first_ui_pages_brief.md` | The handover instruction this plan answers. |
| `docs/plans/phase2_supply_planning_master_backlog.md` | Milestone authority. Items 2D/2E/2F stay the milestone checkboxes; this file is the granular execution plan under them. |
| `docs/scratchpads/ui_implementation.md` | Living findings, decisions, open questions. |

Every work package below names the master-backlog items it satisfies. Tick the
master backlog only when the mapped work package is done **and** verified.

---

## 1. What this UI is for

One sentence: **the maintainer must be able to tell, in seconds, whether a
number can be trusted, and what to do when it cannot.**

That is the product's real job. Recommendation tables are commodity; honest
trust calibration is not. Three consequences drive every decision below:

1. The most important reusable primitive is not a card or a table — it is the
   **freshness/provenance stamp**. It is designed first and used everywhere.
2. **Every problem carries its remedy.** An alert without an action is a bug.
3. **A stale answer is labelled, never hidden and never silently refreshed.**

Non-goals, restated so they cannot drift in: no ordering, approval, supplier
send, ERP write, comments, assignment, or status tracking. No parsing, no
planning arithmetic, no KPI derivation in TypeScript.

---

## 2. Decisions

Maintainer review 2026-08-29 confirmed D2, D5, D7 and D8, and dropped D4.
D1, D3 and D6 remain open.

### D1 — Router: add `react-router-dom` v7 *(open)*

The three destinations are already URL-shaped, including a path parameter
(`/locations/:locationId`), and deep links from Overview KPI cards into a
filtered location tab are central to the "every risk leads to an action"
principle. Hand-rolling that is worse code for no saving.

*Alternative considered:* a hand-written history/hash router. Rejected —
roughly the same amount of code, no nested-layout support, no scroll or focus
restoration, and it would have to be replaced later anyway.

### D2 — Server state: small hand-written hooks, no TanStack Query *(confirmed)*

Recommendation: a ~60-line `useApiResource(fetcher, deps)` hook returning a
discriminated union `{ status: 'idle' | 'loading' | 'success' | 'error' }`,
plus explicit `refetch()` and a tiny `useMutation`-style helper for uploads,
activation, and the run.

Rationale beyond "the journey doc says avoid a large state framework": this
product deliberately **does not want a cache**. Every screen's message is "here
is how fresh this is". A background cache that serves a previous response while
revalidating would put a number on screen whose freshness stamp is a lie. With
no cache, cross-page invalidation stops being a problem — a page refetches on
mount and after its own mutations, and that is always correct.

*Alternative considered:* TanStack Query with `staleTime: 0` and
`refetchOnMount: 'always'`. Legitimate, and it would give retry/dedupe for
free, but it is configuration effort spent turning off the feature you added it
for. Revisit if request volume or polling appears (it would, if runs ever go
async).

### D3 — Tests: add Vitest + Testing Library *(open)*

`apps/web` has no test runner at all, and the brief requires component tests
for auth/session, navigation, typed API errors, upload states, readiness/run
states, and proposal labels. Proposed devDependencies: `vitest`,
`@vitest/coverage-v8` (optional), `@testing-library/react`,
`@testing-library/user-event`, `@testing-library/jest-dom`, `jsdom`.

Adds `"test": "vitest run"` and changes `"check"` to
`lint && typecheck && test && build`. Tests live beside sources as
`*.test.tsx` under `src/` so the existing `tsconfig.app.json` include still
covers them; ESLint gets a test-file override for the Vitest globals.

### D4 — Preview/fixture mode — **DROPPED 2026-08-29**

Proposed only because the repository documentation stated that migration 003,
Auth and credentials were unverified. They are not: a live probe on 2026-08-29
returned readiness `ready` with "Supabase REST and all required backend
migrations are reachable", and the auth boundary returns a proper
`401 invalid_session`. Building a bypass around a working backend adds risk and
a second code path for no benefit. **The UI is built and reviewed against the
real API only.** There is no demo mode, no fixture transport, and no synthetic
fallback anywhere in the application.

Fixtures still exist, but only inside Vitest — never shipped in a bundle.

### D5 — Visual direction: same identity, workspace density *(confirmed)*

Keep the existing identity (stone neutrals, lime accent, Inter) so this reads
as the same product as the foundation shell. Retune for dense operational use:

| Aspect | Foundation shell today | Proposed workspace |
|---|---|---|
| Radius | `rounded-[2rem]` | `rounded-xl` cards, `rounded-lg` controls |
| Page ground | `stone-100` | `stone-50` page, `white` surfaces, `stone-200` hairlines |
| Sidebar | n/a | `stone-950` — carries the existing dark-hero identity |
| Lime | headings, eyebrows, decoration | **only** primary action + active nav item |
| Type | 4xl/5xl display | `text-sm` body, `text-xs` metadata, `text-2xl` page title |
| Status colour | ad-hoc | strict semantic set, always icon + text + colour |

Semantic status palette, fixed once and used everywhere:

| Meaning | Colour | Icon | Used by |
|---|---|---|---|
| Ready / accepted / completed | `emerald` | check | readiness, imports, runs |
| Warning / stale / accepted-with-warnings | `amber` | triangle | freshness, stale calculation |
| Blocked / rejected / failed / at-risk | `rose` | octagon / alert | blockers, exceptions, stockouts |
| Running / validating | `sky` | spinner | run + upload progress |
| Neutral / unknown / known-empty | `stone` | dash / dot | provenance, empty states |
| Proposal-only | `amber` outline | tag | the persistent banner and every recommendation surface |

Colour is never the sole carrier — every badge ships an icon and a text label.

### D6 — Language: English labels, German source terms verbatim *(open)*

UI chrome, actions and status language in English. Terms that name something in
a source document stay exactly as the source writes them —`Liefertag`,
`Bestelldetails`, storage classes `Frisch` / `TK` / `Kühl` / `RT` — because
the maintainer matches them against the real files. Journey doc §12 lists this
as open; this is the proposed answer.

### D7 — Build order: journey doc §13 *(confirmed by evidence)*

Shell → Data & settings → Location planning → Overview.

This turned out to be a hard dependency rather than a preference. `APP_ENV` is
`development`, while the synthetic seed's master version is scoped to
`prototype`, and `_load_master()` filters by environment. So on this environment
**there is no active master version at all** until a master workbook is imported
and activated — and `GET /locations` returns 404, not an empty list, until then.
Overview and Location planning literally cannot render real data before Data &
settings has been used once.

### D8 — Location selector: plain dropdown *(confirmed)*

6–15 locations expected. A `<select>`-style dropdown listing each location with
its readiness badge — compact, familiar, keyboard-native, and no search
machinery to build or test. Segmented control is too wide at 15; a search
combobox is unjustified below ~20.

---

## 3. Screen blueprints

### 3.1 Application shell

```text
┌─ PROPOSAL BANNER (persistent, full width) ───────────────────────────────┐
├──────────────┬───────────────────────────────────────────────────────────┤
│ P2  Supply   │  Page title                    [env] [api] [user ▾]       │
│              │───────────────────────────────────────────────────────────│
│ ▸ Overview   │                                                           │
│ ▸ Location   │   page content                                            │
│   planning   │                                                           │
│ ▸ Data &     │                                                           │
│   settings   │                                                           │
│              │                                                           │
│ ─────────    │                                                           │
│ prototype    │                                                           │
│ API ● ready  │                                                           │
└──────────────┴───────────────────────────────────────────────────────────┘
```

- Persistent proposal banner above everything, never dismissible. Preview mode
  (D4) adds a second, louder banner above it.
- Exactly three nav destinations. "Location planning" links to
  `/locations/<remembered id>`; with none remembered it links to `/overview`
  with a "choose a location" state rather than guessing.
- Selected location is remembered in a `LocationContext` backed by
  `sessionStorage`, so navigating Overview → Data & settings → Location keeps
  the same location and pre-selects it in the location-scoped upload cards.
- Sidebar collapses to a drawer below `lg`, opened by a header button, with
  focus trap, `Esc` to close, and focus returned to the trigger.
- Footer strip: environment label, compact API/Supabase readiness dot with the
  server's own message on hover/focus, current user email, sign out.
- Skip-to-content link; `<main>` receives focus on route change; page title
  announced via `aria-live="polite"`.

### 3.2 Sign-in

Not a fourth destination — a gate. Email + password via
`signInWithPassword`, session persisted by supabase-js, `onAuthStateChange`
keeps React in sync, sign-out clears it. Three distinct states:

1. **Auth not configured** (`getSupabaseClient()` returns `null`): explain that
   `VITE_SUPABASE_URL` / `VITE_SUPABASE_PUBLISHABLE_KEY` are missing. Do not
   render a login form that cannot work.
2. **Signed out**: the form. No self-sign-up, no password reset, no role UI —
   accounts are admin-created (brief).
3. **Session expired** (any domain 401): clear the session, return to the gate
   with "your session expired, sign in again", and preserve the attempted URL
   for post-login redirect.

### 3.3 Overview — exception-first cockpit

```text
┌ TOP ALERT ───────────────────────────────────────────────────────────────┐
│ ⛔ Ratingen is blocked — no accepted stock import   [ Upload stock → ]    │
└──────────────────────────────────────────────────────────────────────────┘
  ┌ ready ─────┐┌ items at ──┐┌ recs due ──┐┌ blocking ──┐┌ latest run ─┐
  │  2 / 3     ││   7        ││   4        ││   1        ││ 2h ago ✓    │
  │  locations ││   at risk  ││   today    ││   issues   ││ current     │
  └────────────┘└────────────┘└────────────┘└────────────┘└─────────────┘
┌ Locations ───────────────────────────────────────────────────────────────┐
│ Location    Readiness   Items at risk  Latest run     Stock     POs   →  │
│ Ratingen    ⛔ Blocked        —         none          —         —     →  │
│ Köln        ✓ Ready          3         ✓ current 2h  27 Aug    28 Aug →  │
│ Berlin      ⚠ Warnings       4         ⚠ stale 3d    24 Aug    28 Aug →  │
└──────────────────────────────────────────────────────────────────────────┘
┌ Data freshness ──────────────────┐┌ Latest planning activity ────────────┐
│ per location × 4 source groups   ││ recent runs, status, current/stale   │
└──────────────────────────────────┘└──────────────────────────────────────┘
┌ Observed purchase-order activity (secondary, collapsed) ─────────────────┐
```

- **Top alert** is the single highest-severity item across all locations, with
  one corrective action. When nothing is wrong it becomes a calm confirmation
  strip, not an empty box.
- **Five KPI cards** map exactly to `overview.kpis`. Every card is a link into
  the view that explains it; a KPI that does not navigate is decoration and is
  cut. Cards show "—" with a "no current run" note rather than `0` when the
  underlying run is stale or missing, because `0` is a claim.
- **Location table** is the workhorse: readiness badge, items at risk + earliest
  risk date, latest run status with **current/stale** label, stock `counted_at`,
  PO imported-at, drill-down. Sorted by severity by default.
- **Data freshness panel** and **latest activity** are secondary; observed PO
  activity is tertiary and collapsed.
- Data sourcing: `GET /overview` for KPIs and risk counts, plus `GET /locations`
  for names/timezones, plus one `GET /locations/{id}/planning-status` per
  location for the freshness columns. See §6 for the contract enhancement that
  would collapse this into one call.
- Explicitly absent: actual waste, actual OOS, supplier service level, any
  mixed-unit total quantity. Cap/shelf-life evidence is labelled "attention",
  never "waste".

### 3.4 Location planning

```text
┌ [Köln ▾]  Europe/Berlin · active            [ Compute latest recommendation ]│
│ Master v4 ✓ │ Forecast → 04 Oct ✓ │ Stock 27 Aug 14:00 ⚠ 2d │ POs 28 Aug ✓ │
│                                              Run: ✓ completed · current      │
├──────────────────────────────────────────────────────────────────────────────┤
│ [ Risk & stock ]  [ Open POs ]  [ Recommendation ]                           │
```

- **Header**: location selector — a plain dropdown listing each location with
  its readiness badge (D8, 6–15 locations) — plus name, timezone, active badge;
  primary run button on the right at all breakpoints.
- **Freshness strip**: five chips, each showing source time *and* import time
  where both exist, each clickable to the matching Data & settings card.
- **Preflight/blockers**: when `ready === false`, the run button is disabled and
  the returned blocker reason is rendered **as visible text beside the button**,
  not only as a tooltip, with a remedy link per blocker.
- **Tabs are URL state** (`?tab=risk|pos|recommendation`, plus `?filter=`), so
  Overview KPI cards can deep-link and a refresh keeps the view.
- **Run interaction**: `idle → submitting → completed | blocked | failed`.
  Button disabled while in flight plus an in-flight guard ref, so a double click
  or an `Enter` repeat cannot create two runs. An explicit "this runs the full
  calculation and can take a while — keep this tab open" note while submitting,
  `aria-live` announcement on completion. `planning_as_of_at` defaults to now in
  the location's timezone; an advanced disclosure allows an explicit cutoff.
  A persisted `blocked`/`failed` run renders its exceptions, not a crash.

**Tab A — Risk & stock** (default): summary chips (stockout risk, unavoidable
pre-arrival shortage, overdue open POs, cap/cover attention), then an item table
— item, storage class, usable stock, expected receipts, demand over horizon,
first stockout date, projected closing balance, severity. Filters: risk only,
storage class, supplier/channel, item search. Row opens a drawer with the
item's projected-balance timeline drawn from `projection_days`, rendered only
for the opened item.

**Tab B — Open POs**: a permanent, non-dismissible caveat that these lines are
derived from imported PDFs and are not live supplier confirmation. Table of
document ID, supplier, item, ordered date, `Liefertag` / expected receipt, open
quantity with unit, mapping state, source import time. Filters: due soon,
future, missing date (quarantined), mapping issue. Link to refresh PO PDFs.

**Tab C — Recommendation**: run metadata block (run id, planning-as-of,
code/policy/master/input versions, proposal status, current-vs-stale), then the
recommendation table — order date, expected receipt, supplier, item, proposed
order units + unit type, packs, grams, exception indicator. Filters: due now,
delivery date, storage class, supplier, exception.

**The derivation drawer is the highest-value screen in the product.** It is the
answer to "why should I believe this number", so it gets real design attention:
a vertical waterfall down the `planning_lines` chain —

```text
  gross requirement           12 400 g
  × yield factor 1.05         13 020 g      [policy default]
  + safety stock               1 800 g      [policy default]
  − usable on hand           − 4 200 g      [observed · counted 27 Aug 14:00]
  − open PO due              − 2 000 g      [observed · imported 28 Aug 09:12]
  ────────────────────────────────────
  raw order                    8 620 g
  shelf-life cap              (none)
  max-cover cap               6 000 g  ⚠ binding — capped
  ────────────────────────────────────
  capped order                 6 000 g
  MOQ 2 · case multiple 1
  ────────────────────────────────────
  PROPOSAL                     3 order units  (6 kg, 6 packs)
```

Each row shows the value, its unit, and its provenance tag. Binding caps and
MOQ inflation are called out inline, because AGENTS.md requires a binding cap to
be visible rather than hidden. Nothing here is recomputed in TypeScript — every
number is a field on the persisted line, formatted only.

**Downloads**: CSV and JSON buttons fetch with the bearer token, turn the
response into a Blob, and trigger a download. Progress and failure states are
explicit; the file is never reconstructed in the browser.

### 3.5 Data & settings

Two groups, in this order:

**Group 1 — Planning inputs** (four upload cards, 2×2 on desktop):

| Card | Scope | Endpoint | Files |
|---|---|---|---|
| Master data & rules | Global | `POST /imports/master-data` | 1 × `.xlsx` |
| Forecast, menu & BOM | Global | `POST /imports/planning-input` | 1 × `.xlsx` |
| Current stock | Location | `POST /imports/stock` | 1 × `.xlsx` + `location_id` |
| Purchase-order PDFs | Location | `POST /imports/purchase-orders` | n × `.pdf` + `location_id` + `as_of_at` |

Each card shows: scope chip, dropzone, current accepted version, **source time
and import time as two separate stamps**, coverage range, record/warning/error
counts, status badge, a "Review issues" expander rendering
`{code, severity, dataset, record_ref, message, remedy}` as an actionable list,
and a version-history disclosure from `GET /imports?dataset_type=…`.

Upload states: empty → selected → uploading → validating → accepted /
accepted-with-warnings / rejected. Client-side extension and size checks are
labelled as a fast pre-check, never as validation. Copy states plainly that
uploading never runs planning and never activates a master draft.

**Group 2 — Maintained data & rules**: master version list (label, status,
created, activated by/at, source import) with an **Activate** action behind a
confirmation dialog that names the version being replaced. Below it, clearly
disabled, labelled-as-planned placeholders for item/policy, location/delivery
rule, menu calendar and BOM editing — per the brief, a visible future state
rather than an invented API.

Stock and observed PO rows are summary-only everywhere. The page says so:
correction means re-export, re-upload, or fixing a maintained mapping.

---

## 4. Component inventory

Follows journey doc §11 as a boundary, not as a design-system mandate.

```text
apps/web/src/
├── app/
│   ├── AppShell.tsx            routes.tsx  RequireAuth.tsx
│   ├── AuthProvider.tsx        LocationProvider.tsx
├── components/                 SideNavigation  PageHeader  StatusBadge
│                               FreshnessStamp  ProvenanceTag  KpiCard
│                               DataTable  EmptyState  ErrorSummary
│                               ActionableAlert  Drawer  ConfirmDialog
│                               ProposalBanner
├── features/
│   ├── auth/                   SignInPage
│   ├── overview/               OverviewPage  TopAlert  KpiRow
│   │                           LocationRiskTable  DataFreshnessPanel
│   │                           LatestRunActivity  ObservedPoActivity
│   ├── location-planning/      LocationPlanningPage  LocationSelector
│   │                           FreshnessStrip  RunAction  BlockerList
│   │                           RiskStockTable  ItemProjectionDrawer
│   │                           OpenPoTable  RecommendationTable
│   │                           DerivationDrawer  DownloadActions
│   └── data-settings/          DataSettingsPage  UploadCard  FileDropzone
│                               ImportIssueList  ImportHistory
│                               MasterVersionList  ActivateVersionDialog
│                               PlannedFeatureCard
└── lib/                        apiClient.ts  types.ts  errors.ts
                                formatting.ts  useApiResource.ts
                                useMutation.ts  supabase.ts  fixtures/
```

Two rules that are enforced in the type signatures rather than by review:

- `ActionableAlert` requires an `action` prop — an alert without a remedy will
  not compile.
- Quantity formatters require an explicit unit argument, so a mixed-unit total
  cannot be produced by accident.

---

## 5. Work packages

Each package ends with `pnpm check` green and this file plus the scratchpad
updated. Master-backlog items are ticked only after the mapped package is
verified.

### WP0 — Foundation (no visible UI)  → 2D:shell prerequisites

> **Complete and verified 2026-08-29.** `pnpm check` — lint, typecheck, tests,
> build — passes.

- [x] Add `react-router-dom` 7.18.2 (D1) and the Vitest 4 / Testing Library
      devDependencies (D3).
- [x] Add `vitest.config.ts` (jsdom, `jest-dom` setup, `threads` pool — the
      default fork pool intermittently timed out spawning workers on Windows)
      and cover it from `tsconfig.node.json`.
- [x] `check` now chains `eslint . && tsc -b && vitest run && vite build`
      directly instead of re-invoking `pnpm`, so it runs under any package
      manager and does not require a `pnpm` shim on PATH.
- [x] Create the `lib/` portion of the folder structure in §4.
- [x] `lib/types.ts` — hand-written TypeScript types for every response shape
      listed in the scratchpad's API section. Numeric fields are typed
      `number | string`, because Python `Decimal` serialization and PostgREST
      can each produce either; `toNumber()` normalizes.
- [x] `lib/errors.ts` — typed error classes for 401 / 403 / 404 / 409 / 422 /
      503 / network, parsing **both** the `{error:{code,message,details}}`
      envelope and FastAPI's `detail` validation array.
- [x] `lib/apiClient.ts` — one client: base URL, bearer injection from the live
      session via a registered token provider (no import cycle with the auth
      provider), JSON requests via `fetch`, uploads via `XMLHttpRequest` for
      real progress on multi-megabyte PDF batches, authenticated blob download
      with `Content-Disposition` filename parsing, abort support, and a global
      unauthorized handler that never retries.
- [x] `lib/useApiResource.ts` + `useMutation.ts` (D2). The mutation hook's
      in-flight guard is a ref, not rendered state, so a rapid second click
      cannot start a second planning run before React re-renders.
- [x] `lib/formatting.ts` — timezone-aware date/time with the zone name always
      shown, relative age, `toNumber` normalization, and quantity formatters
      that **require** an explicit unit argument so a mixed-unit total cannot be
      produced by accident.
- [x] Tests: error parsing for each status code and both envelope shapes,
      bearer-header attachment, no-session fail-closed, unit-formatter guards.
- [x] `pnpm check` green.

**Found while testing:** a 200 response with an unparseable body was resolving
as success with `null` data, which a page would have rendered as "no data".
Success and error bodies now use separate parsers — the error path still never
throws, but the success path raises `malformed_response` instead of silently
handing back nothing.

### WP1 — Shell, auth and navigation  → 2D bullet 2, 2B session behavior

> **Complete and verified 2026-08-29.** `pnpm check` passes; the sign-in page
> was confirmed in a real browser against the live API and Supabase.

- [x] `AuthProvider`: `signInWithPassword`, `onAuthStateChange`, token access,
      sign-out, and the "Auth not configured" state. The token provider is
      registered at module scope, not in an effect, so a request issued during
      the first render still finds one.
- [x] `RequireAuth` route guard with post-login redirect to the attempted URL,
      and a neutral "restoring your session" state so the sign-in form does not
      flash on every load for an already-signed-in maintainer.
- [x] `SignInPage` with the three states in §3.2 and Supabase's terse error
      messages translated into plain language.
- [x] `AppShell`: three-route router, side navigation with an active state
      announced in text as well as colour, responsive drawer with focus trap,
      `Esc`, and focus returned to the trigger, persistent proposal banner,
      skip link, focus moved to `<main>` on navigation, and an
      environment/API-readiness footer plus user and sign-out in the header.
- [x] `SelectedLocationProvider` remembering the selected location in
      `sessionStorage`, with every storage access guarded.
- [x] Global 401 handling: clear session, route to the gate, show the reason,
      never retry.
- [x] 503 / readiness `degraded` presented as "dependency unavailable", visibly
      distinct from "no data", with the reason spelled out in `ErrorState`.
- [x] **First-run state**: a 404 from `GET /locations` renders "No active
      master data yet" with a link to Data & settings, not an error.
- [x] Tests (24 across shell, sign-in and chooser): sign-in blocks domain
      routes; exactly three nav items; active state carried in text; 401
      mid-session returns to the gate after exactly one request; proposal
      banner present and undismissable; drawer opens and closes by keyboard
      with focus restored; readiness distinguishes unconfigured from
      unreachable; the 404 first-run state is not an error.
- [x] Removed the superseded status shell (`App.tsx`, `StatusCard.tsx`,
      `lib/api.ts`) rather than leaving dead code behind the new one.
- [x] Added a SPA rewrite to `vercel.json`; without it a deep link such as
      `/locations/LOC_X` would 404 on Vercel.

### WP2 — Shared primitives  → 2D bullet 3, 2H accessibility

- [ ] `StatusBadge` for the six readiness states in journey doc §8, always icon
      + text + colour.
- [ ] `FreshnessStamp` rendering source time and import time as two labelled
      values with relative age, in the location's timezone.
- [ ] `ProvenanceTag` for observed / manual / proposal-default / unavailable /
      known-empty, with the canonical value in the tooltip.
- [ ] `KpiCard` (link-required), `DataTable` (sortable, keyboard-navigable,
      stacked-card layout below `md`), `EmptyState`, `ErrorSummary`,
      `ActionableAlert` (action-required), `Drawer`, `ConfirmDialog`.
- [ ] Tests: badge renders text not only colour; freshness shows both stamps;
      table sorts by keyboard; drawer traps and restores focus.

### WP3 — Data & settings  → master backlog 2D (all remaining bullets)

> **Complete and verified 2026-08-29.** `pnpm check` passes with 82 tests, and
> the page was confirmed in a real browser against the live API.

- [x] Page scaffold with the two groups and the location-scope selector, which
      renders even when `GET /locations` 404s — this page is where that gets
      fixed, so it must not be blocked by it.
- [x] Four `UploadCard`s wired to the four import endpoints, **numbered as a
      sequence** rather than presented as peers, each computing its own
      prerequisite state and naming the step that unblocks it.
- [x] PO `as_of_at` input, converted to a timezone-aware value because the API
      rejects a naive one, with copy explaining it decides which lines are open.
- [x] `FileDropzone` with drag/drop, a real keyboard-operable file input, and
      an extension pre-check explicitly labelled as a filename check rather
      than validation.
- [x] Upload state machine: idle → uploading (real percentage via
      `XMLHttpRequest`) → validating on the server → accepted /
      accepted-with-warnings / rejected, announced through `aria-live`.
- [x] Accepted-with-warnings is never presented as a plain success, and a
      **duplicate** upload says the content matched an existing import rather
      than claiming a new one — the API de-duplicates on content hash and
      returns the older row.
- [x] A rejection says "nothing was changed" and shows the rejected import id,
      since the failed attempt is still persisted and auditable.
- [x] `ImportIssueList` renders code/severity/dataset/record and the
      **remedy**, blockers first.
- [x] Import history per dataset and scope, including rejected attempts.
- [x] `MasterVersionList` with a confirmation dialog that names the version
      being replaced and states that past runs stay reproducible; activation
      errors surface the server's conflict message.
- [ ] Surface master activation as the final action inside Step 1: show **Draft
      ready**, provide **Activate master data and continue** beside the accepted
      upload, change the state to **Active** afterward, and make Step 2's blocker
      link or move focus to that action. Keep version history below for audit and
      replacement rather than making it the only place to continue.
- [x] `PlannedFeatureCard` placeholders for item/policy, menu and BOM editing,
      visibly disabled with the reason each is deferred.
- [x] Copy stating uploading never runs planning and never activates a draft
      (stated once, at the top — repeating it on four cards was noise).
- [x] Tests (27): the four-step prerequisite chain including the stock-needs-
      planning-workbook rule; current-import selection across statuses and
      location scopes; every upload outcome; remedies shown; activation
      requires confirmation and activates only the confirmed version; no
      inline editing of observed rows.

**Found while building:** the four uploads are a strict sequence, not four
independent cards. The planning workbook validates against the *active* master
version, and stock is refused with `409 planning_input_missing` until a planning
workbook covers that location. Four equal cards would have walked a maintainer
on a fresh environment into a chain of conflicts, so the cards are numbered and
each explains its own blocker before the API has to.

### Maintainer horizon/MHD review — correction tranche (2026-08-30)

- [x] Backend actionable-horizon/MHD contract supplied and tested. Migration
      `004` must be applied before the next connected v2 run; React must use
      `actionable_risk_status`, not classify every full-forecast
      `first_stockout_date` as current risk.
- [ ] Replace the primary full-forecast `Needed` value with server-returned
      demand for the active protection window and show the coverage end.
- [ ] Default the stock chart to the decision window; make four-week/full-
      forecast controls display-only.
- [ ] Label existing and proposed receipt quantities directly and replace the
      smoothed curve with a discrete daily representation.
- [ ] Present cumulative uncovered demand separately from physical usable stock.
- [ ] Show server-returned MHD evidence: expiry, cap basis, projected residual,
      and incomplete forecast. Do not infer shelf-life safety in TypeScript.
- [ ] Surface lead time, review cadence, protection end, and next review as
      versioned policy context. Do not add one global ad-hoc run-horizon slider.
- [ ] Update `PlanningRunResponse` for `planning_line_explanations` and
      `explanation_context`; join by `planning_line_id` and show the exact
      item/policy/delivery-rule version used by the run.
- [ ] Audit and replace every old risk/KPI/label/helper listed in the Claude
      brief's mandatory v2 UI impact table; update fixtures and tests rather
      than adapting only the visible demo row.
- [ ] Add progressive disclosure: a concise scan layer, focusable metric
      definitions, and a complete derivation/source-lineage drawer. Never hide
      blockers, approximations, evidence gaps or remedies in hover-only copy.
- [ ] State the current evidence limits in the drawer: no exact existing-stock
      lot MHD, no historical daily balance, and no persisted dish/silo
      contribution breakdown. Do not infer any of these in TypeScript.

Backend/engine prerequisites and evidence are in
`docs/plans/planning_horizon_and_shelf_life_correction_plan.md`.

**Also found:** file state was initially split between the page and the card,
so the upload button could never enable. The card now owns it.

### WP4 — Location planning  → master backlog 2E (remaining bullets)

> **Complete and verified 2026-08-30.** `pnpm check` passes with 101 tests, and
> a real scenario run was computed end to end against the live API.

- [x] Page scaffold, location selector, `?tab=` URL state so Overview can deep
      link and a refresh keeps the view, and the no-location case falling back
      to the chooser.
- [x] `FreshnessStrip` — master version, forecast horizon, stock age, order
      import age and run currency on one line, each source showing how old it
      is rather than only that it exists.
- [x] `BlockerList` plus a disabled run button whose reason is visible text,
      not a tooltip on a control that cannot be focused.
- [x] `RunAction` with duplicate-submit prevention, "this can take a while,
      keep the tab open" while running, an `aria-live` announcement, and a
      persisted blocked/failed run rendered rather than treated as an error.
- [x] `RiskStockTab` from `netting_results`, sorted worst-first, with an
      at-risk filter and a row drawer carrying the projected-balance chart.
- [x] `ItemProjectionChart` drawn for the opened item only — the run payload
      carries every item across every horizon day.
- [x] `OpenPoTab` with the permanent "read from imported PDFs, not confirmed by
      the supplier" caveat, an open-only filter, undated lines called out, and
      a 404 rendered as "never imported" rather than as an error.
- [x] `RecommendationTab` with run id, proposal count, and a closing line
      stating that placing an order happens elsewhere.
- [x] `DerivationDrawer` — the full chain in the order the engine applies it,
      provenance on the policy-derived inputs, absent caps shown as "none"
      rather than zero, and the engine's own exceptions quoted underneath.
- [x] CSV and JSON downloads through the authenticated blob path.
- [x] Tests (19): the pure risk and derivation logic including a line whose
      numbers deliberately do not add up, plus page behaviour for blocked runs,
      duplicate submission, staleness, the drawer, the purchase-order empty
      state, and the absence of any approve/send/place-order control.

**The boundary that shaped this:** the derivation drawer never recomputes.
Every number is a stored field, and the claim that a cap bound or an order was
inflated to a minimum comes from the engine's own `planning_exceptions`, not
from a comparison made in the browser. A test feeds a line whose fields are
mutually inconsistent and asserts the UI still shows what the engine stored — if
those ever disagree the bug is in the engine, and quietly reconciling it here
would hide it.

**Found while verifying live:** while the last run was being fetched the page
said "No result yet", which on a slow load could push a maintainer into starting
a second synchronous calculation. Loading, failed-to-load and genuinely-absent
are now three distinct states.

### WP5 — Overview  → master backlog 2F (remaining bullets)

- [ ] `TopAlert` severity selection across locations, with corrective action
      and a calm all-clear variant.
- [ ] `KpiRow` from `overview.kpis`, every card a link, "—" instead of `0`
      where no current run backs the number.
- [ ] `LocationRiskTable` with readiness, risk counts, current/stale run label,
      freshness columns, and drill-down.
- [ ] `DataFreshnessPanel` and `LatestRunActivity`.
- [ ] `ObservedPoActivity` as a collapsed secondary section.
- [ ] Render the complete `/overview` read model with page-level failure
      handling. The backend now includes location labels, source freshness,
      current-run status, risk counts, and earliest actionable-risk dates, so
      do not issue one `planning-status` request per location.
- [ ] Tests: stale run is labelled stale and its KPIs are not presented as
      current; no waste/OOS/mixed-unit total appears anywhere; each KPI card
      navigates.

### WP6 — Hardening, verification, handoff  → 2H (frontend parts)

- [ ] Sweep every required state across all three pages: loading, empty,
      unauthenticated, unavailable, validation error, blocked,
      accepted-with-warnings, stale calculation, completed proposal.
- [ ] Accessibility pass: keyboard-only traversal of all three pages, focus
      order and visible focus, `aria-live` regions, status without colour,
      skip link, drawer/dialog focus management.
- [ ] Responsive pass at 360 / 768 / 1024 / 1440 px.
- [ ] `pnpm check` (lint + typecheck + test + build) green.
- [ ] Connected smoke test against the running local API. Readiness, migration
      003 and credentials were verified (2026-08-29); migration 004 must now be
      applied before a v2 run. The remaining data prerequisites are a safe Auth
      user and a master workbook safe to import into `development`. Record
      honestly what was and was not exercised—no live-success claims without
      evidence.
- [ ] Update this backlog, the scratchpad, master backlog 2D/2E/2F, and
      `MEMORY.md` if a durable decision changed.

### WP7 — Optional grounded LLM assistance after the core UI

This is a post-core enhancement, not a dependency for the 2 September demo or
the first feedback cycle. The Python engine and persisted derivation remain the
only calculation authority.

- [ ] Add an optional **Executive summary** panel on Overview that turns the
      current `/overview` readiness, staleness, risk and blocker fields into a
      short prioritised paragraph with links to the exact locations/actions.
      It must say when data or a current run is missing instead of filling gaps.
- [ ] Add an optional **Explain this quantity** action beside a recommendation.
      Ground it only in the persisted planning line, item policy, netting row,
      accepted open POs, daily demand/receipts and engine exceptions: demand to
      protect, stock, POs, lead/review horizon, shelf life, max cover, MOQ/case
      and rounding. The model may simplify wording but may not recompute or
      alter the quantity.
- [ ] Keep the existing derivation drawer and source lineage visible as the
      deterministic fallback. Label generated text, retain the input/run
      version and generation time, and fail without blocking the normal UI.
- [ ] Decide provider, minimum normalized payload, data classification,
      retention/logging, latency and cost limits before enabling the feature.
      Do not send raw XLSX/PDF contents or credentials to a model.
- [ ] Build a small evaluation set from validated synthetic scenarios,
      including the two-location 2 September packet: Berlin pre-arrival pod
      risk, Berlin shelf/max/rounding cases, Hamburg PO-covered zero orders,
      stale runs, missing fields and conflicting exceptions. Reject unsupported
      claims, invented causes, hidden uncertainty and any ordering/approval
      language.

---

## 6. Contract observations for Codex (frontend-blocking? no)

Documented per the brief's rule rather than worked around with a parallel
backend path. None of these blocks WP0–WP5.

1. **Resolved 2026-08-30 — `GET /api/v1/overview` supplies the complete
   per-location read model.** `locations[]` now includes `location_name`,
   `timezone`, `earliest_risk_date`, and
   `sources: {master_data_version, planning_input, stock, purchase_orders}`;
   `kpis` also includes `locations_at_risk`. Claude should consume these fields
   directly rather than constructing a browser-side `1 + N` request path.
2. **`GET /locations/{id}/inventory` and `/purchase-orders` return 404 for
   "not imported yet".** This conflates "known empty" with "not found", which
   the journey doc §8 separates. A 200 with `source_import: null` and an empty
   list would let the UI distinguish them without inferring from the status
   code. The frontend will special-case the 404 in the meantime.
3. **Resolved backend side — deterministic planning-run retry is idempotent.**
   The engine derives `run_id` from the complete input/policy hash and the
   atomic persistence RPC returns the existing run for the same ID/hash while
   rejecting an ID/hash collision. The frontend must still disable duplicate
   submission while a synchronous request is in flight, but it does not need
   to invent an idempotency key.
4. **No historical daily balance is persisted.** `planning_projection_days`
   starts at the run date, so the item chart cannot show any context before it.
   `inventory_snapshots` holds a sparse per-import count, which would mislead if
   drawn as one series alongside a projection. A stored daily actual-balance
   series, or an endpoint returning past snapshots as discrete points, would let
   the chart show where stock has actually been.
5. **`GET /planning-runs/{run_id}` always returns all `projection_days`.** For
   many items over a long horizon this payload grows without bound. A
   `?include=` parameter, or a separate
   `/planning-runs/{run_id}/projections?item_id=` endpoint, would let the UI
   fetch the timeline only for the item the maintainer opened.

---

## 7. Definition of done

The slice is complete when a maintainer can, without the frontend duplicating
backend logic:

- [ ] sign in, and see honest state when Auth or the API is not configured;
- [ ] understand system state from Overview in seconds, including what is stale;
- [ ] upload each of the four source groups and read actionable validation
      results;
- [ ] activate a master draft explicitly;
- [ ] run one location, with blockers explained and duplicates prevented;
- [ ] reopen the persisted result after a refresh;
- [ ] inspect risks, open POs, recommendations and the full derivation of any
      proposed quantity;
- [ ] download the server-generated CSV and JSON;
- [ ] and see, on every screen, that nothing here places an order.

---

## 8. Dated progress

- 2026-08-31 — **Adopted the v2 backend contract** (Codex `b5c819d`). Treated as
  a semantic change, not a type upgrade. Deleted three TypeScript helpers whose
  business meaning came from the wrong field — `riskLevel`, `daysOfCover`,
  `horizonDays` — and rebuilt risk on the explicit `actionable_risk_status`.
  Relabelled Needed → **To protect** (planning-line demand), Lasts →
  **Covered through**, and the negative ending balance → **uncovered demand**.
  Added shelf-life evidence, constraint status and policy context to the drawer,
  a step-geometry chart with labelled receipts and a decision/full-forecast
  zoom, and an `InfoHint` definition layer. Verified live on a fresh v2 run: the
  item that previously read "Runs out — at risk" now reads **Replan later**,
  with the +2 kg horizon-end balance matching Codex's oracle. `pnpm check`
  green with 117 tests. **WP5 must consume the new complete `/overview` read
  model directly — no per-location `planning-status` fan-out.**

- 2026-08-30 — **Codex backend correction complete.** The API now returns
  explicit item-specific risk status/window and candidate expiry, cap basis,
  evidence completeness, residual at expiry, binding constraint, and safe
  rounding outcome. Run/Overview counts no longer use full-forecast
  `first_stockout_date`. Exact packet replay `improved-ded5498f7198` is covered
  through 7 Sep, has a future-context shortage on 10 Sep, and keeps the safe
  6-pack proposal with zero candidate residual at estimated expiry. Claude can
  implement the unchecked presentation items in the correction tranche and
  WP5 after migration 004 is applied; no TypeScript business logic is needed.

- 2026-08-30 — **WP4 complete and verified live.** Signed in against the real
  API, computed a scenario run for `LOC_UI_DEMO_001` from Codex's test packet,
  and confirmed the whole page against real persisted data: freshness strip,
  risk table (1 of 1 items runs out, first stockout 11 Sep, ends at −31 kg),
  proposals (7 order units from TRANSGOURMET), and the derivation drawer
  showing the full chain with the engine's own rounding exception quoted.
  Note the proposal is 7 units rather than the packet's documented 6: the run
  used "now" as the cutoff instead of the packet's `2026-08-29T12:00:00+02:00`,
  and the packet's README states a later cutoff legitimately changes the
  result. Two defects found and fixed while verifying — a loading run reported
  as "no result yet", and raw ISO dates in the drawer.

- 2026-08-29 — Read the brief and all nine referenced sources; verified the API
  response shapes against `services.py` and migrations 001/002 rather than
  assuming the documented contract; recorded findings in
  `docs/scratchpads/ui_implementation.md`; wrote this plan. **No code written.**
- 2026-08-29 — Maintainer review round 1. Confirmed D2 (no cache), D5 (workspace
  density), D8 (dropdown selector, 6–15 locations). Maintainer corrected the
  premise behind D4: migration 003 and Auth are live. Verified that directly —
  local API returned readiness `ready` ("all required backend migrations are
  reachable") and a proper `401 invalid_session` on domain routes — so **D4 is
  dropped, no preview mode will be built.** The probe also surfaced the
  `APP_ENV=development` vs seed-`prototype` scoping gotcha, which turns D7's
  data-first order into a hard dependency and adds a required first-run state.
  D1, D3 and D6 still open. **Still no code written.**
- 2026-08-29 — Started WP0 and hit a hard blocker: **Node.js is not installed
  on this machine** (no `node`/`npm`/`pnpm`/`corepack` anywhere, though
  `node_modules` was populated on 2026-08-28). Cannot install dependencies,
  type-check, lint, test, or run the dev server. Wrote the five
  dependency-free library files anyway — `types.ts`, `errors.ts`,
  `apiClient.ts`, `formatting.ts`, `useApiResource.ts`, `useMutation.ts` — all
  of which need only React and the browser platform. **None of them have been
  compiled or executed.** WP1 onward needs `react-router-dom`, so it is blocked
  until Node is available. Maintainer decision needed on installing Node
  (`winget install OpenJS.NodeJS.LTS`), since the machine is MDM-managed.
- 2026-08-29 — **Node blocker resolved** (maintainer installed Node 24.19.0).
  `corepack enable` needs administrator rights and failed, so `pnpm` has no
  shim on PATH; `corepack pnpm <script>` works, and `check` no longer depends on
  a `pnpm` shim. **WP0 and WP1 complete and verified**: `pnpm check` green with
  55 tests. Live browser check against the running API confirmed the sign-in
  page renders, the gate blocks `/data` when signed out, mobile layout holds at
  375 px, no console errors, and the status line reports the real chain
  (`API ready · development`, all migrations reachable). Next: WP3.
- 2026-08-29 — **Authenticated journey verified end to end.** The maintainer
  signed in with a real admin-created Supabase account. `GET /api/v1/locations`
  returned 404 as predicted for a fresh `development` environment, and the UI
  rendered the first-run state rather than an error. Supabase Auth → session →
  bearer token → FastAPI verification → domain read → typed error → correct
  state all confirmed against the live stack. Starting WP3.
- 2026-08-29 — Decided against building a self-signup page. The brief forbids
  public self-sign-up, and FastAPI treats every valid project user as a
  maintainer, so a signup form on a deployed internal tool would let anyone who
  finds the URL mint a maintainer account. The maintainer creates the first user
  in the Supabase dashboard; signing in through our UI still proves the whole
  chain (Supabase Auth → session → bearer → FastAPI verification → domain data).
