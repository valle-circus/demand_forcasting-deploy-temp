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

Migrations 001–003 are applied in the selected development Supabase project.
Before the next connected planning run, Valentin must apply the new forward
migration
`supabase/migrations/202608300004_actionable_risk_and_shelf_life.sql` through
the Supabase SQL Editor. It adds derivation columns only—no replacement tables—
and the `persist_planning_run_v2` RPC. Until it is applied, readiness will
honestly report the v2 persistence dependency as missing. Claude must not add
tables or work around that state. On 2026-08-29, Codex verified the earlier
18-table/four-RPC contract. Claude also
verified the authenticated browser-to-FastAPI journey with the maintainer's
admin-created user. Continue to treat `/api/v1/readiness` as the runtime truth:
if it later reports a missing dependency, show that non-secret blocker; do not
change the backend or create replacement tables. Connected mode must fail
honestly rather than silently falling back to demo data.

## Synthetic connected-workflow packet

A parser-verified test packet is available for the first real Data & settings
journey:

- `outputs/01a043ce-e551-7492-b41a-bee3c09a1d99/ui_test_packet/`
  contains the filled master workbook, filled planning workbook, Apicbase-style
  stock workbook, and an upload/readme with exact cutoffs and expected results.
- `output/pdf/ui_test_packet/Transgourmet_Bestelldetails_UI_DEMO.pdf` is the
  corresponding parseable cumulative PO input.

This is synthetic development data, not a frontend fallback and not production
seed data. Follow the strict sequence already implemented on Data & settings:
master upload -> explicit activation -> planning upload -> location stock ->
location PO PDFs. Use `LOC_UI_DEMO_001` and the readme's exact timezone-aware
cutoffs. The packet was replayed through the existing Python XLSX/PDF adapters
and the corrected pure scenario engine as `improved-ded5498f7198`; it completed
with one safe 6-pack proposal, `actionable_risk_status = covered` through
7 September, a future-context shortage on 10 September, and zero projected
candidate residual at estimated expiry. Do not hard-code that output in React:
it is only a connected smoke-test oracle.

The test also confirmed two UX rules that must remain explicit:

- activation replaces the active master for the current environment, so the
  packet belongs only in a disposable or explicitly approved development
  project;
- no approved freshness thresholds exist yet, so show source/import times and
  the server's readiness/current-run verdict without inventing age cutoffs.

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

The backend now returns the complete Overview read model. In addition to the
aggregate KPIs (including `locations_at_risk`), every `locations[]` row carries
`location_name`, `timezone`, `earliest_risk_date`, the four `sources` freshness
records, current-run status, risk counts, and blockers. Consume this response
directly; do not fan out to one `planning-status` request per location or
recalculate an earliest risk date in React.

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

#### Horizon and MHD backend contract ready for frontend adoption

Maintainer review on 2026-08-30 found that the old connected view mixed
the full uploaded-forecast projection with the item-specific actionable
recommendation horizon. Read
`docs/plans/planning_horizon_and_shelf_life_correction_plan.md` before further
Location planning or Overview work.

- Use `planning_netting_results.actionable_risk_status` for the default risk
  filter, row status, and Overview meaning. It is `at_risk`, `covered`, or
  `not_evaluated`. Do not treat every full-forecast `first_stockout_date` as
  current risk. A
  shortage after the active planning-line coverage end is expected to be
  reconsidered in a later review cycle and must not inflate the default risk
  filter or Overview KPI.
- Use `planning_lines.gross_requirement_g` plus `coverage_end_date` for
  **Demand to protect through <date>**. Do not use full-forecast gross demand
  as the primary `Needed` value. The
  customer-facing action is demand protected by the current recommendation,
  its coverage end, the existing receipts, and the proposed receipt.
- Keep forecast/data horizon, item protection horizon, shelf-life feasibility
  window, and chart display range distinct. A display zoom is welcome; one
  global ad-hoc planning-horizon slider is not.
- Show the explicit backend fields `candidate_expiry_date`,
  `shelf_life_cap_basis`, `forecast_through_expiry`,
  `projected_candidate_residual_at_expiry_g`, `binding_constraint`, and
  `constraint_status`. A `policy_approximation` is not exact lot MHD. React
  must not derive or override feasibility.
- In the chart, label existing/proposed receipt quantities, use discrete daily
  geometry instead of smoothing, and distinguish usable stock from cumulative
  uncovered demand.

The corrected backend contract is supplied and tested. Claude can now finish
the Location horizon/MHD slice and WP5 Overview, provided it only formats and
filters the explicit fields above.

#### Mandatory UI impact pass after the v2 logic correction

Do not treat this as a type-only API upgrade. Review every existing Location
and Overview label, filter, chart marker, KPI, empty state, and test against the
following semantic changes:

| Existing/ambiguous UI behavior | Correct backend meaning | Required UI adjustment |
|---|---|---|
| Any non-null full-forecast `first_stockout_date` means **At risk** | Only `actionable_risk_status = at_risk` is current decision risk | Use the explicit status for filters, badges, KPIs and alerts; present a later shortage as **Future replan expected** |
| `Needed` shows `netting_results.gross_requirement_g` | That value spans the complete uploaded forecast | Use `planning_lines.gross_requirement_g` and `coverage_end_date` as **Demand to protect through <date>**; keep full-forecast demand secondary |
| `Lasts N days` is presented as a stock KPI | It is derived from a full-forecast shortage and includes calendar/zero-demand days | Prefer **Covered through**, **Shortage within decision window**, or **Future shortage on** using server dates/statuses |
| A negative ending balance looks like negative physical stock | It is cumulative uncovered demand if no later planning cycle places another order | Separate non-negative usable stock from the labelled full-forecast counterfactual |
| Receipt jumps are visible but unexplained | Daily projection includes both accepted POs and the new candidate | Label each existing and proposed receipt with date and quantity |
| A smoothed curve appears to cross zero between dates | The engine evaluates closing balance at daily grain | Use step/straight daily geometry and state that shortage begins on the returned date |
| `10 days` appears to be a universal or user-chosen horizon | Stocked-item protection is item lead time plus versioned review cadence; fresh uses delivery/service windows | Show the item policy context; do not add one global planning-horizon control |
| Shelf-life cap is described as proof of MHD safety | It is candidate-specific supply-position evidence; it may be a policy approximation and may have incomplete forecast coverage | Show expiry basis, evidence completeness and residual; never claim exact MHD or actual waste without exact lot data |
| Pack/MOQ rounding always produces an ordinary proposal | A hard cap may force a lower safe multiple or no safe positive order | Show `constraint_status`, `rounding_direction`, binding constraint and the backend exception/remedy; never manufacture a proposal in React |
| Overview risk counts use browser helpers | Overview now returns backend-classified current-run counts | Render `/overview` values directly and keep stale/not-evaluated states distinct from zero risk |

Update the existing frontend tests and fixtures for every affected row above.
Delete or replace old TypeScript helpers whose business meaning came from
`first_stockout_date`, full-projection demand, or arithmetic comparisons.

#### Progressive explanation without overloading the primary view

Use progressive disclosure, not a permanently dense table:

1. **Scanning layer:** recommendation, status, covered-through date, demand to
   protect, observed stock/POs, and the one most important exception.
2. **Definition layer:** small focusable info buttons/popovers can explain what
   a metric means and which window it uses. Never put a required warning,
   blocker, approximation, or remedy only in hover content.
3. **Audit layer:** the existing derivation drawer is the complete answer to
   “why this quantity?”. Show the ordered arithmetic, versioned policy inputs,
   source versions/provenance, dated receipts/projection, caps, rounding,
   exceptions and known evidence limits.

`GET /api/v1/planning-runs/{run_id}` now supplies everything needed for that
audit layer:

- `planning_lines` — persisted demand/yield/safety/stock/PO/raw-order/cap/
  rounding/final-proposal values;
- `planning_line_explanations` — one object per line from the exact immutable
  master version used by the run, including item name/storage/pack size,
  shelf-life days, safety days, max-cover days, lead time, shelf-life anchor,
  MOQ/case/order-unit settings, supplier/channel, delivery/review rule,
  provenance/data status, protection mode, and evidence scope;
- `explanation_context.field_lineage` — which normalized datasets or policy
  fields own each calculation field; `inputs` carries their exact versions,
  hashes, provenance and record counts;
- `projection_days` and `netting_results` — daily item demand, accepted and
  candidate receipts, balance/uncovered demand, both risk windows and their
  status;
- `exceptions` (persisted `planning_exceptions` rows) — backend-authored code,
  severity, message and remedy;
  and
- run metadata — planning cutoff, code/policy version, config hash and exact
  master version.

Update `apps/web/src/lib/types.ts` for these fields. Join explanations by
`planning_line_id`; do not derive policy inputs from dates or reverse-engineer
formulas in React.

Be explicit about the current evidence boundary. The API can explain the full
persisted recommendation arithmetic and daily item-level demand, but it does
not have exact lot/MHD quantities for existing stock, historical daily stock
balances, or persisted dish/silo contribution rows. Label those as unavailable
rather than inferring them. Exact lot MHD and dish-level demand-lineage drill-
down are future backend/data extensions, not frontend calculations.

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
- Treat activation as the final action within Step 1, not as a disconnected
  maintenance task below the upload flow. After a successful upload, label the
  result **Draft ready** and show a prominent **Activate master data and
  continue** action directly in the Step 1 card. Once activated, label that
  version **Active**. Keep the lower master-version list for audit/history and
  replacement controls; when Step 2 is blocked on activation, its message
  should link or move focus to the Step 1 action. Retain an explicit
  confirmation before activation because it changes the item set, locations,
  and rules used throughout the environment.

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
  connected journey. Do not claim live success if migration 004, Auth, or
  credentials are absent.
- Update the UI sections of the backlog and scratchpad, but do not mark backend
  or live-cloud work complete without evidence.

The UI slice is complete when a maintainer can understand the system state,
upload each source group, activate a master draft, run one location, reopen the
persisted result after refresh, inspect its risks/recommendations, and download
the server-generated output—without the frontend duplicating backend logic.

---
