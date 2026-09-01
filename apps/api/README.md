# Supply Planning API

This is the thin FastAPI deployment boundary for Render. It may orchestrate
uploads, call application services, and persist through adapters, but it must
not contain or duplicate planning calculations.

From the repository root:

```powershell
python -m pip install -e ".[api,pdf-import]"
python -m uvicorn apps.api.supply_planning_api.main:app --reload
```

The system endpoints are:

- `GET /api/v1/health`: process health only; used by Render.
- `GET /api/v1/readiness`: optional Supabase connectivity and migration probe.
- `GET /docs`: generated OpenAPI documentation.

All `/api/v1` domain endpoints verify a Supabase access token before using the
server-side repository. Open `/docs` for the current import, master-version,
overview, location, planning-run, risk, and download contracts. The browser
uses Supabase directly only for Auth; it never receives the server secret and
does not access domain tables directly.

Planning-run reads return per-line explanation context from the exact immutable
master version used by the run. They also return backend-calculated,
event-aware coverage runways for stock alone, stock plus accepted open POs,
and stock plus the proposal. The frontend can therefore show policy inputs,
provenance, field lineage, and a coverage chart without reimplementing
calculations.

Before connected writes, apply all five files in `supabase/migrations/` in
filename order. If 001–004 already exist in the project, run only
`202609010005_event_aware_supply_coverage.sql` as a forward migration in the
Supabase SQL Editor. Configure a safe Supabase Auth user plus the server values
in `.env`; readiness stays degraded until the required tables and v3 RPC are
visible. Existing v2 rows remain readable but do not gain computed coverage
retroactively, so test the new contract with a fresh run. The local test suite
uses fakes and does not prove the remote project.
