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

Domain endpoints for uploads, master-data versions, and planning runs are the
next milestone. Protected domain endpoints must verify the Supabase user JWT
before any server-side secret is used.
