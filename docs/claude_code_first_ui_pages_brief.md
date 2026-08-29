# Claude Code brief — build the connected maintainer UI

Copy the instruction below into Claude Code from the repository root.

---

You are working in the `demand_forcasting` repository. Build the first
connected React/Tailwind maintainer interface for Phase 2 supply planning.
This handover is deliberately **frontend-only**: the FastAPI/Auth/Supabase
backend vertical slice is already owned and implemented by Codex. Do not
rebuild Python repositories, parsers, authentication verification, migrations,
planning orchestration, or KPI calculations in React.

## Read before editing

Read these files in order:

1. `AGENTS.md` — mandatory repository boundaries and checks.
2. `MEMORY.md` — durable status and proposal/operational distinctions.
3. `docs/descriptions/ui_maintainer_journey_and_page_plan.md` — authoritative
   three-page journey, information hierarchy, KPI meanings, page states, and
   component map.
4. `docs/descriptions/ui_api_and_persistence_foundation.md` — runtime,
   security, environment, persistence, and deployment boundaries.
5. `apps/api/supply_planning_api/routes.py` and the generated `/docs` OpenAPI
   page — implemented HTTP contract.
6. `apps/api/supply_planning_api/schemas.py` — planning-run request and common
   response/error shapes.
7. `apps/web/src/`, `apps/web/package.json`, and `apps/web/.env.example` — the
   current React/TypeScript/Vite/Tailwind status shell and lazy Supabase client.
8. `docs/plans/phase2_supply_planning_master_backlog.md` — Milestone 2D UI
   scope and frontend follow-ups.
9. `docs/scratchpads/ui_and_supabase_foundation.md` — recent facts and known
   external setup gaps; it is supporting context, not a product spec.

Inspect the working tree before editing and preserve unrelated changes.

## Backend state to rely on

The backend now provides:

- Supabase access-token verification on every domain route; public health and
  readiness routes remain unauthenticated.
- Server-only PostgREST repositories; the browser must not read or write the
  domain tables directly.
- Controlled master/planning XLSX, stock XLSX, and cumulative PO PDF imports
  using the existing Python adapters, with request-scoped cleanup.
- Immutable accepted source versions and master-version activation.
- One synchronous scenario planning run using the existing pure engine.
- Atomic persistence of selected inputs, lines, recommendations, exceptions,
  netting summaries, and daily projections.
- Overview, location/readiness, inventory, PO, import, run, risk,
  recommendation, and CSV/JSON download endpoints.

The maintainer reports migrations 001 and 002 were applied in Supabase. Before
connected write testing, they must also apply:

- `supabase/migrations/202608290003_ui_backend_transactions.sql`

Assume that migration is applied for UI implementation. If readiness says it
is missing, show the non-secret blocker and tell the maintainer; do not change
the backend or create replacement tables. Real Supabase/Render/Vercel values
may still be absent locally, so connected mode must fail honestly rather than
silently falling back to demo data.

## Goal

Implement a cohesive, responsive internal workspace with persistent desktop
side navigation and a small-screen drawer:

- `/overview` — **Overview**
- `/locations/:locationId` — **Location planning**
- `/data` — **Data & settings**

The normal journey is:

1. Sign in and open Overview.
2. See whether locations and source data are ready/current and where risk or a
   blocker exists.
3. Go to Data & settings to upload or correct the relevant source.
4. Open a location, review the exact selected inputs, and compute one latest
   scenario recommendation.
5. Review risks, observed POs, recommendations, derivations, and exceptions;
   download CSV/JSON.
6. Return to Overview and see the latest current persisted result. A run using
   older inputs must be shown as stale.

Every recommendation remains visibly **proposal-only**. Nothing in this UI
places, approves, sends, or tracks a supplier order.

## Auth and API client

- Use `getSupabaseClient()` in `apps/web/src/lib/supabase.ts` for Auth only.
- Implement email/password sign-in with `signInWithPassword`, persisted session,
  and sign-out. Accounts are admin-created in Supabase for this prototype; do
  not add public self-sign-up or role management. Every valid project user is
  temporarily treated as a maintainer by FastAPI.
- Obtain the current session access token and send
  `Authorization: Bearer <access_token>` on every domain API request.
- On `401`, clear/refresh the session and present a sign-in action. Treat
  `503` as unavailable configuration/dependency, not empty business data.
- Build one typed API client. Handle planner-facing errors shaped as
  `{ error: { code, message, details } }` and ordinary FastAPI request
  validation details without exposing stack traces.
- Keep `/api/v1/health`, `/api/v1/readiness`, and the existing environment/
  proposal status visible in a compact, non-distracting form.
- Never send `SUPABASE_SECRET_KEY` to the browser. Only the
  `VITE_SUPABASE_*` values are browser-safe.

The full route and multipart contract is in `routes.py` and `/docs`. Important
groups are:

- `GET /api/v1/me`, `/locations`, `/overview`
- `GET /api/v1/locations/{location_id}/planning-status`, `/inventory`,
  `/purchase-orders`
- `GET /api/v1/imports`, `/imports/{import_id}`
- `POST /api/v1/imports/master-data` with multipart `file`
- `POST /api/v1/imports/planning-input` with multipart `file`
- `POST /api/v1/imports/stock` with multipart `file` and `location_id`
- `POST /api/v1/imports/purchase-orders` with multipart `files`, `location_id`,
  and timezone-aware `as_of_at`
- `GET /api/v1/master-data/versions` and
  `POST /api/v1/master-data/versions/{version_id}/activate`
- `POST /api/v1/planning-runs` with `location_id`, timezone-aware
  `planning_as_of_at`, `run_mode: "scenario"`, and optional visible source IDs
- `GET /api/v1/planning-runs/{run_id}`, `/recommendations`, `/risks`,
  `/export.csv`, and `/export.json`

Use server-returned KPIs, risks, derivations, statuses, provenance, versions,
and projections. Formatting dates/units in React is expected; recomputing
planning or KPI semantics is not.

## Pages and component priorities

### Application shell

- Persistent proposal/unapproved banner.
- Side navigation with exactly the three destinations above.
- Environment/API/data status, current user, and sign-out.
- Preserve the selected location across navigation where practical.
- Accessible active states, keyboard/focus behavior, text plus icon/status
  cues, and responsive navigation.

### Overview

Build the exception-first hierarchy from section 5 of the journey document:

- highest-severity readiness/blocker alert and corrective action;
- compact KPI cards using the `/overview` response;
- location readiness/risk table with drill-down;
- source freshness/current-run information;
- latest planning activity and secondary observed open-PO activity.

Do not display actual waste, actual OOS, or mixed-unit total quantities. Cap or
shelf-life evidence is only potential attention/risk.

### Location planning

- Location selector/header and source-version/freshness strip.
- Clear readiness/preflight state and disabled run button with the returned
  blocker reason.
- One synchronous **Compute latest recommendation** action with submitting,
  completed, blocked, and failed states; prevent duplicate submissions.
- Tabs or sections for Risk & stock, Open POs, and Recommendations.
- Recommendation table plus explanation/detail drawer using persisted
  planning lines, exceptions, netting results, and daily projections.
- Server-generated CSV/JSON download actions.
- Distinguish observed PO lines from calculated recommendations everywhere.

### Data & settings

- Two groups: **Planning inputs** and **Maintained data & rules**.
- Four focused upload cards: master workbook, planning workbook, stock XLSX,
  and cumulative Transgourmet PDFs.
- Show global versus selected-location scope, accepted/warning/rejected state,
  source time versus import time, versions, hashes/record counts where useful,
  coverage range, and actionable validation issues.
- Uploading never runs planning. Stock and PO corrections mean re-uploading or
  fixing maintained mappings, not editing observed rows inline.
- A master workbook upload creates a draft; list versions and provide an
  explicit activate action. Field-level master/menu grid editing is a later
  separately scoped feature, so show a clear disabled/future state rather than
  inventing an API.

Use the component structure proposed in section 11 of the journey document as
a starting boundary, not as a requirement to build a generic design system.
Prefer small page-focused hooks and components; avoid a large state framework.

## Required states

Implement and test loading, empty, unauthenticated, unavailable, validation
error, blocked, accepted-with-warnings, stale calculation, and completed
proposal states. Never silently replace an API error with synthetic data. If a
separate visual-demo mode is useful, label it prominently and keep it explicit
in configuration and code.

## Non-negotiable boundaries

- Do not edit `src/supply_planning`, backend services/routes/repositories,
  Supabase migrations, or planning tests as part of this frontend handover.
- Do not parse XLSX/PDF or calculate recommendations/KPIs in TypeScript.
- Do not query Supabase domain tables from React.
- Do not add approval, supplier-send, ERP write, comments, assignment, or
  order-placement workflows.
- Do not commit credentials, real uploads, extracted PDFs, or production data.
- If an API contract defect blocks the UI, document the exact request,
  response, and expected behavior for Codex instead of creating a parallel
  backend path.

## Verification and handoff

- Add frontend unit/component tests for Auth/session handling, navigation,
  typed API errors, upload states, readiness/run states, and proposal labels.
- Run `pnpm check` from `apps/web` plus the relevant frontend test command.
- Exercise the three routes at desktop and small-screen widths.
- When safe environment values are present, test sign-in and one representative
  connected journey. Do not claim live success if migration 003, Auth, or
  credentials are absent.
- Update the UI sections of the backlog and scratchpad, but do not mark backend
  or live-cloud work complete without evidence.

The UI slice is complete when a maintainer can understand the system state,
upload each source group, activate a master draft, run one location, reopen the
persisted result after refresh, inspect its risks/recommendations, and download
the server-generated output—without the frontend duplicating backend logic.

---
