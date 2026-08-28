# Phase 2 V1 — assumptions, parameters and admin validation

**Version:** 2026-08-27 local V1 result, pending maintainer approval

## Purpose

This is the short review sheet for the Phase 2 supply-planning V1. It records
the main numbers and operating assumptions in one place so they do not have to
be reconstructed from Excel formulas or code.

It is based on the original `Supply_Planning_Rewe` workbook, the new `CW36`
menu/order workbook, the Circus pod carton/pack metadata, the Apicbase stock
examples, the Transgourmet PDF process, and the operational clarifications
received so far.

Status labels:

- **Confirmed:** supplied or explicitly clarified and safe to implement.
- **V1 approximation:** a practical starting assumption that the maintainer
  must validate.
- **Demo default:** allows a local test but is not an approved production rule.
- **Legacy only:** retained only to reproduce/explain the old workbook; not used
  as the improved V1 policy.

## Logic summary

For each selected planning location and service date, V1 will:

1. Read forecast portions and the active menu.
2. Multiply portions by effective `Dish -> Silo -> Item` grams per portion.
3. Aggregate the same purchased item across dishes before rounding.
4. Project the latest usable stock through dated daily demand.
5. Add open Transgourmet POs on their expected receipt dates.
6. Calculate the required coverage from item lead time plus the next review or
   delivery opportunity.
7. Keep deterministic yield loss and safety stock separate.
8. Apply constraints in this order: zero floor, shelf-life cap, max-cover cap,
   MOQ, then case/order-unit rounding.
9. For fresh items, sum the actual forecast days covered by each delivery
   window instead of multiplying an average day.
10. Output recommendations, derivations and visible exceptions. V1 does not
    place or send an order.

All ten stages are now implemented in one template-driven path. The template,
stock and PO adapters are work packages 1-3; the pure recommendation policy is
work package 4; and the table-ready outputs plus one-command acceptance run are
work package 5. This remains one plan, not two calculation checklists.

## Main values and assumptions to validate

| Area | Current V1 value | Status and requested validation |
|---|---|---|
| Planning timezone | `Europe/Berlin` | V1 approximation. Confirm for each future location. |
| Location | Local test uses `LOC_DEMO_001`; future upload selects `location_id` | Demo default. Replace with stable operational location IDs. |
| Planning horizon | Six dated demo weeks, Monday-Saturday: 36 service days | V1 improvement. The longest proposed protection horizon is 35 calendar days (`28` pod lead + `7` day review), so four weeks alone cannot validate a replenishment recommendation. The current menu is repeated until superseded; changes are assumed known at least four weeks ahead. |
| Demand | Daily `forecast_portions` by location, date and dish | Confirmed target format. The demo repeats supplied CW36 values for six weeks, clearly labelled as dummy data; real runs replace them with the maintained plan. |
| BOM quantity | `forecast_portions × grams_per_portion` | Confirmed calculation. Shared items are aggregated before rounding. |
| Pod lead time | `28 calendar days` | Confirmed. |
| Ordinary TK/Kuehl/RT lead time | `3 days` (stored as calendar days in V1) | Confirmed in the Q1-Q13 response for current Transgourmet ordering. |
| Fresh lead time | `5 days` (stored as calendar days in V1) | Confirmed in the Q1-Q13 response. Actual order cut-off and availability event remain open. |
| Pod shelf life | `365 days from order date` | V1 approximation until lot production/expiry is available. |
| Fresh shelf life | `3 days from receipt`; current fresh max cover also `3 days` | V1 approximation. Confirm whether sealed/opened shelf life differs. |
| Other shelf-life/max-cover | Blank; no cap applied unless approved | V1 approximation. Blank does not mean infinite shelf life. |
| Pod pack/order conversion | `1,000 g` inner pack; `5` packs per carton; proposed order unit `CARTON` | Pack metadata confirmed; Transgourmet order article/unit still requires confirmation. |
| Ordinary order conversion | One consumption pack per order unit (`packs_per_order_unit=1`, order unit `PACK`) | Demo default; confirm item exceptions. |
| Fresh service windows | Saturday delivery covers Monday; Monday covers Tuesday+Wednesday; Wednesday covers Thursday+Friday; Friday covers Saturday | Confirmed baseline. Cut-off, receipt time and holidays remain open. |
| Review period used in template | `2, 2, 2, 1` days for the four fresh windows above | V1 approximation derived from the covered service days; confirm this interpretation. |
| Stocked-item review period | `7 calendar days` for pods and ordinary TK/Kuehl/RT | V1 improvement proposal. This represents the weekly main planning cycle; confirm whether the Monday recheck is also a normal reorder opportunity. |
| Safety stock | Pods `7` days; ordinary TK/Kuehl/RT `2` days; fresh `0.5` day | V1 improvement proposal. The stocked values preserve roughly a 20% extra-demand buffer against the proposed `lead + 7-day review` protection horizon. Fresh uses a smaller absolute time buffer because of its short MHD and is still increased by final pack rounding. Approve or correct by item/class. |
| Safety-stock calculation | `average dated demand over the protection horizon × safety days` | V1 improvement proposal. Safety is added to the target before stock/PO netting; it is not hidden inside recipe grams. |
| Yield factor | `1.00` unless an item-specific production loss is known | V1 improvement proposal. Yield represents deterministic cooking/handling loss only; it is not the OOS buffer. |
| MOQ | `0 order units` | Demo default meaning no MOQ. Fill actual values in the master template. |
| Case multiple | `1 order unit` | Demo default meaning no additional case rounding. Fill actual values in the master template. |
| Stock timestamp | Apicbase export timestamp is the latest-known `counted_at` | V1 approximation confirmed for the file-based process. |
| Stock quantity | Interpreted according to each item's `stock_qty_unit` | Open. Confirm whether `Current Stock (qty)` is packs/order units and how partial packs are represented. |
| PO status | Missing/future `Liefertag` is open; today/past is closed/received | Confirmed interim Transgourmet rule. |
| PO without delivery date | Kept in an undated-open review file and excluded from dated netting | Confirmed safe behavior; no receipt date is invented. |
| PO remaining quantity | PDF ordered quantity is temporarily copied to open quantity | V1 approximation because PDFs lack partial receipt/cancellation status. |
| PO receipt time | Delivery date is represented as `00:00 Europe/Berlin`; receipts are available before that day's demand | Technical V1 approximation. Confirm actual availability time if it affects ordering. |
| Rounding | Keep grams unrounded through BOM aggregation; round only at final pack/MOQ/case conversion | Improved V1 rule. Confirm preferred whole-unit rounding for each order unit. |
| Pod estimated expiry record | `order_date + 365 days` | V1 approximation retained for future shelf-life checks; not lot-level FEFO. |

## How the old Excel factors are replaced

The old profile remains available for workbook comparison. The improved V1
does not simply delete its protection against shortages; it makes each part
explicit and auditable:

| Old workbook rule | Improved V1 replacement | Why this is safer/clearer |
|---|---|---|
| Every daily requirement multiplied by `1.20` | Base recipe demand remains exact. Separate safety stock starts at `7` days for pods, `2` days for ordinary stocked items and `0.5` day for fresh. `yield_factor` stays `1.00` unless real production loss is known. | Retains a conservative buffer intended to reduce OOS risk without pretending forecast uncertainty is ingredient loss. The policy can differ by shelf life and item. |
| Fixed `6-day` coverage for every stocked item | Protection horizon is item-specific: `lead time + next review opportunity`; fresh uses the actual service days covered by each delivery. Initial examples are pods `28 + 7 = 35` days and ordinary stocked items `3 + 7 = 10` days. | A six-day target is too short for pods and may be too long for fresh. The new window matches when replacement stock can actually arrive. |
| `previous-week daily packs × 2.5` stock bridge | Project the timestamped Apicbase stock day by day through the dated demand plan and add dated open POs once on receipt. | Uses the real count time and planned consumption instead of an unexplained global bridge. A pre-arrival stockout becomes a visible exception. |
| Ceiling each line to a whole pack | Aggregate the same item across all dishes in grams, then apply shelf/max-cover, MOQ and final pack/carton rounding once. | Prevents avoidable over-ordering from early line-level rounding while still producing purchasable whole units. |

For stocked items the initial safety recommendations preserve approximately the
old 20% extra-demand buffer: `7 / 35 = 20%` for pods and `2 / 10 = 20%` for
ordinary items. Fresh starts lower because its MHD is short. These are labelled
improvement proposals for approval, not measured optimums.

The order logic is therefore:

1. Calculate dated base demand across the protection horizon.
2. Calculate and add explicit safety stock.
3. Project current usable stock and open POs through the same dates.
4. Net supply from the target and expose any shortage before the earliest
   possible receipt.
5. Apply shelf/max-cover, MOQ and final pack/carton rounding, with exceptions
   for every binding or inflating rule.

## Template and rule questions for the maintainer

Please answer only these points and update the highlighted fields in the two
templates where applicable:

1. **Template usability:** can you maintain the proposed `Items`, `Locations`,
   `Delivery_Rules`, `Demand_Plan`, `Menu_Calendar`, and `BOM_Lines` tabs with
   stable IDs and row-1 headers? What specific field or workflow should change?
2. **Pod ordering:** for every pod, which article and exact description appear
   in Transgourmet, is one order unit the `5 × 1 kg` carton, and what are the
   MOQ/case multiples?
3. **Shelf life and cover:** approve or correct pod `365 days from order`, fresh
   `3 days from receipt`, and any max-cover limits for other items.
4. **Stock units:** for each active item, what does Apicbase `Current Stock
   (qty)` count, and are usable partial/open packs included?
5. **Mappings/conversions:** resolve article `350570`, confirm the chickpea
   litre-to-gram/order conversion, and correct any highlighted Apicbase name or
   UID mapping.
6. **MOQ/case/capacity:** fill actual MOQ, case multiple, order-unit conversion,
   and any hard storage-capacity/max-cover constraint in the master template.
7. **Safety and review proposal:** approve or correct pod `7`, ordinary stocked
   `2` and fresh `0.5` safety days, plus the proposed `7-day` stocked review
   period. Confirm whether the Monday recheck permits a normal reorder. Keep
   `yield_factor=1.00` unless a known item-specific loss should be entered.
8. **Fresh timing:** confirm order cut-offs and when each delivery is usable.
    The four delivery-to-service windows themselves are already recorded as
    confirmed.

## V1 completion and later work

This is the single authoritative V1 implementation checklist. Calculation
stages 6-9 map into work package 4 and stage 10 into work package 5; they are
not extra or alternative steps:

1. **Template readers:** read and validate the two fixed template schemas.
2. **Stock normalizer:** convert the Apicbase stock-report XLSX into timestamped,
   location-aware canonical rows plus mapping exceptions.
3. **PO mappings:** apply reviewed item/location mappings to the existing
   Transgourmet PDF importer.
4. **Recommendation engine:** implement protection horizon (`lead + review`),
   explicit safety stock and yield, dated stock/PO netting, fresh-window
   scheduling, shelf/max-cover, MOQ/case and order-unit rounding. Preserve every
   derivation and exception.
5. **End-to-end acceptance run:** use both templates, one stock export and the
   PO PDFs to generate recommendations, derivations, exceptions and a
   deterministic audit; reconcile and review the result.

**Implementation result:** all five work packages are complete. The local
scenario run `improved-67fb3838775f` used the two templates, the PREP-CGN stock
export timestamped `2026-08-26T17:10:00+02:00`, and cumulative Transgourmet
PDFs. It produced 16 item projections, 39 derivation lines, 23 dated
recommendations across 11 items, 103 proposed order units, and zero blockers.
Seven shareable output files were byte-identical on immediate replay and 44
repository tests pass.

The result is deliberately labelled demo-only. Four required items used an
explicit scenario-zero stock row because no reviewed Apicbase mapping existed;
seven open Transgourmet lines were quarantined because no reviewed item mapping
existed. The three pod pre-arrival shortages and four fresh pack/max-cover
conflicts remain visible exceptions, not hidden calculation failures.

This completes the **local technical V1 milestone**. The next milestone is the
maintainer upload UI using the same schemas, and UI planning/building may start
now. The maintainer must still return approved/corrected templates and policy/
mapping answers before any scenario result is called operational or used for
shadow/production decisions. After feedback, rerun and require zero blockers.
The 2026-08-28 repository foundation now supplies the API/web/deployment seams
and a temporary Supabase master/run schema, but deliberately adds no second
calculation path and does not change this approval gate.
Still later/pending are:

- Phase 1 forecast logic and its accepted daily forecast source;
- Snowflake result persistence and future accepted operational tables;
- Supabase or the agreed editable master/rule store; and
- APIs for Transgourmet PO history and current stock, replacing manual exports.
