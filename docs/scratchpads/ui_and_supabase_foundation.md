# UI and Supabase foundation scratchpad

> Living notes for the maintainer UI, HTTP API, prototype Supabase persistence,
> and Vercel/Render deployment foundation. Keep this concise and update it after
> each meaningful slice; authoritative behavior belongs in `docs/descriptions/`.

## Goal

- Establish a minimal monorepo foundation with a thin Python API, a basic
  React/TypeScript/Tailwind UI, version-controlled Supabase migrations, and
  deployment configuration without designing the final pages or workflows.

## Current plan

- [x] Add the deployable API and browser application without moving the pure engine.
- [x] Add a safe optional Supabase readiness connection and initial typed tables.
- [x] Document the prototype persistence exception and environment boundaries.
- [x] Verify Python tests, frontend checks, API endpoints, and the local web/API route.

## Key decisions (and why)

- 2026-08-28: Keep one repository with separate deployables under `apps/api`
  and `apps/web`; the engine stays under `src/supply_planning` so HTTP and UI
  concerns cannot leak into calculations.
- 2026-08-28: Use React + TypeScript + Vite + Tailwind for the internal UI and
  FastAPI for the thin HTTP boundary. The UI remains presentation-only.
- 2026-08-28: Supabase may temporarily store versioned master data and planning
  outputs during the prototype. The canonical output contract remains portable
  so Snowflake can replace the persistence adapter later.
- 2026-08-28: Browser code receives only Supabase publishable credentials.
  Elevated Supabase credentials stay in the Render API environment.
- 2026-08-28: Raw workbooks/PDFs are not persisted by this foundation. Future
  uploads use temporary processing unless a separately approved private-storage
  retention policy is added.

## What we learned (facts, not guesses)

- The local technical V1 and its typed input/output contracts are complete;
  the UI may start before maintainer approval, but proposal values must remain
  visibly labelled.
- `run_template_v1` already orchestrates the two templates, stock workbook,
  PDF directory, selected location, and deterministic cutoff.
- The repository had no API, web application, Supabase migrations, or Node
  workspace before this slice.
- A fresh Windows virtual environment needs the declared `tzdata` package for
  `ZoneInfo("Europe/Berlin")`; the existing test suite exposed this immediately.
- The real local processes served the page with HTTP 200, returned API
  `health=ok`, reported the expected unconfigured Supabase state, and routed
  `/api/v1/readiness` successfully through the Vite proxy.
- Final verification passed 48 Python tests, focused Ruff/mypy checks for the
  new API, `pip check`, frontend lint/type/build, and frontend peer checks.

## Open questions / unknowns

- Which Supabase project, region, organization, and internal authentication
  method will be used?
- What retention period, if any, is approved for uploaded source files?
- Will production master data ultimately remain in Supabase or move to
  Snowflake with the results?
- Which Render and Vercel projects/domains will be used for preview and
  production environments?

## Next steps

- Select the cloud projects, apply the migration, add environment values, and
  verify deployed CORS/readiness before enabling domain writes.
- In the next product slice, define the actual upload, master-data, result, and
  error-review pages before implementing those workflows.

## Risks / gotchas (things not to forget)

- Never expose `SUPABASE_SECRET_KEY` to Vite or commit it.
- Keep all calculations and business validation in Python; do not duplicate
  recommendation logic in React.
- Do not label scenario/demo recommendations as operational before the
  maintainer gate passes.
- Render local files are temporary; database or private object storage is
  required for intentionally retained data.
- The in-app visual browser check could not initialize because the installed
  Browser plugin requested a missing newer `browser-service.mjs` runtime. Build,
  live HTTP, Vite-proxy, and API checks passed; repeat interactive visual QA
  after the Codex Browser plugin/runtime versions align.
- Supplier dispatch, ERP writes, approval workflow, and complex calendars stay
  outside scope.

## Commands / environment notes

- Python verification: `scripts/check.ps1 -PythonExecutable <python>`.
- API development: `uvicorn apps.api.supply_planning_api.main:app --reload`.
- UI development: run `pnpm dev` from `apps/web`.
- Frontend verification: run `pnpm check` from `apps/web`.
- Focused API quality checks:
  `.venv/Scripts/python -m ruff check apps/api tests/test_api_foundation.py`
  and `.venv/Scripts/python -m mypy apps/api tests/test_api_foundation.py`.
