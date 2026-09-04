# AGENTS.md

This file defines the working rules for AI coding agents in this repository.
The project automates Phase 2 supply planning for autonomous robot kitchens:
daily dish demand is exploded through the BOM, inventory and open purchase
orders are netted, and auditable internal planning recommendations are written
to Snowflake.

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

## Temporary GitHub deployment mirror

- The authoritative repository is
  `https://github.com/circus-kitchens/demand_forcasting.git`. Use it for fetches,
  code review, and pull requests.
- Until Vercel and Render have access to the organization repository, the
  private repository
  `https://github.com/valle-circus/demand_forcasting-deploy-temp.git` is only a
  deployment mirror. Do not treat it as a second source of truth.
- In the established Windows checkout, `origin` fetches from the organization
  repository and has two push URLs: the organization repository first and the
  temporary mirror second. One local `git push` therefore pushes the same refs
  to both. Verify this before relying on it with `git remote -v` and
  `git config --get-all remote.origin.pushurl`; this local configuration is not
  inherited by a new clone.
- Create and merge pull requests only in `circus-kitchens/demand_forcasting`.
  Never create or merge a duplicate pull request in the temporary mirror.
- A pull request merged in GitHub creates a server-side commit that is not
  automatically copied to the mirror. After merging in the organization, run
  `git switch main`, `git pull --ff-only origin main`, and `git push origin main`
  so local `main` and both repositories converge on the organization merge.
- Multiple push URLs are not atomic. Read the complete push output; if one
  destination fails, resolve it and retry before claiming the mirror is current.
- Do not force-push, delete, transfer, or rename either repository as routine
  cleanup. When organization deployment access is restored, reconnect Vercel
  and Render to the authoritative repository, verify the deployed commit, then
  remove the temporary push URL and mirror under an explicitly approved cleanup
  task. Update this section and `MEMORY.md` at that time.

## Project boundaries

- This repository implements the Phase 2 supply-planning calculation. Phase 1
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
- Supplier/ERP dispatch and a proposal-approval workflow are outside the current
  project scope. Do not add them without an explicit scope change.
- Snowflake owns operational source data and Phase 2 result tables. Supabase
  owns only application-managed editable planning rules and their change
  history. The internal UI exists so non-technical users can maintain those
  rules; it is not an ordering/dispatch application.

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
  constants. This includes lead times, simple delivery weekday/cut-off rules,
  pack sizes, shelf life, safety policy, MOQ, case size, and max cover. Do not
  interpret delivery rules as an external calendar integration.
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
  `apply_constraints`, and `schedule_recommendations`.
- Keep engine modules independent from `io`, report, API, and hosting modules.
- Maintain one authoritative master-data path; do not recreate the spreadsheet's
  copied-week tabs or name-based reconciliation.
- Include derivation fields and exception codes in internal Snowflake outputs,
  not only prose.
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
- [ ] No Phase 1 forecasting logic or supplier/ERP write path was introduced.
- [ ] Relevant descriptions were reviewed and updated if behavior changed.
- [ ] A relevant plan/scratchpad was updated if the task uses one.
- [ ] `MEMORY.md` was updated if a durable decision or fact changed.
- [ ] Risks, assumptions, config changes, and dependency changes are called out.
