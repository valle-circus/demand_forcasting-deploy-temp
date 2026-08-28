# Supabase prototype persistence

The two migrations establish the temporary prototype store for:

- versioned application-maintained master data and planning rules; and
- canonical source imports/inputs, planning runs, netting summaries,
  derivations, recommendations, and exceptions.

The schema mirrors the engine contracts so result persistence can later move
to Snowflake without changing calculation logic. During the manual-file
prototype, Supabase holds immutable normalized forecast/menu/BOM/stock/PO
versions so the UI can show freshness and run from visible accepted inputs.
This temporary adapter does not make raw uploads the long-term operational
authority.

## Schema layers

- `202608280001_ui_foundation.sql`: master versions, items/rules/locations, and
  portable run/line/recommendation/exception outputs.
- `202608280002_ui_workflow_inputs.sql`: one compact `source_imports` table,
  normalized forecast/menu/BOM/stock/PO tables, run-to-import references, and
  one item-level `planning_netting_results` summary table.

This is intentionally smaller than the original schema plan. File metadata and
small validation issue lists live on `source_imports`; `po_id` stays on each PO
line; daily projection events and KPI tables are deferred. Split them only when
real volume, retention, or query needs justify it.

Raw XLSX/PDF bytes do not belong in Postgres. If approved retention is needed,
use a private object bucket and keep only its reference in import metadata.

`seed.sql` contains a clearly synthetic location/item/import/run/risk example
for local or disposable development environments. It is not operational data
and must not be included in production.

`tests/test_supabase_schema.py` statically checks required workflow tables,
RLS/revokes, run/import traceability, and seed column references. A real
`supabase db reset` remains the authoritative syntax/application check.

## Validate locally

After installing the Supabase CLI, initialize local Supabase once if this
checkout does not yet have `supabase/config.toml`, then rebuild the disposable
local database from migrations and seed:

```powershell
supabase init
supabase start
supabase db reset
```

## Apply to the selected development project

Install and authenticate the Supabase CLI, then link the intended project and
review the exact target before applying:

```powershell
supabase link --project-ref <project-ref>
supabase db push --dry-run
supabase db push
```

For a disposable remote development project only, seed deliberately with
`supabase db push --include-seed`. Never include the synthetic seed in
production and never use a remote reset against a non-disposable project.

No project reference or credentials belong in this repository. The migrations
enable Row Level Security and grant no browser roles access. Future domain
endpoints must verify maintainer identity in the API before using the server
secret; direct browser policies can be added only when the page design and
role model are approved.
