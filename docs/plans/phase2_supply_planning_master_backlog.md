# Phase 2 Supply Planning — Master Backlog

**Created:** 2026-08-22

**Rebased:** 2026-08-27 for the template-first local V1

**Source of truth:** this file controls priority and milestone status.

**Active implementation checklist:**
`docs/plans/v1_template_first_delivery_plan.md`

## Goal and boundary

This repository consumes a daily dish forecast and calculates auditable
ingredient and purchase recommendations:

```text
daily dish demand + dated menu/BOM + item/rule master
                  + current stock + open POs
                                  ↓
       recommendations + derivations + exceptions
```

Phase 1 forecasting is an upstream input and is not implemented here. Supplier
dispatch, ERP writes, and an approval workflow are outside scope.

The pure Python engine remains independent from files, UI, and databases. The
same canonical rows must support local files now, a maintainer UI next, and
Snowflake/Supabase persistence later.

## Active delivery sequence

### Milestone 1 — local template-driven V1

**Outcome:** one selected location can be planned locally from two maintained
templates, one Apicbase stock export, and cumulative Transgourmet PDFs.

- [x] Define canonical daily forecast, menu, three-level BOM, item, stock, PO,
      provenance, and audit contracts.
- [x] Implement three-level BOM explosion, daily aggregation, current-stock
      selection, dated PO projection/netting, source gates, and deterministic
      audit output.
- [x] Implement the interim private Transgourmet PDF importer, including
      content deduplication, total reconciliation, history, dated open rows,
      undated quarantine, and the confirmed `Liefertag` rule.
- [x] Create and prefill the two project-owned Excel templates with the new
      pod/ingredient/menu evidence and a labelled six-week one-location demo.
- [x] Create one maintainer-facing assumptions/parameters/questions brief so
      active values are not hidden in code or spread across documentation.
- [ ] **Operational approval gate:** obtain maintainer review of the templates,
      yellow/ambiguous fields, and
      assumptions brief.
- [x] **Work package 1 — template readers:** implement strict readers for the
      two project-owned workbook schemas.
- [x] **Work package 2 — stock normalizer:** implement the Apicbase stock-report
      XLSX normalizer with upload-selected
      `location_id`, export timestamp as `counted_at`, and UID/exact-name
      mapping review.
- [x] **Work package 3 — PO mappings:** feed the reviewed item/location mapping
      into the Transgourmet importer.
- [x] **Work package 4 — recommendation engine:** finish protection horizons,
      explicit safety/yield, dated netting, fresh scheduling, shelf/max-cover,
      MOQ/case and order-unit logic, with visible derivations/exceptions.
- [x] **Work package 5 — acceptance run and outputs:** emit table-ready
      recommendation, derivation, exception and audit files, then validate the
      complete one-location demonstration.

Detailed steps and exit criteria are in
`docs/plans/v1_template_first_delivery_plan.md`.

### Milestone 2 — maintainer upload UI

**Outcome:** a planner selects a location, uploads the same four inputs, sees
field/mapping errors, and views/downloads the calculated recommendation.

- [ ] Add a thin upload/validation API around the existing normalizers.
- [ ] Add location selection and the four upload inputs.
- [ ] Show actionable field and rejected-mapping errors.
- [ ] Show/download recommendations, derivations, and exceptions.
- [ ] Decide and implement the minimum authentication and retention controls.

**Entry decision:** UI planning and implementation may start. The completed
local scenario contracts are stable. Maintainer feedback is a gate before the
UI can present a run as operational/shadow-approved, not before the upload and
review experience is built.

Do not add supplier dispatch, ERP writes, approval workflow, complex calendar
integration, or optimization in this milestone.

### Milestone 3 — persistence and source automation

**Outcome:** accepted operational sources and run history no longer depend on
local files, without changing engine contracts.

- [ ] Agree Snowflake result schema, write grants, run-history/latest-view
      behavior, and scheduling ownership.
- [ ] Complete least-privilege service-account and `data-transformation`
      access.
- [ ] Persist application-maintained item/rule data in the agreed Supabase or
      master-data store with versions/change history.
- [ ] Write append-only run/recommendation/exception history to Snowflake.
- [ ] Replace manual forecast/menu, stock, and PO inputs individually only when
      an accepted API/table has proven grain, IDs, units, freshness, lineage,
      and ownership.
- [ ] Keep the local file path as fixture/import/recovery support.

### Milestone 4 — shadow validation and scheduling

- [ ] Compare representative improved runs with the maintainer's decisions.
- [ ] Separate calculation differences from missing-source/policy effects.
- [ ] Approve initial rules and operating measures.
- [ ] Schedule idempotent runs with freshness gates, retries, failure logging,
      and a runbook.

## Historical compatibility track — not a Milestone 1 blocker

The KW33/KW34 profile remains regression evidence, not the recurring input
format:

- [x] Reconcile 27/27 filled stocked order cells and 28/28 bridge values.
- [x] Isolate the legacy `1.20`, six-day horizon, and `×2.5` arithmetic.
- [x] Implement compatibility CSV/audit and synthetic tests.
- [ ] Decide whether a sanitized real fixture may be committed or remains
      private.
- [ ] Add the real workbook extraction/golden assertions if that fixture is
      approved.
- [ ] Preserve the four likely missed blanks and fresh-path differences as
      explicit evidence.

Understanding the operational meaning of `×2.5` can improve the historical
walkthrough, but it does not affect the dated template-driven V1 policy.

## Current status

| Area | Status |
|---|---|
| Canonical contracts and validation | Implemented for nine normalized datasets plus table-ready results |
| Project-owned workbook templates | Created and prefilled; maintainer review open |
| BOM explosion and dated stock/PO projection | Implemented |
| Actual purchase recommendation calculation | Implemented and locally accepted in scenario mode |
| Transgourmet PDF normalization | Implemented; unresolved lines are quarantined for maintainer mapping |
| Apicbase stock XLSX normalization | Implemented for the observed standard report; unresolved rows are visible |
| Live Snowflake input dependency for local V1 | None |
| Snowflake result persistence | Later; ownership/schema open |
| Supabase configuration store | Later; not created |
| Maintainer UI | Milestone 2; ready to plan/build, not started |
| Current repository check | 44 passing tests on 2026-08-27; deterministic 7-file replay passed |

## Source of truth for local V1

| Information | V1 source | Location-aware? | Maintainer action |
|---|---|---:|---|
| Items, pods, pack/order mapping, policy fields | `Phase2_Master_Data_Template_v1.xlsx` → `Items` | No | maintain one row per item and resolve review flags |
| Planning locations | master template → `Locations` | Defines locations | maintain stable IDs |
| Delivery/service coverage rules | master template → `Delivery_Rules` | Yes | maintain per applicable location/rule |
| Daily demand | `Phase2_Planning_Input_Template_v1.xlsx` → `Demand_Plan` | Yes | maintain dated portions and version |
| Menu schedule | planning template → `Menu_Calendar` | Yes | maintain dated active dishes/version |
| Dish → silo → item BOM | planning template → `BOM_Lines` | No | maintain effective recipe rows |
| Current usable stock | Apicbase stock-report XLSX | Yes, selected at upload | export current view and choose location |
| Open POs | Transgourmet PDFs | Yes, selected at upload | maintain cumulative PDF folder |
| Recommendations/results | engine-generated CSV/JSON | Yes | no manual input |

The supplied `CW36_*` and pod metadata workbooks are migration evidence only.
The implementation reads the project-owned schema; it does not chase arbitrary
future tab/column changes in those source workbooks.

## Snowflake and Supabase boundary

A complete controlled local V1 needs no current Snowflake runtime table. The
previously investigated forecast/recommendation models and `BASE_INVENTORY` are
abandoned and must not be wired into the run.

Snowflake remains the intended home for an accepted future Phase 1 forecast,
normalized operational inputs when ingestion exists, and append-only Phase 2
run/recommendation history. Supabase (or the agreed editable master store) is a
future home for application-maintained item/rule data. Neither is a reason to
delay the local template-driven milestone.

## Remaining human gates

The authoritative details are in `human_action_register.md`. For Milestone 1,
the short maintainer questions are:

1. pod Transgourmet article/description, ordered unit, MOQ, and case multiple;
2. Apicbase stock quantity unit and partial-pack treatment per active item;
3. resolution of duplicate/ambiguous article `350570`;
4. approval/correction of the proposed seven-day stocked review period plus
   cut-off/receipt fields; ordinary/fresh/pod lead durations remain confirmed
   as 3/5/28 days; and
5. approval/correction of the proposed safety policy (`7` days pods, `2` days
   ordinary stocked, `0.5` day fresh), item-specific yield losses if any, and
   hard max-cover values.

Already decided for the local demo: one selected location, the supplied menu
remains effective until superseded and is repeated across six dated dummy
weeks, stock export time as latest knowledge, 28-calendar-day pod lead,
order-date-plus-365-day pod shelf-life approximation, Transgourmet for pod POs,
and the four fresh service windows.

## Cross-cutting verification

- [x] Multi-dish aggregation and pre-mix/pod preservation.
- [x] Multiple locations and shared ingredients in canonical engine tests.
- [x] Zero forecast, duplicate/orphan/menu/BOM/input validation, and
      deterministic replay.
- [x] Open PO within/after horizon, same-day receipt ordering, stale inventory,
      and placeholder source gates.
- [x] Strict template-schema and provenance tests.
- [x] Apicbase mapping/unit/fractional-stock tests.
- [x] Lead/review horizon, proposed safety-days policy, and unavoidable
      pre-arrival stockout tests.
- [x] Fresh unequal-day coverage tests.
- [x] Shelf-life/max-cover/MOQ/case/order-unit boundary tests.
- [x] Full local template → normalized inputs → recommendation acceptance run.

## Immediate next slice

1. Send the two templates, assumptions brief, maintainer review summary, and
   recommendation/exception outputs to the maintainer.
2. Start Milestone 2 UI planning/building over the existing schemas, while
   displaying proposal/unapproved statuses explicitly.
3. Receive corrected/approved templates and answers; resolve the four stock
   mappings, seven currently unmatched open-PO lines, item policy fields, and
   fresh timing/pack-cap decisions.
4. Rerun the same one-command workflow and pass the operational-approval gate
   before shadow/production use.
5. Plan Supabase only for editable master/rule/mapping data and change history;
   leave operational result persistence to the agreed Snowflake path.

## Dated progress

- 2026-08-22 to 2026-08-25: legacy reconstruction, canonical contracts,
  validation, BOM explosion, dated projection/netting, and Snowflake source
  investigation completed.
- 2026-08-26: Excel-owner answers reconciled; Transgourmet PDF importer
  implemented; new menu/pod sheets and two Apicbase stock examples analysed.
- 2026-08-27: route rebased to project-owned templates. Two prefilled workbook
  templates and the template-first local V1 plan were created. The supplied
  workbooks are now migration evidence, not recurring adapter contracts; the UI
  is explicitly the next milestone after a complete local recommendation run.
- 2026-08-27: all five local V1 work packages completed. Scenario run
  `improved-67fb3838775f` produced 23 dated recommendations across 11 items with
  zero blockers; seven result files replayed byte-identically and 44 tests
  passed. UI work is unblocked; maintainer approval remains the gate before
  operational/shadow use.
