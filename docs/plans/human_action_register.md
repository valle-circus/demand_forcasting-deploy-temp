# Human Action Register

**Purpose:** list only the information, access, and infrastructure decisions a
person must provide. These are stage gates, not reasons to stop unrelated work.

Status values: `OPEN`, `IN PROGRESS`, `DONE`, `NOT NEEDED YET`.

## HA-01 — Excel-owner process answers

- **Status:** `DONE`
- **Owner:** Valentin / person who builds and uses the Excel workbook
- **Evidence received 2026-08-26:** the Q1-Q13 response was reconciled in brief
  section 10 and `docs/reports/planner-questionnaire-review/source_notes.md`.
  It confirms the current forecast meaning, central-prep scope, external
  in-transit netting, current/future lead-time split, fresh coverage windows,
  selected master-data corrections, and the Thursday/Monday cadence.
- **Remaining action:** none for the original questionnaire. Focused unresolved
  details moved to HA-04, HA-06, HA-08, HA-11, and HA-12.
- **Security:** the supplied response contained a supplier-portal credential.
  Rotate it and use an approved secret-sharing channel for any replacement;
  credential material must not enter this repository.

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

- **Status:** `IN PROGRESS`
- **Owner:** planner / purchasing / operations
- **Evidence received 2026-08-26:** current Transgourmet planning uses about
  3 days for standard goods and 5 days for fresh goods; fresh is treated as
  about 3 days MHD; TK/Kuehl/RT have no explicit MHD cap in the current short
  cycle; future pods are described as about one month lead time and one year
  MHD; the legacy 20% buffer is a broad assumption rather than calibrated
  policy. These are owner-reported starting points, not yet exact calendar or
  supplier-rule records.
- **Action:** approve the versioned values users will maintain through the
  internal UI: lead time and review period, calendar/business-day semantics,
  shelf-life/max-cover and storage-capacity rules, MOQ/case size, simple
  delivery weekdays/cut-offs, and separate initial safety/yield settings.
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

## HA-06 — Validate and ingest the current PO source

- **Status:** `IN PROGRESS`
- **Owner:** Valentin / Excel owner or purchasing / Joel and data platform
- **Evidence received:** Joel confirmed no current PO data is ingested into
  Snowflake to his knowledge. The Excel owner identified Transgourmet order
  history as the current pending-order source: pending orders are downloaded as
  PDFs, analysed outside the workbook, and subtracted before the final visible
  quantities. This identifies the process but not an accepted data contract.
- **Actions:**
  1. Confirm owner, history retention, and CSV/export/API capability without
     storing portal credentials in code or documentation.
  2. Define which portal statuses count as open and how Monday rechecks avoid
     double-counting quantities already ordered on Thursday.
  3. Obtain one approved sanitized example covering PO/line ID, item, location, supplier,
     ordered and remaining quantity/unit, status, order date, expected receipt,
     partial receipts, cancellations/date changes, and source update time.
  4. Confirm how future non-cancellable pod orders are tracked and whether they
     use the same source.
  5. Return the findings to Joel for normalized ingestion and quality tests.
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

- **Status:** `IN PROGRESS`
- **Owner:** Phase 1/data owner
- **Evidence received 2026-08-26:** the manual workbook value represents
  expected dishes sold per day across three REWE sales locations combined,
  because preparation and purchasing are centralized. It is derived in a
  separate Google Sheet from roughly two weeks of consumption plus campaigns,
  approved by REWE, manually trend-adjusted, and then entered into the planning
  workbook.
- **Action:** provide the authoritative daily forecast table/model, owner,
  version, horizon, update cadence, timezone/cutoff, and a reviewed sample at
  `service location × dish × service_date` grain, plus the stable mapping from
  service locations to the central inventory/planning location. Confirm the
  source of the two-week consumption signal and do not duplicate an already
  aggregated three-location forecast across units.
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

## HA-11 — Focused planner follow-ups after Q1-Q13

- **Status:** `OPEN`
- **Owner:** Valentin / Excel owner / purchasing
- **Timing:** after the first comparison using the workbook already available;
  do not request duplicate historical inputs before that run.
- **Action:** obtain a short walkthrough or written confirmation for the
  remaining operational details only where they explain a material comparison
  difference or are needed to approve the affected policy:
  1. exact count weekday/time and opened/partial-pack treatment;
  2. whether `S/M/W/Fr` values are intended, placed, confirmed, or delivered
     quantities and in which units;
  3. whether 3/5-day lead times are calendar or business days, measured from
     which cutoff to which availability event, and which item exceptions exist;
  4. receipt times, holiday behavior, and whether all fresh items use
     `Sat→Mon`, `Mon→Tue+Wed`, `Wed→Thu+Fri`, `Fri→Sat`;
  5. freezer/storage limits that cause split or reduced orders;
  6. forward-menu source, committed horizon, and the non-cancellable pod
     last-order rule;
  7. Thursday and Monday run/cut-off times, urgent-order path, final decision
     owner, and which override reasons should be recorded;
  8. whether the same interim 20% applies to all items/classes and who may
     override it.
- **Blocks:** final legacy interpretation for manual delivery columns and
  business approval of the affected improved scheduling/constraint policies.
- **Does not block:** parameterized implementation and scenario tests.

## HA-12 — Apicbase stock and master-data assessment

- **Status:** `OPEN`
- **Owner:** Valentin / data analyst / Culinary or Apicbase owner
- **Evidence received 2026-08-26:** prep-kitchen operators upload manual stock
  counts to Apicbase and exclude unusable goods. Apicbase is the intended item/
  recipe source, but its master data is currently stale because maintenance has
  a backlog; Excel is used operationally and supplier article numbers exist.
- **Action:** arrange read-only access/API documentation or reviewed exports for
  (1) current stock, including count timestamp, unit, usable-stock semantics and
  partial packs; (2) BOM/recipes, including stable dish/item IDs and grams per
  portion; and (3) item master/pack sizes, including units, storage class and
  available IDs for mapping Transgourmet article numbers. Check ownership,
  freshness, completeness, and change history separately for the three domains.
  A reviewed manual export is sufficient for the feedback V1; API access is the
  later automation path.
- **Blocks:** accepting a live current-stock adapter and a canonical operational
  item master.
- **Does not block:** file contracts, synthetic engine work, or the legacy
  workbook fixture.

## Maintenance rule

Update an action only when its status, owner, evidence, or exact request changes.
Do not add approval, dispatch, ERP-write, or broad UI-workflow actions unless the
project scope is explicitly expanded.
