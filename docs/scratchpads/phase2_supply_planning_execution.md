# Agent Scratchpad — Phase 2 Supply Planning

> Short execution context. Authoritative scope is the brief; priorities are in
> the master backlog; measured SQL counts are in the Snowflake evidence file.

## Goal

Replace the manual KW33/KW34 Phase 2 workbook calculation with an internal job
that consumes a daily Phase 1 forecast, applies BOM/stock/PO/config rules, and
writes explainable recommendations to Snowflake.

## Correct architecture — 2026-08-25

```text
Snowflake operational inputs ─┐
                              ├─> pure Python Phase 2 calculation
Supabase editable rules ──────┘              ↓
                                   Snowflake result tables

internal React UI + Python API ↔ Supabase rules
```

- Phase 1 is independent and supplies forecast portions by location/dish/day.
- Phase 2 owns BOM explosion, stock/open-PO netting, lead/review coverage,
  shelf life/max cover, pack/MOQ/case, fresh delivery rules, and internal
  recommendations.
- Supabase exists so non-technical users can edit application-owned rules.
- Snowflake remains authoritative for operational inputs and calculated output.
- The UI is configuration-focused. Approval, comments/assignment,
  supplier/ERP export, and dispatch are outside scope.
- “Delivery schedule” means simple configured weekdays/cut-offs, not an
  external calendar integration.

## Verified legacy baseline

- Displayed KW34 stocked-item arithmetic is:
  `Daily = round(g/day ÷ pack × 1.20, 2)`;
  `Need = ceil(Daily × 6)`;
  `Bridge = round(KW33 Daily × 2.5, 2)`;
  `After = round(max(0, Stock - Bridge), 1)`;
  `Order = ceil(max(0, Need - After))`.
- This reconciles 27/27 filled KW34 order cells and 28/28 continuing-item
  bridge values at displayed precision.
- Four positive calculated gaps have blank observed orders; the owner thinks
  they were missed. Two planned fresh ingredients are absent from the stocked
  path because they are ordered per fresh window. Creme Fraiche is `5000 g`,
  current Schnittlauch is the distinct `250 g` product, and `Oel` maps to
  `Sonnenblumenoel`.
- The code implements this arithmetic, but automated tests still use synthetic
  rows. The real workbook golden fixture is the main unfinished M1 task.

## Implemented

- Canonical typed contracts, provenance, and actionable file validation.
- Three-level BOM explosion with pre-mixes and shared-item aggregation.
- `legacy_kw34/v1` calculation and deterministic audit CLI.
- Daily forecast/menu/BOM/item/inventory/open-PO file bundle.
- Pure dated event ledger, stock projection, and open-PO netting.
- Visible stale-stock, late-PO, and projected-stockout issues.
- Strict shadow/production source gates.
- 32 passing tests after removing unused approval/workflow scaffolding.

## Data status

- Required V1-V12 Snowflake verification is complete; do not rerun by default.
- Joel confirmed the old forecasts/recommendations and `BASE_INVENTORY` are
  abandoned. The old outputs remain reference evidence only.
- No live PO source is currently ingested into Snowflake. The current process is
  Transgourmet pending-order history downloaded as PDFs and netted outside the
  workbook. An approved export/API and normalized ingestion remain open.
- Prep-kitchen operators upload manual usable-stock counts to Apicbase. Its
  recipe/item master is stale, but current stock-report XLSX exports are
  available. The reduced pod/ingredient BOM and item set can be maintained in
  the new Excel standard for V1; assess Apicbase stock separately.
- The flattened/versioned BOM is a strong candidate. Physical silo-slot mapping
  remains unresolved but does not block ingredient-level planning.
- Waste, consumption, OOS, and forecast-error semantics are later calibration
  work, not core Phase 2 blockers.

## Interim feedback-V1 source decision — 2026-08-26

- Use the original KW33/KW34 workbook as the complete historical comparison
  fixture. Extract its forecast, menu/week context, stock, item/pack values, and
  other available fields with workbook/tab/week provenance; do not ask the Excel
  owner to resend data before the first comparison.
- Keep raw manual Transgourmet downloads outside git and transform them with the
  implemented `scripts/extract_transgourmet_pos.ps1` helper into versioned
  private history, supplier-item review, and `open_pos.csv` files. Transgourmet
  API access is later automation, not a prerequisite for the feedback V1.
- For the new recurring V1, the maintainer edits two workbooks:
  `Phase2_Master_Data.xlsx` (`Items`, `Location_Map`, `Delivery_Rules`) and
  `Phase2_Weekly_Plan.xlsx` (`Demand_Plan`, `Menu_BOM`). Adapters generate the
  canonical CSVs; those CSVs are not extra manual inputs.
- Operational snapshots are two raw-file drops: cumulative Transgourmet PDFs
  for both pods and ingredients, and the current Apicbase stock-report XLSX for
  each relevant prep location.
- Forecast moves from manual `Demand_Plan` rows to the future Phase 1 Snowflake
  table. The current new sheet's `Demand/Silo Load` is forecast-like but not
  explicitly date-stamped.
- Planning rules such as shelf life, lead/review, delivery windows,
  safety/yield, MOQ/case, and capacity live in the manual master first and
  Supabase later.
- The authoritative field-by-field source table is in
  `docs/descriptions/data_requirements.md`, "Interim V1 source map".

## Planner answers received — 2026-08-26

- `Demand/Silo Load` is forecast dishes sold/day across all three REWE sales
  units combined because prep and purchasing are centralized. It is based on
  roughly two weeks of consumption plus campaigns, customer-approved, manually
  trend-adjusted, and entered as one flat weekly rate.
- The target needs an explicit service-location → central-planning-location map;
  never replicate the combined workbook value across the three units.
- Current lead durations are owner-confirmed as 3 days standard and 5 days
  fresh. Pod lead is confirmed at 4 calendar weeks (28 calendar days) and pod
  orders are non-cancellable. Cut-off, receipt, review and item-exception rules
  remain open.
- Fresh coverage is `Sat→Mon`, `Mon→Tue+Wed`, `Wed→Thu+Fri`, `Fri→Sat`.
- The Thursday main order is rechecked Monday after inventory. `S/M/W/Fr` are
  delivery-day allocations; their exact placed/confirmed/delivered status is
  still open. Penne is split/reduced because of freezer space.
- The planner does not know why the bridge is `2.5`; exact count time and
  opened/partial-pack handling also remain open.
- The legacy 20% extra-demand buffer was intended to reduce OOS risk but mixes
  forecast protection with yield. Improved V1 proposes explicit safety days:
  `7` pods, `2` ordinary stocked and `0.5` fresh, while `yield_factor=1.00`
  unless deterministic loss is known. These need maintainer approval/correction.

## New workbook deep dive and corrected V1 source model — 2026-08-26

### New workbook facts recovered

- `CW36_Menu` has 18 component rows across five current dishes. It contains
  dish, silo, purchasable item/pod, article number, supplier label, storage
  class, `Demand/Silo Load`, grams per dish, pack size, required grams and
  calculated packages.
- Observed active-sheet formulas are:
  `required_g = Demand/Silo Load × grams_per_dish`,
  `packages/day = CEILING(required_g / unit_size)`, and
  `packages/week = packages/day × 2.5`. The `2.5` is unexplained and must not
  become target policy.
- `CW36_Bestellliste` has 17 hardcoded order-list rows, separated into
  Transgourmet and Circus display sections. Inventory/order cells are blank and
  the list is not formula-linked to `CW36_Menu`; it is a human template, not a
  canonical result.
- The pod metadata workbook has eight complete carton SKUs `91001–91008`, eight
  corresponding 1 kg pack SKUs `1001–1008`, carton size `5 × 1000 g`, 1000 g
  inner packs, carton/pack EANs, 4-week lead and 1-year shelf life from
  production. Six future pack names lack article/EAN values.
- Current `CW36_Menu` uses pod carton articles `91001`, `91004`, and `91005`.
  The maintainer confirmed that exact identical `Artikelname` may link the
  `9100x` carton to its `100x` inner pack for V1. Validate uniqueness and store
  the resolved mapping; do not use fuzzy name matching.
- Visible quality issues to retain for adapter validation:
  - Arrabbiata is hardcoded as `12.5` packages in the order list while menu
    formulas imply `7.5`;
  - the sheet rounds each BOM line before aggregating shared items;
  - fractional weekly packages (`2.5`, `7.5`) are not purchase units;
  - article `350570` appears under two supplier/name combinations, so article
    number alone is not globally unique;
  - `Kuehl/TK` is not one valid storage class;
  - the unheaded `Extra` tab has no defined active-week role;
  - workbook timezones differ (Los Angeles versus Berlin); and
  - future pod rows have incomplete identifiers.

### Corrected purchasing and menu facts

- `Circus` is the official supplier label for pods, but pods are ordered in
  Transgourmet. The existing Transgourmet PDF/history/`open_pos.csv` path covers
  pods and ordinary ingredients. The previous proposal for a separate Circus
  PO register was wrong and is superseded.
- The current menu remains effective until superseded and changes are
  communicated at least 4 weeks before effect. The six-week dummy repetition
  covers the proposed `28-day pod lead + 7-day review = 35-day` horizon.
- `Demand/Silo Load` is still the only forecast-like field visible in the new
  active menu tab. It can be interpreted using the earlier owner answer as
  combined expected portions/day, but it lacks explicit service dates and plan
  version. V1 therefore needs a dated `Demand_Plan` tab.
- Fresh service-window mapping is answered and should not be reopened:
  `Sat→Mon`, `Mon→Tue+Wed`, `Wed→Thu+Fri`, `Fri→Sat`. Receipt/cut-off time,
  holidays and item exceptions remain configuration details.

### Apicbase stock-export evidence

- Two local 2026-08-26 XLSX examples were inspected read-only:
  `PREP-AD-BW` and `PREP-CGN-MOSE`.
- Both use sheet `Stock Report`; row 1 carries source location and export time,
  row 3 carries 12 headers, and data begin in row 4. Useful fields are stock
  item name, optional UID, accounting/category/subcategory, optional supplier
  article, current stock quantity/value, Par and minimum.
- The examples contain 101 and 90 item rows. UID is absent on 68 and 57 rows;
  supplier article number is absent on 98 and 87 rows. Therefore neither field
  can be the only join key. Use UID when present, otherwise an exact reviewed
  `apicbase_stock_item_name` crosswalk from the manual master.
- Current quantity can be fractional (five fractional rows in the AD-BW sample),
  so the adapter cannot assume integer packs. The source does not state in a
  separate column whether quantity means packs, kilograms, or order units; that
  must be confirmed per item/source contract. Row-1 time is an export request
  time, not yet proven to be the physical count time.
- Which sample location(s) belong to the REWE planning node is not proven by the
  filenames. `Location_Map` must resolve this before quantities are combined.

### Minimal maintainer contract

1. `Phase2_Master_Data.xlsx`
   - `Items`: canonical item, exact display/stock name, item type, official
     supplier, ordering channel, Transgourmet PO article, optional pack article
     and Apicbase UID, pack/order conversion, stock quantity unit, storage,
     lead, shelf-life basis, MOQ/case, max cover, effective/active fields.
   - `Location_Map`: Apicbase source location → planning location/timezone.
   - `Delivery_Rules`: simple order/delivery weekdays, coverage, cut-off,
     review period and effective/active fields.
2. `Phase2_Weekly_Plan.xlsx`
   - `Demand_Plan`: plan version, planning location, service date, dish ID/name,
     forecast portions, menu version and active flag.
   - `Menu_BOM`: line/menu version, dish, silo, purchasable item, grams per
     portion and effective dates.
3. Raw drops:
   - cumulative `data/private/incoming/transgourmet_pdfs/`, including pods;
   - dated `data/private/incoming/apicbase_stock/` XLSX per relevant location;
   - versioned workbook exports under `data/private/incoming/manual/`.

Machine-generated canonical CSVs remain the engine/audit interface; the
maintainer does not edit six side CSVs.

### Snowflake boundary after this correction

- Controlled V1 calculation can run without a current Snowflake input if the
  two workbooks and two raw drops are complete.
- Abandoned forecast/recommendation/`BASE_INVENTORY` tables are not runtime
  inputs. Sales, waste, OOS, silo and historical BOM tables remain later
  reference/calibration evidence only.
- Snowflake remains the target for the future accepted Phase 1 forecast,
  normalized operational inputs after ingestion, and Phase 2 result/run
  history. Manual master/rule data can move to Snowflake/Supabase later without
  changing the pure engine contract.

### Remaining short questions

1. What exactly does the fixed `×2.5` represent?
2. Where will dated per-dish demand/menu version be maintained, and is
   `Demand/Silo Load` the official portions-per-service-day field?
3. For pods, is one PO unit a 1 kg pack or 5 × 1 kg carton, which article is in
   Transgourmet, and what are MOQ/case multiples?
4. Which prep stock location(s) apply, what unit is `Current Stock (qty)`, are
   partial packs included, and is export time an acceptable count timestamp?
5. What approved input/policy covers week four when menu commitment is 3 weeks
   but pod lead is 4 weeks?
6. Can pod lot production/expiry be captured, or is a 365-day policy
   approximation from receipt acceptable for V1?

## Earlier next-step list — superseded 2026-08-27

The earlier ordering that put real KW33/KW34 extraction and arbitrary new-
workbook adapters ahead of the local improved run is superseded. The active
sequence is recorded below and in
`docs/plans/v1_template_first_delivery_plan.md`.

## Template-first route correction and generated artifacts — 2026-08-27

### Decisions

- Do not build recurring adapters around the two supplied workbook layouts.
  They are migration/source evidence. The project now owns two fixed schemas
  that the maintainer will use going forward.
- Global item data have one row per `item_id`. `Demand_Plan` and
  `Menu_Calendar` are location-aware; `BOM_Lines` is location-independent.
  Stock, POs, delivery rules, runs, and recommendations receive `location_id`
  from the plan or upload context.
- Local V1 uses `LOC_DEMO_001` and may treat the supplied source files as one
  location. The future UI assigns the selected location when stock/PO files are
  uploaded.
- Six dated dummy menu/demand weeks are the local-V1 test input. The current
  menu remains effective until superseded; the earlier menu-horizon question
  is no longer a blocker.
- Apicbase row-1 export time is the latest-known stock `counted_at` for V1.
- Pod shelf life is approximated as order date + 365 days and stored as
  `shelf_life_days=365`, `shelf_life_anchor=ORDER_DATE`. Exact lot expiry is a
  later improvement.
- Legacy `×2.5` is compatibility evidence only. It is not required to complete
  or approve the improved template-driven V1.

### Generated project-owned templates

- `Phase2_Master_Data_Template_v1.xlsx`
  - sheets: `Instructions`, `Items`, `Locations`, `Delivery_Rules`,
    `Data_Dictionary`, `Lists`;
  - 21 prefilled active/relevant item rows: all eight known pods plus 13
    ordinary CW36 ingredients;
  - fields include supplier versus ordering channel, PO article/description,
    pod inner-pack/carton/EAN conversion, Apicbase UID/name crosswalk, stock
    quantity unit, storage, lead/shelf anchor, safety/yield, max cover, MOQ,
    case multiple, active and review provenance.
- `Phase2_Planning_Input_Template_v1.xlsx`
  - sheets: `Instructions`, `Demand_Plan`, `Menu_Calendar`, `BOM_Lines`,
    `Data_Dictionary`, `Lists`;
  - 180 dated demo demand rows and 180 matching menu rows across six Mon-Sat
    weeks beginning 2026-08-31;
  - 18 effective BOM rows from the active CW36 menu.
- The templates mark copied values, owner approximations, safe demo defaults,
  and ambiguous/missing values separately. Formula-error inspection returned
  no matches. Visual QA is part of the creation workflow.
- A shareable maintainer brief now consolidates the operative values and
  questions in `docs/descriptions/v1_assumptions_and_admin_validation.md` and
  the generated `Phase2_V1_Assumptions_and_Admin_Validation.docx`. It explicitly
  distinguishes values already used by the engine, values planned for the
  remaining recommendation tranche, demo defaults, and legacy-only constants.

### Prefill details and visible review items

- Pods `91001–91008` are mapped to inner packs `1001–1008`, 1,000 g each,
  five packs per carton, with the supplied carton/pack EANs. Pods use
  `official_supplier=Circus`, `ordering_channel=Transgourmet`, 28-day lead and
  365-day order-date shelf-life approximation.
- Exact old Apicbase names were prefilled for the Chicken, Truffle, and Veggie
  pre-mixes where visible in the AD-BW sample. Ordinary stock-name/UID matches
  were prefilled when defensible.
- Pod Transgourmet article/order-unit confirmation, MOQ/case and stock unit are
  still highlighted. Demo values `moq_order_units=0` and
  `case_multiple_order_units=1` allow a scenario run but are not production
  claims.
- Supplier article `350570` is ambiguous between the current berry mix and
  cranberries evidence; mapping must use an exact PO description or corrected
  article rather than article alone.
- Kichererbsen source packaging is expressed in litres while BOM planning uses
  grams; its stock/order conversion remains a review item.
- Lead durations are confirmed. Initial safety values are explicit improvement
  proposals (`7` pod, `2` ordinary stocked, `0.5` fresh); max-cover remains
  blank/reviewable where not established.

### Local technical V1 completion — 2026-08-27

- All five work packages are implemented: strict template readers, Apicbase
  stock normalization, reviewed/location-aware Transgourmet mapping,
  recommendation policy, and table-ready outputs plus the one-command demo.
- The canonical bundle now includes locations, item policies and delivery rules
  in addition to daily demand/menu/BOM, items, stock and open POs.
- The pure recommendation engine calculates item-specific lead+review
  protection, separate yield/safety, dated stock/PO netting, fresh service
  windows, shelf/max-cover, MOQ/case and final order-unit rounding.
- Acceptance run `improved-67fb3838775f` used `LOC_DEMO_001` at the PREP-CGN
  stock export timestamp `2026-08-26T17:10:00+02:00`. It produced 16 netting
  items, 39 derivation lines, 23 dated recommendations across 11 items, 103
  proposed order units, and zero blockers.
- Pod results are 20 cartons `POD_91001`, 25 cartons `POD_91004`, and 20 cartons
  `POD_91005`. Their 7-day safety is explicit (20% of the 35-day protection
  horizon) and carton rounding remains separate.
- Four required items had no reviewed Apicbase mapping and therefore received
  explicit zero-stock `policy_default` snapshots in scenario mode only. Seven
  unmatched open-PO lines were quarantined. Strict modes do not guess either.
- Three pod pre-arrival shortages are genuine under zero demo stock and 28-day
  lead; four Rucola lines expose one-pack rounding above the proposed max-cover
  cap. Both remain visible review exceptions.
- Seven result files were byte-identical on immediate replay. The output folder
  includes normalized table rows, recommendations, derivations, exceptions,
  stock/PO mapping review, audit JSON and a maintainer review summary.
- The local technical V1 is complete. Maintainer feedback is the gate before
  operational/shadow use, not before UI planning/building. Milestone 2 must
  reuse the exact schemas and show unapproved values visibly.

### Remaining maintainer questions

1. Confirm each pod's Transgourmet article/description, five-pack carton order
   unit, MOQ, and case multiple.
2. Confirm Apicbase `Current Stock (qty)` unit and partial-pack handling for
   every active item.
3. Resolve article `350570` by exact description or corrected article.
4. Approve/correct the proposed seven-day stocked review period, confirm
   whether Monday is a normal reorder opportunity, and provide material
   cut-off/receipt fields; do not re-ask the confirmed 3/5/28-day durations.
5. Approve/correct `7` pod, `2` ordinary-stocked and `0.5` fresh safety days,
   deterministic yield loss if any, and hard max-cover values.

Do not re-ask the menu-valid-until-superseded/six-week-dummy assumption,
upload-selected location, export
timestamp, pod 28-calendar-day lead, pod order-date-plus-365-day approximation,
Transgourmet pod route, fresh coverage windows, or legacy `×2.5` as V1 blockers.

## Transgourmet PDF import validation — 2026-08-26

- Source scope: top-level PDFs in the local Downloads folder; no source PDF was
  copied into the repository. Git ignores `*.pdf`, `data/private/`, and `tmp/`.
- The run scanned 92 PDFs, ignored 11 unrelated files, identified 81 matching
  exports, and deduplicated one re-download to 80 unique order documents.
- Every item and delivery total reconciled. The private history contains 364
  lines across 47 supplier article numbers. One article has more than one
  displayed `Geb.`/`BE` combination and remains a pack-mapping review item. No
  raw line data is documented or committed.
- A same-input rerun produced byte-identical history, dated-open, undated-open,
  supplier-item, and summary files.
- For `as_of_date=2026-08-26`, 356 history lines are closed/received, including
  14 whose `Liefertag` is exactly the as-of date. The canonical output contains
  the 8 strictly future-dated open rows; its parser accepted all 8 with unique
  line IDs and timezone-aware receipt timestamps. No current row lacks
  `Liefertag`, so `undated_open_pos.csv` is header-only.
- PDF-measured fields: order timestamp, scheduled delivery date, supplier
  article number, item description, displayed ordered units, `Geb.` package
  count, `BE` code, and line value.
- The same importer/source is the V1 PO path for Circus-labelled pods because
  they are ordered through Transgourmet.
- Confirmed status rule: missing/future `Liefertag` is open; today/past is
  closed/received. History stores that derived status for the explicit as-of
  date. Missing-date open rows are retained separately instead of receiving an
  invented event date.
- Interim/inferred fields: generated stable PO/line IDs, central planning ID
  `REWE_CENTRAL_PREP`, provisional `TG-<article>` item IDs, ordered units copied
  to open units, and receipt time encoded as 00:00 Europe/Berlin because the
  engine nets at daily grain.
- Open gates: approve the stable planning ID and cross-system item map; obtain
  live remaining quantity, partial receipt, cancellation/date-change,
  update-time, and API/Snowflake ingestion fields.

## Risks

- Do not treat a refreshed abandoned model as authoritative.
- Do not mix Phase 1 forecast creation into this repository.
- Do not call synthetic/default values measured or calibrated.
- Do not silently infer business rules from Snowflake column names.
- Do not commit the workbook, raw production exports, or secrets without the
  recorded approval.
- Do not let files and Supabase become competing production config authorities.
- Do not add supplier/ERP writes or a planning-approval workflow.

## Repository legacy classification audit — 2026-08-27

- `v1-run` uses the two project-owned templates plus a raw Apicbase stock XLSX
  and raw Transgourmet PDFs. No original KW/CW workbook adapter is in the active
  path.
- The isolated KW34 engine/application/CSV adapter, its CLI branch, tests and
  fixture are true compatibility candidates. Keep or move them as one feature
  only after the maintainer/real-input gate and an explicit parity decision.
- Five package `__init__.py` facades still expose stale/legacy APIs. Six domain
  records have no repository consumer outside their definition/re-export.
  Those are cleanup-or-revive decisions, not reasons to create a broad legacy
  dumping ground.
- `run_improved.py`, canonical CSVs and the synthetic improved fixture are
  active under `v1-run`; their names may be neutralized later but they are not
  legacy.
- The authoritative classified path list and cleanup order are in
  `docs/plans/legacy_and_deprecation_register.md`.

## Verification

- Command: `scripts/check.ps1 -PythonExecutable <python-3.12-path>`.
- Current result: 44 tests pass; compilation and `git diff --check` are part of
  the wrapper/final audit.
- Ruff/mypy are configured but unavailable in the bundled runtime.
