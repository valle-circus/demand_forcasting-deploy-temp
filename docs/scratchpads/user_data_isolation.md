# User data and location isolation scratchpad

> Living investigation and implementation notes for the authentication versus
> authorization gap discovered in the deployed maintainer UI. Authoritative
> behavior must move into the relevant description after the fix is designed
> and implemented. Do not record access tokens, secrets, user UUIDs, or private
> production data here.

## Status and goal

- **Status:** active, critical promotion blocker as of 2026-09-04.
- **Goal:** every authenticated user starts in a private data boundary, can
  create or manage their own locations, and can read or mutate only data for
  locations/workspaces they are explicitly allowed to access.
- Shared/global data must be intentional and admin-controlled. A company email
  domain is an account-admission rule, never a data-authorization rule.
- Do not use real operational data or invite further testers until the access
  boundary is fixed and the two-user acceptance matrix below passes.

## 2026-09-04 observation and live evidence

A colleague created a separate approved-domain account and sent an Overview
screenshot that showed the same two demo locations and KPI values as the
existing owner account.

Read-only investigation confirmed:

- the colleague account authenticated successfully but created no source
  imports, master versions, activations, or planning runs;
- all 10 persisted imports, both master versions, and all six persisted runs
  were created by the pre-existing owner account;
- the active master was created on 2026-09-02 and contains
  `LOC_DEMO_BERLIN_001` / **Demo Kitchen Berlin** plus
  `LOC_DEMO_HAMBURG_002` / **Demo Kitchen Hamburg**;
- the colleague account was created on 2026-09-04, after those shared records;
- the screenshot therefore displayed the existing shared backend state. It was
  not evidence that the colleague had independently uploaded the same filled
  templates;
- the live frontend and Supabase-backed API were reachable, readiness was
  healthy, and an anonymous Overview request correctly returned `401`.

The colleague did not alter persisted planning data during this test. The
security problem is nevertheless real: any accepted account can currently see
and potentially mutate the same workspace.

## Root cause

The application implements authentication but not user/workspace/location
authorization:

- `apps/api/supply_planning_api/auth.py` accepts any confirmed account from an
  allowed company domain and treats it as a full maintainer.
- `apps/api/supply_planning_api/routes.py` requires a bearer token, but most
  read routes name the dependency `_user` and discard the resolved user before
  calling the backend.
- `apps/api/supply_planning_api/services.py` selects the active master by the
  shared `APP_ENV`, selects source imports by dataset/location, and selects runs
  by run ID. None of those reads include user, workspace, or membership scope.
- Uploads and runs store `created_by`, but that field is audit provenance only;
  it is not used as an ownership or authorization predicate.
- `apps/api/supply_planning_api/repository.py` uses the server-side Supabase
  secret for PostgREST operations. The existing RLS/revokes correctly stop
  browser roles from reading tables directly, but they do not isolate users
  when the API performs unscoped server-authority queries.
- The schema has no workspace/tenant ownership and no user-to-location
  membership table. `environment` and `location_id` are business/runtime
  dimensions, not authorization boundaries.
- The browser clears its in-memory API cache on sign-out and user change, so
  the matching Overview is not explained by stale data from the previous
  browser account.

## 2026-09-04 implementation progress

Implemented locally, not yet deployed:

- migration `202609040008_user_workspace_isolation.sql` provisions a separate
  empty private workspace and owner membership for every existing and future
  Auth user;
- every persisted planning relation now has a required `workspace_id`, with
  workspace-local active-master uniqueness and composite foreign keys that
  prevent cross-workspace aggregate links;
- the migration backfills root records only through their recorded audit actor
  and aborts when attribution or existing location relationships are unclear;
- database triggers validate master/import/run actors and prevent stock/PO
  child rows or planning result rows from changing location inside a trusted
  transaction payload;
- `SupabaseAccessResolver` re-checks the user's profile, one active default
  membership, role, and optional location grants on every request;
- `WorkspaceScopedStore` is now an unavoidable boundary around all 18 planning
  relations. It injects workspace filters and write fields, checks location
  read/write grants, checks the authenticated audit actor, rejects mismatched
  child locations, and namespaces deterministic result IDs per workspace;
- routes reserve master/planning workbook import and master activation for
  owners/admins, while stock/PO import and calculation require location-write
  access;
- `/api/v1/me` exposes the resolved workspace/role contract; and
- the browser memory cache is cleared and namespaced by authenticated user, so
  an account switch cannot reuse the previous account's entries.

Focused automated checks cover two distinct private workspaces, all planning
relations, direct cross-workspace filters, planner location grants, spoofed
audit actors, cross-location child payloads, workspace-admin routes, schema
requirements, and the synthetic seed. These checks pass. A real PostgreSQL
migration application and deployed two-account test are still required.

A second read-only live preflight checked the exact relationships migration
008 will use. Across 10 source imports, two master versions, and six planning
runs there are zero missing root audit actors, zero master/import/run ownership
chain mismatches, and zero stock/PO or planning-result location mismatches. No
live row was changed. This makes the current backfill eligible to run, but is
not a substitute for post-migration reconciliation.

## 2026-09-05 migration defect found and fixed

The first real application of migration 008 aborted with
`P0001: Finalized source imports are immutable; upload a new version.` from
`reject_accepted_source_import_mutation_v1`. The migration-003 immutability
triggers fire on the `workspace_id` backfill even though it stamps only the new
discriminator and changes no planning value, actor or timestamp. Ten triggers
on `source_imports`, `locations`, `items`, `item_policy_overrides`,
`delivery_rules`, `forecast_daily`, `menu_calendar`, `bom_lines`,
`inventory_snapshots` and `purchase_order_lines` block it; the remaining
relations have no such guard. In-process tests could not catch this because
their fake stores have no triggers.

Migration 008 now lifts exactly those guards with `disable trigger user`
immediately before the backfill and restores them with `enable trigger user`
immediately after, inside the same transaction, so a failed migration cannot
leave the immutability contract switched off. Internal foreign-key triggers
stay in force throughout.
`tests/test_supabase_schema.py` asserts the paired statements and their
ordering.

The corrected migration was then dry-run in full against the development
project inside an explicit transaction ending in `rollback`. It reached the end
of the schema section and produced three workspaces, three owner memberships,
and all ten existing source imports in exactly one workspace, leaving the two
colleague workspaces empty. The rollback left no new table, no `workspace_id`
column and no disabled trigger behind.

Note for whoever applies it: the error
`42P01: relation "public.master_data_versions" does not exist` means the script
ran against a database that does not have migrations 001-007, not a defect in
008. Confirm the target project matches `SUPABASE_URL` in `.env` first.

Approved-domain self-service sign-up intentionally remains available: after
migration 008, a successful sign-up creates a new empty private workspace.
Invitation-only admission would be a separate policy decision, not a necessary
condition for tenant isolation.

This behavior was documented as an expedient private-prototype decision in
`docs/descriptions/ui_api_and_persistence_foundation.md` and
`docs/scratchpads/ui_and_supabase_foundation.md`: any valid project user was a
maintainer and role tiers were deferred. Self-service sign-up made that
prototype assumption unsafe for multi-user testing.

## Confirmed exposure and mutation surface

Today, any confirmed account from an approved company domain can potentially:

- list every active location and see the cross-location Overview;
- inspect inventory, source-import metadata and validation issues, observed PO
  lines, planning runs, netting/projection details, recommendations and
  exceptions for any location;
- retrieve another user's import or run directly when its ID is known;
- download another user's recommendation CSV/JSON;
- upload the global master/planning workbooks or stock/PO data for any existing
  location;
- create a run for any existing location; and
- activate an accepted master version, changing the shared active master for
  every user.

Anonymous users remain blocked, browser roles cannot directly query the domain
tables, allowed-domain and confirmed-email checks work, and the elevated key is
not bundled in Vite. Those controls are valuable but do not provide isolation
between accepted users.

## Required authorization model

Use a private workspace/account boundary rather than treating `created_by` as
the only ownership key:

1. Create `workspaces` and `workspace_memberships`. A new user receives a
   private workspace by default and is not automatically joined to another
   workspace because their email domain matches.
2. Every location belongs to exactly one workspace. A user can have multiple
   locations inside their workspace. Optional collaboration must require an
   explicit membership invitation; private-by-default is the invariant.
3. Add roles with a minimal first contract:
   - `owner`/`admin`: manage workspace members, locations, and intentionally
     shared master/planning inputs;
   - `planner`: view and operate only explicitly assigned locations;
   - `viewer` only if a real read-only use case is approved.
4. Add `workspace_id` to every root aggregate, at minimum master versions,
   source imports, and planning runs. Location-scoped child rows must be tied
   to a location in the same workspace through database constraints. Do not
   rely on globally unique text IDs as authorization.
5. Keep `created_by`/`activated_by` for audit. Ownership and membership are
   separate fields and checks.
6. Treat truly global reference data as a separate explicit admin scope. Do
   not make stock, purchase orders, forecasts, menus, runs, or recommendations
   global merely because item definitions or a BOM may be reusable.

## Required API and database enforcement

- Resolve every authenticated user to an `AccessScope` containing workspace,
  role, and allowed location IDs before executing a domain operation.
- Pass that scope through every backend method; eliminate authenticated routes
  that discard `_user`.
- Scope list/latest/dedup queries by workspace before dataset/location filters.
- Scope direct import, version, run, risk and export lookups by workspace and
  permitted location. Return a non-leaking `404` or an agreed `403`; never
  reveal whether another workspace's identifier exists.
- Reject stock/PO uploads and run requests for unassigned locations.
- A planning workbook containing several locations must either be restricted
  to workspace-admin upload or normalized into independently authorized
  location slices. Never silently accept rows for unauthorized locations.
- Make master activation workspace-local and admin-only. The unique-active
  index must be per workspace/environment, not environment alone.
- Use database enforcement as defense in depth. Preferred direction: use the
  authenticated user's JWT for membership-scoped reads protected by RLS, and
  keep elevated authority only for narrow transaction functions that verify
  actor/workspace/location membership. If server-authority reads remain, every
  repository method still needs an unavoidable scoped interface and negative
  tests because service-role requests bypass RLS.
- Include user/workspace identity in browser resource-cache keys in addition to
  clearing the cache at Auth boundaries.

## Existing-data migration

- Create one private workspace for the current owner account.
- Backfill the current master versions, locations, imports, normalized rows,
  runs, recommendations, exceptions, netting and projections into that
  workspace without changing calculation values or audit timestamps.
- Assign both existing demo locations to the owner workspace.
- Create an empty private workspace for the colleague account; do not copy the
  owner's demo data into it.
- Validate row counts, foreign keys, active-master uniqueness, hashes and run
  reproducibility before and after backfill.
- Do not delete or rewrite existing audit actor fields during migration.

## Immediate containment before the permanent fix

- Disable self-service sign-up or switch to admin invitation/allowlisting.
- Keep only synthetic/demo data in the deployed development environment.
- Ask current testers not to upload, activate, or run planning until isolation
  is deployed.
- Review existing Auth users and persisted `created_by`/`activated_by` audit
  fields. The 2026-09-04 read-only audit found no colleague-created planning
  records.
- Do not rotate the browser publishable key as a substitute for authorization;
  it is intentionally public. Keep protecting the server secret.

## Two-user acceptance matrix

The goal is not complete until two independent accounts, clean browser
sessions, and API-level negative tests prove all of the following:

- [ ] User A creates locations A1/A2; User B creates location B1.
- [ ] A's location list and Overview contain only A1/A2; B sees only B1.
- [ ] A cannot fetch B1 by path, even with the exact location ID.
- [ ] A cannot list or fetch B's import, master version, run, PO, inventory,
      projection, recommendation, risk, or export by a known exact ID.
- [ ] A cannot upload stock/PO data or start a run for B1.
- [ ] A cannot include B1 in a planning-input upload.
- [ ] A non-admin cannot upload/activate global data or manage memberships.
- [ ] Duplicate detection and “latest import/run” selection never cross a
      workspace boundary.
- [ ] Switching accounts in one browser clears or partitions cached domain
      data and never flashes the previous user's content.
- [ ] Direct browser-to-Supabase table access remains denied unless protected
      by the new membership RLS contract.
- [ ] Audit rows retain the real actor and workspace/location scope.
- [ ] Live deployed testing repeats the matrix with separate profiles and
      confirms Overview, Location, Data & settings, downloads and mutations.

## Decisions and open questions

- Confirmed requirement: users see only their own/permitted data and can have
  their own locations. Default to private; do not block implementation waiting
  for a future collaboration policy.
- Decide which master/BOM/item information, if any, is intentionally global and
  who has the admin role. Until approved, keep it workspace-scoped.
- Decide whether one location may later be shared by multiple users. The
  membership model can support this without weakening the default.
- Decide whether removing access should revoke active sessions immediately or
  on the next API request/token refresh. The API must at least re-check current
  membership on every request.

## Next steps

1. Keep the deployment synthetic-only and pause additional external testing.
2. Deploy the workspace-aware API first so authenticated domain access fails
   closed during the short migration window.
3. Apply migration 008 to development and reconcile row counts, ownership,
   foreign keys, active masters, timestamps and hashes.
4. Deploy/verify the browser build and confirm its account cache boundary.
5. Run the full live two-browser/API acceptance matrix above.
6. Close the promotion blocker only after deployed proof; separately decide
   whether invitation-only admission or shared-workspace administration is
   wanted as product policy.
