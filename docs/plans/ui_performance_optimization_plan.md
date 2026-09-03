# UI page-load performance optimization plan

**Status:** tranche 1 implemented and automatically verified; authenticated browser check pending
**Created:** 2026-09-03

## Goal

Make the three-page maintainer UI feel immediate when moving between recently
visited pages, and materially reduce warm first-load latency without changing
planning calculations, risk semantics, source timestamps, or the proposal-only
scope.

The first implementation tranche fixes the two confirmed cross-cutting causes:

1. route data is discarded and fetched from zero on every page mount; and
2. Auth and PostgREST requests repeatedly create short-lived HTTP clients
   instead of reusing connections.

Backend query-shape changes follow as a separately measured tranche. This keeps
the first change small enough to verify and avoids prematurely adding database
views, RPCs, or page-specific persistence contracts.

## User-visible problem

- Overview, Location planning, and Data & settings take roughly 3–4 seconds to
  become useful.
- Returning to a page opened only seconds earlier shows the same full loading
  state and pays the complete request cost again.
- Location planning has a second loading phase because the latest run cannot be
  requested until planning status has supplied its id.

## Evidence and baseline

Read-only probes were run on 2026-09-03 against the configured development
Supabase project. They selected only aggregate/read-model data and made no
writes. Timings below are from the local backend directly to Supabase; they do
not include browser-to-API latency, CORS/preflight, Render scheduling, or the
remote Auth verification performed by every API endpoint.

| Current backend read | Supabase reads | Observed time |
|---|---:|---:|
| `list_locations` | 5 | 402–489 ms |
| `planning_status` | 11 | 764–843 ms |
| `inventory` | 7 | 535–550 ms |
| `get_planning_run` | 12 | 699–769 ms |
| `overview` for two active locations | 35 | 2,444–2,485 ms |
| `list_imports` | 1 | 198 ms |
| `list_master_versions` | 1 | 123 ms |

The current Location route starts locations, status, and inventory reads, then
starts the latest-run read only after status resolves. Across the route this is
35 database reads and four separately authenticated browser API calls. The
critical data path is at least `planning_status` followed by
`get_planning_run`, about 1.5 seconds before browser/API/Auth overhead.

The measured latest-run payload is 121.7 KiB: 9 inputs, 10 planning lines,
10 recommendations, 23 exceptions, 5 netting results, 230 projection days, and
10 explanations. It is worth keeping bounded, but it is not the primary cause
at the current data size.

An isolated read-only comparison changed only HTTP-client lifetime. Reusing one
`httpx.AsyncClient` produced:

| Read | Client per request | Shared client | Change |
|---|---:|---:|---:|
| `list_locations` | 489 ms | 239 ms | -51% |
| `planning_status` | 764 ms | 520 ms | -32% |
| `inventory` | 550 ms | 390 ms | -29% |
| `get_planning_run` | 738 ms | 461 ms | -38% |
| `overview` | 2,444 ms | 1,625 ms | -34% |

These are directional measurements from one session, not production service-
level targets. They do establish that connection churn is material while also
showing that query count remains a second bottleneck.

## Confirmed causes

1. `useApiResource` deliberately has no cache, initializes each enabled mount
   as loading, clears data during refetch, and aborts/discards it on unmount.
   React Router therefore recreates each route with no remembered result.
2. Data & settings starts imports, master versions, locations, and selected-
   location status independently. Location planning starts three reads and then
   waterfalls into the latest run.
3. `SupabaseCanonicalStore._request` creates and closes an
   `httpx.AsyncClient` for every PostgREST operation. The Auth verifier does the
   same for every API request. TCP/TLS connection setup is repeatedly paid.
4. Active/versioned master data is reloaded by locations, status, inventory,
   and latest-run explanation paths, including duplicate loads during one page
   visit.
5. Overview calls `planning_status` sequentially for each location and then
   performs more per-location netting/recommendation/exception/PO reads. The
   browser makes one Overview request, but the backend still has an N+1 read
   pattern.
6. React Strict Mode can duplicate effect setup during local development. It
   may amplify request volume there, but it is not the production fix and must
   not be removed to hide uncached/undeduplicated fetching.

## Unknowns to measure, not assume

- A deployed Render cold start, service tier, and Vercel/Render/Supabase region
  placement may add latency. They have not been verified and do not explain why
  a recently visited route loses all content.
- Browser timing by DNS, preflight, Auth, time-to-first-byte, download, JSON
  parse, and React render still needs one authenticated production-like trace.
- The query-reduction target should be based on after-tranche-1 measurements;
  do not introduce materialized KPI tables before simpler batching is tested.

## Decisions and boundaries

- A source's `source_at`/`imported_at` timestamps remain the freshness truth.
  Keeping that immutable response briefly in the browser does not claim that a
  new source was imported.
- Use a small project-owned resource cache first; do not add TanStack Query in
  tranche 1. Revisit a library only if polling, pagination, optimistic updates,
  or more complex invalidation makes the custom mechanism unsafe.
- Cached data is scoped to the signed-in browser session, cleared on sign-out,
  and never persisted to disk by the new cache.
- First load remains fail-closed. A background refresh may preserve a known
  result, but an error must remain visible and must not silently relabel cached
  data as current.
- Upload, master activation, and planning-run mutations explicitly invalidate
  affected resources. Time alone is not the only invalidation mechanism.
- HTTP connection reuse changes transport lifetime only. It must not cache or
  weaken bearer-token validation, RLS, or server-side authorization.
- No Phase 1 logic, supplier dispatch, approval, ERP write, browser-side
  planning arithmetic, new database, or migration is part of this plan.

## Tranche 1 — immediate revisits and connection reuse

### 1A. Establish regression coverage

- [x] Add frontend tests proving that a recent cached success is rendered on
      remount without a page-level loading blank.
- [x] Test fresh-cache reuse, stale background revalidation, in-flight request
      deduplication, explicit invalidation, refresh failure, and cache clearing
      when the authenticated session ends.
- [x] Add backend tests proving the repository and identity verifier can share
      an injected async client and that application shutdown closes only the
      client owned by the app.
- [x] Keep existing request/error tests; transport failures and sanitized
      user-facing errors must behave exactly as before.

### 1B. Reuse backend HTTP connections

- [x] Create the owned `httpx.AsyncClient` lazily through an app-owned wrapper
      and close it during FastAPI shutdown.
- [x] Inject the shared client into `SupabaseCanonicalStore` and
      `SupabaseIdentityVerifier`; retain `MockTransport`/fake seams for tests.
- [x] Remove the per-operation `async with httpx.AsyncClient(...)` blocks while
      preserving timeout, headers, secret handling, and response mapping.
- [x] Verify concurrent reads share the async-safe client. Retain httpx's
      bounded default connection pool until measurements justify a narrower
      limit.

### 1C. Preserve frontend server state

- [x] Give every resource an explicit stable cache key: Overview, locations,
      imports, master versions, planning status by location, inventory by
      location, POs by location, and planning run by run id.
- [x] Store successful results and fetch time in a module-owned, memory-only
      cache. Use an initial 30-second fresh window; make the value a named UI
      transport policy rather than scattering literals.
- [x] Deduplicate concurrent requests for the same key, including Strict Mode
      remounts. Do not let one unmount abort a request still used by another
      subscriber.
- [x] Return cached data immediately on remount. When stale, keep the data
      visible while revalidating and expose a non-blocking refreshing state.
- [x] Keep the full loading state only when no usable cached result exists.
- [x] Clear all cached domain data on sign-out, Auth loss, restored-session
      ownership reset, or an authenticated-user change.

### 1D. Make mutation invalidation explicit

- [x] After a successful source import, invalidate import history and every
      active read model affected by that dataset. A master draft invalidates
      versions but not active planning data until activation.
- [x] After master activation, invalidate master versions, locations, Overview,
      all planning statuses, and inventory labels derived from master data.
- [x] After a planning run, seed/cache the returned run and invalidate the
      selected planning status plus Overview without discarding the visible
      fresh result.
- [x] Preserve the current explicit Refresh/Retry behavior and ensure it forces
      a network request even inside the fresh window.

### 1E. Verify tranche 1

- [x] Run focused backend and frontend tests while iterating.
- [x] Run the full Python suite plus focused Ruff/strict mypy on changed Python
      files and the complete `pnpm check` frontend pipeline.
- [x] Repeat the read-only backend timing probe at least three times and record
      median/range, not one best result.
- [ ] In an authenticated browser, capture first visit and immediate revisit
      for Overview, Data & settings, and one Location. Record request count,
      loading-state behavior, and time to useful content.
- [x] Update this plan, the UI backlog, scratchpad, description, and project
      memory with measured results and any superseded assumptions.

### Tranche 1 acceptance

- Revisiting a successfully loaded route inside the fresh window renders its
  known content immediately and does not show the full-page loading state.
- A stale or explicitly invalidated resource revalidates without hiding known
  content; errors are still visible.
- No duplicate same-key request is issued by concurrent consumers or a Strict
  Mode remount.
- Every authenticated request is still validated; no token or elevated key is
  cached in the new resource cache.
- The backend does not instantiate one HTTP client per Supabase operation.
- The existing planning/risk/source semantics and all applicable tests pass.
- Direct warm backend timings materially improve relative to the recorded
  baseline. The original 25% directional threshold was met or narrowly missed
  depending on the path and baseline sample; the retained query counts explain
  the remaining gap and make tranche 2 necessary rather than optional polish.

### Tranche 1 measured result

The implemented app-level client was measured through one current pooled store
for three consecutive read cycles. Query counts did not change in this tranche.

| Read | Post-change median | Post-change range | Change versus original observed range |
|---|---:|---:|---:|
| `list_locations` | 240 ms | 238–717 ms | warm samples about 40–51% faster |
| `planning_status` | 614 ms | 583–872 ms | median about 20–27% faster |
| `inventory` | 400 ms | 395–404 ms | median about 25–27% faster |
| `get_planning_run` | 538 ms | 536–541 ms | median about 23–30% faster |
| `overview` | 1,866 ms | 1,827–1,887 ms | median about 24–25% faster |

The first `list_locations` sample was a 717 ms warm-up outlier; the following
two were 238 and 240 ms. These timings remain direct backend-to-Supabase reads,
not production browser service levels. Overview still performs 35 Supabase
reads, so its 1.87-second median confirms that connection reuse helped but did
not remove the dominant query-shape cost.

Automated verification passed: 93 Python unit/integration tests, focused Ruff
and strict mypy, 156 Vitest tests across 13 files, ESLint, TypeScript checking,
and a Vite production build. The navigation regression opens Overview, moves to
Data & settings, returns to Overview, and proves the cached content renders
without `Loading overview` or a second Overview request. The build reports a
1,178.08 KiB minified JavaScript chunk (355.92 KiB gzip); record it for tranche
3 because it affects initial asset loading, not the reported repeat-route wait.

An authenticated browser trace is still required before declaring the UX
accepted. It needs the maintainer's real session and is deliberately not
replaced by guessed timings from jsdom.

## Tranche 2 — reduce backend round trips

Start only after tranche 1 is measured so the remaining bottleneck is known.

- [ ] Add per-request query-count/timing instrumentation suitable for tests and
      safe aggregate production logs; never log tokens, keys, file contents, or
      private row values.
- [ ] Reuse one loaded active master within a composed request. Consider a
      short version-keyed in-process cache only if explicit activation
      invalidation and multi-instance consistency are documented.
- [ ] Replace Overview's sequential per-location `planning_status` calls with
      set-based reads grouped in Python. Parallelizing the current N+1 shape is
      an interim step, not the final query plan.
- [ ] Design a Location bootstrap/read-model endpoint only if it reduces the
      measured waterfall without creating a second planning contract. It may
      compose status, location metadata, latest result summary, and inventory;
      the pure engine remains untouched.
- [ ] Reassess Data & settings after shared locations/versions/imports caching;
      do not add a new endpoint if the route is already acceptably fast.
- [ ] Set query-count regression ceilings for the two-active-location fixture
      and confirm query growth is not linear where set-based reads are possible.
- [ ] Repeat authenticated browser and direct-backend measurements before
      deciding whether a database view/RPC is justified.

### Tranche 2 acceptance

- Overview no longer calls complete planning status sequentially per location.
- Location does not reload identical active-master tables through independent
  page requests where one composed read can safely share them.
- Query counts and warm latency are recorded for two locations and for a larger
  synthetic location count.
- No materialized summary table or new persistence authority is introduced
  without evidence that batching alone is insufficient.

## Tranche 3 — payload and deployment follow-up, only if still material

- [ ] If run payload size/rendering becomes material, split or conditionally
      include `projection_days` so an unopened item timeline is not required for
      initial page content.
- [ ] Consider navigation hover/idle prefetch after cache correctness is proven.
- [ ] Capture Render cold/warm health and authenticated endpoint traces and
      verify service/region placement. Change service tier or topology only from
      measured evidence and an explicit cost decision.
- [ ] Consider local JWT verification or a tightly bounded identity cache only
      if remote Auth verification remains a measured bottleneck. Document key
      rotation, expiry, revocation lag, and security trade-offs first.
- [ ] Define user-facing performance budgets for warm first view, revisit, and
      mutation refresh once deployed measurements are available.

## Risks

- Incorrect invalidation could show a genuinely superseded result. Tests must
  enumerate each mutation/resource relationship before enabling caching.
- Sharing an HTTP client requires explicit ownership and shutdown; test-created
  clients must not be closed unexpectedly.
- Background-refresh errors can become invisible if the state model retains
  only data. Keep error/refresh information separately available to the page.
- A module cache can leak data between users if it survives sign-out. Clearing
  it on every auth loss is a release blocker.
- Faster parallel queries can overload the same upstream while hiding an N+1
  pattern. Tranche 2 should reduce reads, not only overlap them.

## Progress

- 2026-09-03 — Implemented tranche 1. Added the session-owned resource cache,
  explicit mutation invalidation, Auth-boundary clearing, visible background-
  refresh errors, app-owned pooled Supabase transport, and regression tests.
  All automated checks pass. Three-cycle direct probes put Overview at a
  1,866 ms median while retaining 35 reads, so tranche 2 should target query
  shape after the pending authenticated-browser acceptance check.
- 2026-09-03 — Diagnosed the current route, API, Auth, and PostgREST paths;
  recorded two-location query counts, direct timings, payload size, and a
  connection-reuse comparison. Selected the cache/connection-lifetime tranche
  as the first implementation because it directly fixes repeat navigation and
  is independently verifiable before endpoint/query redesign.
