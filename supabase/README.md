# Supabase prototype persistence

The eight forward migrations establish the temporary prototype store for:

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
- `202609030006_signup_email_domain_gate.sql`: a `before insert` trigger on
  `auth.users` that refuses accounts outside the approved company email
  domains. Existing accounts are untouched.
- `202609040007_allow_circus_group_signup_domain.sql`: keeps the database gate
  aligned with the two approved company domains.
- `202609040008_user_workspace_isolation.sql`: provisions one empty private
  workspace per user, adds workspace/location membership and role contracts,
  scopes all planning relations, backfills existing rows by audit actor, and
  rejects cross-workspace or cross-location write relationships.

## Self-service sign-up

Sign-up is open but domain-restricted, and the restriction is enforced in three
places because the browser holds a publishable key and can call Supabase Auth
without going through this application:

1. the trigger in migration `006`, which stops the account existing;
2. `ALLOWED_EMAIL_DOMAINS` in the API, checked on every request, which is what
   actually protects planning data; and
3. `VITE_ALLOWED_EMAIL_DOMAINS` in the browser, which is only form copy.

Changing the allowed domains means editing all three. The migration's list is
a constant inside `public.enforce_signup_email_domain()`.

Three project settings have to match, and none of them live in this repository:

- **Authentication → Sign In / Providers → Email**: "Confirm email" enabled.
  Without it the domain gate is unverified, because anyone could sign up as a
  colleague's address without owning it.
- **Authentication → URL Configuration → Redirect URLs**: add
  `<deployed-origin>/auth/callback` and `http://localhost:5173/auth/callback`.
  A confirmation link whose redirect is not listed falls back to the site URL.
- **Authentication → Emails → SMTP**: the built-in sender is rate-limited and
  restricted in who it will deliver to, so confirmation mail to a colleague
  needs custom SMTP. Verify one real delivery before relying on it.

A sign-up refused by the trigger surfaces to the browser as an opaque
"Database error saving new user"; the React form translates that into the
domain rule.

After migration 008, every successful new account receives its own empty
private planning workspace. The approved email domain only admits the account;
it never joins that account to another user's workspace or locations.

This is intentionally smaller than the original schema plan. File metadata and
small validation issue lists live on `source_imports`; `po_id` stays on each PO
line; KPI/materialized-summary tables are deferred. Split them only when real
volume, retention, or query needs justify it.

Raw XLSX/PDF bytes do not belong in Postgres. If approved retention is needed,
use a private object bucket and keep only its reference in import metadata.

`seed.sql` contains a clearly synthetic location/item/import/run/risk example
in a distinct seed workspace for local or disposable development databases.
It is not automatically granted to a newly signed-up user; add an explicit
disposable membership only when a UI fixture needs it. It is not operational
data and must not be included in production.

`tests/test_supabase_schema.py` statically checks required workflow tables,
workspace columns/constraints, RLS/revokes, transaction/immutability functions,
run/import traceability, and seed column references. A real
`supabase db reset` remains the authoritative syntax/application check.

When applying migrations manually in the Supabase SQL Editor, paste and run
each unapplied file in filename order. Do not edit or rerun older applied
migrations. Migration 008 is deliberately fail-closed: it aborts if existing
root records cannot be attributed from `created_by` or if existing location
relationships are inconsistent. Review the error and repair provenance rather
than inventing an owner.

Deploy the workspace-aware API before applying 008. That creates a short,
intentional maintenance window in which authenticated domain routes fail
closed because the new tables are absent. Apply 008 immediately afterward,
verify `/api/v1/readiness`, then run the two-account isolation matrix. Do not
apply 008 while leaving the old unscoped API serving users.

After 008 commits, run `supabase/verify_user_workspace_isolation.sql`. Its
account/workspace summary must show the pre-existing planning rows only in the
original owner's workspace, every anomaly count must be zero, and every
browser-role privilege flag must be false.

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
