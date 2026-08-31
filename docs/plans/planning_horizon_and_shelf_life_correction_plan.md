# Planning horizon and shelf-life correction plan

## Goal

Make every customer-facing stock risk and order recommendation use one explicit,
actionable time window, and prevent a normal proposal from implying that stock
may safely be ordered when the projected candidate quantity cannot be consumed
before expiry.

Status: **backend/engine implementation complete; Supabase migration application
and frontend adoption pending** (2026-08-30).

This plan covers the pure engine, FastAPI read models, persisted derivations,
and the Location planning/Overview presentation. It does not add supplier
dispatch, approval, or ERP scope.

## Evidence reviewed

- `src/supply_planning/engine/recommend.py`
- `src/supply_planning/engine/netting.py`
- `src/supply_planning/application/run_improved.py`
- `apps/api/supply_planning_api/services.py`
- `apps/web/src/features/location-planning/RiskStockTab.tsx`
- `apps/web/src/features/location-planning/StockProjectionChart.tsx`
- the synthetic connected packet and a deterministic local replay at
  `2026-08-29T12:00:00+02:00`

The exact replay reconciles as follows:

| Measure | Value | Meaning |
|---|---:|---|
| Opening usable stock | 2 kg | observed opening balance |
| Existing PO | 2 kg | confirmed input receipt on 2 Sep |
| New proposal | 6 kg | candidate receipt on 1 Sep |
| Demand in recommendation horizon | 8 kg | 29 Aug–7 Sep, the configured 10-day protection horizon |
| Safety stock | 1.6 kg | proposed two safety days using the horizon average |
| Raw order | 5.6 kg | post-netting target before pack rounding |
| Final proposal | 6 packs / 6 kg | rounded purchasable quantity |
| Demand in uploaded forecast | 42 kg | 29 Aug–11 Oct, not the current order target |
| Full-forecast closing balance | -32 kg | counterfactual if only this one proposal is ever placed |
| First full-forecast shortage | 10 Sep | after the current recommendation horizon ended on 7 Sep |

The screenshot is from a run one day later, so it displays 43 days and about
`-31 kg`; the same semantic mismatch applies.

The corrected replay is `improved-ded5498f7198`. It still proposes 6 kg because
that quantity is feasible, but now returns the meaning explicitly:

- `actionable_risk_status = covered` through 7 Sep;
- full-forecast `first_stockout_date = 2026-09-10` as secondary context;
- `projected_balance_at_risk_horizon_end_g = 2000`;
- estimated candidate expiry `2026-09-30`, basis
  `policy_approximation`, complete forecast evidence, and zero projected
  candidate residual at expiry;
- supply-position-aware shelf-life and max-cover caps of 27 kg and 11 kg; and
- no binding constraint for the 6 kg proposal.

## Findings

### F1 — “At risk” mixed two horizons before the v2 backend contract

Severity: **high**. Confidence: **high**.

The engine emitted `PROJECTED_STOCKOUT` only when shortage occurred within the
active recommendation horizon, while the old API summary, Overview, and React
helper treated any non-null `first_stockout_date` across the complete uploaded
forecast as risk. In the demo, the recommendation covers through
7 Sep and the first shortage is 10 Sep only because no second planning cycle is
simulated. The engine correctly reports zero active-horizon stockout issues,
while the UI reports one item at risk.

The backend is corrected. React still needs to consume
`actionable_risk_status` rather than its old helper.

### F2 — the chart hides the event arithmetic

Severity: **medium**. Confidence: **high**.

The daily balance series includes both the existing 2 kg PO and the new 6 kg
candidate, but the chart only labels their dates by colour. A maintainer reading
“On order 2 kg” reasonably cannot explain the roughly 8 kg receipt jump.
`type="monotone"` also draws a smooth curve between daily closing balances, so
its visual zero crossing does not align with the engine's discrete first
shortage day.

### F3 — “Needed,” “Lasts,” and the negative balance are not actionable labels

Severity: **high**. Confidence: **high**.

- `Needed` currently shows demand over all uploaded forecast dates, not the
  quantity the current order decision protects.
- `Lasts N days` is time to the full-forecast shortage after both existing and
  proposed receipts. It includes zero-demand calendar days and is not the
  classic on-hand days-of-cover measure.
- a negative closing balance is cumulative uncovered demand, not physical
  stock. Showing `-31 kg` as stock makes an expected future replan look like a
  current catastrophe.

### F4 — the old shelf-life cap did not guarantee consumption before MHD

Severity: **high for operational use**. Confidence: **high**.

The old cap was gross adjusted demand from candidate receipt through the
candidate's nominal expiry. It does not account for projected on-hand stock,
earlier planned receipts, or existing POs that compete to satisfy that demand.
It therefore caps an order quantity, but cannot prove that the candidate lot is
fully consumed before expiry.

Counterexample: with a 10-day protection horizon, 1 kg/day demand, 4 kg still
available when a five-day-life candidate arrives, and a 6 kg raw gap, the
current cap permits a 5 kg order because five-day demand is 5 kg. If older stock
is consumed first, 4 kg of the candidate remains at its expiry.

The old implementation also left the cap null when the forecast ended
before the nominal expiry. That is insufficient evidence, not evidence that
the order is shelf-life-safe.

### F5 — nominal shelf life is not lot-level MHD

Severity: **high for chilled/fresh confidence**. Confidence: **high**.

The master stores a configured number of days from order or receipt. Current
stock and PO inputs do not contain lot/expiry quantities. The engine can provide
a transparent conservative approximation for the new candidate, but it cannot
claim exact total waste or FEFO safety for existing stock until lot-level MHD is
available.

### F6 — the demo's 10 days are policy input, not a system default

Severity: **medium**. Confidence: **high**.

The demo combines `lead_time_calendar_days = 3` from the item policy and
`review_period_days = 7` from the delivery rule. The seven-day review period is
still an unapproved V1 proposal. Different items legitimately have different
horizons; fresh uses delivery-to-service windows and pods currently use
`28 + 7 = 35` days.

## Terms that must remain separate

| Term | Owner | Purpose | User editable? |
|---|---|---|---|
| Forecast/data horizon | uploaded forecast/menu source | Last date for which demand evidence exists | Changed by importing a new source, not a run slider |
| Recommendation/protection horizon | item and delivery policy | Period this ordering decision must protect, normally lead time plus review cadence or the next feasible replenishment | Yes, through versioned maintained rules; not an ad-hoc global run setting |
| Pre-arrival horizon | lead-time/schedule policy | Period an order placed now cannot fix | Policy-derived |
| Shelf-life feasibility window | item MHD policy or lot expiry | Period in which the candidate must be consumed | Yes, through versioned item/lot data |
| Display horizon | UI only | Chart zoom for comprehension | Yes; must not alter the recommendation |

Recommendation: do **not** add one global “planning horizon” selector to the
run. It would let a user hide risk and would be wrong for mixed lead times.
Expose the active lead/review/MHD policy beside each derivation and later edit
it through a validated master-data draft. A chart toggle such as **Current
decision / Next 4 weeks / Full forecast** is appropriate because it changes
only presentation. A separately labelled what-if policy override may be added
later if it creates a versioned scenario and never masquerades as the active
rule.

## Implemented risk and metric contract

The primary item row should be decision-oriented:

| Metric | Definition |
|---|---|
| Usable now | opening usable stock from the selected snapshot |
| Existing receipts | accepted open POs due within the active decision horizon, with dates and quantities |
| Demand to protect | adjusted or base demand through the active protection end; label which one is shown |
| Recommended receipt | proposed quantity and date from the active planning line |
| Covered through | active protection end when no shortage occurs within it |
| Action required | shortage before candidate receipt, shortage within protection horizon, constraint conflict, or input blocker |

Full-forecast demand, future shortfall after the protection horizon, and the
forecast-through date remain useful secondary context. They must not feed
`items_at_risk`, the default risk filter, or the Overview alert unless the
backend explicitly classifies them as actionable.

`planning_netting_results` now persists:

- `risk_horizon_end_date` and `risk_evaluated_through_date`;
- `risk_horizon_fully_observed`;
- `actionable_risk_status` as `at_risk`, `covered`, or `not_evaluated`;
- `first_stockout_within_horizon_date` and
  `max_stockout_within_horizon_g`; and
- `projected_balance_at_risk_horizon_end_g`.

Run summaries, `/risks`, and `/overview` use the explicit status. A future
shortage is counted separately as context, and incomplete evidence is not
reported as covered.

Replace ambiguous labels:

- `Needed` → **Demand to protect through <date>**
- `Lasts` → **Shortage date** or **Covered through**
- `Ending stock -31 kg` → **Uncovered demand after <date> if no later orders
  are placed**
- `Runs out` after the active horizon → **Future replan expected**, not risk

## Implemented shelf-life logic

For each candidate receipt:

1. Derive the candidate expiry from exact lot data when available; otherwise
   use the configured anchor/days and label it `policy_approximation`.
2. Project the event ledger to the receipt date without allowing a new receipt
   to repair earlier unmet demand. Pre-arrival shortage stays a separate
   exception.
3. From receipt through expiry, simulate a tagged candidate lot day by day.
   Under the conservative no-lot-data approximation, consume other available
   supply before the candidate. Later receipts cannot satisfy earlier demand.
4. Find the largest candidate quantity whose projected residual at expiry is
   zero. This is the incremental shelf-life cap, not gross demand through
   expiry.
5. Apply max cover to projected post-receipt inventory position, not to order
   quantity in isolation.
6. Apply MOQ/case constraints. A hard MHD/max-cover cap must not be silently
   exceeded: use the largest feasible purchasable quantity at or below the cap,
   or return an explicit infeasible/manual-decision result when MOQ/case leaves
   no safe positive quantity.
7. Persist `candidate_expiry_date`, `shelf_life_cap_basis`,
   `projected_candidate_residual_at_expiry_g`,
   `forecast_through_expiry`, and the binding constraint.

If the forecast does not cover the candidate expiry, return a visible
`SHELF_LIFE_COVERAGE_INCOMPLETE` warning/blocker according to run mode. Do not
interpret a missing cap as unlimited shelf life.

For fresh items, validate that each delivery's covered service dates fall
within the receipt's shelf-life window. If protection/review demand is longer
than shelf life, split across feasible delivery cycles when rules exist;
otherwise surface an infeasible coverage exception rather than one oversized
order.

## UI requirements

- Default the chart to the current decision horizon. Provide display-only zoom
  to the full forecast.
- Label event quantities directly: **Existing PO +2 kg** and **Proposed +6 kg**.
- Use a daily step/linear representation, not a smoothed monotone curve.
- Distinguish non-negative projected usable stock from cumulative uncovered
  demand. Do not call a signed backlog “stock.”
- Mark **Shortage starts on <date>** at the first daily shortage; explain that
  daily grain cannot identify an intra-day crossing.
- Show active policy context: lead, review cadence, protection end, shelf-life
  days/anchor, max cover, next review date, and source/version.
- Show shelf-life evidence on each proposal: estimated expiry, projected
  residual at expiry, exact versus approximation, and insufficient-forecast
  warning.
- Keep all risk classification and shelf-life feasibility in Python/FastAPI.
  React formats and filters explicit server-returned fields only.

FastAPI now returns that policy context as `planning_line_explanations`, joined
from the immutable `master_data_version_id` used by the run, plus a shared
`explanation_context.field_lineage`. This closes the earlier read-model gap:
Claude does not need to infer lead/review/MHD/pack settings from calculation
dates. The contract remains honest that existing-stock lot MHD and persisted
dish/silo contribution rows are not available yet.

## Implementation sequence

- [x] **P0: fix the existing risk definition.** In FastAPI,
      classify actionable risk from planning-line coverage dates and persisted
      daily projection/exception rows. Make run summaries and Overview use the
      same definition. Add contract tests for a shortage after—but not within—
      the protection horizon.
- [ ] **Frontend: correct Location planning labels and chart semantics.** Use the
      active-horizon requirement as the primary number, show receipt quantities,
      default to the decision window, remove monotone smoothing, and demote the
      full-forecast counterfactual. Do not reimplement classification in React.
- [x] **P1: implement supply-position-aware shelf/max-cover caps** in the pure
      engine with tests for existing stock, open POs, incomplete forecast,
      pre-arrival shortage, pack rounding, MOQ infeasibility, and fresh windows.
- [x] **P1: extend portable result contracts** with expiry/cap basis/residual and
      actionable-horizon fields. Add one forward Supabase migration only for
      derivations that must persist; preserve Snowflake portability.
- [x] **P1 backend: expose policy context and MHD insight** in API read models.
- [ ] **Frontend: present policy context and MHD insight** in the proposal
      detail UI without recomputing it.
- [ ] Apply
      `supabase/migrations/202608300004_actionable_risk_and_shelf_life.sql`
      through the Supabase SQL Editor before the next connected planning run.
- [ ] **P2: add versioned maintained-rule editing** for lead, review, shelf life,
      max cover, and delivery cadence. Until then, the fixed master workbook is
      the only write path.
- [ ] **P2: add lot/expiry inventory input** before making high-confidence FEFO
      or waste claims for chilled/fresh stock.
- [x] Re-run the synthetic packet plus counterexample fixtures and update the
      Claude frontend handover after the backend contract is stable.

## Decisions and owner inputs still required

1. Confirm whether the ordinary stocked-item review cadence is genuinely seven
   calendar days or whether the Monday recheck is another normal ordering
   opportunity.
2. Confirm shelf-life meaning per item/category: order-date life, guaranteed
   remaining life at receipt, opened life, or exact lot MHD.
3. Confirm that MHD/max-cover are hard constraints: recommended default is to
   withhold an unsafe rounded proposal and show a manual-decision conflict.
   The v2 backend implements this as the safe provisional default; owner review
   may change the versioned policy, not silently bypass the constraint.
4. Identify whether Apicbase/Snowflake can provide lot/expiry quantity grain for
   chilled/fresh stock and whether supplier POs expose guaranteed remaining MHD.

## Progress

- 2026-08-30: reconciled the synthetic run, confirmed the full-forecast versus
  active-horizon risk inconsistency, confirmed the smoothed chart/event-label
  problem, and demonstrated that the current shelf cap is not
  supply-position-aware.
- 2026-08-30: implemented the v2 engine and persisted API contract, added the
  forward migration and v2 atomic persistence RPC, passed 83 Python tests and
  focused Ruff/mypy, and replayed the connected packet with one safe 6-pack
  proposal, zero actionable stockouts, and zero candidate residual at expiry.
  The final Overview read model now includes location metadata, freshness,
  earliest actionable risk, and aggregate locations-at-risk without browser
  fan-out.
