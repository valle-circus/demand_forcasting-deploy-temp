# Phase 2 supply planning — maintainer guide

Use this guide to understand what the tool calculates, how to interpret the UI,
and which values in the templates influence the result. The companion
[template quick-start](template_quick_start_for_maintainers.md) explains how to
complete and upload the two templates.

## 1. What the tool does

The tool converts the daily dish plan into an explainable purchase proposal for
each kitchen. It combines:

- expected portions by day and dish;
- the recipe/BOM in grams per portion;
- the latest usable stock count;
- purchase orders already on the way; and
- maintained planning rules such as lead time, safety stock, shelf life, MOQ
  and case size.

It then shows what is covered, what is at risk, and what could be ordered.

The result is a **proposal for review**. The tool does not approve, place or
send an order, and it does not write to an ERP. A user must still check the
proposal and place any order in the normal ordering channel.

The source APIs are not connected yet, so the current version uses controlled
Excel and PDF uploads. The system validates and converts them internally into
structured rows. Users do not maintain side CSV files. APIs can later replace
the uploads without changing the calculation.

## 2. KPI versus planning parameter

These two types of values should not be confused:

- A **KPI or status** tells you what the current data or calculation says, for
  example “Kitchens ready” or “At risk”.
- A **planning parameter** changes the calculation, for example lead time,
  safety days or shelf life.

A kitchen can be **ready** because all required inputs exist and still need a
purchase proposal. Ready means “the tool can calculate”, not “nothing needs to
be ordered”.

## 3. The four input groups

| Order | Input | Scope | Purpose |
|---|---|---|---|
| 1 | Master data & rules workbook | Uploaded once for all locations | Shared items and policies, locations, and location-specific delivery rules |
| 2 | Forecast, menu & BOM workbook | Uploaded once; forecast/menu rows contain `location_id` | Daily portions, active menu and the shared Dish → Silo/Pre-Mix → Item BOM |
| 3 | Apicbase stock XLSX | One selected location | Latest usable stock opening balance |
| 4 | Transgourmet PDFs | One selected location; one or more cumulative PDFs | Observed purchase orders already in transit |

The master and planning workbooks are global uploads. Stock and supplier PDFs
are uploaded after selecting a location. Uploading or activating data does not
automatically run planning.

## 4. How the calculation works

### Step 1 — Convert dishes into ingredient demand

For every location and service date, the tool calculates:

`ingredient demand = forecast portions × grams per portion`

It follows the complete **Dish → Silo/Pre-Mix → purchasable item** path. If the
same ingredient is used by several dishes, all grams are added together before
any pack or carton rounding. This avoids rounding every recipe line separately
and over-ordering.

### Step 2 — Determine the protection window

The tool does not use one fixed horizon for every item.

- For stocked items, the normal window is **lead time + review period**. It
  covers the time until an order placed now can arrive and the next normal
  planning review can react.
- Fresh items use the actual service dates covered by the relevant delivery,
  rather than an average day multiplied by a number of days.

Current starting examples are a 35-day window for pods (`28` days lead + `7`
days review) and a 10-day window for ordinary stocked items (`3 + 7`). These
values depend on the maintained rules.

### Step 3 — Add explicit protection

The target contains two separate elements:

- **Yield factor:** only a known, deterministic cooking or handling loss.
- **Safety stock:** an explicit shortage buffer calculated as average dated
  demand in the protection window × maintained safety days.

The old blanket `×1.20` is not applied to every recipe line. Base recipe demand
stays exact, safety is visible, and yield remains `1.00` unless a real loss is
known.

### Step 4 — Project stock and incoming orders through time

The tool starts with the latest usable stock and consumes it against the dated
demand. Accepted open POs are added once on their expected receipt dates.

This matters because having enough stock in total is not sufficient if it runs
out before the next delivery can arrive. A shortage before the earliest
possible receipt is shown as **Too late to fix** instead of being hidden by an
impossible proposal.

### Step 5 — Calculate and constrain the proposal

In simplified form:

`raw need = max(0, adjusted demand + safety stock − usable stock − relevant open POs)`

The engine then applies the rules in this fixed order:

1. floor at zero;
2. shelf-life cap;
3. maximum-cover cap;
4. minimum order quantity (MOQ); and
5. final pack/carton or case-multiple rounding.

The final output is a purchasable order-unit proposal. A cap that reduces the
quantity or an MOQ/case rule that increases it produces a visible explanation
or exception.

## 5. How to interpret Data & settings

The four cards are a required sequence. The planning workbook is validated
against the active master; stock is validated against the planning item set for
the selected location.

| UI value | Meaning |
|---|---|
| **Accepted** | The file passed validation and can be used. |
| **Accepted with warnings** | The file can be used, but review evidence, defaults or mappings remain visible. |
| **Rejected** | The file is not usable. Follow the file/sheet/row/field remedy shown by the UI. |
| **Draft master version** | Validated but not yet active. It changes no run until activated. |
| **Source time / Counted** | When the source was true, for example the Apicbase count/export time. |
| **Imported time** | When the file was uploaded. This is not the same as source freshness. |

Stock and observed PO lines are corrected in their source or in the maintained
item mapping and then re-imported. They are not edited line by line in the UI.

When provenance is shown, **Measured** means observed source data, **Entered by
hand** means a maintained manual value, **Policy default** means a configured
proposal/default, **Known empty** means the source explicitly contains no
records, and **Unavailable** means the source is not known. Known empty and
unavailable must not be interpreted as the same thing.

## 6. How to interpret Overview

Overview is an exception cockpit across all kitchens. It tells you where to go
next; the detailed quantities remain on the location page.

| KPI or status | What it means | What to do |
|---|---|---|
| **Kitchens ready** | Required accepted inputs are present and the location can be calculated. It does not mean no proposal is needed. | Calculate or open the location. |
| **Kitchens needing an order** | A latest current result contains at least one ingredient still classified at risk inside its protection window. This is a risk count, not the number of proposal rows. | Open the location and inspect the risk and proposal. |
| **Ingredients needing an order** | Count of location/ingredient risks inside the current protection window in latest current results. A proposal may exist even when this value is zero. | Use the Proposals tab for the actual list of proposed lines. |
| **Not fully checked** | The available forecast/evidence stops before the end of an item's protection window. This is unknown, not covered. | Extend/correct the planning horizon and calculate again. |
| **Blocking issues** | A required input, mapping, rule or run condition prevents a trustworthy result. | Follow the displayed remedy in Data & settings or the location page. |
| **Out of date** | Newer accepted data exists than the data used by the displayed run. | Recalculate before acting. |
| **Never run** | Inputs may exist, but this location has no result yet. | Open the location and compute a recommendation. |

The location table also shows the first shortage date, when stock was counted,
and when the last result was calculated. **Not known**, a dash, and zero have
different meanings. If there is no current run, the UI deliberately avoids
showing zero risk because no current calculation established that.

An Overview “All clear” means there is no remaining blocker or risk in the
latest current result. It does not mean the Proposals tab is necessarily empty.
Use Overview for remaining cross-kitchen risk, Risk & stock for items that
depend on a proposal, and Proposals for the actual quantities to review.

## 7. How to interpret Location planning

### Freshness and run status

Before looking at quantities, check:

- selected location;
- stock counted time;
- PO import/source time;
- forecast-through date;
- active master version; and
- whether the result is current or out of date.

**Compute latest recommendation** uses the currently accepted versions. If an
input is missing or invalid, the button is blocked and the UI explains what to
fix.

### Risk & stock tab

The status describes whether current stock and accepted POs cover this item's
protection window and whether the proposal solves the gap.

| Value or status | Interpretation |
|---|---|
| **In stock** | Usable opening stock after conversion into grams. |
| **To protect** | Gross dated demand this decision must cover; it is not the entire uploaded forecast. |
| **On order** | Mapped open PO quantity due inside the relevant calculation. |
| **Covered through** | End of the item-specific lead + review/delivery window, or the first shortage inside it. |
| **At risk** | Stock plus already accepted POs run short inside the window unless the proposal is placed. |
| **Order not enough** | The item is still short inside the window even after applying the proposal. |
| **Too late to fix** | The shortage occurs before any order placed now could arrive. A manual operational decision is required. |
| **Not enough data** | The evidence ends before the whole window can be checked. It must not be read as covered. |
| **Covered** | The item is covered through this decision window. A later forecast shortage is expected to be handled by a later review. |

Expanding an item shows the daily stock projection. Negative displayed balance
in the underlying projection represents unmet demand/backlog, not physical
negative stock.

### “How long supply lasts” chart

The horizontal bars show continuous coverage against real dated demand:

- **In stock:** days covered using usable stock only.
- **On order:** extra continuous days added by accepted open POs.
- **Proposal — not ordered:** extra days if the current proposal were placed.
- **Needs to cover:** the item-specific protection target.

A day counts as covered only when all demand that day can be served. A delivery
arriving after an earlier stockout does not repair the gap before it.

- **At least / ≥ N days** means the uploaded forecast ended before the supply
  ran out, so N is a lower bound.
- **Not measurable** for an added layer means the preceding supply already
  covers the whole uploaded forecast; it does not mean the PO or proposal adds
  nothing.

The chart measures demand coverage. Without lot-level expiry data, it is not
proof that every existing stock or PO lot remains usable for all those days.

### On order tab

These rows come from imported Transgourmet PDFs, not a live supplier portal.
They can therefore become outdated if an order is cancelled, partially
received or rescheduled without a newer PDF upload.

- A future `Liefertag` is treated as open.
- Today/past is treated as closed/received in the current file adapter.
- A line without a delivery date stays visible for review but is excluded from
  dated netting; no receipt date is invented.
- **No match** means the supplier line could not be linked safely to a master
  item and will not silently influence the calculation.

### Proposals tab and calculation drawer

The tab lists one proposal per item/date with:

- **Order on:** proposed order date;
- **Expected:** expected delivery/availability date;
- **Supplier:** supplier or ordering-channel identifier; and
- **Order units:** number of purchasable packs/cartons according to the item
  master.

The number of proposal rows is not the same as the sum of order units. Order
units from different items should not be added together unless their unit is
the same and the total is meaningful.

Select an item to see the stored derivation:

1. gross requirement;
2. yield factor and adjusted requirement;
3. safety stock;
4. usable on hand;
5. open POs due;
6. raw order;
7. shelf-life and max-cover caps;
8. MOQ and case multiple; and
9. final proposed order units.

Constraint messages mean:

- **Safe to order:** the proposed purchasable quantity fits the maintained
  rules.
- **Reduced to a safe amount:** a hard cap forced a smaller purchasable amount.
- **No safe order possible:** no positive purchasable quantity fits below the
  cap; the tool intentionally makes no proposal and requires a manual decision.

Shelf-life fields show an estimated candidate expiry and any amount projected
to remain at expiry. **Estimated from policy** is not the MHD printed on the
goods. If the forecast does not reach the estimated expiry, the shelf-life
check is incomplete.

## 8. The template values that most influence the result

These are planning parameters, not measured KPIs. Review their source/status in
the templates before using the output operationally.

| Template value | Why it matters | Current V1 starting point | Status |
|---|---|---|---|
| `storage_class` | Selects stocked or fresh planning behaviour | `TK`, `Kuehl`, `RT`, `Frisch` | Confirm per item |
| `lead_time_calendar_days` | Controls earliest receipt and protection window | Pods 28; ordinary 3; fresh 5 | Confirmed starting durations; timing details may still need correction |
| `review_period_days` | Extends protection until the next planning opportunity | Stocked items 7; fresh windows derived from delivery coverage | Starting proposal — approve/correct |
| `min_safety_days` | Adds explicit shortage protection | Pods 7; ordinary 2; fresh 0.5 | Starting proposal — approve/correct |
| `yield_factor` | Applies known deterministic loss | `1.00` unless a real loss is known | Starting proposal — approve/correct by exception |
| `shelf_life_days` and anchor | Caps what can be consumed before estimated expiry | Pods 365 days from order; fresh about 3 days from receipt | Approximation — not lot-level MHD |
| `max_cover_days` | Optional hard cap on total future cover | Fresh currently 3; others blank unless approved | Approve/correct; blank is not proof of unlimited life/capacity |
| `pack_size_g` and `packs_per_order_unit` | Convert grams into stock packs and supplier order units | Pods use 1 kg inner packs and five packs/carton in the current setup | Confirm supplier article and actual order unit |
| `stock_qty_unit` | Converts Apicbase `Current Stock (qty)` correctly | `PACK` or `ORDER_UNIT` per item | Must be confirmed, including partial packs |
| `moq_order_units` | Can increase a small need to a supplier minimum | Demo default `0` | Fill actual MOQ before operational use |
| `case_multiple_order_units` | Rounds the result to a purchasable multiple | Demo default `1` | Fill actual case multiple before operational use |
| `forecast_portions` | Drives base demand by location/date/dish | Daily numeric value | Replace demo data with the maintained forecast |
| `grams_per_portion` | Converts one dish into exact item demand | Effective BOM value | Confirm recipe and effective dates |

The planning workbook must cover the longest active protection window. With
the current pod starting rule, forecast and menu evidence should reach at least
35 calendar days from the planning date. Every demand row needs a matching
active menu row and effective BOM.

Two control fields explain how much trust to place in a maintained value:

- `data_status` records its review state. `SOURCE_VALUE` comes from supplied
  evidence; `OWNER_APPROXIMATION` contains an owner-provided approximation;
  `DEMO_DEFAULT_REVIEW` is only a runnable demo value; `NEEDS_REVIEW` is missing
  or unconfirmed; and `AMBIGUOUS_ARTICLE_REVIEW` requires supplier-article
  resolution.
- `source_note` should state where a value came from or what still needs to be
  confirmed. Do not remove a review status without resolving the note.

## 9. What users must validate before operational use

- Item, supplier, Apicbase and PO mappings are correct.
- Pack, stock and order units are correct, including partial packs.
- Lead times, review cadence and delivery timing reflect the real process.
- Safety days, shelf life, max cover, MOQ and case multiples are approved.
- The forecast/menu reaches the longest required protection window.
- Stock and PO sources are current and warnings/unmatched lines are resolved.
- The displayed result is current, not based on replaced inputs.

Until these points are approved, the result remains a labelled scenario or
prototype proposal. Use it for comparison and feedback, not as an automatically
approved order.

## 10. A simple first test

1. Complete the two templates using the companion quick-start.
2. Upload and activate the master workbook.
3. Upload the planning workbook.
4. Select one location and upload its current stock and cumulative PO PDFs.
5. Resolve validation blockers and calculate the location.
6. Compare a few proposal lines with the manual process by opening their
   calculation drawers.
7. Record corrections to mappings, units and policy values in the templates,
   re-upload, and calculate again.

The goal of the first test is not to accept every proposed quantity. It is to
confirm that the inputs, assumptions, calculation explanation and exceptions
match how the maintainer actually plans supply.
