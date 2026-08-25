# Human Action Register

**Purpose:** make every manual action, owner decision, access request, and due milestone visible without blocking unrelated engineering work.

Status values: `OPEN`, `IN PROGRESS`, `DONE`, `NOT NEEDED YET`, `SUPERSEDED`.

`HA-*` IDs group work into requests a person can act on. The backlog's `H-*` IDs remain the finer-grained domain gates: `HA-02` clears `H-01`; `HA-01` addresses `H-02`–`H-05`; `HA-04` addresses `H-06`–`H-08`; and `HA-06`–`HA-13` cover the corresponding integration, persistence, validation, UI, forecast, dispatch, and PO-ingestion gates. Use this file for action status and the master backlog for technical exit criteria.

## Actions needed now

### HA-01 — Collect and reconcile the already-sent planner questions

- **Status:** `IN PROGRESS`
- **Owner:** Valentin / current planner
- **Needed by:** Milestone 1 business acceptance; engineering continues meanwhile
- **Action:** the original Q1-Q13 set has already been sent to the person who builds and uses the workbook. No correction is needed and nothing should be resent now. Wait for the answers and record them against the topic map in `docs/descriptions/phase2_supply_planning_brief.md` section 10. The Excel owner is explaining their process and pointing to possible sources; they are not being asked to validate Snowflake tables or lineage.
- **Helpful evidence:** one currently open PO with its expected receipt date, one final supplier order/confirmation, the KW34 stock-count timestamp, and an owner-reviewed item/SKU mapping.
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
- **Action:** approve the planning values and operating rules for lead times/calendars, sealed/opened shelf life, menu commitment/transitions, fresh delivery coverage, and weekly/urgent ordering. Observed delivery/expiry data may inform these decisions but does not replace policy approval.
- **Fallback until then:** explicit supplier/class defaults and scenario calendars.

### HA-05 — Confirm the 20% buffer policy owner

- **Status:** `NOT NEEDED YET`
- **Owner:** Valentin / operations owner
- **Needed by:** Milestone 4 calibration
- **Action:** document the original intent of `1.20`, acceptable service/waste trade-off, and who approves its replacement.
- **Fallback until then:** exact `1.20` only in `legacy_kw34`; separate labelled yield/safety defaults in scenarios.

## Actions needed before Milestone 3 integration

### HA-06 — Confirm read-only source discovery access

- **Status:** `DONE`
- **Owner:** Valentin / data platform owner
- **Needed by:** completed 2026-08-24
- **Action:** `CIRCUS_MODELS_READER` was verified against `BASE`, `INTERMEDIATE`, `REPORTING`, and `TECH_OPS` (140 physical tables). No further permission request is currently needed.
- **Evidence:** local information-schema exports and `docs/descriptions/data_requirements.md`.

### HA-07 — Validate source fitness and ownership

- **Status:** `IN PROGRESS`
- **Owner:** Valentin / data platform / purchasing / ERP owner
- **Needed by:** before Snowflake adapters are accepted for M3; source lineage and the cross-repository boundary must be resolved before replacement models are accepted
- **Evidence received 2026-08-25:** V1-V12 and all saved follow-ups are summarized in `docs/scratchpads/snowflake_verification_evidence.md`. Joel confirmed that `FACT_CG_DISH_DEMAND_FORECASTS`, `FACT_CG_INGREDIENT_DEMAND_FORECASTS`, `FACT_CG_PURCHASE_ORDERS`, and `BASE_INVENTORY` are abandoned previous-data-team models. They may be replaced in [`data-transformation`](https://github.com/circus-kitchens/data-transformation), but are not operational sources of truth. Joel will provision a stable RSA-authenticated Snowflake service account through 1Password. V5 now measures 76 item rows/75 IDs with complete pack/unit values, seven missing EANs, ten missing Apicbase IDs, and one blank ID. V11 proves the materialized menu ended on 2026-08-24 when queried on 2026-08-25. V1/V2B closes the saved location/per-unit sales checks at 622 portions. Corrected V3B remains the only required SQL follow-up.
- **Actions now:**
  1. Valentin requests GitHub access to `data-transformation`.
  2. Joel provisions a least-privilege, read-only Snowflake service account and shares credentials only through 1Password; no key/token is stored in git or documentation.
  3. After repository access, inspect the abandoned model definitions/upstream lineage and agree which normalized inputs/outputs belong in `data-transformation` versus this repository's pure engine before changing either.
  4. Run corrected V3B slot coverage. Enhanced V12 is optional until calibration is in scope. Keep exports private and append results to the evidence register.
- **Later, before waste is shared or calibrated:** ask which field represents physical disposal and how `WASTE_VALUE_EUR` is calculated.
- **Only after V3B:** ask a targeted follow-up about physical silo-slot identity only if the returned data cannot settle it. Forward-menu commitment remains a business/source question because the materialized table has no forward coverage.
- **Fallback until then:** canonical file adapters with explicit provenance; manual open-PO inputs are allowed only in fixture/scenario modes, never silently treated as production-complete.

### HA-13 — Establish the operational PO source and Snowflake ingestion

- **Status:** `IN PROGRESS`
- **Owner:** Valentin / Ops (Deepali, Dor, Ilona) / Joel and data platform
- **Needed by:** M4 shadow start and any operational netting; not needed for M0/M1 or file/scenario M2 engineering
- **Evidence received 2026-08-25:** Joel confirmed that purchase-order data is not currently ingested into Snowflake to his knowledge. Deepali, Dor, and Ilona are the recommended Ops contacts, with Deepali likely knowing the detailed current process. Fivetran may be suitable after the source is identified.
- **Actions now:**
  1. Ask Deepali and Dor, with Ilona optionally included, for a short walkthrough of how Ops tracks POs and expected deliveries, the system/sheet and owner, available history, and export/API access.
  2. Obtain one approved/anonymized example that demonstrates PO and line ID, item/SKU, ordering location, supplier, ordered quantity/unit, remaining open quantity, status, order date, expected receipt date, partial receipts, cancellations/date changes, and source-updated timestamp.
  3. Return the source findings to Joel; agree the raw ingestion route, history/change capture, refresh SLA, and normalized Snowflake model. Use Fivetran only if it fits the actual source and preserves the required history.
  4. Add source-model tests for grain/uniqueness, nonnegative and unit-consistent quantities, PO-line receipt linkage, statuses, expected dates, partial/cancelled lines, update history, completeness, and freshness.
  5. Only then implement and validate this repository's read-only PO adapter against the canonical contract.
- **Fallback until then:** continue the pure event-ledger/netting implementation with synthetic and manual `open_pos.csv` fixtures. Fixture/scenario mode may explicitly use an empty pipeline; shadow/operational mode must refuse an unknown pipeline.
- **Blocks only:** real PO adapter acceptance, trustworthy shadow runs, and operational proposal approval. It does not block building or testing the engine.

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
