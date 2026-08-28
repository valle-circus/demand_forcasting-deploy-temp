# UI, API and prototype persistence foundation

**Status:** repository foundation implemented 2026-08-28; credentials, applied
Supabase project, domain endpoints, authentication, and final UI/UX remain open

## Purpose and decision

The maintainer interface, Python API, Supabase migrations, and pure planning
engine live in one repository as separate deployables. This is a monorepo
boundary, not a combined runtime:

```text
React/TypeScript/Vite/Tailwind on Vercel
                    │
                    │ HTTPS + future Supabase user JWT
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

## Implemented repository layout

```text
├── src/supply_planning/            # existing pure engine and adapters
├── apps/
│   ├── api/supply_planning_api/    # FastAPI entrypoint and Supabase probe
│   └── web/                        # React/TypeScript/Vite/Tailwind shell
├── supabase/
│   └── migrations/                 # version-controlled prototype schema
├── tests/test_api_foundation.py    # API system-boundary tests
├── render.yaml                     # Render API Blueprint
└── .python-version                 # deterministic Render Python line
```

The Render service runs from the repository root because `apps/api` imports
the root Python package. Vercel uses `apps/web` as its project root.

## Implemented foundation contracts

### Python API

- `GET /api/v1/health` checks only the API process and is safe for the Render
  health check.
- `GET /api/v1/readiness` reports `ready`, `not_configured`, or `unavailable`
  for Supabase. It performs a short server-side REST probe against
  `master_data_versions` and never returns upstream error bodies or keys.
- `GET /docs` exposes the generated OpenAPI documentation.
- CORS origins are explicit environment configuration; no wildcard origin is
  used with credentials.

The readiness endpoint returning `degraded/not_configured` is expected until a
Supabase project is selected, the migration is applied, and server environment
variables are configured. Render health remains healthy during that setup.

### Browser application

The initial page is intentionally only a foundation/status shell. It:

- confirms the browser can reach the Python API;
- shows the API's sanitized Supabase state;
- shows whether browser-safe Supabase Auth configuration is present;
- retains the demo/proposal warning; and
- names upload, master maintenance, and recommendation review as later product
  slices without fixing their page or component design prematurely.

The frontend contains a lazy Supabase client initializer for future Auth. It
does not query domain tables directly and receives no elevated credential.

## Environment boundary

| Runtime | Variable | Purpose | Secret? |
|---|---|---|---:|
| Render/local API | `APP_ENV` | Environment label returned by system endpoints | No |
| Render/local API | `CORS_ORIGINS` | Comma-separated allowed web origins | No |
| Render/local API | `SUPABASE_URL` | Supabase project API URL | No |
| Render/local API | `SUPABASE_SECRET_KEY` | Elevated server-side REST access | **Yes** |
| Vercel/local web | `VITE_API_BASE_URL` | Render API origin | No |
| Vercel/local web | `VITE_SUPABASE_URL` | Browser-safe project URL for future Auth | No |
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
| Forecast/menu/BOM/stock/PO source files | Temporary API processing only | Accepted operational source tables |
| Calculation logic | Python engine | Python engine |

The initial migration creates typed tables for `master_data_versions`,
`locations`, `items`, `item_policy_overrides`, `delivery_rules`,
`planning_runs`, `planning_run_inputs`, `planning_lines`,
`planning_recommendations`, and `planning_exceptions`. It enables Row Level
Security and grants no `anon` or `authenticated` table access. Domain API
writes must not be enabled until Supabase user JWT verification and maintainer
authorization are implemented.

Active-version immutability, activation transactions, change-history events,
database-to-domain repositories, and result persistence are deliberately next
steps; the schema alone is not presented as a working master-data workflow.

## Upload and retention boundary

The future upload endpoint will accept the two fixed workbook inputs, the
current Apicbase stock workbook, cumulative Transgourmet PDFs, selected
`location_id`, and deterministic cutoff. It will write files only to a
per-request temporary directory, call the existing Python services directly,
and delete temporary files afterward.

Raw upload retention is off by default. If audit/replay requirements later
justify retention, add an approved retention period and private object-storage
policy. Do not store raw files as Postgres binary columns or on Render's
ephemeral local filesystem.

## Deferred product and security work

- Define the actual upload, validation/mapping review, master-data, run-history,
  and recommendation pages before building their UI components.
- Add multipart limits, file allowlists, archive/PDF count limits, temporary
  cleanup tests, and one synchronous planning-run endpoint.
- Verify Supabase Auth JWTs in FastAPI and define the maintainer role model.
- Implement draft edit, validation, activation, immutability, and change
  history for master-data versions.
- Implement repository adapters that map existing domain records to the
  Supabase tables in one transaction per run.
- Add API integration and frontend component/E2E tests for domain workflows.
- Configure actual Vercel, Render, and Supabase projects and verify deployed
  CORS, Auth, readiness, migrations, logs, and failure behavior.

Supplier dispatch, ERP writes, proposal approval, comments/assignment,
statistical optimization, and complex calendar integration remain outside the
prototype scope.
