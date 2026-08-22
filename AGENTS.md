# AGENTS.md

This file defines the working rules for AI coding agents in this repository.
The project automates Phase 2 supply planning for autonomous robot kitchens:
daily dish demand is exploded through the BOM, inventory and open purchase
orders are netted, and auditable order proposals are produced for human review.

## Start every task

1. Write a short plan before editing files.
2. Read `MEMORY.md` for durable project facts and decisions relevant to the task.
3. Read the relevant files in `docs/descriptions/`. Until more focused
   descriptions exist, `docs/descriptions/phase2_supply_planning_brief.md` is the
   primary domain and architecture reference.
4. Inspect the current repository before assuming the proposed structure in the
   brief has already been implemented.
5. If the task spans several sessions or has dependent milestones, create or
   update a checklist plan in `docs/plans/`.

## Project boundaries

- This repository implements Phase 2 demand planning and ordering. Phase 1
  forecasting is a future, pluggable input and must not be embedded in the
  planning engine.
- Consume demand at daily grain using stable `location_id` and `dish_id` keys.
  Do not reduce the engine contract to a weekly average.
- Preserve the three-level BOM: `Dish -> Silo -> Ingredient`. Pre-mixes are
  first-class silos, not flattened away.
- Treat storage class as first-class master data. `Frisch` uses delivery-slot
  coverage; `TK`, `Kuehl`, and `RT` use stocked-item planning.
- Keep the core engine pure: calculation code takes typed/tabular inputs and
  returns results without database, filesystem, network, or UI access. Put I/O
  behind adapters.
- Nothing may be dispatched to a supplier without an explicit human approval
  step. Generating a proposal or dry-run output is not approval.

## Domain and calculation rules

- Use grams as the internal requirement unit and purchasable packs/cases as the
  ordering unit.
- Coverage horizon is item-specific `lead_time + review_period`; never restore
  the spreadsheet's hard-coded six-day horizon as target behavior.
- Open purchase orders and expected receipt dates must participate in netting.
  In-transit inventory is not optional.
- Keep deterministic yield loss separate from stochastic safety stock. Do not
  reintroduce the spreadsheet's flat `x1.2` factor as the target policy.
- Project inventory through time from timestamped on-hand stock. Do not encode a
  hard-coded `2.5 day` bridge.
- Apply constraints in the documented order: floor at zero, shelf-life cap,
  max-cover cap, MOQ, then case-size rounding. A binding cap or inflated order
  must produce an exception, not be hidden.
- For fresh products, sum the actual daily forecast across the days covered by
  each delivery. Do not multiply an average day by the slot length.
- Preserve intermediate values and policy/config versions so every proposed
  quantity can be explained and a run can be reproduced.
- Use stable IDs for joins. Names, spelling variants, and German display labels
  are presentation data, not keys.
- Make rounding explicit and test it at pack, MOQ, and case boundaries. Avoid
  early rounding during BOM explosion or inventory projection.

## Configuration and data safety

- Business policy belongs in validated config or master data, not scattered
  constants. This includes lead times, delivery calendars, pack sizes, shelf
  life, safety policy, MOQ, case size, and max cover.
- Validate schemas, units, referential integrity, uniqueness, allowed storage
  classes, and impossible combinations before running calculations.
- Validation errors must identify the file/record/field and explain how to fix
  the issue. Do not expose a stack trace as the planner-facing error.
- Never store credentials, customer-private data, supplier secrets, or raw
  production extracts in documentation, scratchpads, fixtures, or git.
- Treat source-system access as read-only unless a task explicitly authorizes a
  write path.
- Use anonymized or explicitly approved data for tests. The real KW34 workbook
  may be used as a golden fixture only when it is available and safe to commit.

## Implementation guidance

- Prefer small, typed, composable functions with domain names such as
  `explode_bom`, `project_inventory`, `net_requirements`,
  `apply_constraints`, and `schedule_orders`.
- Keep engine modules independent from `io`, report, API, and hosting modules.
- Maintain one authoritative master-data path; do not recreate the spreadsheet's
  copied-week tabs or name-based reconciliation.
- Include derivation fields and exception codes in outputs, not only prose.
- Make runs deterministic for the same input snapshots, configuration, and code
  version. Record timestamps and hashes at orchestration boundaries.
- Do not add or change major dependencies, databases, cloud services, or ERP
  integrations without calling out the decision and its tradeoffs.

## Verification expectations

- Add or update tests with behavior changes. Prioritize unit tests for pure
  calculations and integration tests for adapters and orchestration.
- Test at least: multi-dish BOM aggregation, pre-mixes, zero demand, dated stock,
  open POs before/after the horizon, long lead times, fresh slot coverage,
  shelf-life/max-cover conflicts, MOQ inflation, case rounding, and unavoidable
  stockout exceptions.
- During Milestone 1, the acceptance baseline is reproducing the documented
  KW34 spreadsheet logic within its known rounding tolerance. Keep that legacy
  reproduction clearly separated from the corrected target policy.
- Run the narrowest relevant checks while iterating and the broader applicable
  suite before finishing. State which checks ran and why any were skipped.

## Documentation and working memory

- If behavior, architecture, interfaces, assumptions, or business rules change,
  update the relevant file in `docs/descriptions/` in the same task.
- Use `docs/plans/` for long-running work. Plans should contain goal, scope,
  prioritized checkbox steps, decisions, dependencies, and dated progress.
- Use `docs/scratchpads/<topic>.md` only when a task needs cross-session working
  notes. Keep entries short: learned facts, decisions, open questions, next
  steps, risks, and useful commands. Scratchpads are not authoritative specs.
- Update `MEMORY.md` only for stable, high-impact facts or decisions. Include a
  date, evidence path, and `active` or `superseded` status.
- Keep `README.md` and setup/deployment documentation aligned with runnable
  reality once those files exist.

## Done checklist

- [ ] Relevant checks/tests ran, or skipped checks are explained.
- [ ] No domain boundary or human-approval safeguard was bypassed.
- [ ] Relevant descriptions were reviewed and updated if behavior changed.
- [ ] A relevant plan/scratchpad was updated if the task uses one.
- [ ] `MEMORY.md` was updated if a durable decision or fact changed.
- [ ] Risks, assumptions, config changes, and dependency changes are called out.
