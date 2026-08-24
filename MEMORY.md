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

- 2026-08-22: Project status is discovery and KW34 value-level validation
  complete; implementation has not started. The repository structure and
  backlog describe proposed work, not already implemented modules. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` scope/status and section
  9.3, `docs/plans/phase2_supply_planning_master_backlog.md`. Status: `active`.

- 2026-08-22: The reference source is `Supply_Planning_Rewe.xlsx`, an Office
  workbook stored in Google Drive with file ID
  `1W0fwiO_mf7pQ6G0Oqmp6QE92MCljrXQ-`; it was modified 2026-08-21 and inspected
  read-only on 2026-08-22. `Plan KW34` and `Stock KW34` are the first golden
  reference, with KW33 needed for bridge demand. Connector validation exposed
  displayed values rather than the formula AST, so the current evidence is
  value-level until a raw-formula review or owner walkthrough occurs. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` scope and validation
  conclusion, `docs/scratchpads/phase2_supply_planning_execution.md`. Status:
  `active`.

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

- 2026-08-22: The KW34 legacy compatibility profile is now precisely
  reconstructed at displayed-value level: buffered `Daily` is rounded to two
  decimals; `Need = ceil(Daily × 6)`; the bridge uses **KW33** daily demand ×
  `2.5` rounded to two decimals; `After` is rounded to one decimal; and
  `Order = ceil(max(0, Need − After))`. This matches all 27 filled KW34 stocked
  order cells and all 28 bridge values for continuing stocked items. Legacy
  rounding must stay isolated from improved-engine precision. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` sections 4.2 and 5.9,
  `docs/scratchpads/phase2_supply_planning_execution.md`. Status: `active`.

- 2026-08-22: KW34 contains material data-quality/audit cases that golden tests
  must preserve: four stocked rows have a positive gap and blank order cell;
  `Paprika - big` and `Mischsalat` are in `Plan KW34` but absent from
  `Stock KW34`; Creme Fraiche is planned with a 1,000 g pack but netted as 5,000
  g; Schnittlauch appears with 250/500/1,000 g pack sizes; and multiple item/name
  and storage-label variants exist. The blank/missing rows may have been handled
  outside the sheet and must be called unexplained rather than proven missed
  orders. Evidence: `docs/descriptions/phase2_supply_planning_brief.md` sections
  4.3 and 5.2-5.7, `docs/scratchpads/phase2_supply_planning_execution.md`.
  Status: `active`.

- 2026-08-22: The current operating model is Monday-Saturday with delivery slots
  Saturday, Monday, Wednesday, and Friday. `Frisch` holds no stock and is planned
  from delivery to delivery; `TK`, `Kuehl`, and `RT` are stocked classes. These
  values should be configurable rather than hard-coded into engine functions.
  Evidence: `docs/descriptions/phase2_supply_planning_brief.md` sections 2 and
  4.3. Status: `active`.

- 2026-08-22: The target planning horizon is item-specific lead time plus review
  period, adjusted to actual supplier order/delivery calendars. Gross demand
  through that protection period is an inventory-position target, not
  automatically the new order quantity. Correct netting subtracts on-hand and
  dated open POs once, then uses a daily projection to detect stockout before the
  candidate receipt. The earlier target equation double-counted pre-arrival
  demand and is superseded. It remains unknown whether planners duplicate orders
  or track the pipeline outside the sheet and suppress visible cells manually.
  Evidence: `docs/descriptions/phase2_supply_planning_brief.md` sections 5.1,
  5.2, and 7. Status: `active`.

- 2026-08-22: Deterministic yield loss and stochastic safety stock are separate
  concepts. The target design replaces the flat spreadsheet `x1.2` factor with
  an empirically derived/clamped yield factor plus additive safety stock. For
  daily forecast-error sigma, statistical stock uses root-sum-of-squares across
  the protection period with an explicit correlation assumption; do not divide
  by the review period. OOS-censored demand must be corrected before production
  calibration. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` sections 5.3, 7, and 8.
  Status: `active`.

- 2026-08-22: Missing waste, OOS, forecast-error, receipt, and lot/expiry data do
  not block file-based engine development. Fixture/scenario runs use explicit
  policy placeholders/defaults and carry value provenance into every line.
  Missing current stock, canonical pack/SKU, lead time, or open-PO visibility is
  allowed only in non-operational modes and blocks operational approval. Missing
  data is never silently converted to observed zero. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` sections 7-9,
  `docs/plans/phase2_supply_planning_master_backlog.md`. Status: `active`.

- 2026-08-22: The engine should be pure and deterministic: calculation functions
  have no database or filesystem access, policy is held in validated config, and
  input snapshots plus config/version metadata make runs reproducible. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` sections 9.1-9.4. Status:
  `active`.

- 2026-08-22: Target constraints floor the raw need, compute shelf-life and
  max-cover feasibility, cap the unrounded candidate, apply MOQ/case rounding,
  and then **recheck hard caps**. If supplier rounding and a hard cap conflict,
  the engine emits an infeasible-constraints exception instead of silently
  violating a cap or supplier rule. Binding caps, unavoidable stockouts, and
  config gaps remain visible with derivation/provenance. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` section 7. Status:
  `active`.

- 2026-08-22: Phase 2 produces order proposals with item, quantity, order date,
  expected delivery date, and supplier. Nothing is dispatched until a human has
  reviewed and approved it. Every line must retain intermediate calculation
  values so the planner can explain the result. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` sections 7 and 9. Status:
  `active`.

- 2026-08-22: Planning must explicitly handle menu launches and
  discontinuations. It requires a forward committed menu horizon longer than
  the longest lead time, item-level last-order offsets and pipeline
  cancellability, and exceptions for open POs arriving after final service.
  Evidence: `docs/descriptions/phase2_supply_planning_brief.md` sections 7, 9.4,
  and 10. Status: `active`.

- 2026-08-22: The implementation architecture is script-first but not
  throwaway: one Python application service wraps a pure engine; the CLI calls
  it first, later FastAPI and React/Tailwind call the same use case. The CLI and
  CSV/YAML files are a **technical bootstrap interface** for approved fixtures,
  deterministic tests, local development, initial import, recovery, and export;
  they are not the intended configuration workflow for non-technical planners.
  When the operational UI begins, approved Supabase Postgres tables become the
  system of record for master data, policy versions, runs, proposals, and
  approvals. Planners edit through React -> FastAPI, not by editing YAML, CSV,
  or database tables directly. File and database adapters implement the same
  validated schemas so the engine does not change, and operational mode must not
  permit competing file/database authorities. Supabase project creation,
  ownership, region, auth/RLS, retention, and credentials require human approval.
  Evidence: `docs/descriptions/phase2_supply_planning_brief.md` sections 9.1-9.7,
  `docs/plans/phase2_supply_planning_master_backlog.md`. Status: `active`.

- 2026-08-22: Delivery order is locked unless a documented blocker changes it:
  M0 evidence/contracts; M1 exact KW34 Python CLI; M2 improved file-driven engine
  with labelled placeholders; M3 SQL and optional Supabase persistence; M4
  backtest/shadow validation with real data; M5 FastAPI + React/Tailwind UI; M6
  live Phase 1 and operations. Supplier/ERP dispatch is a separate final release
  gate and remains disabled through the first UI. Evidence:
  `docs/descriptions/phase2_supply_planning_brief.md` section 11,
  `docs/plans/phase2_supply_planning_master_backlog.md`. Status: `active`.

- 2026-08-24: Unanswered planning-process questions are treated as staged
  promotion gates, not a global development blocker. Repository scaffolding,
  typed contracts, the pure engine, CLI, synthetic scenario tests, and the
  `legacy_kw34` displayed-value profile may start immediately with explicit
  assumptions and provenance. Answers and real source access become mandatory
  before the affected feature is accepted as business-correct, shadow-tested,
  or used for operational approval. In particular, unknown current stock,
  canonical SKU/pack, lead time/calendar, demand semantics, or open-PO pipeline
  must never pass the operational-mode gate. Evidence:
  `docs/plans/phase2_supply_planning_master_backlog.md` blocker interpretation
  and business-question gate matrix; `docs/scratchpads/phase2_supply_planning_execution.md`.
  Status: `active`.

- 2026-08-22: `docs/plans/phase2_supply_planning_master_backlog.md` is the
  source-of-truth execution backlog; the topic scratchpad is
  `docs/scratchpads/phase2_supply_planning_execution.md`. Update both during
  implementation and after meaningful decisions. Evidence: those files and
  `AGENTS.md`. Status: `active`.

## Open high-impact questions

These are intentionally unresolved and must not be silently converted into
implementation assumptions:

- Is the current `Demand/Silo Load` value portions sold per day or a silo refill
  level?
- What is the exact stock-count timestamp and why does the legacy sheet use a
  2.5-day bridge?
- Are lead times item-specific or supplier-specific, and where are open purchase
  orders stored? Does the planner currently track those orders outside the
  visible workbook?
- What constraints explain the differences between calculated and booked orders?
- Is silo capacity binding, and does sealed or opened shelf life govern each
  item?
- How many weeks ahead is the menu fixed and committed?
- Which source systems/tables and read-only credentials will provide stock, open
  POs, receipts, BOM, menu, sales, waste, and OOS?
- Which Supabase project/region/owner and which user roles/auth policy should be
  used when durable storage and the UI begin?

Evidence for all questions:
`docs/descriptions/phase2_supply_planning_brief.md` section 10. Status: `active`.
