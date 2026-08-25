# Human Action Register

**Purpose:** list only the information, access, and infrastructure decisions a
person must provide. These are stage gates, not reasons to stop unrelated work.

Status values: `OPEN`, `IN PROGRESS`, `DONE`, `NOT NEEDED YET`.

## HA-01 — Excel-owner process answers

- **Status:** `IN PROGRESS`
- **Owner:** Valentin / person who builds and uses the Excel workbook
- **Action:** wait for the already-sent Q1-Q13 answers. No correction or second
  questionnaire is needed. Record the answers against brief section 10.
- **What this should clarify:** `Demand/Silo Load`; stock timestamp and the
  2.5-day bridge; blank/reduced orders; Sa/Mo/We/Fr handling; item/pack mapping;
  fresh handling; lead times; shelf life; other consulted data; and manual
  overrides.
- **Blocks:** final interpretation of the manual logic and business sign-off.
- **Does not block:** synthetic tests, parameterized engine work, or adapters.

## HA-02 — KW33/KW34 fixture handling

- **Status:** `OPEN`
- **Owner:** Valentin / data owner
- **Action:** decide whether the minimal real fixture may be committed as-is,
  anonymized, or kept private/local. Approval should cover item labels and
  demand/stock/order quantities.
- **Blocks:** a committed real golden fixture.
- **Does not block:** local/private golden validation.

## HA-03 — Formula or workbook walkthrough

- **Status:** `OPEN`
- **Owner:** Valentin / Excel owner
- **Action:** provide an approved raw XLSX with formulas or a short walkthrough
  if available.
- **Blocks:** claiming exact cell-reference parity.
- **Fallback:** the displayed-value arithmetic is independently reconciled.

## HA-04 — Phase 2 planning-rule ownership and values

- **Status:** `NOT NEEDED YET`
- **Owner:** planner / purchasing / operations
- **Action:** approve the values users will maintain through the internal UI:
  lead time and review period, shelf-life/max-cover rule, storage-class
  behaviour, MOQ/case size, simple delivery weekdays/cut-offs, and the initial
  safety/yield setting.
- **Important:** observed expiry and receipt history may inform a policy but do
  not define it automatically.
- **Blocks:** calling improved recommendations business-approved.
- **Does not block:** implementing small validated config fields and scenarios.

## HA-05 — Snowflake repository, connection, and result ownership

- **Status:** `IN PROGRESS`
- **Owner:** Valentin / Joel / data platform
- **Evidence received:** Joel confirmed the three generated planning models and
  `BASE_INVENTORY` are abandoned; `data-transformation` may be updated. He will
  create an RSA-authenticated Snowflake service account shared via 1Password.
- **Actions:**
  1. Grant Valentin access to `data-transformation`.
  2. Complete least-privilege service-account provisioning.
  3. Confirm which upstream models data platform owns and which Python job owns
     the Phase 2 calculation.
  4. Confirm the Snowflake database/schema/table for result runs, append versus
     latest-view behavior, write grants, and scheduling owner.
- **Blocks:** live end-to-end Snowflake reads/writes.
- **Does not block:** pure engine, schemas, and file-equivalent adapter tests.

Suggested message to Joel:

> To align the implementation, should the Python Phase 2 job write directly to
> a Snowflake result table, or should `data-transformation` publish the final
> table? Which database/schema should own run history and the latest-result
> view, should runs append, and will the service account have the required
> read/write permissions?

## HA-06 — Establish the current PO source and ingestion

- **Status:** `IN PROGRESS`
- **Owner:** Valentin / Deepali, Dor, Ilona / Joel and data platform
- **Evidence received:** Joel confirmed no current PO data is ingested into
  Snowflake to his knowledge; Fivetran is a possible route after Ops identifies
  the source.
- **Actions:**
  1. Ask Ops where POs and expected deliveries are maintained and who owns it.
  2. Confirm history and export/API access.
  3. Obtain one approved example covering PO/line ID, item, location, supplier,
     ordered and remaining quantity/unit, status, order date, expected receipt,
     partial receipts, cancellations/date changes, and source update time.
  4. Return the findings to Joel for normalized ingestion and quality tests.
- **Blocks:** complete production inventory-position netting.
- **Fallback:** synthetic/manual `open_pos.csv` for development only.

## HA-07 — Supabase configuration store

- **Status:** `NOT NEEDED YET`
- **Owner:** Valentin / platform owner
- **Needed by:** internal non-technical configuration UI
- **Action:** approve organization/project, owner, region, environments,
  credentials, backup, retention, and the initial internal user/auth approach.
- **Scope:** Supabase stores application-owned planning rules and change
  history. It does not replace Snowflake operational inputs or result tables.
- **Blocks:** durable non-technical editing.
- **Does not block:** engine and Snowflake adapter work.

## HA-08 — Live Phase 1 forecast contract

- **Status:** `NOT NEEDED YET`
- **Owner:** Phase 1/data owner
- **Action:** provide the authoritative daily forecast table/model, owner,
  version, horizon, update cadence, timezone/cutoff, and a reviewed sample at
  `location × dish × service_date` grain.
- **Blocks:** scheduled production Phase 2 runs.
- **Fallback:** manual/file daily forecasts for parity and scenarios.

## HA-09 — Physical silo-slot bridge

- **Status:** `NOT NEEDED YET`
- **Owner:** data platform / robot-menu data owner
- **Evidence:** corrected V3B rules out the tested direct resource-position
  join; 1,636/2,576 stock keys match only through ingredient identity and no
  exact physical slot resolves.
- **Action:** inspect `data-transformation`/upstream lineage after access and ask
  the responsible owner only if the authoritative bridge is absent.
- **Blocks:** physical silo-capacity logic.
- **Does not block:** ingredient-level Phase 2 planning.

## HA-10 — Waste semantics, only before calibration or sharing

- **Status:** `NOT NEEDED YET`
- **Owner:** Joel/data owner
- **Action:** define which field represents physical disposal and how
  `WASTE_VALUE_EUR` is valued.
- **Blocks:** yield/waste calibration and external use of the EUR 31k field sum.
- **Does not block:** core Phase 2 calculation.

## Maintenance rule

Update an action only when its status, owner, evidence, or exact request changes.
Do not add approval, dispatch, ERP-write, or broad UI-workflow actions unless the
project scope is explicitly expanded.
