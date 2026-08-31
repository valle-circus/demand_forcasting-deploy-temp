# Maintainer UI — handover

**Status:** the frontend slice defined in
`docs/claude_code_first_ui_pages_brief.md` is complete. WP0–WP6 are done.
`pnpm check` passes from `apps/web`: lint, typecheck, **128 tests**, production
build.

**Branch:** `ui_implementation`. Not merged to `main`.

This document is the status quo, what is deliberately not built, what is worth
improving, and what someone picking this up next should know.

---

## 1. What a maintainer can do today

The full journey works end to end against the live API and a real Supabase
session. Verified in a browser, not only in tests.

1. Sign in with an admin-created Supabase account.
2. See on **Overview** whether anything needs attention, and go straight there.
3. Import the four sources in order on **Data & settings**, activate a master
   version, and read validation issues with their remedies.
4. Open a **location**, see what is blocking a run, compute one, and read the
   result.
5. Inspect any ingredient's projected stock, and any proposal's full derivation.
6. Download the server-generated CSV or JSON.

Nothing in the UI places, approves, sends or tracks a supplier order.

---

## 2. The three rules the code enforces

These are not style preferences. They are the reason the slice is safe to build
on, and breaking them would reintroduce bugs that have already been fixed once.

### No planning arithmetic in the browser

`features/location-planning/planning.ts` reads fields. It does not add,
subtract, cap or round. Where the UI says *why* a quantity came out as it did,
it quotes the engine's `binding_constraint`, `constraint_status` and
`planning_exceptions` rather than comparing numbers.

`planning.test.ts` pins this with a line whose fields deliberately do not add
up, asserting the UI still shows what the engine stored. **If those ever
disagree in production, the bug is in the engine and must stay visible.**

### Risk comes from the backend's classification, never from a date

Three helpers were deleted during the v2 adoption because their meaning came
from the wrong field: `riskLevel`, `daysOfCover`, `horizonDays`. The first
treated any `first_stockout_date` as current risk, which swept in shortages a
later review handles and badly inflated the risk list.

Risk now reads `actionable_risk_status`. A shortage after the protection
horizon renders **Replan later**, and `not_evaluated` is its own state.

### Unknown is never rendered as zero

A count with no current run behind it shows **not known**; a stale location's
risk cell shows a dash. Zero would claim an all-clear nobody established — the
same class of error as the old risk definition.

---

## 3. Deliberately not built

Each of these is a decision, not an omission. Reverse any of them freely.

| Not built | Why |
|---|---|
| Self-service sign-up | The brief forbids it, and FastAPI treats every valid project user as a maintainer, so a signup form on a deployed URL would hand out maintainer access. Accounts are created in the Supabase dashboard. |
| Demo/preview fixture mode | Proposed while the backend looked unverified. Once readiness came back green it would only add a second code path that could show fake data. Fixtures live in Vitest only. |
| Field-level master, menu and BOM editors | The brief defers them. They render as visibly disabled *planned* features rather than controls backed by no API. |
| Data-freshness panel and observed-PO blocks on Overview | Journey doc §5.2 lists them as separate sections. Source freshness is already a column in the location table, and a secondary PO summary adds weight to a page whose job is "what needs attention now". **Worth a second opinion.** |
| Cross-ingredient coverage chart | Requested, then deferred: the demo has one ingredient, so sorting, colour and label crowding cannot be judged. See §5. |
| Dark mode | The `circus-ui` skill says only if asked. A half-done dark mode is worse than none. |

---

## 4. Known limitations

- **The run is synchronous.** No job id, no polling, no idempotency key. The UI
  prevents duplicate submission with an in-flight ref, but a dropped connection
  mid-run leaves the maintainer without a result they may in fact have got.
  A deterministic `run_id` returning the existing run would fix this properly.
- **`GET /planning-runs/{id}` returns every projection day for every item.**
  Fine at one ingredient; it will not be fine at two hundred across a long
  horizon. The chart already renders one item's rows only, so the cost is
  transfer, not rendering.
- **`/overview` is slow.** It is one request from the browser, as required, but
  the server still walks each location. Expect this to be felt at 15 locations.
- **No historical stock.** `planning_projection_days` starts at the run date, so
  the item chart cannot show where stock has actually been.
- **The bundle is ~770 kB** (236 kB gzipped), mostly Recharts. No code splitting
  yet; the chart is a good first `React.lazy` boundary.
- **Only one ingredient and one location have ever been exercised.** Every
  table, sort and empty state is correct in tests, but crowding, column widths
  and scroll behaviour at realistic volume are unverified.

---

## 5. What I would improve next, in order

1. **Get realistic data into a location.** Twenty-plus ingredients, three-plus
   locations. Almost every remaining UI question — column widths, sorting,
   pagination, whether the coverage chart works — is unanswerable without it,
   and guessing produces exactly the kind of rework this slice has already had.
2. **The cross-ingredient coverage chart.** Ingredients against days of cover,
   sorted worst-first, horizontal bars. Needs the backend to persist three
   day-counts per item: cover from usable stock, added by open POs, added by the
   proposed receipt. **Do not compute it as `stock / average daily demand`** —
   that assumes flat demand while the engine projects day by day through the
   dated forecast, and the two would disagree precisely on the lumpy items that
   matter most.
3. **Idempotent runs**, so a retry after a dropped connection is safe.
4. **Code-split the chart** to get the initial bundle down.
5. **German**, if the kitchen staff need it. Strings run ~30% longer; the
   layouts are flexible but untested at that width.
6. **An end-to-end test** over the real journey. Vitest covers behaviour well,
   but nothing yet catches a break in the whole chain except a human clicking.

---

## 6. Where things live

| Concern | Path |
|---|---|
| Typed API client, errors, formatting, hooks | `apps/web/src/lib/` |
| Shell, auth, routing, remembered location | `apps/web/src/app/` |
| Shared primitives (status, freshness, info hints, states) | `apps/web/src/components/` |
| Vendored shadcn/ui — we own and edit these | `apps/web/src/components/ui/` |
| The three pages | `apps/web/src/features/{overview,location-planning,data-settings}/` |
| Design tokens, motion, reduced-motion | `apps/web/src/styles.css` |

Working notes and the reasoning behind each decision:
`docs/scratchpads/ui_implementation.md`. Ordered work packages and contract
requests: `docs/plans/ui_implementation_backlog.md`. Product behaviour:
`docs/descriptions/ui_maintainer_journey_and_page_plan.md`.

---

## 7. Running it

```
# API, from the repository root
uvicorn apps.api.supply_planning_api.main:app --reload

# Web, from apps/web
pnpm dev        # proxies /api to localhost:8000
pnpm check      # lint, typecheck, tests, build
```

`corepack enable` needs an elevated terminal on this machine. Without it there
is no `pnpm` shim on PATH; `corepack pnpm <script>` works, and `check` chains
its tools directly so it does not depend on one.

---

## 8. Before this ships to anyone real

- Apply the migrations and configure environment values in the target Supabase,
  Render and Vercel projects, then verify readiness, CORS and Auth there.
- Decide whether admin-created email/password accounts and the
  every-user-is-a-maintainer policy are acceptable in production, or whether
  SSO and role tiers are needed first.
- Agree freshness thresholds. The UI currently shows raw ages and the server's
  own verdict, and invents no cutoffs of its own.
- Run the real journey with the maintainer on real data and correct the
  information hierarchy and terminology before any visual polish.
- The operational gate still applies: every recommendation is labelled
  proposal-only until it passes.
