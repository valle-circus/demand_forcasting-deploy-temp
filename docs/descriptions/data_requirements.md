# Phase 2 — Data Requirements and Source Status

**Status:** reconciled through 2026-08-25 after reviewing the Lightdash results,
the `CIRCUS_MODELS_READER` information-schema exports, and measured V1-V12
outputs. This is the authoritative source-status document. Detailed counts and
tested zero-row diagnostics are preserved in
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

Nothing blocks continued work on the pure engine, typed contracts, synthetic
tests, or the isolated `legacy_kw34` profile. Do not yet treat the discovered
Snowflake tables as authoritative production inputs. Source ownership,
completeness, grain, units, and lineage must be resolved before their adapters
are accepted for shadow or operational runs.

The first canonical file path is now implemented: a required source manifest
plus daily forecast, menu, BOM, item, inventory, and `open_pos.csv` inputs feed
the pure dated netting engine. This is the approved development/scenario bridge
while real adapters are unavailable. It does not change any source-status
finding below. An explicit manual or observed zero-row PO file is a known empty
result; `empty_placeholder` or `unavailable` provenance is an unknown pipeline
and blocks shadow/operational runs before netting output.

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
ingested into Snowflake**. Source discovery has moved to Ops: Deepali, Dor, and
Ilona can identify how POs and expected deliveries are currently tracked;
Deepali is the likely detailed process owner. Once the source is known, Joel's
team can establish ingestion, potentially with Fivetran, and publish a tested
normalized model. This is an **operational-netting/M4 blocker**, not a blocker
to the pure engine or to manual/file PO scenarios.

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

| # | Planning need | Best current candidate | Status and remaining proof |
|---|---|---|---|
| D0 | Daily dish-demand forecast input | `REPORTING.FACT_CG_DISH_DEMAND_FORECASTS`; ingredient forecast as derived/reference output | **MEASURED/ABANDONED OUTPUT; reference only.** Five current dates, one location, 23 PLUs/day; tested candidate-key checks are clean. Ingredient follow-up finds placeholder rows and one stable ID mixing `g`/`ml`, so it is not a canonical engine input. A replacement's method, owner, coverage, cutoff/timezone, freshness SLA, unit contract, and acceptance remain open; Phase 1 stays pluggable |
| D1 | Sold dishes by unit × day × dish | `REPORTING.FACT_CG_SALES` | **MEASURED/CANDIDATE.** Corrected `CLOSED/SERVED` output returns 622 portions across 221 deployed dish-unit-days; 39 are zero-sale days. Six observed location names each map to one unit, while the corrected per-unit result covers five selling/production units and reconciles to the same 622 portions. Confirm one line item equals one portion, establish stable location IDs, source owner/freshness, and the workbook-field semantics before adapter acceptance |
| D2 | Dishes cooked, including unsold | `REPORTING.FACT_CG_DISH_PRODUCTION` | **CATALOGUED/CANDIDATE**; validate row grain and which statuses/counts represent completed portions before adapter acceptance |
| D3 | Physical ingredient disposal | `REPORTING.FACT_CG_WASTE` | **MEASURED FIELD SUM/CANDIDATE; semantics OPEN.** V4 reproduces 3,750.3 kg and EUR 31,339 across six units, 63 ingredients, and 2026-06-01 through 2026-08-22. Row ratios are strongly bounded, so derivation is possible. `WASTE_QTY_G`, `STRANDED_QTY_G`, `SILO_END_OF_DAY_QTY_G`, and valuation require definitions/lineage before the figures are called physical disposal or used for calibration |
| D4 | Out-of-stock exposure | `REPORTING.FACT_CG_OOS_SILO` plus product/ingredient views | **CATALOGUED/CANDIDATE**. Validate event grain, hard-OOS semantics, duration overlap, and menu join coverage |
| D5 | Current unit stock and expiry observation | `REPORTING.FACT_UNIT_SILO_STOCK_DAILY`; raw `BASE_STOCK_UPDATES` | **MEASURED/CANDIDATE.** V10 found expiry on all 6,497 tested silo-days; the V3 200-row key sample had no composite duplicates. Validate snapshot cutoff/unit semantics, all-class coverage, transition handling, and expiry outliers before adapter acceptance |
| D6 | Menu by unit and day | `INTERMEDIATE.INT_UNIT_DAY_MENU`; `BASE_UCS_MENU` | **MEASURED/CANDIDATE for history; forward horizon OPEN.** All 763 materialized unit-days/26 menu keys resolve to the BOM, but the materialized table ended on 2026-08-24 when queried on 2026-08-25. Base rows extend later but mix operational-looking menus with training/demo/pilot, far-future, long-running, and terminated records. Identify the operational-unit filter, committed forward-menu source, publication timing, and business commitment rule before transition planning |
| D7 | Loaded and consumed grams per day | Daily silo snapshots plus raw stock-update events | **OPEN.** The lagged profile confirms a high-frequency state stream with 12.0% ingredient changes, 62.1% unchanged transitions, gross positive/negative changes above 15 tonnes, and jumps above 7 kg. It does not reconcile to daily net depletion. Filter same-ingredient transitions and confirm event semantics only when calibration is in scope |
| D8 | Versioned `Dish → Silo → Ingredient` BOM in grams | Flattened `FACT_CG_MENU_DISH_INGREDIENTS`, history dimension, raw `BASE_RECIPE_*`, and active-menu/resource stock context | **MEASURED/CANDIDATE for flattened grams and versioning.** 1,193 current rows have complete keys/positive grams/no tested revision-key duplicates; all materialized menu keys resolve; 11,990 valid history intervals and pre-mix decomposition exist. Physical silo/slot topology is still **OPEN**. Corrected V3B found 1,636/2,576 stock keys with menu context through `INGREDIENT_KEY`, but zero resource-position or exact-slot matches; the direct `SILO_RESOURCE_ID ↔ RECIPE_SLOT_INSERTING_POSITION` hypothesis is rejected. Inspect upstream lineage or obtain the authoritative unit/resource/dock-to-effective-slot bridge before using physical capacity |
| D9 | Item/SKU master, pack size, EAN, storage class | `BASE_INGREDIENT_LIST`; `STORAGE_TYPE` is visible on the abandoned generated-recommendation model | **MEASURED/CANDIDATE for pack quantity and unit; partial identity/metadata.** V5 returned 76 rows/75 non-null IDs: one blank ID, zero bad pack quantities, zero missing units, seven missing EANs, and ten missing `APICBASE_ID`s. No non-null duplicate/conflict exception was returned. The abandoned recommendation model's `FRESH`/`FROZEN` values are lineage clues only; resolve the blank record, authoritative storage-class source, ownership, freshness, and whether EAN/Apicbase are required for each adapter |
| D10 | Supplier identity and purchasing terms | Supplier names occur in `BASE_INVENTORY`; article numbers occur in `BASE_STOCKS` | **MEASURED but unsuitable:** three supplier names occur in the stale closed-order extract, while all 21 `BASE_STOCKS` rows lack supplier article numbers. No authoritative supplier-terms master is confirmed. Lead time, MOQ, case size, calendars, and cutoffs remain **POLICY/OPEN** |
| D11 | Open POs and dated in-transit receipts | No current Snowflake source; operational source to be identified with Deepali/Dor/Ilona | **CONFIRMED MISSING FROM SNOWFLAKE / operational blocker.** V7 proves `BASE_INVENTORY` is not the feed, and Joel confirmed no PO data is currently ingested to his knowledge. Ops must identify the system/sheet/process and owner; then data platform must ingest it and publish a normalized source with PO/line ID, item/SKU, location, supplier, ordered and remaining quantities/units, status, order date, expected receipt date, partial receipts, cancellations/date changes, and source update timestamp. Until then, file/manual PO inputs are allowed only with explicit provenance and operational mode fails closed |
| D12 | Goods receipts | No current trusted source; stale `BASE_INVENTORY` is reference only | **OPEN in the same Ops/ingestion workstream.** The old extract is stale (last sync 2025-10-20), all 106 delivery strings failed `TRY_TO_DATE`, and no order timestamp exists. The target source/model must preserve actual and partial receipt events, units, timestamps, cancellations/corrections, and linkage to PO line; completeness and history retention must be tested before lead-time or supplier-performance analysis |

`BASE_INGREDIENT_LIST.APICBASE_ID` makes Apicbase a plausible upstream master
system. It does not prove authority; Joel must confirm the source and owner.

## Configuration entered by a planner or purchasing owner for now

These values belong in validated, versioned configuration until an approved
system integration replaces manual maintenance. “Manual for now” does not mean
they can never have an external source.

| Configuration | Current approach | Evidence that may inform it |
|---|---|---|
| Planning lead time | Item/supplier default plus explicit override | Future order and receipt history once a complete source with both timestamps is found |
| Shelf-life rule and safety margin | Sealed/opened rule, conservative days, and override owner | Observed expiration timestamps; observations do not define the policy |
| MOQ and case/order multiple | Supplier-item configuration | Supplier contract, ERP, or approved purchasing record if later connected |
| Supplier order/delivery calendar, cutoffs, split rules | Supplier/location configuration | Planner and supplier operating process |
| Service level and safety-stock target | Versioned policy by storage class/item | Backtests and service/waste trade-offs |
| Yield-factor bounds and overrides | Versioned policy with provenance | Calibrated consumption and physical-disposal history once available |
| Which classes are stocked vs delivery-to-delivery | Versioned storage policy | Current operating practice; today `Frisch` is treated delivery-to-delivery |
| Approval, export, and dispatch permissions | Versioned workflow policy | Named business owners and four-eyes requirements |

## Question ownership and timing

### Excel owner

The original 13 questions have already been sent and remain appropriate. They
ask the workbook owner to explain the manual process, hidden logic, assumptions,
inputs, overrides, and other information they consult. Do not send a correction
or ask them to validate Snowflake implementation details. Wait for their
answers; section 10 of the brief contains the audience/topic map.

### Joel/data platform—confirmed 2026-08-25

- The three generated planning models and `BASE_INVENTORY` are abandoned models
  from the previous data team. They are not live sources of truth.
- Their definitions are maintained in
  [`data-transformation`](https://github.com/circus-kitchens/data-transformation)
  and may be updated with the replacement logic. Valentin must request GitHub
  access before the definitions and upstream lineage can be inspected.
- Joel will create a stable Snowflake service account using RSA authentication;
  the credential handoff will occur through 1Password. Provisioning is pending.

### Purchase-order source and ingestion—confirmed next workstream

Joel confirmed that purchase-order data is not currently ingested into
Snowflake to his knowledge. Valentin should now ask Deepali and Dor (with Ilona
as another Ops contact) for a short walkthrough of the current PO and expected-
delivery process, source system/sheet, ownership, history, and export/API
capability. After the source is identified, return to Joel to agree ingestion—
potentially via Fivetran—and a normalized, quality-tested Snowflake model.

The data platform is responsible for ingestion/publication; Ops explains and
owns the operational process/source; this repository consumes a read-only
canonical adapter and retains the pure planning calculation. Do not ask Ops to
design the Snowflake model or embed Phase 2 calculation logic in ingestion.

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
| M2 improved file-driven engine | Yes; canonical inputs and policy-free dated netting are implemented | Complete and approve demand semantics, protection periods, yield/safety, constraints, supplier/fresh scheduling, and transition policies before M2 business acceptance |
| M3 Snowflake adapters | Discovery can continue | Owner/lineage, grain, units, coverage, freshness, and three-level BOM mapping for each accepted source |
| M4 shadow run | Not yet | Trustworthy current stock, open POs with expected receipt dates, forward menu, canonical IDs/packs, and comparable planner outputs |
| Operational approval/export | Not yet | All M4 gates plus approval roles and an explicit human approval; no supplier dispatch |

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
