# UI, API and prototype persistence foundation

**Status:** backend vertical slice and connected three-page React UI are
implemented. The 2026-09-01 backend v3 adds event-aware per-item coverage for
the next Location chart. Migration 005 and a fresh connected v3 run remain to
be applied/verified in the development Supabase project; deployed-environment
configuration remains open.

## Purpose and decision

The maintainer interface, Python API, Supabase migrations, and pure planning
engine live in one repository as separate deployables. This is a monorepo
boundary, not a combined runtime:

```text
React/TypeScript/Vite/Tailwind on Vercel
                    │
                    │ HTTPS + Supabase user access token
                    ▼
             FastAPI on Render
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
existing application     Supabase prototype
services and engine      master/run tables
```

The engine under `src/supply_planning` remains independent from HTTP, browser,
database, and deployment libraries. React never parses the operational files
or calculates recommendations. The API is the adapter/orchestration boundary.

The user journey, Overview cockpit, Location planning page, Data & settings
page, component map, planned endpoints, and source-persistence gaps are defined
in `docs/descriptions/ui_maintainer_journey_and_page_plan.md`.

## Implemented repository layout

```text
├── src/supply_planning/            # existing pure engine and adapters
├── apps/
│   ├── api/supply_planning_api/    # Auth, routes, services and Supabase repository
│   └── web/                        # React/TypeScript/Vite/Tailwind shell
├── supabase/
│   └── migrations/                 # version-controlled prototype schema
├── tests/test_api_*.py             # API/auth/repository/route tests
├── render.yaml                     # Render API Blueprint
└── .python-version                 # deterministic Render Python line
```

The Render service runs from the repository root because `apps/api` imports
the root Python package. Vercel uses `apps/web` as its project root.

## Implemented backend contracts

### Python API

- `GET /api/v1/health` checks only the API process and is safe for the Render
  health check.
- `GET /api/v1/readiness` reports `ready`, `not_configured`, or `unavailable`
  for Supabase. It verifies the required tables and transaction RPCs without
  returning upstream error bodies or keys.
- `GET /docs` exposes the generated OpenAPI documentation.
- CORS origins are explicit environment configuration; no wildcard origin is
  used with credentials.
- Unexpected HTTP failures are logged server-side and returned inside the CORS
  boundary as a sanitized `internal_error` envelope. Browser clients therefore
  do not misreport an escaped backend exception as a CORS configuration error.
- Every other `/api/v1` route requires a Supabase access token. In this private
  prototype, any valid project user is a maintainer; role tiers are deferred.
- `routes.py` exposes the identity, location, Overview, imports, master-version
  activation, planning-run, risks, recommendations, and CSV/JSON contracts.
- `services.py` reuses the Python XLSX/PDF adapters, assembles canonical inputs,
  calls the pure engine, and builds portable read models.
- The Overview read model returns aggregate actionable-risk KPIs and one
  self-contained row per location with its display metadata, source freshness,
  current-run status, blockers, risk counts, and earliest actionable-risk date.
  The browser does not need to reconstruct these semantics or make one status
  request per location.
- The planning-run read model enriches each persisted planning line with a
  `planning_line_explanations` record loaded from the exact immutable master
  version referenced by the run. Item, lead/review, shelf-life, safety,
  max-cover, pack/MOQ/case, supplier and delivery-rule context is therefore
  available to an audit drawer without duplicating it in another result table.
  `explanation_context.field_lineage` names the authoritative dataset/policy
  inputs for each calculated field.
- Each v3 netting row carries three event-aware coverage runways: usable stock
  alone, stock plus accepted open POs, and stock plus the proposed receipt.
  Each scenario includes covered calendar days, covered-through date, first
  uncovered date, and whether forecast length makes the result a lower bound.
  Incremental PO/proposal days, exact/lower-bound/not-observable evidence
  status, and late-receipt flags are persisted explicitly.
  `coverage_context` defines these semantics and identifies legacy rows that
  require a fresh v3 run.
- `repository.py` keeps PostgREST persistence behind a protocol so Snowflake
  can later replace result/input storage without changing the browser or engine.

The readiness endpoint returning `degraded/not_configured` is expected until
all five migrations are applied and server environment variables are
configured. Render process health remains healthy during that setup, while
authenticated domain actions fail closed.

### Browser application

The browser now has authenticated shell/navigation and the connected Overview,
Location planning, and Data & settings workflows. The v2 risk/MHD presentation
is adopted. The v3 cross-ingredient coverage chart is the next frontend-only
slice after migration 005 and a fresh run are available.

The frontend contains a lazy Supabase client initializer for Auth. It
does not query domain tables directly and receives no elevated credential.

## Environment boundary

| Runtime | Variable | Purpose | Secret? |
|---|---|---|---:|
| Render/local API | `APP_ENV` | Environment label returned by system endpoints | No |
| Render/local API | `CORS_ORIGINS` | Comma-separated allowed web origins | No |
| Render/local API | `SUPABASE_URL` | Supabase project API URL | No |
| Render/local API | `SUPABASE_SECRET_KEY` | Elevated server-side REST access | **Yes** |
| Render/local API | `SUPABASE_TIMEOUT_SECONDS` | Auth/PostgREST timeout | No |
| Render/local API | `MAX_UPLOAD_BYTES` | Total request upload limit | No |
| Render/local API | `MAX_PO_FILES` | Maximum PDFs in one PO import | No |
| Vercel/local web | `VITE_API_BASE_URL` | Render API origin | No |
| Vercel/local web | `VITE_SUPABASE_URL` | Browser-safe project URL for Auth | No |
| Vercel/local web | `VITE_SUPABASE_PUBLISHABLE_KEY` | Browser-safe Auth/Data API key | No |

`SUPABASE_SECRET_KEY` must never have a `VITE_` prefix, appear in browser
configuration, or be logged. Vercel and Render account/deployment tokens are
CI/platform credentials, not application runtime variables.

## Prototype Supabase exception

The longer-term design keeps operational inputs and Phase 2 result tables in
Snowflake. For the prototype, this project is explicitly allowed to persist
versioned editable master data and canonical planning outputs in Supabase for
simplicity. The exception changes only persistence ownership:

| Contract | Prototype store | Long-term direction |
|---|---|---|
| Editable locations/items/rules | Supabase version tables | Supabase or Snowflake after ownership decision |
| Run/input metadata | Supabase | Snowflake |
| Derivations/recommendations/exceptions | Supabase | Snowflake |
| Normalized forecast/menu/BOM/stock/PO versions | Supabase during the file-based prototype; raw files temporary by default | Accepted operational source tables |
| Calculation logic | Python engine | Python engine |

The foundation migration creates typed tables for `master_data_versions`,
`locations`, `items`, `item_policy_overrides`, `delivery_rules`,
`planning_runs`, `planning_run_inputs`, `planning_lines`,
`planning_recommendations`, and `planning_exceptions`. It enables Row Level
Security and grants no `anon` or `authenticated` table access. The server-only
repository uses the configured Supabase secret only after the request token is
verified.

The additive `202608280002_ui_workflow_inputs.sql` migration supplies the
minimum data needed to exercise the three-page workflows: compact import
metadata/issues, normalized forecast/menu/BOM/stock/PO rows, explicit run/input
references, persisted item-level netting summaries, and the engine's daily
inventory-projection rows. It deliberately avoids separate file, issue,
PO-header, and KPI/materialized-summary tables until evidence requires them.
`supabase/seed.sql` provides a small synthetic UI-only example.

`202608290003_ui_backend_transactions.sql` adds finalized-source and active-
master immutability guards plus narrow transaction RPCs for master imports,
other source imports, master activation, and a complete planning result. A run
is persisted atomically with its selected inputs, lines, recommendations,
exceptions, netting summaries, and daily projection rows.

`202608300004_actionable_risk_and_shelf_life.sql` adds only the v2 derivation
columns required for item-specific actionable risk and tagged-candidate
shelf/max-cover evidence. It also adds `persist_planning_run_v2`, which is the
readiness marker and atomic RPC used by the corrected backend.

`202609010005_event_aware_supply_coverage.sql` adds nullable v3 runway columns
to `planning_netting_results` plus the service-role-only
`persist_planning_run_v3` RPC. The engine calculates the three scenarios from
the dated demand and receipt events; neither SQL nor React reconstructs them.
The v3 schema leaves old v2 rows readable with `null` coverage fields.

The maintainer reports migrations 001–004 applied manually through the
Supabase SQL Editor and has already verified Auth plus the earlier connected
workflow. Migration 005 must now be pasted and run there as one additional
forward migration before the next v3 planning run. Never rewrite the already-
applied files.

## Upload and retention boundary

The import endpoints accept the two fixed workbook inputs, the
current Apicbase stock workbook, cumulative Transgourmet PDFs, and selected
`location_id` where required. They will write raw files only to a per-request
temporary directory, call the existing Python loaders/normalizers directly,
persist accepted normalized source versions, and delete temporary files
afterward. A later planning-run request references those visible accepted
versions plus its deterministic cutoff; it does not carry a second hidden set
of files.

XLSX worksheet-dimension metadata is treated as optional. Both validation and
the post-validation audit-row reader stream worksheet rows, so valid workbooks
from producers that omit the dimension hint remain importable. Excel midnight
`datetime` values in date-only planning fields are normalized to calendar dates
before canonical rows are assembled.

Raw upload retention is off by default. If audit/replay requirements later
justify retention, add an approved retention period and private object-storage
policy. Do not store raw files as Postgres binary columns or on Render's
ephemeral local filesystem.

## Deferred work

- Apply migration 005 and verify readiness plus one fresh representative v3
  run; old v2 rows cannot populate the new calculated fields retroactively.
- Render the cross-ingredient coverage chart from the explicit v3 fields,
  including forecast-limited and not-evaluated states, without browser-side
  planning calculation.
- Add field-level draft editing and change-event history after the upload/
  activation workflow proves useful; workbook import remains the V1 write path.
- Add frontend component/E2E tests and live API smoke coverage in a safe dev
  project.
- Configure actual Vercel, Render, and Supabase projects and verify deployed
  CORS, Auth, readiness, migrations, logs, and failure behavior.

Supplier dispatch, ERP writes, proposal approval, comments/assignment,
statistical optimization, and complex calendar integration remain outside the
prototype scope.
