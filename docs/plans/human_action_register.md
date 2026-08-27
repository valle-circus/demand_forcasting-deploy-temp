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

- **Status:** `NOT NEEDED YET`
- **Owner:** Valentin / Excel owner
- **Action:** provide an approved raw XLSX with formulas or a short walkthrough
  if available.
- **Blocks:** only a future claim of exact legacy cell-reference parity. It is
  not part of the template-driven V1 exit criteria.
- **Fallback:** the displayed-value arithmetic is independently reconciled.

## HA-04 — Phase 2 planning-rule ownership and values

- **Status:** `IN PROGRESS`
- **Owner:** planner / purchasing / operations
- **Evidence received 2026-08-26:** current Transgourmet planning uses 3 days
  for standard goods and 5 days for fresh goods; fresh is treated as about 3 days
  MHD; TK/Kuehl/RT have no explicit MHD cap in the current short cycle; pods
  have a confirmed lead of 4 calendar weeks and about one year MHD. The local
  V1 approximates pod expiry as order date plus 365 days. The legacy 20% extra-
  demand buffer was intended to reduce OOS risk but mixes safety and yield.
  The V1 improvement proposal makes it explicit as `7` safety days for pods,
  `2` for ordinary stocked items and `0.5` for fresh, with
  `yield_factor=1.00` unless deterministic loss is known. The 3/5-day
  durations and pod day type are settled;
  review period, cut-off/receipt timing, receipt age and supplier-rule details
  are not.
- **Action:** approve the versioned values users will maintain through the
  internal UI: lead time, the proposed seven-day stocked review period and
  safety days, calendar/business-day semantics,
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
  quantities. The repository now contains a private/local PDF importer that
  deduplicates documents, reconciles extracted line values to delivery totals,
  and writes history plus canonical CSV columns. The operational status rule is
  now confirmed: missing/future `Liefertag` is open; today/past is
  closed/received. The PDFs still do not expose remaining quantity, partial
  receipts, cancellations, or receipt time, so this is not an accepted live
  data contract. The same Transgourmet PDFs contain pod orders; `Circus` is the
  official pod supplier, not a separate V1 ordering system.
- **Actions:**
  1. Confirm owner, history retention, and CSV/export/API capability without
     storing portal credentials in code or documentation.
  2. Confirm how Monday rechecks handle partial receipts, cancellations, and
     quantities already ordered on Thursday without double-counting.
  3. Obtain one approved sanitized example covering PO/line ID, item, location, supplier,
     ordered and remaining quantity/unit, status, order date, expected receipt,
     partial receipts, cancellations/date changes, and source update time.
  4. Confirm which pod article/order unit appears in the PDF and map it to the
     Circus pack/carton master; no separate pod-order register is needed.
  5. Return the findings to Joel for normalized ingestion and quality tests.
- **Blocks:** complete production inventory-position netting.
- **Fallback:** the implemented manual PDF-to-CSV helper for controlled file
  runs, using the confirmed date rule, an undated-open quarantine, and explicit
  remaining-quantity/item-mapping limitations.

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
- **Additional evidence:** the new active `CW36_Menu` still contains
  `Demand/Silo Load`, but no explicit `service_date` column. REWE communicates
  the fixed menu at least 4 weeks ahead and changes become effective only after
  that notice period. Until a dated change supersedes it, the current menu
  remains effective.
- **Fallback:** a maintained `Demand_Plan` tab at
  `location_id × dish_id × service_date`, with forecast/menu versions. The
  local V1 repeats the current menu/demand as six dated dummy weeks so the
  proposed 35-calendar-day pod protection horizon can be tested. This is a
  declared demo assumption, not an unresolved implementation blocker.

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
- **Timing:** during maintainer review of the project-owned templates. Do not
  request duplicate historical inputs.
- **Action:** obtain a short walkthrough or written confirmation for the
  remaining operational details needed to approve a production-quality run:
  1. whether pod PO quantity is a 1 kg pack or `5 × 1 kg` carton, which article
     appears in Transgourmet, and the MOQ/case multiple;
  2. what unit Apicbase `Current Stock (qty)` represents for each active item
     and whether usable partial packs are included;
  3. which exact description or corrected article resolves the duplicate
     Transgourmet article `350570`;
  4. approve/correct the proposed seven-day stocked review period, confirm
     whether Monday is a normal reorder opportunity, and fill only cut-off/
     receipt fields that materially affect scheduling; current lead durations
     remain 3 days ordinary, 5 days fresh and 28 calendar days pods; and
  5. approve/correct `7` pod, `2` ordinary-stocked and `0.5` fresh safety days;
     identify any deterministic yield loss and hard max-cover values.
- **Already settled for local V1:** pod lead is 28 calendar days; pod POs use
  Transgourmet; fresh service windows are `Sat→Mon`, `Mon→Tue+Wed`,
  `Wed→Thu+Fri`, `Fri→Sat`; the current menu remains effective until superseded
  and is repeated for six dummy weeks; the selected
  upload location is authoritative for the demo; stock export time is
  `counted_at`; and pod expiry is approximated as order date plus 365 days.
  The legacy `×2.5` is compatibility-only and must not be re-asked as a V1
  policy blocker.
- **Evidence 2026-08-27:** the local V1 now exercises the proposed values. The
  three pods show unavoidable pre-arrival shortages under zero demo stock; four
  fresh lines show a pack-rounding versus max-cover conflict. These are the
  concrete results to review, not abstract blockers.
- **Blocks:** business approval of the affected scheduling/constraint policies
  and any operational/shadow use.
- **Does not block:** the completed local V1 or Milestone 2 UI planning/building.

## HA-12 — Apicbase stock-export assessment

- **Status:** `OPEN`
- **Owner:** Valentin / data analyst / Culinary or Apicbase owner
- **Evidence received 2026-08-26:** prep-kitchen operators upload manual stock
  counts to Apicbase and exclude unusable goods. Apicbase is the intended item/
  recipe source, but its master is stale; the new Excel standard will therefore
  maintain the smaller pod/ingredient BOM and item set manually for V1. Two
  current stock-report XLSX samples were inspected: location/export time are in
  row 1, headers in row 3, and current quantity is present. Most rows lack UID
  and supplier article number, so a reviewed name fallback is required.
- **Decision for local V1:** the user selects the planning `location_id` when
  uploading a stock file, and the export timestamp is the latest-known
  `counted_at`. Supplied examples may be treated as the same demo location.
- **Action:** approve the remaining stock-export contract only: quantity unit,
  usable-stock semantics, opened/partial packs, filename cadence, and mapping
  precedence of Apicbase UID then exact reviewed stock name. API access is later automation. Recipe/item
  API assessment may continue separately but is not a V1 blocker.
- **Evidence 2026-08-27:** the stock adapter is implemented and tested against
  the standard report. The PREP-CGN run mapped 12 required items and visibly
  defaulted four missing mappings to zero in scenario mode only. Strict modes
  do not make that assumption.
- **Blocks:** approving current-stock semantics and mappings for operational use.
- **Does not block:** the completed scenario adapter, local V1, or the UI upload/
  mapping-review flow.

## HA-13 — Approve the new-standard V1 input contract

- **Status:** `AWAITING MAINTAINER REVIEW`
- **Owner:** Valentin / Excel maintainer / planning owner
- **Action:** approve the maintainer-facing contract in
  `canonical_data_contracts.md` section 3.11:
  1. `Phase2_Master_Data_Template_v1.xlsx` with `Items`, `Locations`, and
     `Delivery_Rules`;
  2. `Phase2_Planning_Input_Template_v1.xlsx` with `Demand_Plan`,
     `Menu_Calendar`, and `BOM_Lines`;
  3. cumulative Transgourmet PDF drop for ingredients and pods; and
  4. current Apicbase stock-report XLSX drop per relevant prep location.
- **Evidence 2026-08-27:** both project-owned templates were created and
  prefilled from the supplied menu/pod evidence. Item rows are global;
  demand/menu are location-aware; BOM rows are location-independent.
- **Acceptance evidence 2026-08-27:** all five local work packages are
  implemented. Run `improved-67fb3838775f` produced 23 dated recommendations
  across 11 items with zero blockers; seven result files replayed
  byte-identically and 44 tests pass. The packet includes a concise maintainer
  result summary plus stock/PO mapping-review CSVs.
- **Review packet:** validate the two templates together with
  `docs/descriptions/v1_assumptions_and_admin_validation.md`, which identifies
  confirmed rules, V1 approximations, demo defaults, legacy-only constants and
  the exact remaining questions.
- **Important:** the maintainer edits these two project-owned schemas and
  supplies the two raw exports. The supplied `CWxx_*` workbooks are migration
  inputs, not layouts that code must support indefinitely. Normalizers generate
  canonical table/CSV rows; those are not additional manual files.
- **Blocks:** declaring the highlighted master fields operationally approved
  and presenting a UI result as shadow/production-ready.
- **Does not block:** local technical V1 completion or starting the thin UI and
  Supabase schema planning over the same contracts.

## Maintenance rule

Update an action only when its status, owner, evidence, or exact request changes.
Do not add approval, dispatch, ERP-write, or broad UI-workflow actions unless the
project scope is explicitly expanded.
