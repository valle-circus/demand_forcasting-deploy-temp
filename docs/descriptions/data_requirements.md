# Phase 2 — Data Requirements and Source Status

**Status:** reconciled through 2026-08-26 after reviewing the Lightdash results,
the `CIRCUS_MODELS_READER` information-schema exports, measured V1-V12 outputs,
and the Excel owner's Q1-Q13 response. This is the authoritative source-status
document. Detailed counts and tested zero-row diagnostics are preserved in
`docs/scratchpads/snowflake_verification_evidence.md`. The earlier
build-sequencing report and `scripts/snowflake_discovery.sql` are historical
evidence only.

## Evidence labels

| Label | Meaning |
|---|---|
| **MEASURED** | A saved query was executed and returned the stated result |
| **CATALOGUED** | The table, row count, and columns were observed through `information_schema`; data values, grain, completeness, and semantics are not yet validated |
| **CANDIDATE** | The schema could satisfy the need, subject to source-fitness checks and owner confirmation |
| **POLICY** | A reviewed business/configuration value; it is not inferred from an observation |
| **OPEN** | The source, definition, authority, or coverage remains unknown |

`CIRCUS_MODELS_READER` can read 140 physical tables across `BASE`,
`INTERMEDIATE`, `REPORTING`, and `TECH_OPS`. Access is **MEASURED** and is no
longer a blocker. The Lightdash service role sees only `LOOKER_STUDIO_CIRCUS`
and must not be used to prove that data is absent elsewhere.

## Current decision

### Phase ownership and storage

- **Phase 1, outside this repository:** produces forecast portions at
  `service location × dish × service_date` grain. When purchasing/stock is
  centralized, the source or adapter must map service locations to one stable
  inventory/planning location and aggregate once. Historical sales, OOS, and
  related demand signals belong primarily to forecasting.
- **Phase 2, this repository:** consumes that forecast and calculates
  ingredient/purchase requirements from menu/BOM, stock, open POs, lead time,
  shelf life, pack/MOQ/case, storage behaviour, and simple delivery rules.
- Waste/consumption and forecast-error history are optional later calibration
  inputs. They do not block the first Phase 2 calculation.

Operational inputs and Phase 2 results belong in Snowflake. Application-owned
rules that non-technical users must edit belong in Supabase and are managed
through the internal UI/API. Every Snowflake result run must retain the active
Supabase config version/hash. Supabase is not a duplicate warehouse or result
store.

Nothing blocks continued work on the pure engine, typed contracts, synthetic
tests, or the isolated `legacy_kw34` profile. Do not yet treat the discovered
Snowflake tables as authoritative production inputs. Source ownership,
completeness, grain, units, and lineage must be resolved before their adapters
are accepted for shadow or production runs.

The first canonical file path is now implemented: a required source manifest
plus daily forecast, menu, BOM, item, inventory, and `open_pos.csv` inputs feed
the pure dated netting engine. This is the approved development/scenario bridge
while real adapters are unavailable. It does not change any source-status
finding below. An explicit manual or observed zero-row PO file is a known empty
result; `empty_placeholder` or `unavailable` provenance is an unknown pipeline
and blocks shadow/production runs before netting output.

Joel confirmed on 2026-08-25 that
`REPORTING.FACT_CG_PURCHASE_ORDERS`, `FACT_CG_DISH_DEMAND_FORECASTS`,
`FACT_CG_INGREDIENT_DEMAND_FORECASTS`, and `BASE_INVENTORY` are abandoned models
from the previous data team. V6/V8 show that some job still refreshes three of
them, but refresh activity does not make them operational or authoritative.
They may be useful reference implementations and their definitions may be
replaced with this project's logic in the
[`data-transformation`](https://github.com/circus-kitchens/data-transformation)
repository once access is granted.

That repository statement does not resolve the target architecture. Before
changing the models, inspect their definitions and decide whether
`data-transformation` owns normalized Snowflake inputs/outputs while this
repository retains the pure Phase 2 calculation engine, or whether a different
boundary is intended. Do not maintain the same business logic independently in
both repositories.

`BASE_INVENTORY` is now ruled out as the operational open-PO feed. V7 returned
106 lines across 35 POs, all `Closed`, with ordered quantity equal to delivered
quantity, no undelivered lines, and a last sync on 2025-10-20. Joel then
confirmed that, to his knowledge, **no purchase-order data is currently
ingested into Snowflake**. The Excel owner has since identified Transgourmet
order history as the current pending-order source: PDFs are downloaded and
analysed outside the workbook before final quantities are entered. Source
identification is therefore closed, while export/API fitness, field semantics,
history, ownership, and normalized ingestion remain open. Joel's team can
establish ingestion once an approved sanitized example is available. This is a
**production-netting/M4 blocker**, not a blocker to the pure engine or to
manual/file PO scenarios.

Joel will create a stable Snowflake service account authenticated with RSA
credentials shared through 1Password. This resolves the intended connection
method once provisioned; it does not provide missing PO data. Store no private
key, token, or 1Password secret in this repository or its documentation.

## Measured verification findings — 2026-08-25

- The three generated models refreshed sequentially at approximately 04:31-04:32
  Berlin time on 2026-08-25. This strongly suggests one automated pipeline, but
  Joel confirmed that the models themselves are abandoned and not an approved
  operational planning flow.
- Dish forecasts contain 115 rows and ingredient forecasts 190 rows, covering
  five dates (2026-08-25 through 2026-08-29) and one location. The dish
  candidate key `date × location × PLU` passed its duplicate/conflict check;
  each date has 23 PLUs with no missing, negative, or zero forecasts.
- The ingredient candidate key `date × location × ingredient_id × unit` also
  passed its duplicate/conflict check. Each date has 38 rows/31 IDs, including
  18 zero-quantity rows with missing unit. The follow-up classifies 19 affected
  IDs: 12 placeholder-only, six with a real unit plus a null/zero placeholder,
  and one (`Rotes Thai Curry`) carrying both `g` and `ml`. This abandoned output
  passes key uniqueness but fails a canonical-unit requirement.
- The recommendation output contains 76 lines for one location, all for order
  date 2026-08-25 and arrival date 2026-08-26: 73 `Sufficient` and 3
  `Order Today`. Netting, pack ceiling, and estimated-cost arithmetic reconcile
  on every exported row.
- For all 18 positive-demand recommendation lines,
  `DEMAND_PLUS_SAFETY / DEMAND_IN_WINDOW = 1.05`. This is a measured 5% uplift
  in the current model, not an approved Phase 2 policy.
- Recommendation quality caveats: one of 76 lines lacks `INGREDIENT_ID`, two
  lack `PACKAGE_PRICE`, only `FRESH` and `FROZEN` appear, and the export covers
  only one location. The output is internally coherent but not adapter-ready.
- `BASE_INVENTORY` is a stale closed-order/receipt snapshot, not a pipeline
  source. All 106 nonblank `DELIVERED_ON` strings failed `TRY_TO_DATE`; its use
  even for historical receipts requires a format and coverage investigation.
- `BASE_STOCKS` returned 21 rows for one location, last synced 2025-10-30, with
  all supplier article numbers missing. It is not a current stock or supplier
  master for operational planning.
- `BASE_INGREDIENT_LIST` has 76 rows and 75 non-null ingredient IDs. One row
  has no ID; no row has a bad/nonpositive pack quantity or missing unit; seven
  rows lack EAN and ten lack `APICBASE_ID`. The only duplicate/conflict
  diagnostic row is the blank ID. This makes pack quantity and unit strong
  candidates after the blank-ID record and ownership are resolved; EAN and
  Apicbase coverage are incomplete.
- The current flattened BOM has 1,193 rows across 52 menus, 122 PLUs, and 120
  ingredients, with no bad gram/key rows and no revision-aware duplicates. All
  763 materialized unit-days/26 menu keys resolve to it. The history table has
  11,990 valid intervals; raw three-level recipe and pre-mix mappings also
  exist. Corrected V3B tested 2,576 stock keys: 1,636 match the active menu via
  `INGREDIENT_KEY`, but none match `SILO_RESOURCE_ID` to
  `RECIPE_SLOT_INSERTING_POSITION` and no physical slot is resolved. Physical
  silo/recipe-slot identity therefore remains unresolved, and that tested
  direct position join is ruled out.
- Expiry is populated on all 6,497 tested silo-days, but remaining life ranges
  from -2 to 368 days. It is an observation, not an approved shelf-life rule.
- Raw stock data contain 148,158 high-frequency state updates across 34 silos
  in the tested window. The 147,980-transition follow-up contains 17,691
  ingredient changes, 91,831 unchanged states, and gross positive/negative
  changes above 15 tonnes each. Daily `NET_DEPLETION` can also be negative.
  Neither source is physical consumption without reset filtering and semantics.
- `INT_UNIT_DAY_MENU` materializes 2025-10-21 through 2026-08-24 across six
  units and 26 menus. When queried on 2026-08-25, it had **zero forward-day
  coverage** (`days_ahead_of_today = -1`). `BASE_UCS_MENU` contains later rows,
  but mixes production-looking CW35 menus with training/demo/pilot,
  far-future, long-running, and terminated records. The warehouse therefore
  has historical/current menu evidence but no verified committed forward-menu
  feed yet.
- In the 2026-08-17 through 2026-08-22 sales window, the six observed location
  names each map to one unit serial. Corrected per-unit output reconciles to
  622 valid portions across five selling/production units: 191, 157, 126, 106,
  and 42 portions, or 31.8, 26.2, 31.5, 17.7, and 8.4 per service day. This
  closes the saved V1/V2B checks but does not replace a stable location-ID
  contract or define the workbook's `Demand/Silo Load` field.
- The corrected `CLOSED/SERVED` dish-sales comparison has 622 portions across
  221 deployed dish-unit-days, including 39 zero-sale days, for 2026-08-17
  through 2026-08-22. The earlier provisional 626 total is superseded.
- V4 reproduces field sums of 3,750.3 kg `WASTE_QTY_G` and EUR 31,339
  `WASTE_VALUE_EUR` across six units, 63 ingredients, and 314 unit-days. These
  are not one-dish or one-unit figures and are not yet validated as physical
  disposal or accounting valuation.

## Corrections to the earlier discovery

- `FACT_CG_SALES_DAILY` has no dish dimension. Dish demand history belongs in
  `REPORTING.FACT_CG_SALES`.
- Storage, expiry, supplier-name, recipe, and mixed-ingredient fields exist
  outside the Lightdash-visible schema. Their presence makes them candidate
  sources; it does not make them authoritative master data.
- `BASE_MIXED_INGREDIENT_MAPPINGS` proves that a decomposition mapping exists.
  It does not prove whether pre-mixes are purchased, assembled on site, or
  handled both ways.
- The `Demand/Silo Load` comparison is directional evidence only. Its meaning
  and per-unit/network scope remain open.
- The waste field sums are now reproducible, but their physical meaning and
  valuation are not verified. Do not describe or share the EUR 31k figure as
  physical waste until lineage is confirmed.

## Data-source matrix

How this matrix is used:

- `D0` is the independent Phase 1 forecast input contract; Phase 2 consumes it
  but does not build the forecast.
- `D5`, `D6`, `D8`, `D9`, and `D11` are core Phase 2 runtime inputs.
- `D10` is primarily editable Phase 2 configuration until a trusted master
  source exists.
- `D1`-`D4`, `D7`, and historical receipt analysis in `D12` are reference or
  later calibration work; they do not block the minimum Phase 2 engine.

### Interim V1 source map — decided 2026-08-26

The first planner-feedback run uses the existing `Supply_Planning_Rewe.xlsx`
week as one historical fixture. It does not require another data request to the
Excel owner before the run. Every value extracted from the workbook must retain
its workbook/tab/week provenance. Workbook data are evidence for that historical
run, not a recurring operational source.

For recurring file-based runs, use a manual, versioned CSV source of truth until
an accepted automated source is available. Operational sources should ultimately
be published to Snowflake; editable planning policy should ultimately be stored
in Supabase. A table that merely exists in Snowflake is a candidate, not an
accepted source.

| Information | Historical feedback V1 | Interim recurring source of truth | Intended automated source | Current status / next action |
|---|---|---|---|---|
| Comparison baseline | Original KW33/KW34 workbook, including observed final quantities | Not applicable | None required | **AVAILABLE.** Use read-only as the historical comparison fixture; do not commit raw workbook data without approval |
| Daily forecast | `Demand/Silo Load` and week context from the original workbook | Versioned `forecast_daily.csv`, manually supplied by Phase 1 | New Phase 1 daily forecast table in Snowflake | **TARGET KNOWN, TABLE OPEN.** Existing `FACT_CG_*_FORECASTS` models are abandoned; do not use them as live sources |
| Menu by service date | Original workbook week/tabs | Versioned `menu_calendar.csv`; it may be produced from the Phase 1 file only if Phase 1 explicitly carries the complete active dish/date schedule | Accepted forward-menu model in Snowflake | **SOURCE UNCLEAR.** Historical Snowflake menu candidates exist, but the current committed forward-menu source/horizon is not accepted |
| BOM / grams per portion | Use workbook values that are actually present and label any derived ingredient requirement as legacy evidence, not as a complete authoritative BOM | Versioned `bom_lines.csv` from a reviewed export | Accepted BOM model in Snowflake, potentially sourced from Apicbase or the existing recipe models | **AUTHORITY UNCLEAR.** Snowflake has a strong flattened/versioned candidate; Apicbase is intended but reported stale. Validate the read-only endpoint/export rather than assuming authority |
| Item master, pack size, unit, storage class | Original workbook values plus the owner-confirmed corrections | Versioned `items.csv` maintained manually from the best reviewed export | Accepted item model in Snowflake, potentially sourced from Apicbase | **AUTHORITY UNCLEAR.** Request Apicbase item/pack endpoints or exports and validate freshness; Excel remains the current operational fallback |
| Current usable stock | Historical `Stock KWxx` values from the original workbook | Versioned `inventory_snapshots.csv` from the current manual count or an Apicbase export | Snowflake stock model after an Apicbase source is accepted/ingested | **ACCESS/CONTRACT OPEN.** Request the Apicbase stock endpoint/export, timestamp, unit, usable-stock semantics, and partial-pack representation |
| Open POs / in-transit | Not required to create the workbook-only legacy fixture; use only if available to explain off-sheet historical overrides | Raw manual Transgourmet download kept outside git, transformed into versioned `open_pos.csv` | Normalized Snowflake PO table after Transgourmet API ingestion | **INTERIM DECIDED.** Manual raw-file-to-CSV flow now; Transgourmet API later. Snowflake has no accepted live PO table |
| Cross-system item mapping | Workbook labels may be used only inside the historical fixture with an explicit mapping record | Manually maintained mapping from canonical `item_id` to Apicbase ID and Transgourmet article number | Accepted normalized item/supplier-item mapping in Snowflake | **MISSING.** Request available IDs/article fields with the Apicbase assessment and map Transgourmet lines before producing `open_pos.csv` |
| Lead time, shelf life, delivery windows, safety/yield, MOQ/case, capacity | Workbook constants and received owner answers, explicitly labelled as legacy or provisional | Versioned manual config CSV/YAML maintained by the planning owner | Supabase editable configuration | **MANUAL SOURCE OF TRUTH.** Exact policies can remain provisional for the first comparison and must not be inferred from operational observations |

The immediate external request is therefore limited to read-only Apicbase
access/documentation or exports for three domains—current stock, BOM/recipes,
and item master/pack sizes—plus available IDs needed to map Transgourmet article
numbers. API access is desirable for automation but is not required if a
reviewed manual export can populate the interim CSVs.

| # | Planning need | Best current candidate | Status and remaining proof |
|---|---|---|---|
| D0 | Daily dish-demand forecast input | Current manual forecast in a separate Google Sheet; `REPORTING.FACT_CG_DISH_DEMAND_FORECASTS` is abandoned reference output | **OWNER-CONFIRMED MANUAL BASELINE; live contract OPEN.** The workbook value is expected dishes sold/day across three REWE sales units combined at central prep, based on roughly two weeks of consumption plus campaigns, customer-approved, manually trend-adjusted, and entered as one flat weekly rate. The abandoned Snowflake output remains reference only. A replacement needs daily grain, method/owner/version/horizon/cutoff/freshness, source of consumption history, stable service-location IDs, and an explicit service-to-planning-location map so the combined value is not tripled |
| D1 | Sold dishes by unit × day × dish | `REPORTING.FACT_CG_SALES` | **MEASURED/CANDIDATE.** Corrected `CLOSED/SERVED` output returns 622 portions across 221 deployed dish-unit-days; 39 are zero-sale days. Six observed location names each map to one unit, while the corrected per-unit result covers five selling/production units and reconciles to the same 622 portions. Confirm one line item equals one portion, establish stable location IDs, source owner/freshness, and the workbook-field semantics before adapter acceptance |
| D2 | Dishes cooked, including unsold | `REPORTING.FACT_CG_DISH_PRODUCTION` | **CATALOGUED/CANDIDATE**; validate row grain and which statuses/counts represent completed portions before adapter acceptance |
| D3 | Physical ingredient disposal | `REPORTING.FACT_CG_WASTE` | **MEASURED FIELD SUM/CANDIDATE; semantics OPEN.** V4 reproduces 3,750.3 kg and EUR 31,339 across six units, 63 ingredients, and 2026-06-01 through 2026-08-22. Row ratios are strongly bounded, so derivation is possible. `WASTE_QTY_G`, `STRANDED_QTY_G`, `SILO_END_OF_DAY_QTY_G`, and valuation require definitions/lineage before the figures are called physical disposal or used for calibration |
| D4 | Out-of-stock exposure | `REPORTING.FACT_CG_OOS_SILO` plus product/ingredient views | **CATALOGUED/CANDIDATE**. Validate event grain, hard-OOS semantics, duration overlap, and menu join coverage |
| D5 | Current unit stock and expiry observation | Apicbase manual prep-kitchen counts; `REPORTING.FACT_UNIT_SILO_STOCK_DAILY` and raw `BASE_STOCK_UPDATES` as measured candidates | **OWNER-IDENTIFIED PROCESS plus MEASURED WAREHOUSE CANDIDATES.** Operators count manually, upload to Apicbase, and exclude expired, damaged, reserved, or otherwise unusable goods. Count timestamp, partial/open-pack treatment, API/export fields, planning-location scope, freshness/history, and source authority still require read-only validation. V10 found expiry on all 6,497 tested silo-days, but robot-silo data alone does not establish all-class central prep stock |
| D6 | Menu by unit and day | Planner-controlled current process; `INTERMEDIATE.INT_UNIT_DAY_MENU` and `BASE_UCS_MENU` as measured history candidates | **OWNER PROCESS PARTIAL; forward horizon OPEN.** The planner drives menu changes and can cancel Transgourmet orders but not future pod orders. The owner did not provide the committed horizon or versioned source. All 763 materialized unit-days/26 menu keys resolve to the BOM, but the materialized table ended on 2026-08-24 when queried on 2026-08-25. Identify the operational-unit filter, committed forward-menu source/publication timing, change owner, and non-cancellable pod last-order rule before production planning |
| D7 | Loaded and consumed grams per day | Daily silo snapshots plus raw stock-update events | **OPEN.** The lagged profile confirms a high-frequency state stream with 12.0% ingredient changes, 62.1% unchanged transitions, gross positive/negative changes above 15 tonnes, and jumps above 7 kg. It does not reconcile to daily net depletion. Filter same-ingredient transitions and confirm event semantics only when calibration is in scope |
| D8 | Versioned `Dish → Silo → Ingredient` BOM in grams | Flattened `FACT_CG_MENU_DISH_INGREDIENTS`, history dimension, raw `BASE_RECIPE_*`, and active-menu/resource stock context | **MEASURED/CANDIDATE for flattened grams and versioning.** 1,193 current rows have complete keys/positive grams/no tested revision-key duplicates; all materialized menu keys resolve; 11,990 valid history intervals and pre-mix decomposition exist. Physical silo/slot topology is still **OPEN**. Corrected V3B found 1,636/2,576 stock keys with menu context through `INGREDIENT_KEY`, but zero resource-position or exact-slot matches; the direct `SILO_RESOURCE_ID ↔ RECIPE_SLOT_INSERTING_POSITION` hypothesis is rejected. Inspect upstream lineage or obtain the authoritative unit/resource/dock-to-effective-slot bridge before using physical capacity |
| D9 | Item/SKU master, pack size, EAN, storage class | Excel operational fallback; Apicbase intended but stale; `BASE_INGREDIENT_LIST` measured candidate | **OWNER-CONFIRMED EXAMPLES, authority OPEN.** Creme Fraiche is 5,000 g; current Schnittlauch is the distinct 250 g product; Oel equals Sonnenblumenoel; Paprika-big/Mischsalat are fresh; supplier article numbers exist. The owner reports Apicbase maintenance backlog, so Excel is used now. V5 pack/unit coverage is strong but still has one blank ID and incomplete EAN/Apicbase IDs. Obtain the supplier-article extract, define canonical ID precedence, owner/freshness/change history, and validate pack/unit/storage mappings before acceptance |
| D10 | Supplier identity and purchasing terms | Transgourmet current assortment and supplier portal; future Circus pods; stale warehouse extracts only as reference | **OWNER-REPORTED POLICY STARTING POINTS, exact terms OPEN.** Current planning uses about 3 days for standard goods and 5 days for fresh; future pods are about one month and non-cancellable. Supplier article numbers exist. Calendar/business-day semantics, cut-offs, delivery times, item exceptions, MOQ/case, pod go-live, and the future assortment need approved records/configuration |
| D11 | Open POs and dated in-transit receipts | Transgourmet order-history pending orders/PDFs; no current Snowflake source | **OPERATIONAL PROCESS IDENTIFIED / Snowflake ingestion still missing / production blocker.** The planner reviews pending orders, downloads PDFs, and subtracts them before workbook final quantities. V7 proves `BASE_INVENTORY` is not the feed, and Joel confirmed no current PO ingestion. Validate export/API access and publish a normalized source with PO/line/article IDs, planning location, ordered and remaining quantities/units, status, order/expected-receipt timestamps, partial receipts, cancellations/date changes, and update time. Manual files require explicit provenance; production fails closed until accepted |
| D12 | Goods receipts | Transgourmet may contain order history, but no receipt-history contract was established; stale `BASE_INVENTORY` is reference only | **OPEN in the same ingestion workstream.** Pending-order visibility does not prove actual/partial receipt events or retained history. The old extract is stale (last sync 2025-10-20), all 106 delivery strings failed `TRY_TO_DATE`, and no order timestamp exists. The target model must preserve actual/partial receipts, units, timestamps, cancellations/corrections, PO-line linkage, completeness, and retention before lead-time or supplier-performance analysis |

`BASE_INGREDIENT_LIST.APICBASE_ID` and the owner's operational description make
Apicbase a plausible upstream source for stock, recipes, and item identity. They
do not prove one field-level authority: the owner explicitly reports stale
master data. Assess stock, BOM, and item-master fitness separately through
read-only API/export evidence.

## Configuration entered by a planner or purchasing owner for now

These values belong in validated, versioned Supabase configuration and are
edited through the internal UI once that tranche exists. CSV/YAML are temporary
fixtures/imports until then. “Manual for now” does not mean they can never have
an external source.

| Configuration | Current approach | Evidence that may inform it |
|---|---|---|
| Planning lead time | Owner-reported starting classes: Transgourmet standard ~3 days, fresh ~5 days, future pods ~1 month; store exact supplier/item defaults and overrides only after calendar/cut-off approval | Future order and receipt history once a complete source with both timestamps is found |
| Shelf-life rule and safety margin | Current practice applies no explicit MHD cap to TK/Kuehl/RT in the short cycle, about 3 days for fresh, and anticipates about one year for pods; preserve sealed/opened rule, conservative days, and override owner | Observed expiration timestamps; current non-use does not mean infinite shelf life and observations do not define policy |
| MOQ and case/order multiple | Supplier-item configuration | Supplier contract, ERP, or approved purchasing record if later connected |
| Simple delivery weekdays/cutoffs | Supplier/planning-location configuration; current fresh windows are `Sat→Mon`, `Mon→Tue+Wed`, `Wed→Thu+Fri`, `Fri→Sat`; receipt times/cutoffs/holidays remain open | Planner and supplier operating process |
| Safety days | Simple versioned default by storage class with item override | Backtests may refine it later |
| Yield factor | Legacy `1.20` remains compatibility-only; improved mode uses a separate versioned default/override with provenance | The owner confirms `1.20` is a broad assumption; consumption and physical-disposal history may calibrate it later |
| Which classes are stocked vs delivery-to-delivery | Versioned storage policy | Current operating practice; today `Frisch` is treated delivery-to-delivery |

## Question ownership and timing

### Excel owner — original Q1-Q13 complete, focused follow-up open

The response was received and reconciled on 2026-08-26. Do not resend the
original questionnaire or request duplicate historical inputs before the first
comparison: use the workbook already available. Return to the Excel owner with
the first output and ask only the narrowed questions needed to explain material
differences or approve affected policies. Section 10 of the brief and HA-11
retain those follow-ups. HA-12 tracks the separate read-only Apicbase source
assessment with the data analyst/Apicbase owner.

### Joel/data platform—confirmed 2026-08-25

- The three generated planning models and `BASE_INVENTORY` are abandoned models
  from the previous data team. They are not live sources of truth.
- Their definitions are maintained in
  [`data-transformation`](https://github.com/circus-kitchens/data-transformation)
  and may be updated with the replacement logic. Valentin must request GitHub
  access before the definitions and upstream lineage can be inspected.
- Joel will create a stable Snowflake service account using RSA authentication;
  the credential handoff will occur through 1Password. Provisioning is pending.

### Purchase-order source and ingestion—source identified, contract open

Joel confirmed that purchase-order data is not currently ingested into
Snowflake to his knowledge. The Excel owner identified Transgourmet pending
order history as the current source and described a manual PDF-analysis step.
Valentin should now obtain a read-only, sanitized export/API walkthrough with
the required line/status/quantity/date fields, then return to Joel to agree
ingestion and a normalized, quality-tested Snowflake model.

The data platform is responsible for source ingestion/publication; Ops explains
and owns the operational process/source; this repository consumes those inputs,
retains the pure planning calculation, and writes only to an agreed internal
Snowflake result schema. Do not ask Ops to design the Snowflake model or embed
Phase 2 calculation logic in ingestion.

After repository access is granted, inspect the existing definitions and agree
with Joel on the ownership boundary between Snowflake transformations/publication
and the pure planning engine before replacing any model.

### SQL verification status and physical silo-capacity follow-up

All required V1-V12 verification blocks, including corrected V3B, are complete.
V3B could not establish physical slot identity and rules out the tested direct
resource-position equality. After `data-transformation` access, inspect lineage
for an authoritative unit/resource/dock-to-effective-recipe-slot bridge; if it
is absent, ask Joel or the robot/menu data owner. The enhanced V12 same-
ingredient profile remains optional until consumption/refill calibration is in
scope. Do not delay core engine work for either optional investigation.

### Ask later, before using waste

Ask which waste field represents physical disposal and how
`WASTE_VALUE_EUR` is calculated. Until then, do not present the reproduced
warehouse field sums as physical waste or use them to calibrate yield.

## Stage gates

| Stage | Can continue now? | Required before acceptance/promotion |
|---|---|---|
| M0/M1 foundation and legacy reproduction | Yes | Planner interpretation is needed for business sign-off, not for synthetic engineering |
| M2 improved file-driven engine | Yes; canonical inputs and policy-free dated netting are implemented | Demand meaning and baseline fresh windows are confirmed; approve planning-location mapping, exact receipt/cut-off calendars, protection periods, simple yield/safety settings, and capacity/shelf-life constraints before M2 business acceptance |
| M3 Snowflake/Supabase integration | Discovery can continue | Accepted source grain/units/freshness, service account, target result schema/write pattern, and approved Supabase config ownership |
| M4 shadow run | Not yet | Trustworthy current stock, open POs with expected receipt dates, forward menu, canonical IDs/packs, and comparable planner outputs |
| Scheduled production result | Not yet | All M4 source/config gates plus reliable internal Snowflake write and monitoring; supplier/ERP dispatch is out of scope |

## Tooling and execution order

- `scripts/snowflake_discovery.sql` is historical and must not be used for
  current conclusions.
- `scripts/snowflake_verification.sql` is the current read-only verification
  file. All required V1-V12 blocks were reviewed on 2026-08-25; enhanced V12 is
  optional calibration work and the physical slot gap now requires lineage or
  owner evidence rather than another rerun of the tested direct join. Keep
  exports private and record results in
  `docs/scratchpads/snowflake_verification_evidence.md` rather than committing
  raw CSVs.
- `scripts/explore_snowflake.py` remains non-authoritative and should not be
  used until repaired.

Standing rule: no claim of absence without the searched role/scope; no
aggregate headline without a saved reproducible query; no adapter-ready label
without grain, key, unit, freshness, coverage, and owner checks.
