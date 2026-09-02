# Phase 2 templates — quick start for maintainers

This is the file-completion companion to the
[maintainer logic and UI guide](tool_logic_and_ui_guide_for_maintainers.md),
which explains the calculation, the important UI KPIs and how to interpret the
result.

## What to provide

The current file-based process uses four upload groups:

| Order | File | Scope |
|---|---|---|
| 1 | `Phase2_Master_Data_Template_v1.xlsx` | One workbook for all locations |
| 2 | `Phase2_Planning_Input_Template_v1.xlsx` | One workbook containing all location rows |
| 3 | Current Apicbase `Stock Report` XLSX | One export for the location selected in the UI |
| 4 | Cumulative Transgourmet `Bestelldetails` PDFs | One or more PDFs for the location selected in the UI |

The source APIs are not connected yet. These files are therefore the controlled
input bridge. The system creates the internal table/CSV rows automatically; do
not create or maintain side CSV files.

## Rules for both project templates

- Use the current template files. Do not rename tabs, row-1 headers or columns,
  and do not change their order.
- Keep IDs stable. `location_id`, `dish_id`, `silo_id` and `item_id` are join
  keys; names are only for display and matching.
- Enter dates as real Excel dates, quantities as numbers and flags as
  `TRUE`/`FALSE`. Use the supplied drop-down values.
- Use `active=FALSE` instead of deleting a previously used ID.
- Do not guess. Mark values with the appropriate review status and explain the
  source or uncertainty in `source_note`.
- Use the `Data_Dictionary` tab for exact field meanings and `Lists` for allowed
  values.
- Keep row 1 as the header and enter one record per row below it. Do not add
  formulas, merged cells or free-text sections to machine-read tabs.

## 1. Master data & rules workbook

### `Items` — one global row per purchasable item

Do not duplicate an item for each location. Review these groups carefully:

| Field group | What to maintain |
|---|---|
| Identity and mapping | Stable `item_id`, display name, pod/ingredient type, official supplier, ordering channel, supplier article/description, and Apicbase UID or exact stock name |
| Units | `pack_size_g`, packs per order unit, `PACK` or `CARTON`, and what one Apicbase stock quantity represents |
| Planning rules | Storage class, lead time, shelf life and its anchor, safety days, yield factor, optional max cover, MOQ and case multiple |
| Control fields | `active`, `data_status` and a short `source_note` |

Important distinctions:

- `official_supplier` and `ordering_channel` are different. Circus pods can be
  supplied by Circus and ordered through Transgourmet.
- `min_safety_days` is the shortage buffer. `yield_factor` is only for a known
  deterministic production/handling loss.
- Blank `max_cover_days` or shelf life means no approved cap is applied; it
  should not be interpreted as evidence of unlimited storage life.
- Confirm the true supplier order unit, MOQ and case multiple before using a
  recommendation operationally.

### `Locations` — one row per planning location

Maintain a stable location ID, readable name, IANA timezone such as
`Europe/Berlin`, active flag, review status and mapping note.

### `Delivery_Rules` — location-specific rules

Maintain the location, ordering channel, storage class, delivery weekday,
service days covered, review period and effective dates. Add order cut-off and
receipt-availability time when confirmed.

The current fresh baseline is:

- Saturday delivery → Monday service;
- Monday → Tuesday and Wednesday;
- Wednesday → Thursday and Friday;
- Friday → Saturday.

## 2. Forecast, menu & BOM workbook

This workbook is uploaded once. Location separation is by `location_id` in the
rows, not by separate files or tabs.

| Tab | One row represents | What to maintain |
|---|---|---|
| `Demand_Plan` | location × service date × dish × forecast version | Expected `forecast_portions` for each service day and dish |
| `Menu_Calendar` | location × service date × dish × menu version | Whether the dish is active at that location on that date |
| `BOM_Lines` | effective dish × silo × purchasable item | Exact `grams_per_portion`, including the Dish → Silo/Pre-Mix → Item path |

Every demand row must have a matching active menu row and an effective BOM for
that dish/date. The BOM is shared across locations unless the recipe genuinely
differs.

Provide dated forecast/menu coverage through the longest active protection
window. With the current pod proposal, this is at least **35 calendar days**
from the planning date (`28` days lead time + `7` days until review). Do not
encode a weekly average in place of daily rows.

## 3. Stock and 4. purchase-order files

- Export a fresh Apicbase `Stock Report` for the selected location; do not
  manually rewrite its lines. The count/export time becomes the stock source
  time.
- Upload all relevant cumulative Transgourmet PDFs for the same selected
  location and set **Documents seen as of** correctly.
- Correct stock or PO problems in the source file or maintained item mapping,
  then re-import. Do not edit observed stock or PO lines in the UI.

## Upload and check

1. Upload the master workbook, review validation, and **activate** the accepted
   draft.
2. Upload the planning workbook and resolve any unknown location, item, menu or
   BOM errors.
3. Select a location and upload its current stock export.
4. For the same location, upload the cumulative PO PDFs with the correct as-of
   time.
5. Repeat steps 3–4 for each additional location.
6. Go to **Location planning**, confirm the displayed source versions and
   freshness, then compute the recommendation.

Uploading a file never places an order and does not automatically run the
calculation.

## Before returning the templates

- [ ] No tabs, headers or column order were changed.
- [ ] Stable IDs are present and consistent across tabs.
- [ ] Every demand row has matching menu and BOM coverage.
- [ ] Forecast/menu dates cover the longest lead + review window.
- [ ] Pack, stock and order units have been confirmed.
- [ ] Lead time, safety, shelf-life/max-cover, MOQ, case and delivery rules were
      approved or clearly marked for review.
- [ ] `source_note` explains manual values, assumptions and unresolved fields.
- [ ] Demo or placeholder rows are removed or remain visibly labelled as
      non-operational.
