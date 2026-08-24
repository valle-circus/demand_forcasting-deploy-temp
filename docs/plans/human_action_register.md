# Human Action Register

**Purpose:** make every manual action, owner decision, access request, and due milestone visible without blocking unrelated engineering work.

Status values: `OPEN`, `IN PROGRESS`, `DONE`, `NOT NEEDED YET`, `SUPERSEDED`.

`HA-*` IDs group work into requests a person can act on. The backlog's `H-*` IDs remain the finer-grained domain gates: `HA-02` clears `H-01`; `HA-01` addresses `H-02`–`H-05`; `HA-04` addresses `H-06`–`H-08`; and `HA-06`–`HA-12` cover the corresponding integration, persistence, validation, UI, forecast, and dispatch gates. Use this file for action status and the master backlog for technical exit criteria.

## Actions needed now

### HA-01 — Send the Tier A process questions

- **Status:** `OPEN`
- **Owner:** Valentin / current planner
- **Needed by:** Milestone 1 business acceptance; engineering continues meanwhile
- **Action:** obtain answers for Q1, Q4, Q5, Q6, and Q9 from the question-to-gate matrix: open POs/in-transit, `S/M/W/Fr`, `Demand/Silo Load`, stock-count timing/2.5-day bridge, and canonical item/pack/SKU checks.
- **Helpful evidence:** one open-PO example, one final supplier order/confirmation, the KW34 stock-count timestamp, and an item/SKU export or owner-reviewed mapping.
- **Fallback until then:** assumption flags, unexplained-order exceptions, and quarantined master-data rows.
- **Blocks only:** calling M1 business-approved and interpreting actual/manual order differences.

### HA-02 — Decide whether a KW34-derived fixture may be committed

- **Status:** `OPEN`
- **Owner:** Valentin / data owner
- **Needed by:** the real 27-cell KW34 golden test commit
- **Action:** choose one: approve a minimal sanitized fixture for git; require anonymization; or require the real fixture to remain local/private.
- **Important:** approval should cover ingredient/item labels, supplier-related fields, demand quantities, and stock/order quantities in the GitHub repository.
- **Fallback until then:** synthetic committed fixture plus local, ignored real-data validation.
- **Blocks only:** committing the real-data golden baseline; it does not block implementation or synthetic tests.

### HA-03 — Provide formula-level workbook evidence if available

- **Status:** `OPEN`
- **Owner:** Valentin / workbook owner
- **Needed by:** M1 confidence/sign-off, but not by initial implementation
- **Action:** provide an approved raw XLSX copy with formulas or arrange a short owner walkthrough of the Plan/Stock formulas.
- **Fallback until then:** displayed-value specification already reconciled for KW34.
- **Blocks only:** claiming formula/cell-reference equivalence rather than displayed-value equivalence.

## Actions needed before Milestone 2 acceptance

### HA-04 — Resolve improved-policy operating rules

- **Status:** `NOT NEEDED YET`
- **Owner:** Valentin / planner / purchasing owner
- **Needed by:** Milestone 2 business acceptance and Milestone 4 shadow start
- **Action:** answer Q2, Q3, Q7, Q10, and Q11: lead times/calendars, shelf life, menu horizon/transitions, fresh delivery coverage, and weekly/urgent order workflow.
- **Fallback until then:** explicit supplier/class defaults and scenario calendars.

### HA-05 — Confirm the 20% buffer policy owner

- **Status:** `NOT NEEDED YET`
- **Owner:** Valentin / operations owner
- **Needed by:** Milestone 4 calibration
- **Action:** document the original intent of `1.20`, acceptable service/waste trade-off, and who approves its replacement.
- **Fallback until then:** exact `1.20` only in `legacy_kw34`; separate labelled yield/safety defaults in scenarios.

## Actions needed before Milestone 3 integration

### HA-06 — Obtain read-only source discovery access

- **Status:** `NOT NEEDED YET`
- **Owner:** Valentin / data platform owner
- **Needed by:** Milestone 3 start
- **Action:** obtain/confirm Snowflake access for relevant `base_*` and `int_*` models and provide source DDL/columns, grain, keys, timezone, freshness, retention, and sample rows.
- **Fallback until then:** canonical CSV fixtures and adapter interfaces.

### HA-07 — Identify authoritative operational sources

- **Status:** `NOT NEEDED YET`
- **Owner:** Valentin / data platform / purchasing / ERP owner
- **Needed by:** Milestone 3 exit
- **Action:** identify authoritative sources for open POs, goods receipts, BOM/recipes, item/SKU master, supplier terms, stock snapshots, and menu calendar. Confirm whether Xentral holds the missing purchasing/master data.
- **Fallback until then:** file adapters; open POs may be manually supplied only for non-live development.

### HA-08 — Approve Supabase project and ownership

- **Status:** `NOT NEEDED YET`
- **Owner:** Valentin / platform owner
- **Needed by:** before Supabase migrations are created
- **Action:** decide new versus shared project, organization/owner, region, billing, backup/retention, environments, and secret-management process.
- **Fallback until then:** local files and output artifacts; no Supabase project is created.

## Actions needed for validation, UI, and operations

### HA-09 — Approve shadow-run criteria

- **Status:** `NOT NEEDED YET`
- **Needed by:** Milestone 4 shadow start
- **Action:** agree duration, locations, comparison metrics, acceptable differences, override capture, and sign-off owners.

### HA-10 — Define application roles and authentication

- **Status:** `NOT NEEDED YET`
- **Needed by:** Milestone 5 auth implementation
- **Action:** approve viewer, planner, config-editor, approver, and admin roles plus SSO/auth requirements.

### HA-11 — Provide the Phase 1 live contract

- **Status:** `NOT NEEDED YET`
- **Needed by:** Milestone 6
- **Action:** provide owner, schema/version, delivery mechanism, horizon, update cadence, and a reviewed daily sample.

### HA-12 — Approve any dispatch integration separately

- **Status:** `NOT NEEDED YET`
- **Needed by:** Milestone 6 P2 only
- **Action:** approve the destination ERP/supplier channel, credentials process, duplicate prevention, readback, cancellation, and four-eyes controls.
- **Fallback until then:** human-approved CSV export only; no supplier send.

## Maintenance rule

When an action becomes needed, update its status to `IN PROGRESS`, record the exact request in the scratchpad, and mention it in the task handoff. When evidence arrives, link the reviewed artifact without storing credentials or private extracts in git.
