# Claude Code brief — first UI pages

Copy the instruction below into Claude Code from the repository root.

---

You are working in the `demand_forcasting` repository. Build the first
presentational/navigation slice of the internal Phase 2 supply-planning UI.
Do not redesign the planning logic or invent a second calculation path.

Before editing, read these files in order:

1. `AGENTS.md` — mandatory repository boundaries and verification rules.
2. `MEMORY.md` — durable project decisions and current implementation status.
3. `docs/descriptions/ui_maintainer_journey_and_page_plan.md` — primary product
   and UX specification: user journey, the three pages, KPIs, page states,
   component map, API handover, and acceptance criteria.
4. `docs/descriptions/ui_api_and_persistence_foundation.md` — monorepo,
   frontend/API, security, environment, Supabase, and deployment boundaries.
5. `docs/plans/phase2_supply_planning_master_backlog.md` — implementation order;
   focus on the shell and first page work in Milestone 2D-2F without claiming
   the later upload/run/edit workflows are finished.
6. `apps/web/src/App.tsx`, `apps/web/src/components/StatusCard.tsx`,
   `apps/web/src/lib/api.ts`, and `apps/web/src/lib/supabase.ts` — current React
   foundation to evolve rather than discard blindly.
7. `supabase/migrations/202608280001_ui_foundation.sql`,
   `supabase/migrations/202608280002_ui_workflow_inputs.sql`, and
   `supabase/seed.sql` — database shapes and synthetic UI test data. React must
   still access domain data through FastAPI, not query these tables directly.

Implement this first UI slice:

- Add a responsive application shell with persistent desktop side navigation
  and a small-screen drawer.
- Add routes for `/overview`, `/locations/:locationId`, and `/data` with the
  labels **Overview**, **Location planning**, and **Data & settings**.
- Preserve the current API/Supabase readiness information in a compact shell
  status area and preserve the visible demo/proposal warning.
- Build the high-level page structures and reusable components described in the
  UI journey document:
  - Overview: alert/readiness strip, five KPI cards, location-risk table, data-
    freshness panel, and latest-run/PO activity placeholders.
  - Location planning: location selector/header, freshness/preflight strip,
    Risk & stock, Open POs, and Recommendation views, a run-status area,
    recommendation table/detail affordance, and CSV/JSON actions.
  - Data & settings: Planning inputs and Maintained data & rules groups, four
    dataset/upload cards, version/freshness metadata, validation states, and
    clear edit-versus-re-upload affordances.
- Use typed, explicitly synthetic/demo page data behind a small frontend data
  adapter until authenticated domain read endpoints exist. Include realistic
  loading, empty, warning, blocked, and error states. Do not query Supabase
  domain tables directly from React and do not expose a server secret.
- Make unavailable actions visibly disabled with a reason. Do not fake working
  upload, master-data write, calculation, authentication, order placement, or
  supplier/ERP behavior.
- Keep units, timestamps, provenance, “recommendation” versus “observed PO”,
  and “potential risk” versus actual waste explicit.
- Keep the result practical and restrained: use the existing Tailwind visual
  language, avoid a generic design-system project, large state frameworks, or
  complex chart libraries. Add only the routing dependency needed for these
  routes and call out that dependency change.

Suggested frontend boundaries are documented in section 11 of
`ui_maintainer_journey_and_page_plan.md`. You may adjust filenames when the code
makes a simpler boundary obvious, but keep page-specific components grouped and
shared components genuinely reusable.

Do not change `src/supply_planning` for this presentational slice. The Python
engine stays pure. Do not parse XLSX/PDF in TypeScript. Do not add approval,
comments, assignments, supplier send, ERP write, or ordering status.

Verification and handover:

- Run `pnpm check` from `apps/web`.
- Add focused frontend tests only if the repository already has the required
  test tooling; do not introduce a large test stack solely for this slice.
- Exercise all three routes and their responsive/navigation states in a local
  browser when available.
- Update the relevant Milestone 2 backlog checkboxes and UI scratchpad with
  exactly what is implemented and what remains mocked/unavailable.
- In the final response, list changed files, checks run, deliberate mock/demo
  boundaries, and the next backend/API dependency.

The success condition is a coherent, navigable first version of all three pages
that a designer and maintainer can react to, while every not-yet-working domain
workflow remains honest and clearly separated from the completed UI shell.

---
