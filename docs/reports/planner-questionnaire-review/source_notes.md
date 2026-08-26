# Planner questionnaire review — source notes

**Reviewed:** 2026-08-26
**Audience:** Phase 2 product and engineering stakeholders
**Decision:** which planner answers are strong enough to update the specification,
which remain provisional, and which focused follow-ups still gate business
acceptance.

## Source handling

The supplied Q1-Q13 response was reviewed as an owner-authored description of
the current manual process. It contained a supplier-portal credential. The
credential and the raw attachment path are intentionally not reproduced in this
repository or report artifact. The credential should be rotated because it was
shared in chat.

Planner statements describe operating practice, not validated API schemas,
supplier SLAs, or complete source-system history. Repository/Snowflake evidence
continues to control claims about implemented behavior and warehouse coverage.

## Sanitized answer reconciliation

| Question | Assessment | What the answer establishes | What remains open |
|---|---|---|---|
| Q1 — In-transit | Partial | Pending Transgourmet orders are checked in the supplier portal, downloaded as PDFs, analysed outside the workbook, and subtracted before the visible final quantities. The four positive-gap KW34 blanks were probably omissions. | Export/API capability, status meanings, stable line IDs, remaining quantity, expected receipt timestamps, partial receipts/cancellations, and a source record proving the four omissions. |
| Q2 — Lead time | Partial | Current Transgourmet planning uses about 3 days for standard goods and 5 days for fresh goods. Future Circus pods are expected to have about a one-month lead time and to replace much of the current assortment. | Calendar versus business days, start/end events, cut-offs, delivery calendars, item exceptions, exact pod policy, and go-live timing. |
| Q3 — Shelf life | Partial | Current short ordering cycles mean no explicit MHD cap is normally applied to TK, Kuehl, or RT. Fresh is planned around about 3 days. Future pods are expected to have about one year. | Sealed/opened semantics, item exceptions, whether the values are hard caps or planning defaults, and approved max-cover/storage-capacity rules. |
| Q4 — S/M/W/Fr | Partial | The columns are Saturday/Monday/Wednesday/Friday delivery-day allocations. Penne is deliberately split or reduced because of freezer space and the ability to replenish again soon. | Whether values mean intended, placed, confirmed, or delivered units; pack/order units; edit timing; and exact capacity limits. |
| Q5 — Demand/Silo Load | Confirmed for the manual baseline | The value is expected dishes sold per day across all three REWE sales locations combined because preparation and purchasing are centralized. It is based on roughly two weeks of consumption plus campaigns, approved by REWE, manually trend-adjusted, and entered into the planning workbook. | The authoritative Phase 1 owner/table, daily rather than flat-week profile, version/cut-off, source of the consumption history, and stable sales-location to central-planning-location mapping. |
| Q6 — Stock count | Partial | Prep-kitchen operators count stock manually and upload it to Apicbase. Expired, damaged, reserved, and otherwise unusable goods are excluded. | Count weekday/time, opened and partial-pack treatment, exact Apicbase fields/API/freshness, and the reason for the legacy 2.5-day bridge. |
| Q7 — Menu changes | Partial | The planner drives menu changes, generally knows what to order, can cancel Transgourmet orders, and cannot cancel pods. | Committed horizon, source/version of the forward menu, change publication, substitutions, pod last-order rule, and ownership when the current planner is unavailable. |
| Q8 — 20% buffer | Partial | The factor is an assumption intended to cover multiple operational uncertainties/loss scenarios. | Whether it applies uniformly, approved interim overrides, and how to separate deterministic yield from stochastic safety. |
| Q9 — Master data | Confirmed with source caveat | Creme Fraiche uses 5,000 g; current Schnittlauch is the 250 g product and the other sizes are distinct products; Oel maps to Sonnenblumenoel; Paprika-big and Mischsalat are fresh; supplier article numbers exist. Apicbase is the intended source, but its master data is currently stale, so Excel is used operationally. | Canonical ID precedence, article-number extract, pack/unit validation, ownership, maintenance SLA, and a safe migration from Excel to an accepted master. |
| Q10 — Fresh coverage | Confirmed for the manual baseline | Saturday delivery covers Monday; Monday covers Tuesday and Wednesday; Wednesday covers Thursday and Friday; Friday covers Saturday. | Receipt availability time, holiday exceptions, whether every fresh item shares the calendar, and the operational meaning of same-day receipts. |
| Q11 — Weekly process | Partial | The main order is prepared Thursday for the following week. Inventory is counted and sufficiency is rechecked Monday. | Exact run/cut-off times, urgent orders between runs, who reviews/finalizes/places orders, and how Monday changes are recorded without double-counting the pipeline. |
| Q12 — Other data | Inconclusive | The planner reports no other data currently available for the listed history/calibration topics. | This conflicts with the separate forecast sheet, Apicbase stock process, Transgourmet history, and catalogued Snowflake candidates; clarify whether “no” means unavailable, not trusted, or simply not used in the weekly process. |
| Q13 — Planner experience | Partial | Historical stockouts were attributed to unclear delivery models; the current process is considered mature enough to automate step by step. | Which forecast, menu, capacity, and exception decisions remain human judgement and what evidence/explanation is required before acting on an automated recommendation. |

Assessment totals are 3 confirmed for the stated manual baseline, 9 partial,
and 1 inconclusive. “Confirmed” does not mean production-source acceptance; it
means the answer is specific enough to update the legacy/business description.

## Validation notes

- The answer resolves the business meaning of `Demand/Silo Load`, but creates a
  grain requirement: three service locations roll up to one central planning
  location. The target must map this explicitly and must not duplicate an
  already-aggregated forecast across units.
- The current PO source is identified, but normalized operational data remain
  absent from Snowflake. Manual PDF analysis is evidence of the process, not an
  acceptable production adapter contract.
- The former statement that all goods have a four-week lead time was too broad.
  It belongs to future pods; current Transgourmet planning uses shorter values.
- The answer corrects the fresh coverage windows. They are service-day windows,
  not same-day/next-slot multipliers inferred from the workbook headings.
- `Q12 = no` is not accepted as a global data-absence claim because it conflicts
  with sources named elsewhere in the same response and with measured warehouse
  discovery.
- No application-code behavior is changed by this review. Exact cut-offs,
  calendars, source mappings, and approved policy versions are still needed
  before implementing or promoting the corresponding configurable rules.

## Report-shape notes

The reader-facing report uses the product-stakeholder shape: title, visible
Executive Summary, findings, recommended next steps, further questions, and
caveats. The primary evidence is the exact question-by-question table. The
portable report validator also requires a chart, so one compact horizontal bar
compares the three assessment counts (3 confirmed, 9 partial, 1 inconclusive).
The chart is not a quality score and does not replace the row-level audit.

### Chart map

| Section | Question | Family/type | Fields | Supported takeaway | Palette | Delivery |
|---|---|---|---|---|---|---|
| The answers narrow the blockers | How many original question groups are confirmed, partial, or inconclusive for the manual baseline? | Comparison / horizontal bar | `assessment`, `question_count`; retains `question_ids` and `share_of_13` | Most answers narrow rather than fully close their gate | Single blue root, direct value labels, no redundant legend | Native chart in the canonical HTML report artifact |

The chart has only three categories, which is appropriate for this discrete
status comparison but too coarse to carry the decision alone. The adjacent
13-row table supplies the necessary detail and is the authoritative lookup.
