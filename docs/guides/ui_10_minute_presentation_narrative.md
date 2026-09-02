# Phase 2 supply planning — 10-minute user presentation

## The one message to repeat

> The tool turns the daily dish plan, recipes, usable stock and already ordered
> supply into an explainable purchase recommendation for each kitchen. It does
> not place or approve an order.

The user still reviews the proposal. The improvement is that the repetitive
calculation is consistent, dated and traceable instead of being rebuilt
manually in Excel.

## 0:00–1:00 — Set the context

Suggested wording:

> Today the source APIs are not connected, so this first version uses controlled
> file uploads. The user uploads Excel workbooks and supplier PDFs; the system
> validates them and converts them internally into structured table/CSV rows.
> Users do not have to maintain side CSV files. Later, APIs can replace each
> upload without changing the planning logic.

Also state the boundary clearly: the result is an internal proposal. There is
no automatic supplier order, ERP write or approval workflow.

## 1:00–4:00 — Data & settings: the four inputs

Present the upload cards in their numbered order. Uploading validates and saves
an input version; it does not run the calculation.

| Step | Input | Scope | Main point to explain |
|---|---|---|---|
| 1 | **Master data & rules** | One global workbook | Contains shared items and item rules, the list of locations, and location-specific delivery rules. A new upload is a draft and must be activated. |
| 2 | **Forecast, menu & BOM** | One global workbook | `Demand_Plan` and `Menu_Calendar` contain `location_id` on every row. `BOM_Lines` is shared unless a recipe genuinely differs. Do not upload one planning workbook after another for separate locations. |
| 3 | **Current stock** | One Apicbase XLSX per selected location | The stock count is the opening balance. Its source time is the count/export time, not the upload time. |
| 4 | **Purchase-order PDFs** | One or more cumulative Transgourmet PDFs per selected location | These are observed orders already in transit and must be netted before proposing more. The “documents seen as of” time determines which lines still count as open. |

This scope distinction is worth saying twice: **the master and planning
workbooks are uploaded once; stock and PO files are uploaded after selecting a
location.** The planning workbook is global as a file but location-specific by
row.

### The important planning parameters

Shelf life and lead time are planning parameters, not KPIs. Explain the small
set that materially changes a recommendation:

| Parameter | Meaning in the calculation | Current V1 starting point |
|---|---|---|
| `storage_class` | Selects stocked-item or fresh-delivery behaviour | `TK`, `Kuehl`, `RT`, `Frisch` |
| `lead_time_calendar_days` | Earliest time replacement stock can be available | Pods 28 days; ordinary stocked items 3; fresh 5 |
| `review_period_days` | Time until the next normal planning opportunity | Stocked-item proposal: 7 days; fresh follows its delivery window |
| `min_safety_days` | Explicit shortage buffer, calculated separately from recipe demand | Proposal: pods 7; ordinary 2; fresh 0.5 |
| `yield_factor` | Known deterministic cooking/handling loss | `1.00` unless a real item loss is known; it is not the safety buffer |
| `shelf_life_days` | Limits how much of a new candidate delivery can reasonably be used before estimated expiry | Pods: 365 days from order date as an approximation; fresh: about 3 days from receipt; others blank unless approved |
| `max_cover_days` | Optional hard limit on how much future demand one order may cover | Only fill when an approved cap exists |
| Pack, order unit, MOQ and case multiple | Convert grams into something that can actually be purchased | Must match the supplier article and ordering unit |

These starting values are visible assumptions for user validation, not claimed
optima. The old blanket `×1.20` buffer is not reused: recipe demand stays exact,
safety stock is explicit, and `yield_factor` is reserved for real deterministic
loss.

## 4:00–6:00 — Explain the calculation in seven sentences

1. Read expected portions for each **location, service date and dish**.
2. Multiply portions by the effective **Dish → Silo → Item** grams per portion.
3. Aggregate the same purchased item across all dishes before any pack or
   carton rounding.
4. Project the latest usable stock day by day and add accepted open POs once on
   their expected receipt dates.
5. Calculate what must be protected until stock can arrive and planning can be
   reviewed again: normally **lead time + review period**; fresh items use the
   actual service days covered by each delivery.
6. Add explicit safety stock, net usable stock and due POs, then apply the rules
   in order: zero floor, shelf-life cap, max-cover cap, MOQ, and final
   pack/carton rounding.
7. Return a dated proposal plus the derivation and any exception, so the user
   can see why the number exists.

Useful nuance: shelf life does not reduce demand. It can cap a proposed receipt
and raise a visible warning. A shortage before the earliest possible receipt is
also shown; the tool does not hide it by creating an impossible order date.

For imported Transgourmet PDFs, a future `Liefertag` is treated as open,
today/past as closed, and a missing date is quarantined instead of inventing a
receipt date.

## 6:00–8:30 — Location planning page

Choose one location and walk from top to bottom:

1. **Freshness strip:** point out stock counted time, PO import time,
   forecast-through date, active master version and last calculation. A result
   based on replaced inputs is shown as out of date.
2. **Compute latest recommendation:** this performs the pre-check and uses the
   currently accepted input versions. A blocker explains which file, row or
   field must be corrected.
3. **Risk & stock:** focus on items that are short inside their own protection
   window. “Future replan expected” means a later planning cycle should handle
   a later shortage; it is not automatically an order needed now.
4. **How long supply lasts:** explain the three layers as current usable stock,
   accepted open POs, and the additional coverage if the proposal were placed.
   The last layer is still **proposal — not ordered**.
5. **Open POs:** these are observations from imported PDFs, not live supplier
   confirmation. Mapping or missing-date issues remain visible.
6. **Recommendation:** show order date, expected receipt, supplier/channel,
   purchasable units and warnings. Open one explanation drawer to show demand,
   safety, stock, POs, caps, MOQ and rounding behind the final number.

Do not describe an estimated shelf-life result as exact MHD. Existing stock and
open POs do not yet have lot-level expiry evidence.

## 8:30–9:30 — Overview page

Present Overview as the cross-kitchen exception cockpit, not another detailed
calculation screen. It answers three questions:

- Which kitchens are ready to calculate?
- Which kitchens or ingredients need attention inside the current order
  window?
- Is the problem missing/stale data, a calculation blocker, or a genuine
  replenishment risk?

Briefly point to the cards for kitchens ready, kitchens needing an order,
ingredients needing an order, items not fully checked, and blocking issues.
“Not fully checked” means the uploaded evidence did not reach the end of that
item's protection window; it is not the same as a confirmed all-clear.
Then show the location table: status, first shortage, stock count age and last
calculation. A blank or “not known” is deliberately not presented as zero.

## 9:30–10:00 — Close and request feedback

Suggested wording:

> The calculation path is working and explainable. What we need from you is not
> to rebuild the formula, but to validate the maintained facts and rules: item
> mappings and units, lead/review timing, safety days, shelf life, MOQ/case
> multiples and delivery rules. Once those are approved and the source files
> pass validation, we can compare the proposals with the manual process before
> any operational use.

Ask whether the templates are practical to maintain and which highlighted
assumptions or mappings must be corrected. Avoid promising live APIs, exact
lot-level MHD, or automatic ordering in this version.

## Thirty-second fallback version

> We upload one shared master workbook, one planning workbook containing all
> location rows, and then stock and PO files per selected location. The tool
> converts daily dish demand through the BOM into ingredient demand, projects
> stock and incoming POs through time, protects the item-specific lead/review
> window, and applies shelf-life, cover, MOQ and rounding rules. The result is
> an explainable recommendation and exceptions—not a placed order. The user’s
> main job is to keep the inputs current and approve or correct the visible
> planning assumptions.
