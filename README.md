# Phase 2 Supply Planning

This project will replace a manual Excel-based supply-planning process for autonomous robot kitchens with a deterministic, auditable planning service. It converts daily dish demand into ingredient-level order proposals while considering recipes, stock, open purchase orders, supplier constraints, shelf life, delivery schedules, and menu changes.

> **Current status:** KW34 displayed-value validation and the main Snowflake verification pass are complete. The first M0/M1 implementation tranche is runnable: canonical typed contracts, provenance/run-mode gates, pure BOM explosion, the isolated `legacy_kw34/v1` calculation, a synthetic fixture, deterministic audit JSON, and automated tests. Joel confirmed that the discovered forecast, generated-recommendation, and `BASE_INVENTORY` models are abandoned previous-team models and that purchase-order data is not currently ingested into Snowflake. Ops source discovery with Deepali/Dor/Ilona and a subsequent ingestion/modeling workstream with Joel are therefore required before operational PO netting. This does **not** block the pure engine, manual/file PO contract, scenario tests, or other file adapters. GitHub access, the RSA Snowflake service account, the real KW34 golden fixture, and broader source adapters remain gated/in progress.

## Scope

This repository implements **Phase 2: supply planning and ordering**.

- **Phase 1, forecasting:** supplies expected portions per dish, location, and day. It remains a pluggable upstream input and is not implemented here; the discovered Snowflake forecast models are abandoned and may be replaced, not accepted as a live forecast source.
- **Phase 2, this project:** explodes dish demand through the BOM, projects inventory, nets open purchase orders, applies planning constraints, and produces explainable order proposals for human approval.

The first reference case is the manually maintained `Supply_Planning_Rewe.xlsx` workbook, primarily `Plan KW34` and `Stock KW34`, with KW33 used for the legacy bridge calculation.

## Planned architecture

The project starts as a Python CLI, but the calculation engine is designed as a reusable library rather than a throwaway script. File inputs prove the logic first; SQL adapters, Supabase persistence, FastAPI, and the React UI are added in later milestones without moving business logic out of the engine.

```text
SOURCE SYSTEMS
┌──────────────────────┐  Snowflake: sales, stock movements, menu, waste, OOS
├──────────────────────┤  ERP / ordering source: POs, receipts, supplier terms
├──────────────────────┤  Phase 1: daily forecast, initially a file fixture
├──────────────────────┤  Supabase: approved configuration and master data
└──────────────────────┘  XLSX / CSV / YAML: development fixtures and fallback
             │
             ▼
┌──────────────────────────────────────────┐
│ Source adapters                          │
│ Map source-specific fields into stable   │
│ canonical planning contracts             │
└────────────────────┬─────────────────────┘
                     ▼
┌──────────────────────────────────────────┐
│ Application service                      │
│ Validate → snapshot → run → persist       │
└────────────────────┬─────────────────────┘
                     ▼
┌──────────────────────────────────────────┐
│ Pure Python planning engine              │
│ No database, filesystem, network, UI,    │
│ or clock dependencies                    │
└────────────────────┬─────────────────────┘
                     ▼
┌──────────────────────────────────────────┐
│ Supabase                                 │
│ Config versions, runs, proposals,        │
│ exceptions, approvals, and audit history │
└─────────────┬───────────────────┬────────┘
              ▼                   ▼
       React planner UI     Approved-order API/export
                            for a later ordering tool
```

Both the first CLI and the later FastAPI backend call the same application service. Source adapters may change as real schemas are discovered; the canonical contracts and engine should not.

## Planning logic

At a high level, each run will:

1. Load daily dish demand by location.
2. Check the forward menu calendar.
3. Explode `Dish → Silo / pre-mix → Ingredient` into grams required per day.
4. Apply an explicit yield factor and safety-stock policy.
5. Project timestamped inventory and dated open-PO receipts through the protection period.
6. Net demand against usable on-hand stock and the inbound pipeline.
7. Apply shelf-life and maximum-cover caps.
8. Apply MOQ and case-size rounding, then recheck hard caps.
9. Schedule order and expected delivery dates using supplier calendars.
10. Produce proposals, derivation fields, warnings, and exceptions for human review.

Two policies remain intentionally separate:

- `legacy_kw34` reproduces the spreadsheet's displayed-value arithmetic and rounding as the Milestone 1 acceptance baseline.
- `improved` uses daily time-phased demand, item-specific lead times, open-PO netting, safety stock, shelf life, supplier constraints, and menu transitions.

## Data, menu, BOM, and configuration

The engine consumes canonical datasets rather than depending on guessed SQL table names. Initial CSV/XLSX fixtures and later Snowflake, ERP, API, or Supabase adapters all map into the same contracts.

Core inputs are:

- `forecast_daily`: location, dish, date, expected portions, and optional uncertainty;
- `menu_calendar`: which dish is served at each location and date;
- `bom_lines`: dish, silo/pre-mix, ingredient, and grams per portion;
- item and supplier master data: pack size, storage class, shelf life, lead time, MOQ, case size, and delivery rules;
- `inventory_snapshots`: timestamped usable stock;
- `purchase_orders`: open quantities and expected receipt dates.

The menu may initially be represented by a fixture and later mapped from an authoritative Snowflake model or menu API. Snowflake's flattened/versioned BOM now passes the tested key, gram, history, and materialized-menu coverage checks, while its physical silo/recipe-slot mapping and ownership remain open. Until those are resolved, the cleaned workbook remains the approved legacy reference; application-owned versioned master data is a fallback only if no authoritative recipe source is accepted.

During early development, policy and master data are represented through validated CSV/YAML files. These files are engineering fixtures, imports/exports, and fallback—not the intended workflow for non-technical planners. The eventual React UI will manage approved configuration through FastAPI and versioned Supabase records.

Configuration applies at the appropriate level:

- item: pack size, storage class, shelf life, safety or yield override;
- supplier-item: supplier SKU, MOQ, case size, lead-time override, cancellability;
- supplier/location: order cut-offs and delivery calendar;
- global/storage class: policy defaults;
- dish/location/date: menu availability;
- dish/silo/item: recipe quantities.

## Persistence and downstream ordering

Supabase is planned as the operational store for application-owned configuration and audit history, not as a replacement for all source systems. Relevant source snapshots, versions, hashes, planning lines, proposals, exceptions, and approvals are persisted so a run can be reproduced and explained.

A future ordering application should consume only **approved** proposals through a controlled API, view, or export. Calculating or storing a proposal is not permission to order. Supplier or ERP dispatch remains a separate final release gate.

## Missing data and open decisions

Unanswered business questions are stage-exit gates, not a reason to pause initial development. Fixture and scenario runs may use explicit placeholders with provenance such as `policy_default`, `empty_placeholder`, or `unavailable`.

Operational mode must fail closed when critical inputs are unknown, especially current stock, canonical SKU/pack size, lead time/calendar, demand semantics, or the open-PO pipeline. Missing waste, OOS, forecast-error, receipt, and lot data delays calibration and confidence, but does not block building the file-based engine.

See the backlog's blocker register and question-to-gate matrix for the current decisions and allowed fallbacks.

## Delivery plan

1. **M0 — Evidence and contracts:** approve fixtures, define canonical schemas, run modes, exceptions, and architecture decisions.
2. **M1 — Legacy CLI:** reproduce KW34 in Python with golden tests and auditable outputs.
3. **M2 — Improved file engine:** add time-phased planning, open POs, constraints, scheduling, transitions, and labelled placeholders.
4. **M3 — SQL and persistence:** map real source schemas, add read-only adapters, and introduce approved Supabase storage.
5. **M4 — Validation:** backtest and shadow-run against the planner with real data.
6. **M5 — Planner UI:** add FastAPI, React/Tailwind, authentication, configuration, proposal review, and approval.
7. **M6 — Operations:** integrate live Phase 1 and separately approve any ERP or supplier dispatch path.

## Engineer handover: start here

| File | Purpose |
|---|---|
| [`AGENTS.md`](AGENTS.md) | Repository rules, domain invariants, safety boundaries, and verification expectations |
| [`docs/descriptions/phase2_supply_planning_brief.md`](docs/descriptions/phase2_supply_planning_brief.md) | Primary domain and architecture specification, including the verified Excel logic and improved target logic |
| [`docs/plans/phase2_supply_planning_master_backlog.md`](docs/plans/phase2_supply_planning_master_backlog.md) | Source-of-truth implementation backlog, priorities, human gates, exit criteria, and immediate next slice |
| [`docs/descriptions/data_requirements.md`](docs/descriptions/data_requirements.md) | Candidate source systems, known tables, gaps, access context, and data-discovery sequence |
| [`docs/scratchpads/snowflake_verification_evidence.md`](docs/scratchpads/snowflake_verification_evidence.md) | Durable measured V1-V12 counts, zero-row diagnostics, interpretations, and remaining SQL without committing the private exports |
| [`docs/descriptions/canonical_data_contracts.md`](docs/descriptions/canonical_data_contracts.md) | Implemented canonical input/output contracts, provenance, run-mode gates, and source-mapping rules |
| [`docs/plans/human_action_register.md`](docs/plans/human_action_register.md) | Manual actions and information needed from the user, with the milestone where each becomes blocking |
| [`MEMORY.md`](MEMORY.md) | Durable decisions and verified facts that must survive handovers and context compaction |
| [`docs/scratchpads/phase2_supply_planning_execution.md`](docs/scratchpads/phase2_supply_planning_execution.md) | Short-lived execution context, risks, open questions, and next actions |

The immediate engineering work is listed under **Immediate next execution slice** in the master backlog. There is now a runnable Python CLI foundation; SQL, persistence, API, UI, and deployment are not implemented.

## Quick start

The current core has no third-party runtime dependencies and targets Python 3.12.

PowerShell:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
python -m supply_planning legacy-run `
  --input tests\fixtures\synthetic_legacy\legacy_inputs.csv `
  --output output\synthetic_legacy_audit.json
```

Or run the checked-in verification wrapper with an explicit Python executable when `python` is not on `PATH`:

```powershell
.\scripts\check.ps1 -PythonExecutable "C:\path\to\python.exe"
```

The CLI is deliberately restricted to `fixture` and `scenario` modes. It calculates proposals only; it cannot approve or dispatch an order.

## Non-negotiable safeguards

- Keep the engine pure and deterministic; I/O belongs in adapters.
- Use grams internally and explicit units in all field names.
- Preserve the three-level BOM and stable IDs; never join operational data by display name.
- Keep legacy spreadsheet compatibility isolated from the improved policy.
- Never silently treat missing data as observed zero.
- Preserve derivations, input/config versions, and exception codes for every proposal.
- Never dispatch an order without explicit human approval.
- Never commit credentials, raw production extracts, or unapproved KW34 data.
