# Supabase prototype persistence

The migrations in this directory establish the temporary prototype store for:

- versioned application-maintained master data and planning rules; and
- canonical planning-run, derivation, recommendation, and exception records.

The schema mirrors the engine contracts so result persistence can later move
to Snowflake without changing calculation logic. It does not make Supabase an
operational source for forecasts, stock, or purchase orders.

## Apply later, after the project is selected

Install and authenticate the Supabase CLI, then link the intended project and
review the exact target before applying:

```powershell
supabase link --project-ref <project-ref>
supabase db push
```

No project reference or credentials belong in this repository. The migration
enables Row Level Security and grants no browser roles access. Future domain
endpoints must verify maintainer identity in the API before using the server
secret; direct browser policies can be added only when the page design and
role model are approved.
