# MEMORY.md

Long-term project memory for durable, high-impact facts and decisions. This is
not a task log or a replacement for the detailed engineering brief.

## Scope and usage

- Read relevant entries before implementation or design work.
- Keep entries concise and update them in place when a decision changes.
- Each entry includes a date, the decision/fact, evidence artifact path(s), and
  status (`active` or `superseded`).
- Put temporary findings, commands, and session notes in a topic scratchpad, not
  here.
- Never store secrets or private operational data here.

## Active memory

- 2026-08-22: This repository is for Phase 2 supply-planning automation only:
  BOM explosion, time-phased inventory projection, netting, constraints,
  delivery scheduling, and auditable order proposals. Phase 1 forecasting does
  not exist yet and must remain a pluggable upstream input. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` sections 1-3. Status:
  `active`.

- 2026-08-22: Project status is discovery complete and build not started. The
  repository structure in the engineering brief is proposed architecture, not
  evidence of already implemented modules. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` scope/status and section
  9.3. Status: `active`.

- 2026-08-22: The Phase 2 demand interface is daily and location-aware, with
  `location_id`, stable `dish_id`, `date`, `forecast_portions`, and optional
  `forecast_sigma`. The engine must not be designed around one flat weekly
  demand number. Evidence: `docs/descriptions/phase2_supply_planning_brief.md`
  section 3. Status: `active`.

- 2026-08-22: Core domain invariants are the three-level
  `Dish -> Silo -> Ingredient` BOM, storage class as a first-class attribute,
  grams as the internal unit, and purchasable packs as the order unit. Pre-mixes
  must remain represented as silos. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` sections 4 and 6. Status:
  `active`.

- 2026-08-22: The current operating model is Monday-Saturday with delivery slots
  Saturday, Monday, Wednesday, and Friday. `Frisch` holds no stock and is planned
  from delivery to delivery; `TK`, `Kuehl`, and `RT` are stocked classes. These
  values should be configurable rather than hard-coded into engine functions.
  Evidence: `docs/descriptions/phase2_supply_planning_brief.md` sections 2 and
  4.3. Status: `active`.

- 2026-08-22: The target planning horizon is item-specific lead time plus review
  period. In-transit/open purchase orders must be included in projected
  availability. The legacy six-day horizon and missing-delivery regression are
  known critical defects, not behaviors to preserve in the target policy.
  Evidence: `docs/descriptions/phase2_supply_planning_brief.md` sections 5.1,
  5.2, and 7. Status: `active`.

- 2026-08-22: Deterministic yield loss and stochastic safety stock are separate
  concepts. The target design replaces the flat spreadsheet `x1.2` factor with
  an empirically derived/clamped yield factor plus additive variance-based safety
  stock and a policy floor. OOS-censored demand must be corrected before
  estimating variance. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` sections 5.3, 7, and 8.
  Status: `active`.

- 2026-08-22: The engine should be pure and deterministic: calculation functions
  have no database or filesystem access, policy is held in validated config, and
  input snapshots plus config/version metadata make runs reproducible. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` sections 9.1-9.4. Status:
  `active`.

- 2026-08-22: Target constraints are applied in this order: floor at zero,
  shelf-life cap, max-cover cap, MOQ, and case-size rounding. Binding caps,
  MOQ-inflated orders, unavoidable stockouts, and configuration gaps must be
  visible exceptions with derivation data. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` section 7. Status:
  `active`.

- 2026-08-22: Phase 2 produces order proposals with item, quantity, order date,
  expected delivery date, and supplier. Nothing is dispatched until a human has
  reviewed and approved it. Every line must retain intermediate calculation
  values so the planner can explain the result. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` sections 7 and 9. Status:
  `active`.

- 2026-08-22: Delivery should proceed in milestones: first reproduce the legacy
  KW34 logic as a golden baseline; then add lead-time-aware horizons, in-transit
  netting, caps, MOQ/case rounding, and exceptions; then calibrate yield/safety
  stock from SQL history; automate dispatch only after parallel validation; plug
  in Phase 1 without changing the engine contract. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` section 11. Status:
  `active`.

## Open high-impact questions

These are intentionally unresolved and must not be silently converted into
implementation assumptions:

- Is the current `Demand/Silo Load` value portions sold per day or a silo refill
  level?
- What is the exact stock-count timestamp and why does the legacy sheet use a
  2.5-day bridge?
- Are lead times item-specific or supplier-specific, and where are open purchase
  orders stored?
- What constraints explain the differences between calculated and booked orders?
- Is silo capacity binding, and does sealed or opened shelf life govern each
  item?

Evidence for all questions:
`docs/descriptions/phase2_supply_planning_brief.md` section 10. Status: `active`.
