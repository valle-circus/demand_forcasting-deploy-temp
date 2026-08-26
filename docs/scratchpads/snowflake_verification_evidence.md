# Snowflake Verification Evidence Register

**As of:** 2026-08-25
**Purpose:** preserve the measured results and their interpretation so the
private CSV exports do not need to be reopened for routine project work.
`docs/descriptions/data_requirements.md` remains the authoritative source-status
document; this register is its evidence trail.

The raw Snowflake exports are private operational data and must remain outside
git. Counts below come from saved outputs of
`scripts/snowflake_verification.sql`. A zero-row diagnostic means no exception
was found for the exact tested condition; it is not universal proof of source
quality.

## Owner confirmation received 2026-08-25

Joel confirmed that `FACT_CG_DISH_DEMAND_FORECASTS`,
`FACT_CG_INGREDIENT_DEMAND_FORECASTS`, `FACT_CG_PURCHASE_ORDERS`, and
`BASE_INVENTORY` are abandoned previous-data-team models. They may be replaced
in [`data-transformation`](https://github.com/circus-kitchens/data-transformation),
but their currently refreshed rows are not operational source-of-truth data or
approved policy. A stable RSA-authenticated Snowflake service account is planned
with credential handoff through 1Password. Joel also confirmed that purchase-
order data is not currently ingested into Snowflake to his knowledge. Source
discovery now belongs with Ops (Deepali, Dor, and Ilona; Deepali likely knows the
details), followed by ingestion/modeling with Joel's team; Fivetran is a
possible route once the actual source is known.

## Verification results

| Block | Measured result | Interpretation | Remaining work |
|---|---|---|---|
| V6 generated recommendations | 76 rows for one location and one order date: 73 `Sufficient`, 3 `Order Today`. Net requirement, pack ceiling, and estimated cost reconcile on every row. All 18 positive-demand rows use exactly `1.05 × DEMAND_IN_WINDOW`. One row lacks `INGREDIENT_ID`; two lack price; only `FRESH`/`FROZEN` occur. | This is internally coherent generated planning output, not an actual PO ledger. Joel confirmed the model is abandoned. | Inspect its definition/lineage after `data-transformation` access and use it only as reference until a replacement design is approved. |
| V7 purchase/receipt candidates | `BASE_INVENTORY`: 106 lines, 35 POs, all closed and fully delivered, latest sync 2025-10-20; all 106 nonblank delivery strings fail `TRY_TO_DATE`. `BASE_STOCKS`: 21 rows, one location, latest sync 2025-10-30; every supplier article number is missing. Joel confirmed no PO data is currently ingested into Snowflake to his knowledge. | Neither table can support current open-PO netting; the missing feed is confirmed rather than merely undiscovered in the reviewed schemas. The Excel owner later identified Transgourmet pending-order history/PDFs as the current manual process, but not an accepted warehouse feed. | Validate a sanitized Transgourmet export/API with the canonical line/status/quantity/date fields, then coordinate normalized PO/receipt ingestion with Joel/data platform. |
| V8 dish forecast | Each of 2026-08-25 through 2026-08-29 has 23 rows/23 PLUs, four categories, no missing PLU or forecast, and no negative/zero forecasts. Daily totals are 113, 80, 97, 100, and 86 units (476 total). The tested `forecast_date × location × PLU` duplicate/conflict query returned **0 rows**. One location only. | Candidate daily dish-forecast grain passes the tested uniqueness and basic-value checks, but Joel confirmed the model is abandoned. | Treat as reference evidence only. A replacement still needs an owner, approved method, full location coverage, timezone/cutoff, and freshness SLA before adapter acceptance. |
| V8 ingredient forecast | Each of the same five days has 38 rows/31 IDs; the tested `date × location × ingredient_id × unit` duplicate/conflict query returned **0 rows**. The follow-up found 19 affected IDs: 12 have only null-unit/zero-quantity placeholders, six have a valid `g`/`ml` row plus a null/zero placeholder, and `Rotes Thai Curry` has both `g` and `ml` rows. None of 90 null-unit rows has nonzero quantity. | Candidate-key uniqueness passes, but semantic uniqueness does not: the same stable ingredient can carry incompatible units, and almost half of all rows are placeholders. Joel confirmed the model is abandoned. | Do not build an adapter to this output. Use the anomaly as a replacement-model test: canonical requirement unit, no mixed unit per item/date/location without explicit conversion, and explicit placeholder handling. |
| V9 flattened/versioned BOM | Current flattened model: 1,193 rows, 52 menus, 122 PLUs, 120 ingredients, no missing keys or invalid/nonpositive `TOTAL_AMOUNT_G`. The revision-aware candidate-key duplicate query returned **0 rows**. All 763 materialized unit-days and all 26 menu keys join to a BOM. History: 11,990 rows, no missing `VALID_FROM` or invalid intervals, earliest start 2025-01-23, with open-ended records. | The flattened, versioned PLU-to-ingredient grams source is a strong adapter candidate and covers the materialized menu table. | Confirm owner/lineage and effective-date selection. It does not by itself preserve physical silo/slot identity. |
| V9 raw topology and pre-mix | The 200-row raw recipe sample spans 32 recipes, 48 recipe products, 200 product slots, 153 recipe slots, and 60 ingredients; no missing ingredient/amount and no nonpositive amount; 79 rows lack `PORTION_SIZE_ID`. The mixed-ingredient mapping has 16 rows, six mixes, eight components, complete positive `GR`/`FACTOR` values. | A three-level recipe topology and mix decomposition exist. The sample alone does not establish final per-portion semantics or whether a mix is purchased, assembled, or both. | Resolve `PORTION_SIZE_ID` meaning and effective recipe-slot-to-robot mapping before using physical capacity. |
| V3 silo/BOM join | 62 ingredient IDs are ambiguous under an ingredient-only join. The superseded first path incorrectly used constant `CHAMBER_ALIAS`. Corrected V3B tested 2,576 stock keys: 610 (23.7%) have no active-menu/detailed-menu match; no active menu is ambiguous; 489 map to a menu only outside the event day; 1,636 match a detailed-menu slot through `INGREDIENT_KEY`, but zero match through the other tested ingredient IDs or `SILO_RESOURCE_ID ↔ RECIPE_SLOT_INSERTING_POSITION`; zero physical slots are uniquely or ambiguously resolved. | `ACTIVE_MENU_PUBLIC_ID` is unambiguous where present and `INGREDIENT_KEY` provides menu-ingredient context for 83.2% of keys that have an active menu. It still does **not** identify the physical silo slot. The proposed direct resource-position equality is ruled out for this window, and ingredient-only capacity remains invalid. | SQL verification is complete. Inspect `data-transformation`/upstream lineage for the bridge from unit/resource/dock to effective recipe slot; if absent, ask Joel or the robot/menu data owner for the authoritative mapping. Do not use silo capacity in production logic until this is resolved. |
| V5 item master | 76 rows/75 non-null ingredient IDs; one missing ID, zero bad/nonpositive pack quantities, zero missing units, seven missing EANs, and ten missing `APICBASE_ID`s. The exception query returned only the blank ID; no non-null duplicate/conflicting pack/unit/EAN row. Storage consistency likewise surfaced one blank-ID `FRESH` row unmatched to the item master. | Pack quantity and unit coverage are strong in the tested table, while identity, EAN, Apicbase, storage authority, ownership, and freshness still need explicit acceptance. The blank-ID problem propagates into the abandoned recommendation output. | Quarantine/fix the blank-ID row, determine whether EAN/Apicbase are required, and confirm authoritative item/storage lineage before adapter acceptance. |
| V10 expiry observations | 6,497 silo-days in the queried `2026-06-01 <= day < 2026-08-24` window; 100% have `EXPIRATION_DATE`; 4,493 warning rows (69.2%); `DAYS_UNTIL_EXPIRATION` ranges from -2 to 368, average 3.4. Across 72 ingredients, 22 have at least one negative day and nine have a maximum above 60 days. | Expiry observations have excellent coverage but a heterogeneous distribution. They do not define sealed/open shelf-life policy. | Validate date/warning semantics and outliers before using expiry for projection; planner still supplies approved shelf-life rules and margins. |
| V11 menu horizon | `INT_UNIT_DAY_MENU` spans 2025-10-21 through 2026-08-24 across six units and 26 menus. Queried on 2026-08-25, `DAYS_AHEAD_OF_TODAY = -1`: it has no forward-day coverage. The base query returned 11 later/current rows but mixes operational-looking CW35 menus with a 2032-2036 pilot, demo/training, a record lasting to 2027, and one terminated row. | The materialized table is useful historical/current evidence but is not currently a forward planning feed. A naive base-table maximum and name heuristics cannot define a committed operating horizon. | Excel-owner Q7/Ops must identify the committed forward-menu source/process, production-unit filter, and publication timing before transition planning. |
| V12 stock activity | Daily model: 18 service days, 259.9 kg summed net depletion including one negative day. Raw model: 148,158 state updates. The lagged profile has 147,980 transitions: 17,691 ingredient changes (12.0%), 25,332 positive, 30,817 negative, and 91,831 unchanged; gross changes are +15,275.5 kg and -15,317.9 kg, with jumps above 7 kg. | This is conclusively a state stream containing ingredient resets/corrections, not a direct consumption fact. Gross transition deltas also do not reconcile to the daily net-depletion total. | D7 remains open. Only if calibration becomes current work, rerun the enhanced query using same-ingredient transitions, then inspect model/event definitions before assigning physical meaning. |
| V1/V2 sales and zero days | Status population: 673 `CLOSED/SERVED`, 3 `CLOSED/ERROR_HALT`, 2 `REFUNDED/SERVED`, 1 `CLOSED/(null)`. Corrected dish-level V2 returns 20 dishes, 221 deployed dish-unit-days, 39 zero-sale days (17.65%), 622 portions, and maximum dish-unit-day 15. V1 maps each of six observed location names to one unit serial. V2B reconciles the 622 portions across five selling/production units: 191, 157, 126, 106, and 42 portions; 31.8, 26.2, 31.5, 17.7, and 8.4 per service day. | The status filter, saved location mapping, and saved per-unit denominator checks are closed. The sixth location is Secura/training and does not appear in V2B. A name-based one-to-one sample is not a stable location-ID contract. | Confirm that one served line item equals one portion, accept source ownership/freshness and stable location IDs, and keep workbook-number meaning/scope as an Excel-owner question. |
| V4 waste | For 2026-06-01 through 2026-08-22: 5,699 rows, 314 unit-days, six units, 63 ingredients; field sums are 3,750.3 kg `WASTE_QTY_G`, EUR 31,339 `WASTE_VALUE_EUR`, and 4,691.5 kg end-of-day silo quantity. All waste values are non-null; 60 pack values are null. Of 5,305 positive-denominator rows, `WASTE_QTY_G / SILO_END_OF_DAY_QTY_G` has p10 0.018, median 0.771, p90 0.912, maximum 0.982. Rows are fresh solid/liquid except 60 null-type rows. | The headline is now reproducible as a warehouse **field sum across six units, 63 ingredients, and an 83-day window**—not one dish or one unit. It is not yet validated as physical disposal. The bounded ratio is a derivation warning, not proof. | Before sharing it as waste or using it for yield calibration, ask Joel for the physical meaning/lineage of the waste fields and valuation formula. |

## Optional diagnostics or owner evidence still needed

1. Inspect model/upstream lineage or obtain owner evidence for the authoritative
   unit/resource/dock-to-effective-recipe-slot bridge. This is not another SQL
   rerun of the tested direct equality.
2. Optional enhanced V12 same-ingredient transition profile only if daily
   consumption/refill calibration becomes current work.

## Durable conclusions

- Build work on pure calculations and file contracts can continue.
- The strongest operational blocker is still actual open POs with remaining
  quantity and expected receipt date. It is now confirmed as a missing
  Snowflake ingestion, with Ops source discovery and data-platform ingestion as
  the explicit workstream. It does not block pure/file engine development.
- The abandoned forecasts/recommendations are reference evidence only. The
  flattened/versioned BOM remains a credible requirements adapter candidate
  pending lineage. V3B rules out the tested direct resource-position join, so
  physical-slot/capacity use additionally requires an authoritative bridge.
- Physical silo capacity, daily consumption, forward menu commitment, storage
  authority, and physical-waste semantics remain open for different reasons;
  none should be replaced with an unlabelled assumption.
