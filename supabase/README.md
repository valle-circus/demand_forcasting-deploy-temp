# Supabase prototype persistence

The five migrations establish the temporary prototype store for:

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
  item-level netting summaries plus daily projection rows.
- `202608290003_ui_backend_transactions.sql`: finalized-source and active-
  master immutability guards plus service-role-only transaction functions for
  imports, master activation, and full planning result persistence.
- `202608300004_actionable_risk_and_shelf_life.sql`: additive v2 derivation
  fields for actionable item horizons and candidate MHD/max-cover evidence,
  plus `persist_planning_run_v2`.
- `202609010005_event_aware_supply_coverage.sql`: additive v3 event-aware
  coverage runways for usable stock, accepted open POs, and proposed receipts,
  plus `persist_planning_run_v3`.

This is intentionally smaller than the original schema plan. File metadata and
small validation issue lists live on `source_imports`; `po_id` stays on each PO
line; KPI/materialized-summary tables are deferred. Split them only when real
volume, retention, or query needs justify it.

Raw XLSX/PDF bytes do not belong in Postgres. If approved retention is needed,
use a private object bucket and keep only its reference in import metadata.

`seed.sql` contains a clearly synthetic location/item/import/run/risk example
for local or disposable development environments. It is not operational data
and must not be included in production.

`tests/test_supabase_schema.py` statically checks required workflow tables,
RLS/revokes, transaction/immutability functions, run/import traceability, and
seed column references. A real
`supabase db reset` remains the authoritative syntax/application check.

When applying migrations manually in the Supabase SQL Editor, paste and run
each unapplied file in filename order. Do not edit or rerun older applied
migrations to introduce the v3 fields. Existing v2 runs remain readable after
005, but their new coverage columns are intentionally `null`; create a fresh
v3 run before testing the coverage chart.

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
enable Row Level Security and grant no browser roles access. Implemented domain
endpoints verify the Supabase user through Auth before using the server secret.
The browser uses Supabase directly only for Auth.
